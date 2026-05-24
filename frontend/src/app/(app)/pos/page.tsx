"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, ShoppingCart, X, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney } from "@/lib/utils";

type Product = {
  id: string;
  name: string;
  code?: string | null;
  barcode?: string | null;
  price: string;
  cost: string;
  track_by_imei?: boolean;
  track_by_serial?: boolean;
  warranty_period_days?: number;
};

type Customer = { id: string; name: string; phone?: string | null; debt_cached: string };

type Device = {
  id: string;
  product_id: string;
  imei: string | null;
  serial_number: string | null;
  status: string;
};

type Line = {
  product_id?: string;
  description: string;
  qty: number;
  unit_price: string;
  discount: string;
  is_service: boolean;
  // IMEI tracking: required when product is tracked. UI blocks submit until set.
  device_instance_id?: string;
  device_imei?: string;
  product_tracked?: boolean;
};

export default function PosPage() {
  const [branchId, setBranchId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [paidAmount, setPaidAmount] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  // Pick up the active branch from the logged-in user.
  useEffect(() => {
    api
      .get("/auth/me")
      .then((r) => setBranchId(r.data.data?.user?.default_branch_id || null))
      .catch(() => {});
  }, []);

  const productsQuery = useQuery<{ data: Product[] }>({
    queryKey: ["products-search", search],
    queryFn: async () =>
      (await api.get("/products/", { params: { q: search || undefined, per_page: 12 } }))
        .data,
    enabled: search.length === 0 || search.length >= 1,
  });

  // Stock levels for the current branch — keyed by product_id for fast lookup
  const stockQuery = useQuery<{ data: { product_id: string; qty_on_hand: number }[] }>({
    queryKey: ["stock-levels", branchId],
    queryFn: async () =>
      (
        await api.get("/inventory/stock-levels", {
          params: { branch_id: branchId, per_page: 500 },
        })
      ).data,
    enabled: !!branchId,
    refetchInterval: 30_000,
  });
  const stockByProduct = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of stockQuery.data?.data || []) m.set(s.product_id, s.qty_on_hand);
    return m;
  }, [stockQuery.data]);

  const subtotal = useMemo(
    () =>
      lines.reduce(
        (s, l) => s + Number(l.unit_price) * l.qty - Number(l.discount || 0),
        0,
      ),
    [lines],
  );

  // Which line (if any) is asking for an IMEI right now
  const [imeiPickerFor, setImeiPickerFor] = useState<{
    lineIdx: number;
    productId: string;
    productName: string;
  } | null>(null);

  function addProduct(p: Product) {
    const tracked = !!(p.track_by_imei || p.track_by_serial);
    setLines((prev) => {
      // Tracked products are 1-per-line (one IMEI per unit). Adding the same
      // tracked product again creates a new line; the IMEI picker opens for
      // the new one. Untracked products stack qty as before.
      if (!tracked) {
        const idx = prev.findIndex((l) => l.product_id === p.id && !l.product_tracked);
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = { ...copy[idx], qty: copy[idx].qty + 1 };
          return copy;
        }
      }
      const next: Line = {
        product_id: p.id,
        description: p.name,
        qty: 1,
        unit_price: p.price,
        discount: "0",
        is_service: false,
        product_tracked: tracked,
      };
      const newIdx = prev.length;
      // If tracked, open the IMEI picker on the next tick so the new line
      // exists in state when the modal opens.
      if (tracked) {
        setTimeout(() => {
          setImeiPickerFor({ lineIdx: newIdx, productId: p.id, productName: p.name });
        }, 0);
      }
      return [...prev, next];
    });
    setSearch("");
    searchRef.current?.focus();
  }

  function addServiceLine() {
    setLines((prev) => [
      ...prev,
      {
        description: "خدمة (عدّل الوصف)",
        qty: 1,
        unit_price: "0",
        discount: "0",
        is_service: true,
      },
    ]);
  }

  function update(idx: number, patch: Partial<Line>) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  function remove(idx: number) {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  // POS lookup-on-enter for scanned barcode
  async function onSearchEnter() {
    if (!search.trim()) return;
    try {
      const r = await api.get("/products/lookup", { params: { q: search.trim() } });
      addProduct(r.data.data);
    } catch {
      toast.message("لا يوجد منتج بهذا الباركود/الكود — استعرض من القائمة");
    }
  }

  async function submitSale(asCash: boolean) {
    if (!branchId) return toast.error("لا يوجد فرع نشط");
    if (lines.length === 0) return toast.error("أضف منتج واحد على الأقل");

    // Tracked-line validation: every tracked line needs an IMEI; tracked
    // sales require a customer (warranty owner).
    const missingImei = lines.find((l) => l.product_tracked && !l.device_instance_id);
    if (missingImei) {
      return toast.error(
        `اختر IMEI للمنتج "${missingImei.description}" قبل إتمام البيع.`,
      );
    }
    const hasTracked = lines.some((l) => l.product_tracked);
    if (hasTracked && !customer) {
      return toast.error("اختيار العميل مطلوب لبيع الأجهزة المسجلة (الضمان).");
    }

    setSubmitting(true);
    try {
      const payload = {
        branch_id: branchId,
        customer_id: customer?.id || undefined,
        customer_name: customer?.name,
        lines: lines.map((l) => ({
          product_id: l.product_id || undefined,
          description: l.description,
          qty: l.qty,
          unit_price: String(l.unit_price),
          discount: String(l.discount || "0"),
          is_service: l.is_service,
          device_instance_id: l.device_instance_id || undefined,
        })),
        paid_amount: asCash ? String(subtotal.toFixed(2)) : (paidAmount || "0"),
      };
      const r = await api.post("/sales/", payload);
      const sale = r.data.data;
      toast.success(`تم تسجيل الفاتورة ${sale.sale_number}`);
      setLines([]);
      setCustomer(null);
      setPaidAmount("");
      setSearch("");
    } catch (err: any) {
      toast.error(err?.response?.data?.error?.message || "فشل حفظ الفاتورة");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-12 gap-4 min-h-[calc(100vh-3rem)]">
      {/* Product picker */}
      <div className="col-span-12 lg:col-span-7 space-y-4">
        <Card>
          <CardContent className="p-4">
            <div className="relative">
              <Search className="h-4 w-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={searchRef}
                placeholder="امسح الباركود أو اكتب اسم/كود المنتج..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onSearchEnter()}
                className="pr-10 h-12 text-base"
                autoFocus
              />
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {(productsQuery.data?.data || []).map((p) => {
            const qty = stockByProduct.get(p.id);
            const stockTone =
              qty === undefined ? "muted" :
              qty <= 0 ? "danger" :
              qty <= 3 ? "warn" : "success";
            const stockLabel =
              qty === undefined ? "—" :
              qty <= 0 ? "نفد" :
              `${qty} متاح`;
            const outOfStock = qty !== undefined && qty <= 0;
            return (
              <button
                key={p.id}
                onClick={() => addProduct(p)}
                disabled={outOfStock}
                className={`text-right p-3 rounded-lg border bg-card hover:border-primary hover:shadow transition-all relative ${
                  outOfStock ? "opacity-60 cursor-not-allowed" : ""
                }`}
              >
                <span className={`pill pill-${stockTone} absolute top-2 left-2`}>
                  {stockLabel}
                </span>
                <div className="font-semibold line-clamp-2 min-h-[2.5rem] pe-12">
                  {p.name}
                </div>
                <div className="text-xs text-muted-foreground mt-1 tabular" dir="ltr">
                  {p.code || p.barcode || ""}
                </div>
                <div className="font-bold text-primary mt-2 tabular">
                  {formatMoney(p.price)}
                </div>
              </button>
            );
          })}
        </div>
        <Button variant="outline" size="sm" onClick={addServiceLine}>
          <Plus className="h-4 w-4" /> إضافة بند خدمة
        </Button>
      </div>

      {/* Cart */}
      <div className="col-span-12 lg:col-span-5">
        <Card className="sticky top-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="h-5 w-5" /> الفاتورة الحالية
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <CustomerPicker value={customer} onChange={setCustomer} />

            <div className="space-y-2 max-h-[40vh] overflow-y-auto">
              {lines.length === 0 && (
                <div className="text-center text-muted-foreground py-8 text-sm">
                  لم تتم إضافة أي بند بعد
                </div>
              )}
              {lines.map((l, idx) => (
                <div
                  key={idx}
                  className={`p-2 rounded items-center ${
                    l.product_tracked && !l.device_instance_id
                      ? "bg-amber-500/10 border border-amber-500/40"
                      : "bg-muted/40"
                  }`}
                >
                  <div className="grid grid-cols-12 gap-2 items-center">
                    <Input
                      className="col-span-5 h-9"
                      value={l.description}
                      onChange={(e) => update(idx, { description: e.target.value })}
                    />
                    <Input
                      className="col-span-2 h-9"
                      type="number"
                      min={1}
                      value={l.qty}
                      onChange={(e) => update(idx, { qty: Math.max(1, Number(e.target.value) || 1) })}
                      disabled={l.product_tracked}
                    />
                    <Input
                      className="col-span-3 h-9"
                      type="number"
                      min={0}
                      step="0.01"
                      value={l.unit_price}
                      onChange={(e) => update(idx, { unit_price: e.target.value })}
                    />
                    <button
                      onClick={() => remove(idx)}
                      className="col-span-2 h-9 flex items-center justify-center text-red-600 hover:bg-red-100 rounded"
                      aria-label="حذف"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  {l.product_tracked && (
                    <div className="mt-1.5 flex items-center justify-between text-xs">
                      {l.device_imei ? (
                        <button
                          onClick={() =>
                            setImeiPickerFor({
                              lineIdx: idx,
                              productId: l.product_id!,
                              productName: l.description,
                            })
                          }
                          className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 hover:underline"
                        >
                          <span className="font-mono" dir="ltr">
                            ✓ IMEI: {l.device_imei}
                          </span>
                          <span className="text-muted-foreground">(تغيير)</span>
                        </button>
                      ) : (
                        <button
                          onClick={() =>
                            setImeiPickerFor({
                              lineIdx: idx,
                              productId: l.product_id!,
                              productName: l.description,
                            })
                          }
                          className="flex items-center gap-1.5 text-amber-700 dark:text-amber-400 font-semibold hover:underline"
                        >
                          <span>⚠ اختر IMEI</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t pt-4 space-y-2">
              <Row label="الإجمالي قبل الدفع" value={formatMoney(subtotal)} bold />
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-muted-foreground">المدفوع</span>
                <Input
                  className="w-32 h-9 text-left"
                  type="number"
                  min={0}
                  step="0.01"
                  value={paidAmount}
                  onChange={(e) => setPaidAmount(e.target.value)}
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="success"
                onClick={() => submitSale(true)}
                disabled={submitting || lines.length === 0}
                className="h-12"
              >
                دفع كاش
              </Button>
              <Button
                onClick={() => submitSale(false)}
                disabled={submitting || lines.length === 0 || !customer}
                className="h-12"
                variant="outline"
              >
                تسجيل آجل
              </Button>
            </div>
            {!customer && (
              <div className="text-xs text-amber-600 text-center">
                البيع الآجل يتطلب اختيار عميل
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* IMEI picker modal */}
      {imeiPickerFor && (
        <ImeiPicker
          productId={imeiPickerFor.productId}
          productName={imeiPickerFor.productName}
          onClose={() => setImeiPickerFor(null)}
          onPick={(device) => {
            const lineIdx = imeiPickerFor.lineIdx;
            update(lineIdx, {
              device_instance_id: device.id,
              device_imei: device.imei || device.serial_number || undefined,
            });
            setImeiPickerFor(null);
          }}
        />
      )}
    </div>
  );
}

// --- IMEI picker ----------------------------------------------------------

function ImeiPicker({
  productId,
  productName,
  onClose,
  onPick,
}: {
  productId: string;
  productName: string;
  onClose: () => void;
  onPick: (d: Device) => void;
}) {
  const [scan, setScan] = useState("");
  const list = useQuery<{ data: Device[] }>({
    queryKey: ["devices-for-product", productId],
    queryFn: async () =>
      (
        await api.get("/devices/", {
          params: { product_id: productId, status: "in_stock", per_page: 50 },
        })
      ).data,
  });

  const filtered = (list.data?.data || []).filter((d) => {
    if (!scan.trim()) return true;
    const q = scan.trim().toLowerCase();
    return (
      d.imei?.toLowerCase().includes(q) ||
      d.serial_number?.toLowerCase().includes(q)
    );
  });

  function exact() {
    const q = scan.trim();
    if (!q) return;
    const hit = (list.data?.data || []).find(
      (d) => d.imei === q || d.serial_number === q,
    );
    if (hit) onPick(hit);
    else toast.error("لا يوجد جهاز بهذا الـ IMEI في المخزن");
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-lg card-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">اختيار IMEI</div>
              <div className="text-xs text-muted-foreground">{productName}</div>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-muted rounded">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="relative">
            <Search className="h-4 w-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              dir="ltr"
              autoFocus
              placeholder="امسح أو اكتب IMEI / Serial"
              value={scan}
              onChange={(e) => setScan(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && exact()}
              className="pr-10"
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {filtered.length} جهاز متاح في المخزن
          </div>
          <div className="max-h-72 overflow-y-auto divide-y rounded-lg border">
            {filtered.length === 0 && (
              <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                لا يوجد أجهزة متاحة لهذا المنتج. سجّل جهاز جديد من{" "}
                <a href="/devices" className="text-primary hover:underline">
                  صفحة الأجهزة
                </a>
                .
              </div>
            )}
            {filtered.map((d) => (
              <button
                key={d.id}
                onClick={() => onPick(d)}
                className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-muted/50 text-right transition-colors"
              >
                <code className="font-mono text-sm" dir="ltr">
                  {d.imei || d.serial_number}
                </code>
                <span className="pill pill-success text-[10px]">في المخزن</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CustomerPicker({
  value,
  onChange,
}: {
  value: Customer | null;
  onChange: (c: Customer | null) => void;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const { data } = useQuery<{ data: Customer[] }>({
    queryKey: ["customers-pick", q],
    queryFn: async () =>
      (await api.get("/customers/", { params: { q: q || undefined, per_page: 10 } }))
        .data,
    enabled: open,
  });

  if (value) {
    return (
      <div className="flex items-center justify-between bg-primary/10 p-2 rounded">
        <div>
          <div className="font-medium">{value.name}</div>
          <div className="text-xs text-muted-foreground">
            {value.phone || "—"} • مديونية: {formatMoney(value.debt_cached || 0)}
          </div>
        </div>
        <button
          onClick={() => onChange(null)}
          className="p-1 hover:bg-muted rounded"
          aria-label="إزالة العميل"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }
  return (
    <div className="relative">
      <Input
        placeholder="ابحث عن عميل بالاسم أو الهاتف (اختياري)"
        value={q}
        onFocus={() => setOpen(true)}
        onChange={(e) => setQ(e.target.value)}
      />
      {open && (data?.data?.length || 0) > 0 && (
        <div className="absolute z-10 right-0 left-0 mt-1 max-h-64 overflow-y-auto bg-card border rounded shadow-lg">
          {data!.data.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                onChange(c);
                setOpen(false);
                setQ("");
              }}
              className="w-full text-right px-3 py-2 hover:bg-accent flex items-center justify-between"
            >
              <span className="font-medium">{c.name}</span>
              <span className="text-xs text-muted-foreground">{c.phone || ""}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={bold ? "font-bold text-lg" : ""}>{value}</span>
    </div>
  );
}
