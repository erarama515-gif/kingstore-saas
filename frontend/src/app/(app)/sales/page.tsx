"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Receipt,
  CheckCircle2,
  Clock,
  XCircle,
  Download,
  TrendingUp,
  ShoppingBag,
} from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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

type Filter = "all" | "paid" | "credit" | "refunded";

export default function SalesPage() {
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = today.slice(0, 8) + "01";
  const [from, setFrom] = React.useState(monthStart);
  const [to, setTo] = React.useState(today);
  const [filter, setFilter] = React.useState<Filter>("all");

  const list = useQuery<{ data: Sale[] }>({
    queryKey: ["sales", from, to],
    queryFn: async () =>
      (await api.get("/sales/", { params: { from, to, per_page: 200 } })).data,
  });

  const rows = list.data?.data || [];
  const filtered = rows.filter((s) => {
    if (filter === "all") return true;
    if (filter === "refunded") return s.status === "refunded";
    if (filter === "paid") return s.is_paid && s.status !== "refunded";
    if (filter === "credit") return !s.is_paid && s.status !== "refunded";
    return true;
  });

  // Derived KPIs
  const k = React.useMemo(() => {
    const active = rows.filter((r) => r.status !== "refunded");
    const sum = active.reduce((a, b) => a + Number(b.total), 0);
    const paid = active.filter((r) => r.is_paid).length;
    const credit = active.filter((r) => !r.is_paid).length;
    const refunds = rows.filter((r) => r.status === "refunded").length;
    const avg = active.length > 0 ? sum / active.length : 0;
    return {
      count: active.length,
      sum,
      paid,
      credit,
      refunds,
      avg,
    };
  }, [rows]);

  function exportCsv() {
    const headers = ["#", "التاريخ", "العميل", "الإجمالي", "المدفوع", "المتبقي", "الحالة"];
    const lines = filtered.map((s) => [
      s.sale_number,
      s.sale_date,
      s.customer_name || "عميل نقدي",
      s.total,
      s.paid_amount,
      (Number(s.total) - Number(s.paid_amount)).toFixed(2),
      s.status === "refunded" ? "مستردة" : s.is_paid ? "مدفوعة" : "آجل",
    ]);
    const csv =
      "﻿" + // BOM for Excel to recognize UTF-8 + Arabic
      [headers, ...lines]
        .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
        .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sales_${from}_${to}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="المبيعات"
        description="سجل كل عمليات البيع — اضغط على أي فاتورة لرؤية التفاصيل وطباعتها"
        action={
          <Button onClick={exportCsv} variant="outline">
            <Download className="h-4 w-4" /> تصدير Excel
          </Button>
        }
      />

      {/* KPI strip */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <Kpi
          icon={Receipt}
          label="إجمالي الفواتير"
          value={k.count.toLocaleString("en-US")}
          hint={`${k.refunds} مستردة`}
        />
        <Kpi
          icon={TrendingUp}
          label="إجمالي المبيعات"
          value={formatMoney(k.sum)}
          tone="success"
        />
        <Kpi
          icon={ShoppingBag}
          label="متوسط الفاتورة"
          value={formatMoney(k.avg)}
        />
        <Kpi
          icon={Clock}
          label="آجل (تحت التحصيل)"
          value={k.credit.toLocaleString("en-US")}
          hint={`${k.paid} مدفوعة بالكامل`}
          tone={k.credit > 0 ? "warn" : "default"}
        />
      </motion.div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">من</label>
          <Input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">إلى</label>
          <Input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          <Chip active={filter === "all"} onClick={() => setFilter("all")}>
            الكل ({rows.length})
          </Chip>
          <Chip active={filter === "paid"} onClick={() => setFilter("paid")} tone="success">
            <CheckCircle2 className="h-3.5 w-3.5" /> مدفوعة ({k.paid})
          </Chip>
          <Chip active={filter === "credit"} onClick={() => setFilter("credit")} tone="warn">
            <Clock className="h-3.5 w-3.5" /> آجل ({k.credit})
          </Chip>
          <Chip active={filter === "refunded"} onClick={() => setFilter("refunded")} tone="danger">
            <XCircle className="h-3.5 w-3.5" /> مستردة ({k.refunds})
          </Chip>
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <EmptyState />
      ) : (
        <DataTable<Sale>
          rows={filtered}
          rowKey={(s) => s.id}
          rowHref={(s) => `/sales/${s.id}`}
          columns={[
            {
              header: "رقم الفاتورة",
              render: (s) => (
                <span className="font-mono text-xs bg-muted/60 px-2 py-1 rounded">
                  {s.sale_number}
                </span>
              ),
            },
            { header: "التاريخ", render: (s) => formatDate(s.sale_date) },
            {
              header: "العميل",
              render: (s) =>
                s.customer_name ? (
                  <span>{s.customer_name}</span>
                ) : (
                  <span className="text-muted-foreground italic">عميل نقدي</span>
                ),
            },
            {
              header: "الإجمالي",
              render: (s) => <span className="font-bold tabular">{formatMoney(s.total)}</span>,
            },
            {
              header: "المدفوع",
              render: (s) => <span className="tabular">{formatMoney(s.paid_amount)}</span>,
            },
            {
              header: "المتبقي",
              render: (s) => {
                const r = Number(s.total) - Number(s.paid_amount);
                if (s.status === "refunded") return <span className="text-muted-foreground">—</span>;
                return r > 0 ? (
                  <span className="tabular text-amber-600 font-medium">{formatMoney(r)}</span>
                ) : (
                  <span className="text-muted-foreground tabular">—</span>
                );
              },
            },
            {
              header: "الحالة",
              render: (s) =>
                s.status === "refunded" ? (
                  <span className="pill pill-danger">مستردة</span>
                ) : s.is_paid ? (
                  <span className="pill pill-success">مدفوعة</span>
                ) : (
                  <span className="pill pill-warn">آجل</span>
                ),
            },
          ]}
        />
      )}
    </div>
  );
}

