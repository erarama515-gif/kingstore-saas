"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  Download,
  TrendingUp,
  TrendingDown,
  Scale,
  ShoppingBag,
  Target,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/data-table";
import { formatMoney } from "@/lib/utils";

type AccountLine = { code: string; name: string; name_ar: string | null; amount: string };
type PnL = {
  revenue: AccountLine[]; expense: AccountLine[];
  total_revenue: string; total_expense: string; net_profit: string;
};
type BS = {
  assets: AccountLine[]; liabilities: AccountLine[]; equity: AccountLine[];
  total_assets: string; total_liabilities: string; total_equity: string;
  is_balanced: boolean;
};
type SalesSummary = {
  invoice_count: number;
  gross_revenue: string; discount_total: string; net_revenue: string;
  cogs_total: string; gross_profit: string; avg_ticket: string;
};
type TopProduct = {
  product_id: string; product_name: string; qty_sold: number;
  revenue: string; cogs: string; profit: string;
};

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export default function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [from, setFrom] = React.useState(firstOfMonth);
  const [to, setTo] = React.useState(today);

  const pnl = useQuery<PnL>({
    queryKey: ["pnl", from, to],
    queryFn: async () => (await api.get("/reports/pnl", { params: { from, to } })).data.data,
  });
  const bs = useQuery<BS>({
    queryKey: ["bs", to],
    queryFn: async () => (await api.get("/reports/balance-sheet", { params: { as_of: to } })).data.data,
  });
  const sales = useQuery<SalesSummary>({
    queryKey: ["sales-sum", from, to],
    queryFn: async () =>
      (await api.get("/reports/sales-summary", { params: { from, to } })).data.data,
  });
  const top = useQuery<TopProduct[]>({
    queryKey: ["top-products", from, to],
    queryFn: async () =>
      (await api.get("/reports/top-products", { params: { from, to, limit: 8 } })).data.data,
  });

  // Helper: turn an account-line list into Recharts series
  const revSeries = (pnl.data?.revenue || [])
    .filter((r) => Number(r.amount) > 0)
    .map((r) => ({ name: r.name_ar || r.name, value: Number(r.amount) }));
  const expSeries = (pnl.data?.expense || [])
    .filter((r) => Number(r.amount) > 0)
    .map((r) => ({ name: r.name_ar || r.name, value: Number(r.amount) }));

  function exportPnlCsv() {
    if (!pnl.data) return;
    const rows = [
      ["الإيرادات"],
      ...(pnl.data.revenue || []).map((r) => [r.name_ar || r.name, r.amount]),
      ["إجمالي الإيرادات", pnl.data.total_revenue],
      [],
      ["المصروفات"],
      ...(pnl.data.expense || []).map((r) => [r.name_ar || r.name, r.amount]),
      ["إجمالي المصروفات", pnl.data.total_expense],
      [],
      ["صافي الربح", pnl.data.net_profit],
    ];
    const csv = "﻿" + rows.map((r) => r.map((v) => `"${v ?? ""}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `pnl_${from}_${to}.csv`;
    a.click();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="التقارير المالية"
        description="قائمة الدخل، الميزانية العمومية، ملخص المبيعات، وأعلى المنتجات"
        action={
          <Button variant="outline" onClick={exportPnlCsv}>
            <Download className="h-4 w-4" /> تصدير P&L
          </Button>
        }
      />

      {/* Date range */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">من</label>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">إلى</label>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        </div>
        <div className="flex gap-1.5">
          {[
            { label: "اليوم", days: 0 },
            { label: "7 أيام", days: 6 },
            { label: "30 يوم", days: 29 },
            { label: "هذا الشهر", days: -1 },
          ].map((p) => (
            <button
              key={p.label}
              onClick={() => {
                const today = new Date();
                const t = today.toISOString().slice(0, 10);
                let f: string;
                if (p.days === -1) {
                  f = t.slice(0, 8) + "01";
                } else {
                  const d = new Date(today);
                  d.setDate(d.getDate() - p.days);
                  f = d.toISOString().slice(0, 10);
                }
                setFrom(f);
                setTo(t);
              }}
              className="px-3 py-1.5 text-xs border rounded-full hover:bg-muted transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI strip */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05 } } }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <Kpi
          icon={TrendingUp}
          label="إجمالي الإيرادات"
          value={formatMoney(pnl.data?.total_revenue || 0)}
          tone="success"
        />
        <Kpi
          icon={TrendingDown}
          label="إجمالي المصروفات"
          value={formatMoney(pnl.data?.total_expense || 0)}
          tone="danger"
        />
        <Kpi
          icon={Target}
          label="صافي الربح"
          value={formatMoney(pnl.data?.net_profit || 0)}
          tone={Number(pnl.data?.net_profit || 0) >= 0 ? "success" : "danger"}
        />
        <Kpi
          icon={ShoppingBag}
          label="متوسط الفاتورة"
          value={formatMoney(sales.data?.avg_ticket || 0)}
        />
      </motion.div>

      {/* P&L + BS */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* P&L with revenue-vs-expense pie */}
        <Card className="card-elevated">
          <CardHeader className="pb-2">
            <CardTitle>قائمة الدخل</CardTitle>
            <CardDescription>الإيرادات − المصروفات = صافي الربح</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <CategoryPie title="مصادر الإيراد" data={revSeries} palette={COLORS} />
              <CategoryPie title="أوجه الصرف" data={expSeries} palette={[
                "hsl(var(--chart-3))", "hsl(var(--chart-5))",
                "hsl(var(--chart-4))", "hsl(var(--chart-1))",
              ]} />
            </div>
            <div className="space-y-2 pt-2 text-sm border-t">
              <Section title="الإيرادات" rows={pnl.data?.revenue || []} />
              <Bottom k="إجمالي الإيرادات" v={pnl.data?.total_revenue || "0"} tone="success" />
              <Section title="المصروفات" rows={pnl.data?.expense || []} />
              <Bottom k="إجمالي المصروفات" v={pnl.data?.total_expense || "0"} tone="danger" />
              <div className="flex justify-between text-lg font-bold border-t pt-3 mt-2">
                <span>صافي الربح</span>
                <span
                  className={
                    Number(pnl.data?.net_profit || 0) >= 0
                      ? "text-emerald-600 dark:text-emerald-400 tabular"
                      : "text-red-600 dark:text-red-400 tabular"
                  }
                >
                  {formatMoney(pnl.data?.net_profit || 0)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Balance sheet */}
        <Card className="card-elevated">
          <CardHeader className="pb-2 flex flex-row items-center justify-between gap-2">
            <div>
              <CardTitle>الميزانية العمومية</CardTitle>
              <CardDescription>
                الأصول = الالتزامات + حقوق الملكية{" "}
                {bs.data?.is_balanced ? (
                  <span className="pill pill-success ms-1">متوازنة ✓</span>
                ) : (
                  <span className="pill pill-warn ms-1">قيد المعالجة</span>
                )}
              </CardDescription>
            </div>
            <Scale className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-4">
            {/* A=L+E visual bar */}
            <EqBar
              left={Number(bs.data?.total_assets || 0)}
              right={Number(bs.data?.total_liabilities || 0) + Number(bs.data?.total_equity || 0)}
            />
            <div className="space-y-2 text-sm">
              <Section title="الأصول" rows={bs.data?.assets || []} />
              <Bottom k="إجمالي الأصول" v={bs.data?.total_assets || "0"} />
              <Section title="الالتزامات" rows={bs.data?.liabilities || []} />
              <Bottom k="إجمالي الالتزامات" v={bs.data?.total_liabilities || "0"} />
              <Section title="حقوق الملكية" rows={bs.data?.equity || []} />
              <Bottom k="إجمالي حقوق الملكية" v={bs.data?.total_equity || "0"} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top products bar chart */}
      <Card className="card-elevated">
        <CardHeader className="pb-2">
          <CardTitle>أعلى المنتجات مبيعًا</CardTitle>
          <CardDescription>الإيراد vs الربح لكل منتج خلال الفترة المختارة</CardDescription>
        </CardHeader>
        <CardContent className="h-80">
          {(top.data?.length ?? 0) === 0 ? (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              لا توجد مبيعات في هذه الفترة بعد.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={(top.data || []).map((p) => ({
                  name: p.product_name,
                  الإيراد: Number(p.revenue),
                  الربح: Number(p.profit),
                }))}
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
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "hsl(var(--foreground))" }}
                  axisLine={false}
                  tickLine={false}
                  width={150}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v: any) => formatMoney(v)}
                />
                <Bar dataKey="الإيراد" fill="hsl(var(--chart-1))" radius={[0, 4, 4, 0]} />
                <Bar dataKey="الربح" fill="hsl(var(--chart-2))" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------- atoms ----------

function Kpi({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: any;
  label: string;
  value: string;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    danger: "bg-red-500/10 text-red-600 dark:text-red-400",
  }[tone];
  const valCls = {
    default: "",
    success: "text-emerald-600 dark:text-emerald-400",
    warn: "text-amber-600 dark:text-amber-400",
    danger: "text-red-600 dark:text-red-400",
  }[tone];
  return (
    <motion.div
      variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}
      transition={{ duration: 0.25 }}
    >
      <Card className="card-elevated h-full">
        <CardContent className="p-4 flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase text-muted-foreground tracking-wide">{label}</div>
            <div className={`text-xl font-bold tabular mt-0.5 ${valCls}`}>{value}</div>
          </div>
          <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${ring}`}>
            <Icon className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function CategoryPie({
  title,
  data,
  palette,
}: {
  title: string;
  data: { name: string; value: number }[];
  palette: string[];
}) {
  const total = data.reduce((a, b) => a + b.value, 0);
  if (data.length === 0) {
    return (
      <div className="text-center text-xs text-muted-foreground py-6">
        لا بيانات لـ "{title}"
      </div>
    );
  }
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">{title}</div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={28}
              outerRadius={50}
              paddingAngle={2}
              stroke="hsl(var(--background))"
              strokeWidth={2}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={palette[i % palette.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                fontSize: 11,
              }}
              formatter={(v: any) => formatMoney(v)}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="text-center text-xs text-muted-foreground tabular">
        إجمالي: <span className="font-semibold text-foreground">{formatMoney(total)}</span>
      </div>
    </div>
  );
}

function EqBar({ left, right }: { left: number; right: number }) {
  const max = Math.max(left, right, 1);
  return (
    <div className="space-y-1.5">
      <BarRow color="hsl(var(--chart-1))" label="الأصول" value={left} pct={(left / max) * 100} />
      <BarRow color="hsl(var(--chart-2))" label="الالتزامات + حقوق" value={right} pct={(right / max) * 100} />
    </div>
  );
}

function BarRow({ color, label, value, pct }: { color: string; label: string; value: number; pct: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular">{formatMoney(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-muted/40 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6 }}
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
        />
      </div>
    </div>
  );
}

function Section({
  title,
  rows,
}: {
  title: string;
  rows: AccountLine[];
}) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1 mt-2">
        {title}
      </div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted-foreground italic">لا توجد حركات</div>
      ) : (
        rows.map((r) => (
          <div key={r.code} className="flex justify-between py-0.5 text-xs">
            <span>{r.name_ar || r.name}</span>
            <span className="tabular">{formatMoney(r.amount)}</span>
          </div>
        ))
      )}
    </div>
  );
}

function Bottom({ k, v, tone = "default" }: { k: string; v: string; tone?: "default" | "success" | "danger" }) {
  const c =
    tone === "success" ? "text-emerald-600 dark:text-emerald-400" :
    tone === "danger" ? "text-red-600 dark:text-red-400" : "";
  return (
    <div className="flex justify-between font-semibold border-t pt-1.5">
      <span>{k}</span>
      <span className={`tabular ${c}`}>{formatMoney(v)}</span>
    </div>
  );
}

function abbrev(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return String(n);
}
