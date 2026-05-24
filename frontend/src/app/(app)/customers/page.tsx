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

type Customer = {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  total_spent_cached: string;
  debt_cached: string;
  visits_count: number;
};

export default function CustomersPage() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const list = useQuery<{ data: Customer[] }>({
    queryKey: ["customers", q],
    queryFn: async () =>
      (await api.get("/customers/", { params: { q: q || undefined, per_page: 50 } })).data,
  });

  return (
    <div>
      <PageHeader
        title="العملاء"
        description="قاعدة بيانات العملاء وأرصدتهم"
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> عميل جديد
          </Button>
        }
      />

      <div className="mb-4 max-w-md">
        <Input
          placeholder="ابحث بالاسم أو الهاتف..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <DataTable<Customer>
        rows={list.data?.data || []}
        columns={[
          { header: "الاسم", render: (c) => c.name },
          { header: "الهاتف", render: (c) => c.phone || "—" },
          { header: "البريد", render: (c) => c.email || "—" },
          { header: "الزيارات", render: (c) => String(c.visits_count) },
          {
            header: "إجمالي المشتريات",
            render: (c) => formatMoney(c.total_spent_cached),
          },
          {
            header: "المديونية",
            render: (c) => {
              const v = Number(c.debt_cached);
              return (
                <span className={v > 0 ? "text-amber-600 font-semibold" : ""}>
                  {formatMoney(c.debt_cached)}
                </span>
              );
            },
          },
        ]}
      />

      {open && (
        <CustomerDialog
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            qc.invalidateQueries({ queryKey: ["customers"] });
          }}
        />
      )}
    </div>
  );
}

function CustomerDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", address: "", notes: "" });
  const m = useMutation({
    mutationFn: async (payload: typeof form) => {
      const body: any = { name: payload.name };
      if (payload.phone) body.phone = payload.phone;
      if (payload.email) body.email = payload.email;
      if (payload.address) body.address = payload.address;
      if (payload.notes) body.notes = payload.notes;
      return (await api.post("/customers/", body)).data.data;
    },
    onSuccess: () => {
      toast.success("تم حفظ العميل");
      onSaved();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل الحفظ"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">عميل جديد</h2>
          <button onClick={onClose} className="hover:bg-muted p-1 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-sm">الاسم</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm">الهاتف</label>
              <Input
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm">البريد</label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm">العنوان</label>
            <Input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>
            إلغاء
          </Button>
          <Button onClick={() => m.mutate(form)} disabled={m.isPending}>
            حفظ
          </Button>
        </div>
      </div>
    </div>
  );
}
