"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { formatMoney } from "@/lib/utils";

type Product = {
  id: string;
  name: string;
  category: string;
  code: string | null;
  barcode: string | null;
  cost: string;
  price: string;
  reorder_point: number;
  is_active: boolean;
};

const CATS: { value: string; label: string }[] = [
  { value: "mobile", label: "موبايل" },
  { value: "accessory", label: "إكسسوار" },
  { value: "spare", label: "قطع غيار" },
  { value: "service", label: "خدمة" },
  { value: "other", label: "أخرى" },
];

export default function ProductsPage() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const list = useQuery<{ data: Product[] }>({
    queryKey: ["products", q],
    queryFn: async () =>
      (await api.get("/products/", { params: { q: q || undefined, per_page: 50 } })).data,
  });

  return (
    <div>
      <PageHeader
        title="المنتجات"
        description="إدارة الكتالوج والأسعار والباركودات"
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> منتج جديد
          </Button>
        }
      />

      <div className="mb-4 max-w-md">
        <Input
          placeholder="ابحث بالاسم / الكود / الباركود..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <DataTable<Product>
        rows={list.data?.data || []}
        columns={[
          { header: "الاسم", render: (p) => p.name },
          {
            header: "النوع",
            render: (p) => CATS.find((c) => c.value === p.category)?.label || p.category,
          },
          { header: "الكود", render: (p) => p.code || "—" },
          { header: "الباركود", render: (p) => p.barcode || "—" },
          { header: "التكلفة", render: (p) => formatMoney(p.cost) },
          {
            header: "السعر",
            render: (p) => <span className="font-bold">{formatMoney(p.price)}</span>,
          },
          {
            header: "الربح",
            render: (p) => {
              const profit = Number(p.price) - Number(p.cost);
              return (
                <span className={profit >= 0 ? "text-emerald-600" : "text-red-600"}>
                  {formatMoney(profit)}
                </span>
              );
            },
          },
        ]}
      />

      {open && (
        <ProductDialog
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            qc.invalidateQueries({ queryKey: ["products"] });
          }}
        />
      )}
    </div>
  );
}

function ProductDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: "",
    category: "mobile",
    code: "",
    barcode: "",
    cost: "0",
    price: "0",
    reorder_point: 2,
  });

  const m = useMutation({
    mutationFn: async (payload: typeof form) => {
      const body: any = { ...payload };
      if (!body.code) delete body.code;
      if (!body.barcode) delete body.barcode;
      return (await api.post("/products/", body)).data.data;
    },
    onSuccess: () => {
      toast.success("تم حفظ المنتج");
      onSaved();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل الحفظ"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">منتج جديد</h2>
          <button onClick={onClose} className="hover:bg-muted p-1 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="الاسم">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </Field>
          <Field label="النوع">
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
            >
              {CATS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="الكود (اختياري)">
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <Field label="الباركود (اختياري)">
            <Input
              value={form.barcode}
              onChange={(e) => setForm({ ...form, barcode: e.target.value })}
              placeholder="يُولَّد تلقائيًا"
            />
          </Field>
          <Field label="التكلفة">
            <Input
              type="number"
              step="0.01"
              value={form.cost}
              onChange={(e) => setForm({ ...form, cost: e.target.value })}
            />
          </Field>
          <Field label="السعر">
            <Input
              type="number"
              step="0.01"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
            />
          </Field>
          <Field label="حد إعادة الطلب">
            <Input
              type="number"
              min={0}
              value={form.reorder_point}
              onChange={(e) =>
                setForm({ ...form, reorder_point: Number(e.target.value) || 0 })
              }
            />
          </Field>
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>
            إلغاء
          </Button>
          <Button onClick={() => m.mutate(form)} disabled={m.isPending}>
            {m.isPending ? "جاري الحفظ..." : "حفظ"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      {children}
    </div>
  );
}
