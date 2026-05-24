"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowRight,
  Printer,
  Receipt,
  CreditCard,
  Undo2,
  Calendar,
  User,
  Hash,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney, formatDate } from "@/lib/utils";

type Line = {
  id: string;
  description: string;
  qty: number;
  unit_price: string;
  discount: string;
  line_total: string;
  cost_snapshot: string;
  is_service: boolean;
};
type Sale = {
  id: string;
  sale_number: string;
  branch_id: string;
  customer_id: string | null;
  customer_name: string | null;
  sale_date: string;
  subtotal: string;
  discount_total: string;
  total: string;
  paid_amount: string;
  is_paid: boolean;
  status: string;
  notes: string | null;
  lines: Line[];
  created_at: string;
};
type Tenant = { name: string; slug: string };

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [payOpen, setPayOpen] = React.useState(false);
  const [payAmount, setPayAmount] = React.useState("");

  const sale = useQuery<Sale>({
    queryKey: ["sale", id],
    queryFn: async () => (await api.get(`/sales/${id}`)).data.data,
  });
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/auth/me")).data.data as { tenant: Tenant },
  });

  const pay = useMutation({
    mutationFn: (amount: string) =>
      api.post(`/sales/${id}/payments`, { amount, method: "cash" }),
    onSuccess: () => {
      toast.success("تم تحصيل الدفعة");
      setPayOpen(false);
      setPayAmount("");
      qc.invalidateQueries({ queryKey: ["sale", id] });
      qc.invalidateQueries({ queryKey: ["sales"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.error?.message || "فشل التحصيل"),
  });

  const refund = useMutation({
    mutationFn: () => api.post(`/sales/${id}/refund`, { reason: "إلغاء الفاتورة" }),
    onSuccess: () => {
      toast.success("تم استرداد الفاتورة");
      qc.invalidateQueries({ queryKey: ["sale", id] });
      qc.invalidateQueries({ queryKey: ["sales"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.error?.message || "فشل الاسترداد"),
  });

  if (sale.isLoading || !sale.data) {
    return <DetailSkeleton />;
  }
  const s = sale.data;
  const remaining = Number(s.total) - Number(s.paid_amount);
  const tenantName = meQuery.data?.tenant.name || "Kingstore";

  return (
    <div className="space-y-6 print:bg-white print:p-0">
      {/* Toolbar (hidden when printing) */}
      <div className="flex items-center justify-between print:hidden">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowRight className="h-4 w-4" /> رجوع
        </Button>
        <div className="flex items-center gap-2">
          {s.status !== "refunded" && remaining > 0 && (
            <Button onClick={() => setPayOpen(true)} variant="default">
              <CreditCard className="h-4 w-4" /> تحصيل دفعة
            </Button>
          )}
          {s.status !== "refunded" && (
            <Button
              variant="outline"
              onClick={() => {
                if (confirm("تأكيد استرداد الفاتورة كاملة؟ سيتم إنشاء قيد عكسي.")) {
                  refund.mutate();
                }
              }}
            >
              <Undo2 className="h-4 w-4" /> استرداد
            </Button>
          )}
          <Button onClick={() => window.print()} variant="outline">
            <Printer className="h-4 w-4" /> طباعة
          </Button>
        </div>
      </div>

      {/* Invoice surface */}
      <div className="mx-auto max-w-3xl bg-card border rounded-xl shadow-sm print:shadow-none print:border-0 print:max-w-none">
        {/* Header */}
        <div className="p-8 border-b flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-primary to-chart-5 text-primary-foreground flex items-center justify-center font-bold text-xl">
                K
              </div>
              <div>
                <div className="text-xl font-bold">{tenantName}</div>
                <div className="text-xs text-muted-foreground">ERP & POS</div>
              </div>
            </div>
            <StatusPill status={s.status} isPaid={s.is_paid} />
          </div>
          <div className="text-left">
            <div className="text-xs uppercase text-muted-foreground tracking-wider">
              فاتورة
            </div>
            <div className="text-2xl font-bold tracking-tight tabular">{s.sale_number}</div>
            <div className="text-xs text-muted-foreground mt-2 tabular">
              {formatDate(s.sale_date)}
            </div>
          </div>
        </div>

        {/* Customer + meta */}
        <div className="grid grid-cols-2 gap-6 p-6 border-b text-sm">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
              العميل
            </div>
            <div className="font-semibold">{s.customer_name || "عميل نقدي"}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">
              تفاصيل
            </div>
            <div className="space-y-0.5">
              <Meta icon={Hash}     label={s.sale_number} />
              <Meta icon={Calendar} label={formatDate(s.sale_date)} />
              {s.customer_id && <Meta icon={User} label="عميل مسجّل" />}
            </div>
          </div>
        </div>

        {/* Line items */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs uppercase tracking-wider">
              <tr>
                <th className="text-right p-3 font-medium">البيان</th>
                <th className="text-center p-3 font-medium">الكمية</th>
                <th className="text-center p-3 font-medium">السعر</th>
                <th className="text-center p-3 font-medium">الخصم</th>
                <th className="text-left p-3 font-medium">الإجمالي</th>
              </tr>
            </thead>
            <tbody>
              {s.lines.map((l) => (
                <tr key={l.id} className="border-t">
                  <td className="p-3">
                    {l.description}
                    {l.is_service && (
                      <span className="ms-2 pill pill-info">خدمة</span>
                    )}
                  </td>
                  <td className="p-3 text-center tabular">{l.qty}</td>
                  <td className="p-3 text-center tabular">{formatMoney(l.unit_price)}</td>
                  <td className="p-3 text-center tabular text-muted-foreground">
                    {Number(l.discount) > 0 ? formatMoney(l.discount) : "—"}
                  </td>
                  <td className="p-3 text-left tabular font-medium">
                    {formatMoney(l.line_total)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Totals */}
        <div className="p-6 border-t bg-muted/20 print:bg-transparent">
          <div className="ms-auto max-w-sm space-y-2 text-sm">
            <Row label="المجموع الفرعي" value={formatMoney(s.subtotal)} />
            {Number(s.discount_total) > 0 && (
              <Row
                label="إجمالي الخصم"
                value={"− " + formatMoney(s.discount_total)}
                muted
              />
            )}
            <Row label="الإجمالي" value={formatMoney(s.total)} big />
            <Row label="المدفوع" value={formatMoney(s.paid_amount)} muted />
            {remaining > 0 ? (
              <Row
                label="المتبقي"
                value={formatMoney(remaining)}
                big
                tone="warn"
              />
            ) : (
              <div className="flex items-center justify-end gap-2 text-emerald-600 pt-2">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-semibold">مدفوعة بالكامل</span>
              </div>
            )}
          </div>
        </div>

        {s.notes && (
          <div className="p-4 border-t text-xs text-muted-foreground italic">
            ملاحظات: {s.notes}
          </div>
        )}

        {/* Footer (print-only emphasis) */}
        <div className="p-6 border-t text-center text-xs text-muted-foreground">
          <div>شكرًا لتعاملكم معنا — هذه الفاتورة دليل إثبات للشراء.</div>
          <div className="mt-1 tabular">{tenantName} • {formatDate(new Date())}</div>
        </div>
      </div>

      {/* Payment dialog */}
      {payOpen && (
        <div
          className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm flex items-center justify-center p-4 print:hidden"
          onClick={() => setPayOpen(false)}
        >
          <Card
            className="w-full max-w-md card-elevated animate-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" /> تحصيل دفعة
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">إجمالي الفاتورة</span>
                  <span className="font-semibold tabular">{formatMoney(s.total)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">المدفوع سابقًا</span>
                  <span className="tabular">{formatMoney(s.paid_amount)}</span>
                </div>
                <div className="flex justify-between border-t pt-2 font-semibold">
                  <span>المتبقي</span>
                  <span className="tabular text-amber-600">{formatMoney(remaining)}</span>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">مبلغ الدفعة</label>
                <Input
                  type="number"
                  step="0.01"
                  min={0}
                  max={remaining}
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  placeholder={remaining.toString()}
                  autoFocus
                />
                <div className="flex gap-1">
                  <button
                    className="text-xs px-2 py-1 rounded bg-muted hover:bg-accent"
                    onClick={() => setPayAmount(remaining.toString())}
                  >
                    المبلغ كله
                  </button>
                  <button
                    className="text-xs px-2 py-1 rounded bg-muted hover:bg-accent"
                    onClick={() => setPayAmount((remaining / 2).toFixed(2))}
                  >
                    50%
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" onClick={() => setPayOpen(false)}>
                  إلغاء
                </Button>
                <Button
                  onClick={() => pay.mutate(payAmount)}
                  disabled={!payAmount || Number(payAmount) <= 0 || pay.isPending}
                >
                  {pay.isPending ? "جاري التحصيل..." : "تأكيد"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <style jsx global>{`
        @media print {
          @page { size: A5; margin: 8mm; }
          body { background: white; }
          .sidebar, aside { display: none !important; }
          main { margin: 0 !important; padding: 0 !important; }
        }
      `}</style>
    </div>
  );
}

// ---------- atoms ----------

function StatusPill({ status, isPaid }: { status: string; isPaid: boolean }) {
  if (status === "refunded") return <span className="pill pill-danger">مستردة</span>;
  if (isPaid) return <span className="pill pill-success">مدفوعة بالكامل</span>;
  return <span className="pill pill-warn">آجل / تحت التحصيل</span>;
}

function Row({
  label,
  value,
  big,
  muted,
  tone = "default",
}: {
  label: string;
  value: string;
  big?: boolean;
  muted?: boolean;
  tone?: "default" | "warn" | "success";
}) {
  const valueCls = [
    "tabular",
    big ? "text-lg font-bold" : "font-medium",
    tone === "warn" ? "text-amber-600 dark:text-amber-400" : "",
    tone === "success" ? "text-emerald-600 dark:text-emerald-400" : "",
  ].join(" ");
  return (
    <div className={`flex items-center justify-between ${muted ? "text-muted-foreground" : ""}`}>
      <span className={big ? "font-semibold" : ""}>{label}</span>
      <span className={valueCls}>{value}</span>
    </div>
  );
}

function Meta({ icon: Icon, label }: { icon: any; label: string }) {
  return (
    <div className="flex items-center gap-2 text-muted-foreground">
      <Icon className="h-3.5 w-3.5" />
      <span className="tabular">{label}</span>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-10 w-32 bg-muted rounded animate-pulse" />
      <div className="mx-auto max-w-3xl space-y-3">
        <div className="h-24 bg-muted rounded-xl animate-pulse" />
        <div className="h-48 bg-muted rounded-xl animate-pulse" />
        <div className="h-32 bg-muted rounded-xl animate-pulse" />
      </div>
    </div>
  );
}
