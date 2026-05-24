"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Wallet,
  Banknote,
  Boxes,
  HandCoins,
  Receipt,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ShoppingCart,
  ArrowRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AnimatedNumber } from "@/components/animated-number";
import { formatMoney, formatNumber } from "@/lib/utils";

// ---------- Types ----------

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
type TrendPoint = { date: string; sales: string; profit: string; invoices: number };
type TopProduct = {
  product_id: string; product_name: string; qty_sold: number;
  revenue: string; cogs: string; profit: string;
};

// ---------- Page ----------

export default function DashboardPage() {
  const dashboard = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/reports/dashboard")).data.data,
    refetchInterval: 30_000,
  });
  const trend = useQuery<TrendPoint[]>({
    queryKey: ["sales-trend", 30],
    queryFn: async () => (await api.get("/reports/sales-trend?days=30")).data.data,
    refetchInterval: 60_000,
  });
  const top = useQuery<TopProduct[]>({
    queryKey: ["top-products", 5],
    queryFn: async () => (await api.get("/reports/top-products?limit=5")).data.data,
    refetchInterval: 60_000,
  });

  if (dashboard.isLoading || !dashboard.data) {
    return <DashboardSkeleton />;
  }
  const d = dashboard.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">لوحة القيادة</h1>
          <p className="text-sm text-muted-foreground mt-1">
            نظرة فورية على وضع المحل اليوم — <span className="tabular">{d.today}</span>
          </p>
        </div>
        <div className="pill pill-info">
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
          مزامنة لحظية كل 30 ثانية
        </div>
      </header>

      {/* KPI grid */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <Kpi
          title="الكاش في الخزينة"
          value={d.cash_balance}
          icon={Wallet}
          tone="success"
          subtitle="رصيد لحظي من القيود"
        />
        <Kpi
          title="ديون مستحقة لنا"
          value={d.ar_total}
          icon={HandCoins}
          tone={Number(d.ar_total) > 0 ? "warn" : "default"}
          subtitle="من العملاء"
        />
        <Kpi
          title="قيمة المخزون"
          value={d.inventory_value}
          icon={Boxes}
          subtitle="بسعر التكلفة"
        />
        <Kpi
          title="رصيد البنك"
          value={d.bank_balance}
          icon={Banknote}
          subtitle={d.bank_balance === "0" ? "(لا تحركات)" : ""}
        />
      </motion.div>

      {/* Trend + Top products */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="card-elevated xl:col-span-2 overflow-hidden">
          <CardHeader className="flex flex-row items-end justify-between gap-3 pb-2">
            <div>
              <CardTitle>الإيرادات والأرباح — آخر 30 يوم</CardTitle>
              <CardDescription>
                مبيعات يومية vs صافي الربح (الإيرادات − التكلفة)
              </CardDescription>
            </div>
            <div className="text-xs text-muted-foreground tabular">
              المجموع الشهري:&nbsp;
              <span className="text-foreground font-semibold">{formatMoney(d.month_sales)}</span>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend.data || []} margin={{ top: 6, right: 12, left: 6, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradSales" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradProfit" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--chart-2))" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickFormatter={(v) => {
                      const d = new Date(v);
                      return `${d.getDate()}/${d.getMonth() + 1}`;
                    }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    axisLine={false}
                    tickLine={false}
                    width={50}
                    tickFormatter={(v) => abbrev(Number(v))}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--popover))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value: any, name: string) => [
                      formatMoney(value),
                      name === "sales" ? "المبيعات" : "صافي الربح",
                    ]}
                    labelFormatter={(label) => `التاريخ: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="sales"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={2}
                    fill="url(#gradSales)"
                  />
                  <Area
                    type="monotone"
                    dataKey="profit"
                    stroke="hsl(var(--chart-2))"
                    strokeWidth={2}
                    fill="url(#gradProfit)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Treasury composition */}
        <Card className="card-elevated">
          <CardHeader className="pb-2">
            <CardTitle>توزيع الأصول</CardTitle>
            <CardDescription>قيمة الأصول الحالية</CardDescription>
          </CardHeader>
          <CardContent>
            <TreasuryDonut data={d} />
          </CardContent>
        </Card>
      </div>

      {/* Today + Top products */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="card-elevated">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="h-4 w-4" /> اليوم
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Row label="عدد الفواتير" value={formatNumber(d.today_invoices)} />
            <Row label="إجمالي المبيعات" value={formatMoney(d.today_sales)} />
            <Row
              label="صافي الربح"
              value={formatMoney(d.today_net_profit)}
              tone={Number(d.today_net_profit) >= 0 ? "success" : "danger"}
              icon={Number(d.today_net_profit) >= 0 ? TrendingUp : TrendingDown}
            />
          </CardContent>
        </Card>

        <Card className="card-elevated lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle>أعلى 5 منتجات مبيعًا</CardTitle>
            <CardDescription>هذا الشهر — حسب الإيرادات</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={(top.data || []).slice().reverse()}
                layout="vertical"
                margin={{ top: 6, right: 16, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => abbrev(Number(v))}
                />
                <YAxis
                  type="category"
                  dataKey="product_name"
                  tick={{ fontSize: 11, fill: "hsl(var(--foreground))" }}
                  axisLine={false}
                  tickLine={false}
                  width={130}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: any) => [formatMoney(value), "الإيراد"]}
                />
                <Bar dataKey="revenue" fill="hsl(var(--chart-1))" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
            {(top.data?.length ?? 0) === 0 && (
              <div className="text-center text-sm text-muted-foreground py-10">
                لا توجد مبيعات هذا الشهر بعد.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Alerts strip */}
      <Card className="card-elevated">
        <CardContent className="p-4 flex flex-wrap items-center gap-4">
          <AlertBadge
            icon={AlertTriangle}
            tone={d.low_stock_count > 0 ? "warn" : "muted"}
            label={
              d.low_stock_count > 0
                ? `${d.low_stock_count} منتج وصل لحد إعادة الطلب`
                : "المخزون سليم"
            }
          />
          <AlertBadge
            icon={Receipt}
            tone={Number(d.ap_total) > 0 ? "warn" : "muted"}
            label={
              Number(d.ap_total) > 0
                ? `مستحقات الموردين: ${formatMoney(d.ap_total)}`
                : "لا توجد مستحقات للموردين"
            }
          />
          <AlertBadge
            icon={TrendingUp}
            tone="success"
            label="كل العمليات مترجمة محاسبيًا"
          />
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- Sub-components ----------

function Kpi({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const accent = {
    default: "text-foreground",
    success: "text-emerald-600 dark:text-emerald-400",
    warn: "text-amber-600 dark:text-amber-400",
    danger: "text-red-600 dark:text-red-400",
  }[tone];
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    danger: "bg-red-500/10 text-red-600 dark:text-red-400",
  }[tone];
  return (
    <motion.div
      variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      <Card className="card-elevated h-full">
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                {title}
              </div>
              <div className={`kpi-value ${accent}`}>
                <AnimatedNumber
                  value={Number(value)}
                  formatter={(n) =>
                    n.toLocaleString("en-US", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }) + " ج.م"
                  }
                />
              </div>
              {subtitle && (
                <div className="text-xs text-muted-foreground">{subtitle}</div>
              )}
            </div>
            <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${ring}`}>
              <Icon className="h-5 w-5" />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function Row({
  label,
  value,
  tone = "default",
  icon: Icon,
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "danger";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const c =
    tone === "success" ? "text-emerald-600 dark:text-emerald-400" :
    tone === "danger" ? "text-red-600 dark:text-red-400" : "";
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`font-semibold tabular flex items-center gap-1 ${c}`}>
        {Icon && <Icon className="h-3.5 w-3.5" />}
        {value}
      </span>
    </div>
  );
}

