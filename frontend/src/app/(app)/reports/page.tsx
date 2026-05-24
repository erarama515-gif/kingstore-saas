"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/data-table";
import { formatMoney } from "@/lib/utils";

export default function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [from, setFrom] = useState(firstOfMonth);
  const [to, setTo] = useState(today);

  const pnl = useQuery({
    queryKey: ["pnl", from, to],
    queryFn: async () =>
      (await api.get("/reports/pnl", { params: { from, to } })).data.data,
  });

  const bs = useQuery({
    queryKey: ["bs", to],
    queryFn: async () =>
      (await api.get("/reports/balance-sheet", { params: { as_of: to } })).data.data,
  });

  const sales = useQuery({
    queryKey: ["sales-sum", from, to],
    queryFn: async () =>
      (await api.get("/reports/sales-summary", { params: { from, to } })).data.data,
  });

  const top = useQuery({
    queryKey: ["top-products", from, to],
    queryFn: async () =>
      (await api.get("/reports/top-products", { params: { from, to, limit: 10 } })).data.data,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="التقارير المالية" />

      <div className="flex gap-3">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">من</label>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">إلى</label>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* P&L */}
        <Card>
          <CardHeader>
            <CardTitle>قائمة الدخل (الأرباح والخسائر)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Section title="الإيرادات" rows={pnl.data?.revenue || []} />
            <div className="flex justify-between font-semibold border-t pt-2">
              <span>إجمالي الإيرادات</span>
              <span className="text-emerald-600">{formatMoney(pnl.data?.total_revenue || 0)}</span>
            </div>
            <Section title="المصروفات" rows={pnl.data?.expense || []} />
            <div className="flex justify-between font-semibold border-t pt-2">
              <span>إجمالي المصروفات</span>
              <span className="text-red-600">{formatMoney(pnl.data?.total_expense || 0)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold border-t pt-3">
              <span>صافي الربح</span>
              <span
                className={
                  Number(pnl.data?.net_profit || 0) >= 0
                    ? "text-emerald-600"
                    : "text-red-600"
                }
              >
                {formatMoney(pnl.data?.net_profit || 0)}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Balance Sheet */}
        <Card>
          <CardHeader>
            <CardTitle>الميزانية العمومية</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Section title="الأصول" rows={bs.data?.assets || []} />
            <div className="flex justify-between font-semibold border-t pt-2">
              <span>إجمالي الأصول</span>
              <span>{formatMoney(bs.data?.total_assets || 0)}</span>
            </div>
            <Section title="الالتزامات" rows={bs.data?.liabilities || []} />
            <div className="flex justify-between font-semibold border-t pt-2">
              <span>إجمالي الالتزامات</span>
              <span>{formatMoney(bs.data?.total_liabilities || 0)}</span>
            </div>
            <Section title="حقوق الملكية" rows={bs.data?.equity || []} />
            <div className="flex justify-between font-semibold border-t pt-2">
              <span>إجمالي حقوق الملكية</span>
              <span>{formatMoney(bs.data?.total_equity || 0)}</span>
            </div>
            <div className="text-xs text-center pt-2">
              {bs.data?.is_balanced ? (
                <span className="text-emerald-600">الميزانية متزنة ✓</span>
              ) : (
                <span className="text-amber-600">الميزانية غير متزنة (قيد المعالجة)</span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Sales summary */}
        <Card>
          <CardHeader>
            <CardTitle>ملخص المبيعات</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row k="عدد الفواتير" v={String(sales.data?.invoice_count || 0)} />
            <Row k="إجمالي قبل الخصم" v={formatMoney(sales.data?.gross_revenue || 0)} />
            <Row k="إجمالي الخصومات" v={formatMoney(sales.data?.discount_total || 0)} />
            <Row k="صافي المبيعات" v={formatMoney(sales.data?.net_revenue || 0)} bold />
            <Row k="تكلفة المبيعات" v={formatMoney(sales.data?.cogs_total || 0)} />
            <Row
              k="مجمل الربح"
              v={formatMoney(sales.data?.gross_profit || 0)}
              bold
            />
            <Row k="متوسط الفاتورة" v={formatMoney(sales.data?.avg_ticket || 0)} />
          </CardContent>
        </Card>

        {/* Top products */}
        <Card>
          <CardHeader>
            <CardTitle>أعلى المنتجات مبيعًا</CardTitle>
          </CardHeader>
          <CardContent>
            {(top.data || []).length === 0 ? (
              <div className="text-muted-foreground text-sm">لا توجد بيانات</div>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {(top.data || []).map((r: any) => (
                    <tr key={r.product_id} className="border-b last:border-0">
                      <td className="py-2">{r.product_name}</td>
                      <td className="py-2 text-center">{r.qty_sold}</td>
                      <td className="py-2 text-left font-semibold">{formatMoney(r.revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Section({
  title,
  rows,
}: {
  title: string;
  rows: { code: string; name: string; name_ar: string | null; amount: string }[];
}) {
  return (
    <div>
      <div className="text-xs font-semibold text-muted-foreground mb-1">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted-foreground italic">لا توجد حركات</div>
      ) : (
        rows.map((r) => (
          <div key={r.code} className="flex justify-between py-0.5">
            <span>{r.name_ar || r.name}</span>
            <span>{formatMoney(r.amount)}</span>
          </div>
        ))
      )}
    </div>
  );
}

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className={bold ? "font-bold" : ""}>{v}</span>
    </div>
  );
}
