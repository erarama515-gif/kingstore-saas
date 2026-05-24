"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X, Truck, HandCoins, ShoppingBag } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable, PageHeader, TableSkeleton } from "@/components/ui/data-table";
import { formatMoney } from "@/lib/utils";

type Supplier = {
  id: string;
  name: string;
  name_ar: string | null;
  phone: string | null;
  email: string | null;
  contact_person: string | null;
  address: string | null;
  notes: string | null;
  total_purchased_cached: string;
  payable_cached: string;
};

export default function SuppliersPage() {
  const [q, setQ] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const qc = useQueryClient();

  const list = useQuery<{ data: Supplier[] }>({
    queryKey: ["suppliers", q],
    queryFn: async () =>
      (await api.get("/suppliers/", { params: { q: q || undefined, per_page: 100 } }))
        .data,
  });

  const rows = list.data?.data || [];
  const k = React.useMemo(() => {
    const totalPurchased = rows.reduce(
      (a, b) => a + Number(b.total_purchased_cached || 0),
      0,
    );
    const totalPayable = rows.reduce((a, b) => a + Number(b.payable_cached || 0), 0);
    return { count: rows.length, totalPurchased, totalPayable };
  }, [rows]);

  const create = useMutation({
    mutationFn: (form: Partial<Supplier>) => api.post("/suppliers/", form),
    onSuccess: () => {
      toast.success("تم إضافة المورد");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.error?.message || "فشل الحفظ"),
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="الموردين"
        description="إدارة قاعدة الموردين ومتابعة المستحقات والمدفوعات"
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> مورد جديد
          </Button>
        }
      />

      {/* KPI strip */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        className="grid grid-cols-1 sm:grid-cols-3 gap-3"
      >
        <Kpi icon={Truck} label="عدد الموردين" value={k.count.toLocaleString("en-US")} />
        <Kpi
          icon={ShoppingBag}
          label="إجمالي المشتريات"
          value={formatMoney(k.totalPurchased)}
          tone="success"
        />
        <Kpi
          icon={HandCoins}
          label="مستحق للموردين"
          value={formatMoney(k.totalPayable)}
          tone={k.totalPayable > 0 ? "warn" : "default"}
        />
      </motion.div>

      <div className="max-w-md">
        <Input
          placeholder="ابحث بالاسم / الهاتف / البريد..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {list.isLoading ? (
        <TableSkeleton />
      ) : rows.length === 0 ? (
        <Card className="card-elevated">
          <CardContent className="py-16 flex flex-col items-center text-center gap-3">
            <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center">
              <Truck className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="font-semibold">لا يوجد موردين بعد</div>
            <div className="text-sm text-muted-foreground">
              ابدأ بإضافة أول مورد لتسجيل المشتريات والذمم الدائنة.
            </div>
            <Button onClick={() => setOpen(true)}>
              <Plus className="h-4 w-4" /> إضافة مورد
            </Button>
          </CardContent>
        </Card>
      ) : (
        <DataTable<Supplier>
          rows={rows}
          columns={[
            { header: "الاسم", render: (s) => <span className="font-medium">{s.name}</span> },
            {
              header: "جهة الاتصال",
              render: (s) => s.contact_person || s.phone || "—",
            },
            {
              header: "الهاتف",
              render: (s) => (
                <span className="tabular text-sm">{s.phone || "—"}</span>
              ),
            },
            {
              header: "إجمالي المشتريات",
              render: (s) => (
                <span className="tabular">{formatMoney(s.total_purchased_cached)}</span>
              ),
            },
            {
              header: "مستحق له",
              render: (s) =>
                Number(s.payable_cached) > 0 ? (
                  <span className="pill pill-warn">
                    {formatMoney(s.payable_cached)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                ),
            },
          ]}
        />
      )}

      {open && (
        <CreateSupplierDialog
          onClose={() => setOpen(false)}
          onSubmit={(form) => create.mutate(form)}
          submitting={create.isPending}
        />
      )}
    </div>
  );
}

function CreateSupplierDialog({
  onClose,
  onSubmit,
  submitting,
}: {
  onClose: () => void;
  onSubmit: (form: Partial<Supplier>) => void;
  submitting: boolean;
}) {
  const [form, setForm] = React.useState({
    name: "",
    phone: "",
    email: "",
    contact_person: "",
    address: "",
    notes: "",
  });
  const set =
    (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((s) => ({ ...s, [k]: e.target.value }));

  return (
    <div
      className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-lg card-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold">
              <Truck className="h-5 w-5 text-primary" /> مورد جديد
            </div>
            <button onClick={onClose} className="p-1 hover:bg-muted rounded">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-3">
            <Labeled label="اسم المورد *">
              <Input value={form.name} onChange={set("name")} required autoFocus />
            </Labeled>
            <div className="grid grid-cols-2 gap-3">
              <Labeled label="الهاتف">
                <Input value={form.phone} onChange={set("phone")} dir="ltr" />
              </Labeled>
              <Labeled label="جهة الاتصال">
                <Input value={form.contact_person} onChange={set("contact_person")} />
              </Labeled>
            </div>
            <Labeled label="البريد الإلكتروني">
              <Input value={form.email} onChange={set("email")} dir="ltr" />
            </Labeled>
            <Labeled label="العنوان">
              <Input value={form.address} onChange={set("address")} />
            </Labeled>
            <Labeled label="ملاحظات">
              <textarea
                value={form.notes}
                onChange={set("notes")}
                rows={2}
                className="w-full px-3 py-2 text-sm border rounded-md bg-background"
              />
            </Labeled>
          </div>
          <div className="grid grid-cols-2 gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>
              إلغاء
            </Button>
            <Button
              onClick={() => {
                if (!form.name.trim()) return toast.error("اسم المورد مطلوب");
                onSubmit({
                  name: form.name.trim(),
                  phone: form.phone || undefined,
                  email: form.email || undefined,
                  contact_person: form.contact_person || undefined,
                  address: form.address || undefined,
                  notes: form.notes || undefined,
                } as Partial<Supplier>);
              }}
              disabled={submitting}
            >
              {submitting ? "جاري الحفظ..." : "حفظ"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: any;
  label: string;
  value: string;
  tone?: "default" | "success" | "warn";
}) {
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  }[tone];
  return (
    <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
      <Card className="card-elevated">
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">
              {label}
            </div>
            <div className="text-xl font-bold tabular mt-0.5">{value}</div>
          </div>
          <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${ring}`}>
            <Icon className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
