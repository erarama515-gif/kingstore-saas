"""Sales / POS service.

The POS flow in one transaction:

  for each line:
      if not is_service: inventory.decrement_for_sale(...)   # → COGS journal
  post revenue journal entry:
      DR Cash (if paid in full) or AR (if credit) or BOTH (if partial)
      CR Sales Revenue (inventory lines)
      CR Service Revenue (service lines)
  update customer cached totals
  commit (in route)

If anything raises, the whole thing rolls back — no half-decremented stock,
no orphan accounting entry.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date as date_t, datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, NotFound

from app.core.pagination import paginate_offset
from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.service import LineInput
from app.modules.customers.models import Customer
from app.modules.inventory import service as inventory_svc
from app.modules.products.models import Product
from app.modules.sales import repository as repo
from app.modules.sales.models import Sale, SaleLine, SalePayment, SaleStatus
from app.modules.sales.schemas import SaleCreate, SaleLineInput


log = logging.getLogger(__name__)


# --- Create ----------------------------------------------------------------

def create_sale(
    *,
    tenant_id: uuid.UUID,
    payload: SaleCreate,
    cashier_id: Optional[uuid.UUID] = None,
) -> Sale:
    """Ring up a sale. Handles cash, credit, partial, and service lines.

    The caller commits (route handler). If the route's commit fails the whole
    chain — inventory decrements, journal entries, customer cache updates —
    rolls back together.
    """
    session = db.session
    sale_date = payload.sale_date or date_t.today()

    # Resolve and validate customer when given (and required for credit sales).
    customer = None
    if payload.customer_id is not None:
        customer = session.get(Customer, payload.customer_id)
        if customer is None or customer.tenant_id != tenant_id or customer.deleted_at is not None:
            raise NotFound("Customer not found.")

    # Pre-flight: line totals, product validity, prices.
    products_by_id = _resolve_products(tenant_id, payload.lines)
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    line_records: list[dict] = []  # filled below; persisted after Sale insert
    for li in payload.lines:
        unit_price = li.unit_price
        line_total = ((Decimal(li.qty) * unit_price) - li.discount).quantize(Decimal("0.01"))
        if line_total < 0:
            raise BadRequest("Line discount cannot exceed qty × unit_price.")
        # Cost snapshot: 0 for service lines; Product.cost otherwise.
        cost_snap = Decimal("0")
        if not li.is_service and li.product_id:
            p = products_by_id[li.product_id]
            cost_snap = Decimal(p.cost or 0)
        subtotal += Decimal(li.qty) * unit_price
        discount_total += li.discount
        line_records.append({
            "line_input": li,
            "line_total": line_total,
            "cost_snapshot": cost_snap,
        })

    total = (subtotal - discount_total).quantize(Decimal("0.01"))
    paid_amount = min(payload.paid_amount, total)
    is_credit = paid_amount < total
    if is_credit and customer is None:
        raise BadRequest("Credit sale (paid_amount < total) requires customer_id.")

    sale = _insert_sale_with_unique_number(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        sale_date=sale_date,
        customer=customer,
        customer_name=payload.customer_name,
        subtotal=subtotal.quantize(Decimal("0.01")),
        discount_total=discount_total.quantize(Decimal("0.01")),
        total=total,
        paid_amount=paid_amount,
        cashier_id=cashier_id,
        notes=payload.notes,
    )

    # Per-line: persist SaleLine + decrement inventory (which posts COGS).
    has_inventory = False
    has_service = False
    for rec in line_records:
        li: SaleLineInput = rec["line_input"]
        line = SaleLine(
            tenant_id=tenant_id,
            sale_id=sale.id,
            product_id=li.product_id,
            description=(li.description or _fallback_description(li, products_by_id)),
            qty=li.qty,
            unit_price=li.unit_price,
            discount=li.discount,
            line_total=rec["line_total"],
            cost_snapshot=rec["cost_snapshot"],
            is_service=li.is_service,
        )
        session.add(line)
        session.flush()

        if not li.is_service and li.product_id:
            res = inventory_svc.decrement_for_sale(
                tenant_id=tenant_id,
                product_id=li.product_id,
                branch_id=payload.branch_id,
                qty=li.qty,
                sale_id=sale.id,
                movement_date=sale_date,
                user_id=cashier_id,
            )
            line.stock_movement_id = res.movement.id
            has_inventory = True
        else:
            has_service = True

    # Post revenue journal: DR Cash + DR AR / CR Sales Revenue + CR Service Revenue
    revenue_entry = _post_revenue_journal(
        tenant_id=tenant_id,
        sale=sale,
        line_records=line_records,
        sale_date=sale_date,
        cashier_id=cashier_id,
        has_inventory=has_inventory,
        has_service=has_service,
    )
    sale.revenue_journal_entry_id = revenue_entry.id

    # Update customer cache (best-effort: ledger is authoritative).
    if customer is not None:
        if paid_amount > 0:
            customer.total_spent_cached = (customer.total_spent_cached + paid_amount).quantize(Decimal("0.01"))
        if is_credit:
            customer.debt_cached = (customer.debt_cached + (total - paid_amount)).quantize(Decimal("0.01"))
        customer.visits_count = (customer.visits_count or 0) + 1
        customer.last_txn_at = datetime.now(timezone.utc)

    session.flush()
    log.info(
        "sale_created",
        extra={
            "tenant_id": str(tenant_id),
            "sale_id": str(sale.id),
            "sale_number": sale.sale_number,
            "total": str(total),
            "paid": str(paid_amount),
            "credit": is_credit,
            "lines": len(line_records),
        },
    )
    return sale


def _insert_sale_with_unique_number(
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    sale_date: date_t,
    customer: Optional[Customer],
    customer_name: Optional[str],
    subtotal: Decimal,
    discount_total: Decimal,
    total: Decimal,
    paid_amount: Decimal,
    cashier_id: Optional[uuid.UUID],
    notes: Optional[str],
) -> Sale:
    session = db.session
    # Up to 3 retries on the (tiny) chance two cashiers race the COUNT.
    for attempt in range(3):
        sale_number = repo.next_sale_number(session, tenant_id=tenant_id)
        sale = Sale(
            tenant_id=tenant_id,
            sale_number=sale_number,
            branch_id=branch_id,
            customer_id=customer.id if customer else None,
            customer_name=(
                customer_name or (customer.name if customer else None)
            ),
            sale_date=sale_date,
            subtotal=subtotal,
            discount_total=discount_total,
            total=total,
            paid_amount=paid_amount,
            is_paid=(paid_amount >= total),
            status=SaleStatus.posted,
            cashier_id=cashier_id,
            notes=notes,
        )
        session.add(sale)
        try:
            session.flush()
            return sale
        except IntegrityError:
            session.rollback()
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def _resolve_products(
    tenant_id: uuid.UUID, lines: Iterable[SaleLineInput]
) -> dict[uuid.UUID, Product]:
    session = db.session
    ids = [l.product_id for l in lines if l.product_id is not None and not l.is_service]
    if not ids:
        return {}
    out: dict[uuid.UUID, Product] = {}
    for pid in ids:
        p = session.get(Product, pid)
        if p is None or p.tenant_id != tenant_id or p.deleted_at is not None:
            raise NotFound(f"Product {pid} not found.")
        if not p.is_active:
            raise BadRequest(f"Product '{p.name}' is inactive.")
        out[pid] = p
    return out


def _fallback_description(
    li: SaleLineInput, products_by_id: dict[uuid.UUID, Product]
) -> str:
    if li.product_id and li.product_id in products_by_id:
        return products_by_id[li.product_id].name
    return "(service)"


def _post_revenue_journal(
    *,
    tenant_id: uuid.UUID,
    sale: Sale,
    line_records: list[dict],
    sale_date: date_t,
    cashier_id: Optional[uuid.UUID],
    has_inventory: bool,
    has_service: bool,
) -> "JournalEntry":  # noqa: F821 - type hint
    """Compose the revenue side of the sale.

    Inventory-line totals → Sales Revenue.
    Service-line totals → Service Revenue.
    Debit split between Cash (paid_amount) and AR (remainder).
    """
    inv_revenue = Decimal("0")
    svc_revenue = Decimal("0")
    for rec in line_records:
        li: SaleLineInput = rec["line_input"]
        if li.is_service:
            svc_revenue += rec["line_total"]
        else:
            inv_revenue += rec["line_total"]
    inv_revenue = inv_revenue.quantize(Decimal("0.01"))
    svc_revenue = svc_revenue.quantize(Decimal("0.01"))

    paid = sale.paid_amount
    ar_amount = (sale.total - paid).quantize(Decimal("0.01"))

    lines: list[LineInput] = []

    if paid > 0:
        lines.append(LineInput(
            account_id=acct.get_system_account_id(tenant_id, SystemAccount.CASH),
            debit=paid,
            description=f"Cash received for sale {sale.sale_number}",
        ))
    if ar_amount > 0:
        lines.append(LineInput(
            account_id=acct.get_system_account_id(tenant_id, SystemAccount.AR),
            debit=ar_amount,
            customer_id=sale.customer_id,
            description=f"AR for sale {sale.sale_number}",
        ))
    if inv_revenue > 0:
        lines.append(LineInput(
            account_id=acct.get_system_account_id(tenant_id, SystemAccount.SALES_REVENUE),
            credit=inv_revenue,
            description=f"Sales revenue {sale.sale_number}",
        ))
    if svc_revenue > 0:
        lines.append(LineInput(
            account_id=acct.get_system_account_id(tenant_id, SystemAccount.SERVICE_REVENUE),
            credit=svc_revenue,
            description=f"Service revenue {sale.sale_number}",
        ))

    return acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=sale_date,
        branch_id=sale.branch_id,
        source="sale",
        source_ref=f"sale:{sale.id}",
        reference=sale.sale_number,
        description=f"Revenue for {sale.sale_number}",
        posted_by_id=cashier_id,
        lines=lines,
    )


# --- Reads -----------------------------------------------------------------

def get_sale(*, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> Sale:
    sale = repo.get_sale(db.session, sale_id)
    if sale is None or sale.tenant_id != tenant_id or sale.deleted_at is not None:
        raise NotFound("Sale not found.")
    return sale


def list_sales(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
    branch_id: Optional[uuid.UUID] = None,
    customer_id: Optional[uuid.UUID] = None,
    date_from: Optional[date_t] = None,
    date_to: Optional[date_t] = None,
    only_unpaid: bool = False,
) -> dict:
    stmt = repo.list_sales_query(
        tenant_id=tenant_id,
        branch_id=branch_id,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        only_unpaid=only_unpaid,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


def list_open_debts(
    *,
    tenant_id: uuid.UUID,
    page: int,
    per_page: int,
) -> dict:
    return list_sales(
        tenant_id=tenant_id, page=page, per_page=per_page, only_unpaid=True
    )


# --- Payment / collect debt ------------------------------------------------

def apply_payment(
    *,
    tenant_id: uuid.UUID,
    sale_id: uuid.UUID,
    amount: Decimal,
    payment_date: Optional[date_t] = None,
    method: str = "cash",
    notes: Optional[str] = None,
    received_by_id: Optional[uuid.UUID] = None,
) -> SalePayment:
    """Apply a payment to an outstanding sale.

    Journal: DR Cash (or BANK) / CR AR (tagged with customer_id).
    """
    session = db.session
    sale = get_sale(tenant_id=tenant_id, sale_id=sale_id)
    if sale.is_paid:
        raise BadRequest("Sale is already fully paid.")
    if amount <= 0:
        raise BadRequest("Payment amount must be positive.")
    outstanding = (sale.total - sale.paid_amount).quantize(Decimal("0.01"))
    if amount > outstanding:
        raise BadRequest(
            f"Payment {amount} exceeds outstanding balance {outstanding}."
        )

    pdate = payment_date or date_t.today()
    cash_key = SystemAccount.CASH if method == "cash" else SystemAccount.BANK

    payment = SalePayment(
        tenant_id=tenant_id,
        sale_id=sale.id,
        amount=amount,
        payment_date=pdate,
        method=method,
        notes=notes,
        received_by_id=received_by_id,
    )
    session.add(payment)
    session.flush()

    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=pdate,
        branch_id=sale.branch_id,
        source="payment",
        source_ref=f"payment:{payment.id}",
        reference=sale.sale_number,
        description=f"Debt payment for {sale.sale_number}",
        posted_by_id=received_by_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, cash_key),
                debit=amount,
                description=f"Payment received ({method})",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.AR),
                credit=amount,
                customer_id=sale.customer_id,
                description=f"AR collected for {sale.sale_number}",
            ),
        ],
    )
    payment.journal_entry_id = entry.id

    # Update sale + customer cache
    sale.paid_amount = (sale.paid_amount + amount).quantize(Decimal("0.01"))
    sale.is_paid = sale.paid_amount >= sale.total
    if sale.customer_id:
        cust = session.get(Customer, sale.customer_id)
        if cust:
            cust.debt_cached = max(
                Decimal("0"),
                (cust.debt_cached - amount).quantize(Decimal("0.01")),
            )
            cust.total_spent_cached = (cust.total_spent_cached + amount).quantize(Decimal("0.01"))
            cust.last_txn_at = datetime.now(timezone.utc)
    session.flush()
    log.info(
        "payment_applied",
        extra={
            "tenant_id": str(tenant_id),
            "sale_id": str(sale.id),
            "amount": str(amount),
            "fully_paid": sale.is_paid,
        },
    )
    return payment


# --- Refund (whole-sale reversal) ------------------------------------------

def refund_sale(
    *,
    tenant_id: uuid.UUID,
    sale_id: uuid.UUID,
    reason: str,
    user_id: Optional[uuid.UUID] = None,
) -> Sale:
    """Full refund: reverses revenue journal and any COGS movements,
    then marks the Sale as ``refunded``.

    Inventory: each inventoried line produces a counter-movement via
    ``inventory.increment_for_return`` (which posts DR Inventory / CR COGS).
    Revenue: ``accounting.reverse_journal_entry`` on the original revenue
    entry — reverses DR/CR cleanly. Payments are NOT auto-refunded as cash
    here (that's a separate "refund payment" flow); we leave AR/cash treatment
    to the user to reconcile if needed.
    """
    session = db.session
    sale = get_sale(tenant_id=tenant_id, sale_id=sale_id)
    if sale.status == SaleStatus.refunded:
        raise BadRequest("Sale already refunded.")

    # Reverse revenue side
    if sale.revenue_journal_entry_id:
        acct.reverse_journal_entry(
            tenant_id=tenant_id,
            entry_id=sale.revenue_journal_entry_id,
            reason=f"Refund of {sale.sale_number}: {reason}",
            posted_by_id=user_id,
        )

    # Reverse inventory side line-by-line
    for line in sale.lines:
        if line.is_service or line.product_id is None:
            continue
        inventory_svc.increment_for_return(
            tenant_id=tenant_id,
            product_id=line.product_id,
            branch_id=sale.branch_id,
            qty=line.qty,
            unit_cost=line.cost_snapshot,
            sale_reference=f"refund:{sale.sale_number}",
            movement_date=date_t.today(),
            user_id=user_id,
        )

    sale.status = SaleStatus.refunded
    sale.notes = (sale.notes or "") + f"\nREFUND: {reason}"

    # Restore customer cache approximately (best-effort)
    if sale.customer_id:
        cust = session.get(Customer, sale.customer_id)
        if cust:
            cust.total_spent_cached = max(
                Decimal("0"),
                (cust.total_spent_cached - sale.paid_amount).quantize(Decimal("0.01")),
            )
            ar = (sale.total - sale.paid_amount).quantize(Decimal("0.01"))
            if ar > 0:
                cust.debt_cached = max(Decimal("0"), (cust.debt_cached - ar).quantize(Decimal("0.01")))

    session.flush()
    log.info(
        "sale_refunded",
        extra={"tenant_id": str(tenant_id), "sale_id": str(sale.id), "reason": reason},
    )
    return sale
