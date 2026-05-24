"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { formatMoney, formatDate } from "@/lib/utils";

type Expense = {
  id: string;
  expense_date: string;
  amount: string;
  description: string;
  payment_method: string;
  reference: string | null;
};

const EXPENSE_KEYS = [
  { key: "RENT", label: "إيجار" },
  { key: "SALARIES", label: "مرتبات" },
  { key: "UTILITIES", label: "كهرباء/مياه/إنترنت" },
  { key: "OPERATING_EXPENSES", label: "مصروفات تشغيلية" },
  { key: "OTHER_EXPENSES", label: "أخرى" },
];

export default function ExpensesPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const list = useQuery<{ data: Expense[] }>({
    queryKey: ["expenses"],
    queryFn: async () => (await api.get("/expenses/", { params: { per_page: 100 } })).data,
  });

  return (
    <div>
      <PageHeader
        title="المصروفات"
        description="تسجيل كل المصروفات اليومية"
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> مصروف جديد
          </Button>
        }
      />

      <DataTable<Expense>
        rows={list.data?.data || []}
        columns={[
          { header: "التاريخ", render: (e) => formatDate(e.expense_date) },
          { header: "البيان", render: (e) => e.description },
          {
            header: "المبلغ",
            render: (e) => (
              <span className="text-red-600 font-bold">{formatMoney(e.amount)}</span>
            ),
          },
          {
            header: "طريقة الدفع",
            render: (e) => (e.payment_method === "cash" ? "كاش" : "بنك"),
          },
          { header: "مرجع", render: (e) => e.reference || "—" },
        ]}
      />

      {open && (
        <ExpenseDialog
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            qc.invalidateQueries({ queryKey: ["expenses"] });
            qc.invalidateQueries({ queryKey: ["dashboard"] });
          }}
        />
      )}
    </div>
  );
}

function ExpenseDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [branchId, setBranchId] = useState<string | null>(null);
  const [form, setForm] = useState({
    expense_account_key: "OPERATING_EXPENSES",
    amount: "",
    payment_method: "cash" as "cash" | "bank",
    description: "",
    reference: "",
  });

  // Read default branch from the logged-in user
  useState(() => {
    api.get("/auth/me").then((r) => setBranchId(r.data.data?.user?.default_branch_id));
    return null;
  });

  const m = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("لا يوجد فرع نشط");
      const body: any = {
        branch_id: branchId,
        amount: form.amount,
        payment_method: form.payment_method,
        description: form.description,
        expense_account_key: form.expense_account_key,
      };
      if (form.reference) body.reference = form.reference;
      return (await api.post("/expenses/", body)).data.data;
    },
    onSuccess: () => {
      toast.success("تم تسجيل المصروف");
      onSaved();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل التسجيل"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg w-full max-w-md p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">مصروف جديد</h2>
          <button onClick={onClose} className="hover:bg-muted p-1 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-sm">البند</label>
            <select
              value={form.expense_account_key}
              onChange={(e) => setForm({ ...form, expense_account_key: e.target.value })}
              className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
            >
              {EXPENSE_KEYS.map((x) => (
                <option key={x.key} value={x.key}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm">المبلغ</label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm">الدفع</label>
              <select
                value={form.payment_method}
                onChange={(e) =>
                  setForm({ ...form, payment_method: e.target.value as "cash" | "bank" })
                }
                className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
              >
                <option value="cash">كاش</option>
                <option value="bank">بنك</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm">البيان</label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="إيجار شهر يونيو..."
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm">مرجع (اختياري)</label>
            <Input
              value={form.reference}
              onChange={(e) => setForm({ ...form, reference: e.target.value })}
              placeholder="رقم فاتورة الكهرباء..."
            />
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button onClick={() => m.mutate()} disabled={m.isPending}>
            تسجيل
          </Button>
        </div>
      </div>
    </div>
  );
}