// ---------- atoms ----------

function Kpi({
  icon: Icon,
  label,
  value,
  hint,
  tone = "default",
}: {
  icon: any;
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    danger: "bg-red-500/10 text-red-600 dark:text-red-400",
  }[tone];
  return (
    <motion.div
      variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}
      transition={{ duration: 0.25 }}
    >
      <Card className="card-elevated h-full">
        <CardContent className="p-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase text-muted-foreground tracking-wide">{label}</div>
            <div className="text-xl font-bold tabular mt-0.5 truncate">{value}</div>
            {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
          </div>
          <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${ring}`}>
            <Icon className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function Chip({
  active,
  onClick,
  tone = "default",
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: "default" | "success" | "warn" | "danger";
  children: React.ReactNode;
}) {
  const toneCls = {
    default: active ? "bg-primary text-primary-foreground" : "hover:bg-muted",
    success: active ? "bg-emerald-600 text-white" : "hover:bg-muted",
    warn: active ? "bg-amber-500 text-white" : "hover:bg-muted",
    danger: active ? "bg-red-600 text-white" : "hover:bg-muted",
  }[tone];
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all ${toneCls}`}
    >
      {children}
    </button>
  );
}

function EmptyState() {
  return (
    <Card className="card-elevated">
      <CardContent className="py-16 flex flex-col items-center text-center gap-3">
        <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center">
          <Receipt className="h-8 w-8 text-muted-foreground" />
        </div>
        <div>
          <div className="font-semibold">لا توجد فواتير في هذه الفترة</div>
          <div className="text-sm text-muted-foreground mt-1">
            ابدأ بإجراء عملية بيع من نقطة البيع.
          </div>
        </div>
        <Link href="/pos">
          <Button>
            <Receipt className="h-4 w-4" /> فتح نقطة البيع
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}