function AlertBadge({
  icon: Icon,
  tone,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  tone: "success" | "warn" | "danger" | "muted";
  label: string;
}) {
  const cls = {
    success: "pill-success",
    warn: "pill-warn",
    danger: "pill-danger",
    muted: "pill-muted",
  }[tone];
  return (
    <span className={`pill ${cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

function TreasuryDonut({ data }: { data: DashboardData }) {
  const items = [
    { name: "كاش", value: Math.max(0, Number(data.cash_balance)), key: "cash" },
    { name: "بنك", value: Math.max(0, Number(data.bank_balance)), key: "bank" },
    { name: "ديون لنا", value: Math.max(0, Number(data.ar_total)), key: "ar" },
    { name: "مخزون", value: Math.max(0, Number(data.inventory_value)), key: "inv" },
  ].filter((x) => x.value > 0);
  const colors = ["hsl(var(--chart-2))", "hsl(var(--chart-4))", "hsl(var(--chart-3))", "hsl(var(--chart-1))"];
  const total = items.reduce((a, b) => a + b.value, 0);

  if (items.length === 0) {
    return (
      <div className="text-center text-sm text-muted-foreground py-10">
        لا توجد أصول حتى الآن.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              nameKey="name"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={2}
              stroke="hsl(var(--background))"
              strokeWidth={2}
            >
              {items.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value: any) => formatMoney(value)}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-2 text-sm">
        {items.map((it, i) => {
          const pct = total > 0 ? (it.value / total) * 100 : 0;
          return (
            <li key={it.key} className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: colors[i % colors.length] }}
              />
              <span className="text-muted-foreground flex-1">{it.name}</span>
              <span className="font-semibold tabular">{formatMoney(it.value)}</span>
              <span className="text-xs text-muted-foreground tabular w-10 text-left">
                {pct.toFixed(0)}%
              </span>
            </li>
          );
        })}
        <li className="border-t pt-2 mt-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">الإجمالي</span>
          <span className="font-bold tabular text-gradient">{formatMoney(total)}</span>
        </li>
      </ul>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 rounded-md bg-muted animate-pulse" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 rounded-xl bg-muted animate-pulse" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  );
}

function abbrev(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return String(n);
}
