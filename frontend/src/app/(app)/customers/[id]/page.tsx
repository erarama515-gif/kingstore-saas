"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowRight,
  User,
  Phone,
  Mail,
  MapPin,
  ShoppingBag,
  HandCoins,
  CalendarDays,
  TrendingUp,
  Receipt,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatMoney, formatDate } from "@/lib/utils";

type Customer = {
  id: string;
  name: string;
  name_ar: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  created_at: string;
  last_txn_at: string | null;
  total_spent_cached: string;
  debt_cached: string;
  visits_count: number;
};

type StatementRow = {
  date: string;
  entry_id: string;
  source: string;
  source_ref: string | null;
  description: string | null;
  debit: string;
  credit: string;
  balance: string;
};

type Sale = {
  id: string;
  sale_number: string;
  sale_date: string;
  total: string;
  paid_amount: string;
  is_paid: boolean;
  status: string;
};

type Repair = {
  id: string;
  ticket_number: string;
  device_model: string;
  problem: string;
  status: string;
  actual_cost: string | null;
  estimated_cost: string;
  created_at: string;
};

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const customer = useQuery<Customer>({
    queryKey: ["customer", id],
    queryFn: async () => (await api.get(`/customers/${id}`)).data.data,
  });

  const sales = useQuery<{ data: Sale[] }>({
    queryKey: ["customer-sales", id],
    queryFn: async () =>
      (await api.get("/sales/", { params: { customer_id: id, per_page: 50 } })).data,
  });

  const repairs = useQuery<{ data: Repair[] }>({
    queryKey: ["customer-repairs", id],
    queryFn: async () =>
      (await api.get("/repairs/", { params: { customer_id: id, per_page: 20 } })).data,
  });

  const statement = useQuery<{ data: StatementRow[] }>({
    queryKey: ["customer-statement", id],
    queryFn: async () => (await api.get(`/customers/${id}/statement`)).data,
  });

  if (customer.isLoading || !customer.data) return <DetailSkeleton />;
  const c = customer.data;
  const salesList = sales.data?.data || [];
  const repairsList = repairs.data?.data || [];
  const stmt = statement.data?.data || [];

  // Derived KPIs
  const lifetimeSpent = Number(c.total_spent_cached || 0);
  const outstandingDebt = Number(c.debt_cached || 0);
  const avgTicket = salesList.length > 0
    ? salesList.reduce((a, s) => a + Number(s.total), 0) / salesList.length
    : 0;
  const lastSaleDays = c.last_txn_at
    ? Math.floor((Date.now() - new Date(c.last_txn_at).getTime()) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowRight className="h-4 w-4" /> رجوع
        </Button>
      </div>

      {/* Hero card */}
      <Card className="card-elevated overflow-hidden">
        <div className="bg-gradient-to-br from-primary/10 via-background to-chart-5/10 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-gradient-to-br from-primary to-chart-5 text-primary-foreground flex items-center justify-center text-2xl font-bold shadow-md">
                {c.name.charAt(0)}
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight">{c.name}</h1>
                <div className="flex flex-wrap gap-3 mt-1 text-sm text-muted-foreground">
                  {c.phone && (
                    <span className="flex items-center gap-1 tabular" dir="ltr">
                      <Phone className="h-3.5 w-3.5" /> {c.phone}
                    </span>
                  )}
                  {c.email && (
                    <span className="flex items-center gap-1" dir="ltr">
                      <Mail className="h-3.5 w-3.5" /> {c.email}
                    </span>
                  )}
                  {c.address && (
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" /> {c.address}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <CalendarDays className="h-3.5 w-3.5" /> عميل منذ{" "}
                    <span className="tabular">{formatDate(c.created_at)}</span>
                  </span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              {outstandingDebt > 0 && (
                <span className="pill pill-warn">
                  مديونية: {formatMoney(outstandingDebt)}
                </span>
              )}
              {lifetimeSpent > 10000 && (
                <span className="pill pill-success">عميل VIP</span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <Kpi
          icon={TrendingUp}
          label="إجمالي الإنفاق"
          value={formatMoney(lifetimeSpent)}
          tone="success"
          hint="Customer LTV"
        />
        <Kpi
          icon={HandCoins}
          label="مديونية حالية"
          value={formatMoney(outstandingDebt)}
          tone={outstandingDebt > 0 ? "warn" : "default"}
          hint={outstandingDebt > 0 ? "تحت التحصيل" : "لا مديونية"}
        />
        <Kpi
          icon={Receipt}
          label="عدد الفواتير"
          value={String(c.visits_count || salesList.length)}
          hint={`متوسط ${formatMoney(avgTicket)}`}
        />
        <Kpi
          icon={CalendarDays}
          label="آخر زيارة"
          value={lastSaleDays !== null ? `منذ ${lastSaleDays} يوم` : "لم يزر بعد"}
          tone={lastSaleDays !== null && lastSaleDays > 60 ? "warn" : "default"}
        />
      </motion.div>

      {/* Tabs-as-grid layout: invoices | statement | repairs */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Recent invoices */}
        <Card className="card-elevated xl:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-4 w-4" /> آخر الفواتير
            </CardTitle>
            <CardDescription>اضغط على أي فاتورة لرؤية التفاصيل</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {salesList.length === 0 ? (
              <Empty label="لا توجد فواتير لهذا العميل بعد" />
            ) : (
              <div className="divide-y max-h-96 overflow-y-auto">
                {salesList.slice(0, 20).map((s) => {
                  const remaining = Number(s.total) - Number(s.paid_amount);
                  return (
                    <Link
                      key={s.id}
                      href={`/sales/${s.id}`}
                      className="flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <code className="text-xs bg-muted px-2 py-1 rounded shrink-0">
                          {s.sale_number}
                        </code>
                        <div className="min-w-0">
                          <div className="text-xs text-muted-foreground tabular">
                            {formatDate(s.sale_date)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-left">
                          <div className="font-bold tabular">{formatMoney(s.total)}</div>
                          {remaining > 0 && s.status !== "refunded" && (
                            <div className="text-xs tabular text-amber-600">
                              متبقي {formatMoney(remaining)}
                            </div>
                          )}
                        </div>
                        {s.status === "refunded" ? (
                          <span className="pill pill-danger">مستردة</span>
                        ) : s.is_paid ? (
                          <span className="pill pill-success">مدفوعة</span>
                        ) : (
                          <span className="pill pill-warn">آجل</span>
                        )}
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Statement / payment behavior */}
        <Card className="card-elevated">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <HandCoins className="h-4 w-4" /> كشف الحساب
            </CardTitle>
            <CardDescription>الذمم المدينة — قيود AR للعميل</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {stmt.length === 0 ? (
              <Empty label="لا توجد حركات AR" />
            ) : (
              <div className="divide-y max-h-96 overflow-y-auto text-sm">
                {stmt.slice(0, 30).map((r, i) => (
                  <div key={i} className="px-4 py-2.5 flex items-center justify-between">
                    <div className="min-w-0">
                      <div className="text-xs text-muted-foreground tabular">
                        {formatDate(r.date)} · {r.source}
                      </div>
                      <div className="text-xs truncate">{r.description || "—"}</div>
                    </div>
                    <div className="text-left tabular shrink-0">
                      {Number(r.debit) > 0 && (
                        <div className="text-amber-600 font-medium">
                          +{formatMoney(r.debit)}
                        </div>
                      )}
                      {Number(r.credit) > 0 && (
                        <div className="text-emerald-600 font-medium">
                          −{formatMoney(r.credit)}
                        </div>
                      )}
                      <div className="text-[10px] text-muted-foreground">
                        رصيد {formatMoney(r.balance)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Repairs history */}
      {repairsList.length > 0 && (
        <Card className="card-elevated">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Wrench className="h-4 w-4" /> سجل الصيانة
            </CardTitle>
            <CardDescription>
              {repairsList.length} تذكرة صيانة مرتبطة بهذا العميل
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y">
              {repairsList.map((r) => (
                <div
                  key={r.id}
                  className="px-4 py-3 flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <div className="font-medium">{r.device_model}</div>
                    <div className="text-xs text-muted-foreground truncate max-w-md">
                      {r.problem}
                    </div>
                    <div className="text-[11px] text-muted-foreground tabular mt-0.5">
                      {r.ticket_number} · {formatDate(r.created_at)}
                    </div>
                  </div>
                  <div className="text-left shrink-0 flex items-center gap-3">
                    <span className="tabular font-medium">
                      {formatMoney(r.actual_cost || r.estimated_cost)}
                    </span>
                    <RepairStatusPill status={r.status} />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {c.notes && (
        <Card className="card-elevated">
          <CardHeader>
            <CardTitle className="text-sm">ملاحظات</CardTitle>
          </CardHeader>
          <CardContent className="text-sm whitespace-pre-wrap">{c.notes}</CardContent>
        </Card>
      )}
    </div>
  );
}

// ---- atoms ----

function Kpi({
  icon: Icon, label, value, hint, tone = "default",
}: {
  icon: any; label: string; value: string; hint?: string;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    danger: "bg-red-500/10 text-red-600 dark:text-red-400",
  }[tone];
  return (
    <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
      <Card className="card-elevated">
        <CardContent className="p-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase text-muted-foreground tracking-wide">
              {label}
            </div>
            <div className="text-lg font-bold tabular mt-0.5 truncate">{value}</div>
            {hint && <div className="text-xs text-muted-foreground truncate">{hint}</div>}
          </div>
          <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${ring}`}>
            <Icon className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function RepairStatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    received: "pill-info",
    in_progress: "pill-warn",
    done: "pill-success",
    delivered: "pill-muted",
    canceled: "pill-danger",
  };
  const labels: Record<string, string> = {
    received: "مستلم",
    in_progress: "قيد الإصلاح",
    done: "جاهز للتسليم",
    delivered: "مسلّم",
    canceled: "ملغي",
  };
  return (
    <span className={`pill ${map[status] || "pill-muted"}`}>
      {labels[status] || status}
    </span>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="py-10 text-center text-sm text-muted-foreground">{label}</div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-10 w-32 bg-muted rounded animate-pulse" />
      <div className="h-32 bg-muted rounded-xl animate-pulse" />
      <div className="grid grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 bg-muted rounded-xl animate-pulse" />
        ))}
      </div>
      <div className="h-64 bg-muted rounded-xl animate-pulse" />
    </div>
  );
}
