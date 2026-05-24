"""Inventory service — the only writer for StockLevel and StockMovement.

Atomicity contract
==================
Every mutation:

1. Opens a Postgres ``SELECT ... FOR UPDATE`` on the StockLevel row.
2. Applies the delta.
3. Re-checks the result against the CHECK constraint (qty_on_hand >= 0).
4. Inserts a StockMovement audit row.
5. (Optionally) posts a matching journal entry through ``accounting.service``.

Steps 1-5 happen in the *caller's* transaction. The service does NOT commit
— callers (routes, sales service, purchase service) commit so that the
business mutation and the accounting effect land together or not at all.

Public functions
================
* ``adjust_stock`` — manual adjustment by a warehouse manager.
* ``decrement_for_sale`` — called by the sales service (F6). Decrements +
  posts ``DR COGS / CR Inventory``. Returns the movement so the caller can
  attach it to the SaleLine.
* ``increment_for_purchase`` — called by the purchase service. Increments +
  posts ``DR Inventory / CR (AP|Cash)``. Updates ``avg_cost`` (weighted).
* ``increment_for_return`` — customer return.
* ``open_or_create_level`` — lazy-init a (product, branch) StockLevel row.
* ``get_stock_level`` — read-only convenience.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date as date_t, date
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from app.extensions import db
from app.modules.accounting import service as acct
from app.modules.accounting.coa_seed import SystemAccount
from app.modules.accounting.service import LineInput
from app.modules.inventory import repository as repo
from app.modules.inventory.models import MovementType, StockLevel, StockMovement
from app.modules.products.models import Product


log = logging.getLogger(__name__)


# --- Result containers ------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MovementResult:
    movement: StockMovement
    new_qty: int
    journal_entry_id: Optional[uuid.UUID]


# --- Locks ------------------------------------------------------------------

def _lock_level(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    create_if_missing: bool = True,
) -> StockLevel:
    """Lock the (product, branch) StockLevel row, creating an empty one if
    needed. Returns the locked row inside the current transaction.

    Creating a missing row uses INSERT ... ON CONFLICT semantics — two
    concurrent sales of a never-stocked product would otherwise race here.
    For MVP we settle for catching IntegrityError on insert and re-selecting.
    """
    session = db.session
    level = repo.get_level(
        session,
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        for_update=True,
    )
    if level is not None:
        return level
    if not create_if_missing:
        raise NotFound("No stock record for this product at this branch.")

    # Make sure the product exists in this tenant before lazy-creating a row.
    product = session.get(Product, product_id)
    if product is None or product.tenant_id != tenant_id or product.deleted_at is not None:
        raise NotFound("Product not found.")

    # Lazy-create. Race-safe via the (product_id, branch_id) UNIQUE.
    level = StockLevel(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        qty_on_hand=0,
        avg_cost=Decimal("0"),
    )
    try:
        repo.add_level(session, level)
    except IntegrityError:
        session.rollback()
        # Loser of the race re-fetches the winner's row, then re-locks.
        level = repo.get_level(
            session,
            tenant_id=tenant_id,
            product_id=product_id,
            branch_id=branch_id,
            for_update=True,
        )
        if level is None:
            raise Conflict("Concurrent stock-level init race; please retry.")
    return level


# --- Inbound (increase) primitives ------------------------------------------

def _apply_inbound(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    unit_cost: Decimal,
    movement_type: MovementType,
    movement_date: date_t,
    reference: Optional[str],
    notes: Optional[str],
    user_id: Optional[uuid.UUID],
) -> tuple[StockMovement, StockLevel]:
    if qty <= 0:
        raise BadRequest("qty must be positive.")
    if unit_cost < 0:
        raise BadRequest("unit_cost must be non-negative.")
    if not movement_type.is_inbound:
        raise BadRequest(f"{movement_type.value} is not an inbound movement.")

    level = _lock_level(tenant_id=tenant_id, product_id=product_id, branch_id=branch_id)

    # Weighted-average cost update — only on inbound.
    old_qty = level.qty_on_hand
    old_avg = level.avg_cost or Decimal("0")
    new_qty = old_qty + qty
    if new_qty <= 0:
        # Shouldn't happen on inbound, but guard.
        raise BadRequest("Resulting qty must be positive after inbound.")
    new_avg = ((old_qty * old_avg) + (qty * unit_cost)) / new_qty
    level.qty_on_hand = new_qty
    level.avg_cost = new_avg.quantize(Decimal("0.0001"))

    movement = StockMovement(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        movement_type=movement_type,
        qty=qty,
        unit_cost=unit_cost,
        movement_date=movement_date,
        reference=reference,
        notes=notes,
        created_by_id=user_id,
    )
    repo.add_movement(db.session, movement)
    return movement, level


# --- Outbound (decrease) primitives -----------------------------------------

def _apply_outbound(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    movement_type: MovementType,
    movement_date: date_t,
    reference: Optional[str],
    notes: Optional[str],
    user_id: Optional[uuid.UUID],
    explicit_unit_cost: Optional[Decimal] = None,
) -> tuple[StockMovement, StockLevel]:
    if qty <= 0:
        raise BadRequest("qty must be positive.")
    if movement_type.is_inbound:
        raise BadRequest(f"{movement_type.value} is not an outbound movement.")

    level = _lock_level(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        create_if_missing=False,
    )
    new_qty = level.qty_on_hand - qty
    if new_qty < 0:
        raise BadRequest(
            f"Insufficient stock: have {level.qty_on_hand}, need {qty}."
        )
    level.qty_on_hand = new_qty

    # Outbound unit_cost = caller-supplied (sale uses Product.cost or avg_cost
    # depending on policy) or the current avg_cost.
    unit_cost = explicit_unit_cost if explicit_unit_cost is not None else (level.avg_cost or Decimal("0"))

    movement = StockMovement(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        movement_type=movement_type,
        qty=qty,
        unit_cost=unit_cost,
        movement_date=movement_date,
        reference=reference,
        notes=notes,
        created_by_id=user_id,
    )
    repo.add_movement(db.session, movement)
    return movement, level


# --- Public service functions -----------------------------------------------

def adjust_stock(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    direction: str,                 # "in" or "out"
    reason: str,
    unit_cost: Optional[Decimal] = None,
    movement_date: Optional[date_t] = None,
    user_id: Optional[uuid.UUID] = None,
) -> MovementResult:
    """Manual stock adjustment with matching journal entry.

    Inbound  → DR Inventory / CR Owner's Capital  (opening / found stock)
    Outbound → DR Operating Expenses / CR Inventory  (damage / shrinkage)

    These counterparties are chosen for a small-shop MVP; a richer setup
    would expose them as configurable per-reason mappings.
    """
    move_date = movement_date or date.today()
    if direction == "in":
        # Default unit_cost = product's standard cost when not supplied.
        eff_cost = unit_cost if unit_cost is not None else _product_cost(
            tenant_id=tenant_id, product_id=product_id
        )
        movement, level = _apply_inbound(
            tenant_id=tenant_id,
            product_id=product_id,
            branch_id=branch_id,
            qty=qty,
            unit_cost=eff_cost,
            movement_type=MovementType.adjustment_in,
            movement_date=move_date,
            reference=f"adjustment:{reason[:80]}",
            notes=reason,
            user_id=user_id,
        )
        total = (Decimal(qty) * eff_cost).quantize(Decimal("0.01"))
        entry = acct.post_journal_entry(
            tenant_id=tenant_id,
            entry_date=move_date,
            branch_id=branch_id,
            source="inventory",
            source_ref=f"movement:{movement.id}",
            reference="Stock adjustment (in)",
            description=f"Inbound adjustment: {reason}",
            posted_by_id=user_id,
            lines=[
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.INVENTORY),
                    debit=total,
                    description=f"Inventory + {qty}",
                ),
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.OWNER_CAPITAL),
                    credit=total,
                    description="Counterparty: owner capital",
                ),
            ],
        )
    elif direction == "out":
        movement, level = _apply_outbound(
            tenant_id=tenant_id,
            product_id=product_id,
            branch_id=branch_id,
            qty=qty,
            movement_type=MovementType.adjustment_out,
            movement_date=move_date,
            reference=f"adjustment:{reason[:80]}",
            notes=reason,
            user_id=user_id,
            explicit_unit_cost=unit_cost,
        )
        total = (Decimal(qty) * movement.unit_cost).quantize(Decimal("0.01"))
        entry = acct.post_journal_entry(
            tenant_id=tenant_id,
            entry_date=move_date,
            branch_id=branch_id,
            source="inventory",
            source_ref=f"movement:{movement.id}",
            reference="Stock adjustment (out)",
            description=f"Outbound adjustment: {reason}",
            posted_by_id=user_id,
            lines=[
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.OPERATING_EXPENSES),
                    debit=total,
                    description=f"Inventory loss ({reason})",
                ),
                LineInput(
                    account_id=acct.get_system_account_id(tenant_id, SystemAccount.INVENTORY),
                    credit=total,
                    description=f"Inventory - {qty}",
                ),
            ],
        )
    else:
        raise BadRequest("direction must be 'in' or 'out'.")

    movement.journal_entry_id = entry.id
    db.session.flush()
    log.info(
        "stock_adjusted",
        extra={
            "tenant_id": str(tenant_id),
            "product_id": str(product_id),
            "branch_id": str(branch_id),
            "direction": direction,
            "qty": qty,
            "new_qty": level.qty_on_hand,
            "entry_id": str(entry.id),
        },
    )
    return MovementResult(
        movement=movement, new_qty=level.qty_on_hand, journal_entry_id=entry.id
    )


def increment_for_purchase(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    unit_cost: Decimal,
    movement_date: date_t,
    paid_in_cash: bool,
    reference: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
) -> MovementResult:
    """Receive stock from a supplier (or a cash purchase).

    Journal:  DR Inventory  / CR (Cash if paid_in_cash else AP).

    Does NOT commit — the calling purchase-receive service typically posts
    multiple lines in one transaction.
    """
    movement, level = _apply_inbound(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        qty=qty,
        unit_cost=unit_cost,
        movement_type=MovementType.purchase,
        movement_date=movement_date,
        reference=reference,
        notes=None,
        user_id=user_id,
    )
    total = (Decimal(qty) * unit_cost).quantize(Decimal("0.01"))
    counter_key = SystemAccount.CASH if paid_in_cash else SystemAccount.AP
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=movement_date,
        branch_id=branch_id,
        source="purchase",
        source_ref=f"movement:{movement.id}",
        reference=reference,
        description="Purchase receipt" + (" (cash)" if paid_in_cash else " (credit)"),
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.INVENTORY),
                debit=total,
                description=f"Inventory + {qty}",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, counter_key),
                credit=total,
                description="Cash paid" if paid_in_cash else "Owed to supplier",
            ),
        ],
    )
    movement.journal_entry_id = entry.id
    db.session.flush()
    return MovementResult(
        movement=movement, new_qty=level.qty_on_hand, journal_entry_id=entry.id
    )


def decrement_for_sale(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    sale_id: uuid.UUID,
    movement_date: date_t,
    user_id: Optional[uuid.UUID] = None,
) -> MovementResult:
    """Decrement stock for a POS sale and post DR COGS / CR Inventory.

    Returns the MovementResult so the sale service can attach the journal
    entry id and cost snapshot to the SaleLine. The sale service is
    responsible for posting the *revenue* side (DR Cash/AR, CR Sales Revenue).
    """
    move_date = movement_date or date.today()
    # COGS unit cost = current Product.cost snapshot (MVP). We could switch
    # to avg_cost from the StockLevel in one line below — kept as standard
    # cost so legacy data migrates cleanly.
    cogs_unit = _product_cost(tenant_id=tenant_id, product_id=product_id)
    movement, level = _apply_outbound(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        qty=qty,
        movement_type=MovementType.sale,
        movement_date=move_date,
        reference=f"sale:{sale_id}",
        notes=None,
        user_id=user_id,
        explicit_unit_cost=cogs_unit,
    )
    total = (Decimal(qty) * cogs_unit).quantize(Decimal("0.01"))
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=move_date,
        branch_id=branch_id,
        source="sale",
        source_ref=f"sale:{sale_id}",
        reference=str(sale_id),
        description=f"COGS for sale {sale_id}",
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.COGS),
                debit=total,
                description=f"COGS {qty}@{cogs_unit}",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.INVENTORY),
                credit=total,
                description=f"Inventory - {qty}",
            ),
        ],
    )
    movement.journal_entry_id = entry.id
    db.session.flush()
    return MovementResult(
        movement=movement, new_qty=level.qty_on_hand, journal_entry_id=entry.id
    )


def increment_for_return(
    *,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    branch_id: uuid.UUID,
    qty: int,
    unit_cost: Decimal,
    sale_reference: Optional[str],
    movement_date: date_t,
    user_id: Optional[uuid.UUID] = None,
) -> MovementResult:
    """Customer return — opposite of decrement_for_sale.

    Journal: DR Inventory / CR COGS (reverse the original COGS impact).
    The sale-refund flow handles the revenue side.
    """
    movement, level = _apply_inbound(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        qty=qty,
        unit_cost=unit_cost,
        movement_type=MovementType.return_in,
        movement_date=movement_date,
        reference=sale_reference,
        notes=None,
        user_id=user_id,
    )
    total = (Decimal(qty) * unit_cost).quantize(Decimal("0.01"))
    entry = acct.post_journal_entry(
        tenant_id=tenant_id,
        entry_date=movement_date,
        branch_id=branch_id,
        source="return",
        source_ref=f"movement:{movement.id}",
        reference=sale_reference,
        description=f"Customer return {qty} units",
        posted_by_id=user_id,
        lines=[
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.INVENTORY),
                debit=total,
                description=f"Inventory + {qty} (return)",
            ),
            LineInput(
                account_id=acct.get_system_account_id(tenant_id, SystemAccount.COGS),
                credit=total,
                description="COGS reversal",
            ),
        ],
    )
    movement.journal_entry_id = entry.id
    db.session.flush()
    return MovementResult(
        movement=movement, new_qty=level.qty_on_hand, journal_entry_id=entry.id
    )


# --- Reads ------------------------------------------------------------------

def get_stock_level(
    *, tenant_id: uuid.UUID, product_id: uuid.UUID, branch_id: uuid.UUID
) -> Optional[StockLevel]:
    return repo.get_level(
        db.session,
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        for_update=False,
    )


def open_or_create_level(
    *, tenant_id: uuid.UUID, product_id: uuid.UUID, branch_id: uuid.UUID
) -> StockLevel:
    return _lock_level(tenant_id=tenant_id, product_id=product_id, branch_id=branch_id)


def list_levels_for_branch(
    *, tenant_id: uuid.UUID, branch_id: uuid.UUID, page: int, per_page: int,
    only_low_stock: bool = False,
) -> dict:
    from app.core.pagination import paginate_offset
    stmt = repo.list_levels_query(
        tenant_id=tenant_id,
        branch_id=branch_id,
        only_low_stock=only_low_stock,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


def list_movements_for_product(
    *, tenant_id: uuid.UUID, product_id: uuid.UUID,
    page: int, per_page: int,
    branch_id: Optional[uuid.UUID] = None,
    date_from: Optional[date_t] = None,
    date_to: Optional[date_t] = None,
) -> dict:
    from app.core.pagination import paginate_offset
    stmt = repo.list_movements_query(
        tenant_id=tenant_id,
        product_id=product_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )
    return paginate_offset(db.session, stmt, page=page, per_page=per_page)


# --- Helpers ----------------------------------------------------------------

def _product_cost(*, tenant_id: uuid.UUID, product_id: uuid.UUID) -> Decimal:
    """Resolve the product's standard cost for COGS / default adjust cost."""
    p = db.session.get(Product, product_id)
    if p is None or p.tenant_id != tenant_id or p.deleted_at is not None:
        raise NotFound("Product not found.")
    return Decimal(p.cost or 0)
