"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Wallet,
  Banknote,
  Boxes,
  HandCoins,
  Receipt,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney, formatNumber } from "@/lib/utils";

type DashboardData = {
  today: string;
  cash_balance: string;
  bank_balance: string;
  ar_total: string;
  ap_total: string;
  inventory_value: string;
  today_sales: string;
  today_invoices: number;
  today_net_profit: string;
  month_sales: string;
  month_net_profit: string;
  low_stock_count: number;
};

function Kpi({
  title,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const toneClasses = {
    default: "text-muted-foreground",
    success: "text-emerald-600",
    warn: "text-amber-600",
    danger: "text-red-600",
  };
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-sm text-muted-foreground">{title}</div>
            <div className={`text-2xl font-bold mt-1 ${toneClasses[tone]}`}>{value}</div>
            {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
          </div>
          <Icon className="h-8 w-8 text-muted-foreground/40" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/reports/dashboard")).data.data,
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return <div className="text-muted-foreground">جاري تحميل لوحة القيادة...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">لوحة القيادة</h1>
        <p className="text-sm text-muted-foreground">
          نظرة فورية على وضع المحل اليوم — {data.today}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi
          title="الكاش في الخزينة"
          value={formatMoney(data.cash_balance)}
          icon={Wallet}
          tone="success"
        />
        <Kpi
          title="رصيد البنك"
          value={formatMoney(data.bank_balance)}
          icon={Banknote}
        />
        <Kpi
          title="قيمة المخزون"
          value={formatMoney(data.inventory_value)}
          icon={Boxes}
        />
        <Kpi
          title="ديون مستحقة لنا"
          value={formatMoney(data.ar_total)}
          icon={HandCoins}
          tone="warn"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>اليوم</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Row label="عدد الفواتير" value={formatNumber(data.today_invoices)} />
            <Row label="إجمالي المبيعات" value={formatMoney(data.today_sales)} />
            <Row
              label="صافي الربح"
              value={formatMoney(data.today_net_profit)}
              tone={Number(data.today_net_profit) >= 0 ? "success" : "danger"}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>الشهر الحالي</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Row label="إجمالي المبيعات" value={formatMoney(data.month_sales)} />
            <Row
              label="صافي الربح"
              value={formatMoney(data.month_net_profit)}
              tone={Number(data.month_net_profit) >= 0 ? "success" : "danger"}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>تنبيهات</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {data.low_stock_count > 0 ? (
              <div className="flex items-center gap-2 text-amber-600">
                <AlertTriangle className="h-4 w-4" />
                <span>{data.low_stock_count} منتج وصل لحد إعادة الطلب</span>
              </div>
            ) : (
              <div className="text-muted-foreground">لا توجد تنبيهات</div>
            )}
            {Number(data.ap_total) > 0 && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Receipt className="h-4 w-4" />
                <span>مستحقات للموردين: {formatMoney(data.ap_total)}</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-emerald-600">
              <TrendingUp className="h-4 w-4" />
              <span>كل العمليات محاسبيًا مترجمة في القيود</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "danger";
}) {
  const c =
    tone === "success" ? "text-emerald-600" : tone === "danger" ? "text-red-600" : "";
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`font-semibold ${c}`}>{value}</span>
    </div>
  );
}
