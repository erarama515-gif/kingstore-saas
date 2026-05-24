"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { formatMoney, formatDate } from "@/lib/utils";

type Sale = {
  id: string;
  sale_number: string;
  sale_date: string;
  customer_name: string | null;
  total: string;
  paid_amount: string;
  is_paid: boolean;
  status: string;
};

export default function SalesPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const list = useQuery<{ data: Sale[] }>({
    queryKey: ["sales", from, to],
    queryFn: async () =>
      (
        await api.get("/sales/", {
          params: { from: from || undefined, to: to || undefined, per_page: 100 },
        })
      ).data,
  });

  return (
    <div>
      <PageHeader title="المبيعات" description="سجل كل عمليات البيع" />

      <div className="flex gap-3 mb-4">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">من</label>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">إلى</label>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      <DataTable<Sale>
        rows={list.data?.data || []}
        columns={[
          { header: "رقم الفاتورة", render: (s) => <code>{s.sale_number}</code> },
          { header: "التاريخ", render: (s) => formatDate(s.sale_date) },
          { header: "العميل", render: (s) => s.customer_name || "عميل نقدي" },
          {
            header: "الإجمالي",
            render: (s) => <span className="font-bold">{formatMoney(s.total)}</span>,
          },
          { header: "المدفوع", render: (s) => formatMoney(s.paid_amount) },
          {
            header: "الحالة",
            render: (s) =>
              s.status === "refunded" ? (
                <span className="text-red-600">مستردة</span>
              ) : s.is_paid ? (
                <span className="text-emerald-600">مدفوعة</span>
              ) : (
                <span className="text-amber-600">آجل</span>
              ),
          },
        ]}
      />
    </div>
  );
}
