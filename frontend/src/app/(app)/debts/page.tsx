"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { HandCoins } from "lucide-react";
import { api } from "@/lib/api";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatMoney, formatDate } from "@/lib/utils";

type Sale = {
  id: string;
  sale_number: string;
  sale_date: string;
  customer_name: string | null;
  total: string;
  paid_amount: string;
};

export default function DebtsPage() {
  const qc = useQueryClient();
  const [collecting, setCollecting] = useState<Sale | null>(null);

  const list = useQuery<{ data: Sale[] }>({
    queryKey: ["debts"],
    queryFn: async () => (await api.get("/sales/debts", { params: { per_page: 100 } })).data,
  });

  const totalDebt = (list.data?.data || []).reduce(
    (s, x) => s + (Number(x.total) - Number(x.paid_amount)),
    0,
  );

  return (
    <div>
      <PageHeader
        title="الديون والآجل"
        description={`إجمالي الديون المستحقة: ${formatMoney(totalDebt)}`}
      />

      <DataTable<Sale>
        rows={list.data?.data || []}
        columns={[
          { header: "رقم الفاتورة", render: (s) => <code>{s.sale_number}</code> },
          { header: "التاريخ", render: (s) => formatDate(s.sale_date) },
          { header: "العميل", render: (s) => s.customer_name || "—" },
          { header: "الإجمالي", render: (s) => formatMoney(s.total) },
          { header: "المدفوع", render: (s) => formatMoney(s.paid_amount) },
          {
            header: "المتبقي",
            render: (s) => {
              const r = Number(s.total) - Number(s.paid_amount);
              return <span className="text-amber-600 font-bold">{formatMoney(r)}</span>;
            },
          },
          {
            header: "تحكم",
            render: (s) => (
              <Button size="sm" variant="success" onClick={() => setCollecting(s)}>
                <HandCoins className="h-4 w-4" /> تحصيل
              </Button>
            ),
          },
        ]}
        emptyMessage="لا توجد ديون مستحقة"
      />

      {collecting && (
        <CollectDialog
          sale={collecting}
          onClose={() => setCollecting(null)}
          onDone={() => {
            setCollecting(null);
            qc.invalidateQueries({ queryKey: ["debts"] });
          }}
        />
      )}
    </div>
  );
}

function CollectDialog({
  sale,
  onClose,
  onDone,
}: {
  sale: Sale;
  onClose: () => void;
  onDone: () => void;
}) {
  const outstanding = Number(sale.total) - Number(sale.paid_amount);
  const [amount, setAmount] = useState(String(outstanding.toFixed(2)));
  const [method, setMethod] = useState<"cash" | "bank">("cash");

  const m = useMutation({
    mutationFn: async () =>
      (await api.post(`/sales/${sale.id}/payments`, { amount, method })).data,
    onSuccess: () => {
      toast.success("تم تحصيل المبلغ");
      onDone();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل التحصيل"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card p-6 rounded-lg max-w-sm w-full space-y-4 shadow-2xl">
        <h3 className="text-lg font-bold">تحصيل من {sale.sale_number}</h3>
        <div className="text-sm text-muted-foreground">
          المتبقي: <span className="font-semibold">{formatMoney(outstanding)}</span>
        </div>
        <div className="space-y-2">
          <label className="text-sm">المبلغ</label>
          <Input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm">طريقة الدفع</label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value as "cash" | "bank")}
            className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
          >
            <option value="cash">كاش</option>
            <option value="bank">بنك</option>
          </select>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button variant="success" onClick={() => m.mutate()} disabled={m.isPending}>
            تحصيل
          </Button>
        </div>
      </div>
    </div>
  );
}
