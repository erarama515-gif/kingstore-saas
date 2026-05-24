"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Smartphone,
  Search,
  ShieldCheck,
  ShieldAlert,
  Package,
  Phone,
  Calendar,
  ScanLine,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, TableSkeleton } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { formatMoney, formatDate } from "@/lib/utils";

type Device = {
  id: string;
  product_id: string;
  product_name: string | null;
  imei: string | null;
  serial_number: string | null;
  status: "in_stock" | "sold" | "under_repair" | "returned" | "damaged" | "archived";
  customer_id: string | null;
  sold_at: string | null;
  warranty_ends_at: string | null;
  is_under_warranty: boolean;
  purchase_cost: string;
};

const STATUSES: { value: Device["status"] | "all"; label: string; cls: string }[] = [
  { value: "all",          label: "الكل",          cls: "" },
  { value: "in_stock",     label: "في المخزن",     cls: "pill-info" },
  { value: "sold",         label: "مباعة",          cls: "pill-success" },
  { value: "under_repair", label: "قيد الصيانة",   cls: "pill-warn" },
  { value: "returned",     label: "مرتجعة",         cls: "pill-muted" },
  { value: "damaged",      label: "تالفة",          cls: "pill-danger" },
];

export default function DevicesPage() {
  const [q, setQ] = React.useState("");
  const [filter, setFilter] = React.useState<Device["status"] | "all">("all");
  const [scanOpen, setScanOpen] = React.useState(false);

  const list = useQuery<{ data: Device[] }>({
    queryKey: ["devices", q, filter],
    queryFn: async () =>
      (
        await api.get("/devices/", {
          params: {
            q: q || undefined,
            status: filter === "all" ? undefined : filter,
            per_page: 200,
          },
        })
      ).data,
  });

  const rows = list.data?.data || [];
  const k = React.useMemo(() => {
    const all = rows;
    return {
      total: all.length,
      inStock: all.filter((d) => d.status === "in_stock").length,
      sold: all.filter((d) => d.status === "sold").length,
      underRepair: all.filter((d) => d.status === "under_repair").length,
      warrantyActive: all.filter((d) => d.is_under_warranty).length,
    };
  }, [rows]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="سجل الأجهزة (IMEI)"
        description="كل جهاز موبايل تم استلامه أو بيعه — مع IMEI كامل وتاريخ الملكية والضمان"
        action={
          <Button onClick={() => setScanOpen(true)} variant="outline">
            <ScanLine className="h-4 w-4" /> بحث IMEI سريع
          </Button>
        }
      />

      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05 } } }}
        className="grid grid-cols-2 lg:grid-cols-5 gap-3"
      >
        <Kpi icon={Smartphone}    label="إجمالي الأجهزة" value={String(k.total)} />
        <Kpi icon={Package}       label="في المخزن"       value={String(k.inStock)} tone="info" />
        <Kpi icon={ShieldCheck}   label="مباعة"            value={String(k.sold)} tone="success" />
        <Kpi icon={ShieldAlert}   label="قيد الصيانة"     value={String(k.underRepair)} tone="warn" />
        <Kpi icon={ShieldCheck}   label="ضمان ساري"        value={String(k.warrantyActive)} tone="success" />
      </motion.div>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="relative max-w-md flex-1 min-w-[220px]">
          <Search className="h-4 w-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="ابحث بـ IMEI أو Serial..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pr-10"
            dir="ltr"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {STATUSES.map((s) => (
            <button
              key={s.value}
              onClick={() => setFilter(s.value)}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                filter === s.value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "hover:bg-muted"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {list.isLoading ? (
        <TableSkeleton rows={6} />
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <Card className="card-elevated">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-muted-foreground text-xs uppercase tracking-wider">
                  <tr>
                    <th className="text-right p-3">IMEI / Serial</th>
                    <th className="text-right p-3">المنتج</th>
                    <th className="text-right p-3">الحالة</th>
                    <th className="text-right p-3">تاريخ البيع</th>
                    <th className="text-right p-3">الضمان</th>
                    <th className="text-right p-3">التكلفة</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((d) => {
                    const statusCfg = STATUSES.find((s) => s.value === d.status);
                    return (
                      <tr key={d.id} className="border-t hover:bg-muted/30">
                        <td className="p-3">
                          <code className="font-mono text-xs bg-muted px-2 py-1 rounded" dir="ltr">
                            {d.imei || d.serial_number}
                          </code>
                        </td>
                        <td className="p-3 font-medium">{d.product_name || "—"}</td>
                        <td className="p-3">
                          <span className={`pill ${statusCfg?.cls || "pill-muted"}`}>
                            {statusCfg?.label || d.status}
                          </span>
                        </td>
                        <td className="p-3 tabular text-xs">
                          {d.sold_at ? formatDate(d.sold_at) : "—"}
                        </td>
                        <td className="p-3">
                          {d.warranty_ends_at ? (
                            <span
                              className={`pill ${
                                d.is_under_warranty ? "pill-success" : "pill-muted"
                              }`}
                            >
                              <ShieldCheck className="h-3 w-3" />
                              {d.is_under_warranty
                                ? `حتى ${formatDate(d.warranty_ends_at)}`
                                : `منتهي ${formatDate(d.warranty_ends_at)}`}
                            </span>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </td>
                        <td className="p-3 tabular">{formatMoney(d.purchase_cost)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {scanOpen && <ScanDialog onClose={() => setScanOpen(false)} />}
    </div>
  );
}

// ---- Scan dialog ----

function ScanDialog({ onClose }: { onClose: () => void }) {
  const [imei, setImei] = React.useState("");
  const [submitted, setSubmitted] = React.useState("");

  const lookup = useQuery({
    queryKey: ["device-lookup", submitted],
    queryFn: async () => (await api.get("/devices/lookup", { params: { q: submitted } })).data.data,
    enabled: submitted.length >= 5,
    retry: false,
  });

  return (
    <div
      className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-lg card-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold">
              <ScanLine className="h-5 w-5 text-primary" /> فحص جهاز بـ IMEI
            </div>
            <button onClick={onClose} className="p-1 hover:bg-muted rounded">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">امسح أو اكتب IMEI</label>
            <div className="flex gap-2">
              <Input
                value={imei}
                onChange={(e) => setImei(e.target.value)}
                placeholder="15-digit IMEI أو serial"
                dir="ltr"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && setSubmitted(imei.trim())}
              />
              <Button onClick={() => setSubmitted(imei.trim())}>فحص</Button>
            </div>
          </div>

          {submitted && lookup.isFetching && (
            <div className="text-sm text-muted-foreground">جاري البحث...</div>
          )}
          {submitted && lookup.isError && (
            <div className="text-sm text-red-600 dark:text-red-400">
              لا يوجد جهاز بهذا الرقم — تأكد من IMEI أو سجّل الجهاز عند الاستلام.
            </div>
          )}
          {lookup.data && <LookupResult result={lookup.data} />}
        </CardContent>
      </Card>
    </div>
  );
}

function LookupResult({ result }: { result: any }) {
  const d = result.device;
  return (
    <div className="space-y-3 border-t pt-3">
      <div>
        <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
          الجهاز
        </div>
        <div className="font-semibold">{d.product_name || "منتج غير معروف"}</div>
        <code className="font-mono text-xs text-muted-foreground" dir="ltr">
          {d.imei || d.serial_number}
        </code>
        <div className="mt-1 flex flex-wrap gap-1.5">
          <span className="pill pill-info">{d.status}</span>
          {d.is_under_warranty && (
            <span className="pill pill-success">
              <ShieldCheck className="h-3 w-3" /> ضمان ساري
            </span>
          )}
        </div>
      </div>
      {result.sale && (
        <div>
          <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
            بيع
          </div>
          <a
            href={`/sales/${result.sale.id}`}
            className="block hover:bg-muted/40 px-2 py-1.5 rounded text-sm"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs">{result.sale.sale_number}</span>
              <span className="tabular font-semibold">{formatMoney(result.sale.total)}</span>
            </div>
            <div className="text-xs text-muted-foreground tabular">
              {result.sale.customer_name || "عميل نقدي"} ·{" "}
              {formatDate(result.sale.sale_date)}
            </div>
          </a>
        </div>
      )}
      {result.recent_repairs?.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
            سجل الصيانة ({result.recent_repairs.length})
          </div>
          <div className="space-y-1">
            {result.recent_repairs.map((r: any) => (
              <div key={r.id} className="text-sm flex items-center justify-between border-t pt-1">
                <div>
                  <code className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                    {r.ticket_number}
                  </code>
                  <span className="ms-2 text-xs">{r.problem}</span>
                </div>
                <span className="text-xs tabular text-muted-foreground">
                  {formatDate(r.date_in)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: any;
  label: string;
  value: string;
  tone?: "default" | "success" | "warn" | "info";
}) {
  const ring = {
    default: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warn:    "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    info:    "bg-sky-500/10 text-sky-600 dark:text-sky-400",
  }[tone];
  return (
    <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
      <Card className="card-elevated">
        <CardContent className="p-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase text-muted-foreground tracking-wide">
              {label}
            </div>
            <div className="text-xl font-bold tabular mt-0.5">{value}</div>
          </div>
          <div className={`h-8 w-8 rounded-lg flex items-center justify-center ${ring}`}>
            <Icon className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function EmptyState() {
  return (
    <Card className="card-elevated">
      <CardContent className="py-16 flex flex-col items-center text-center gap-3">
        <div className="h-16 w-16 rounded-full bg-muted/50 flex items-center justify-center">
          <Smartphone className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="font-semibold">لا توجد أجهزة مسجلة بعد.</div>
        <div className="text-sm text-muted-foreground max-w-md">
          فعّل "تتبع بـ IMEI" على منتج هاتف، ثم سجّل الأجهزة عند الاستلام أو
          عند البيع.
        </div>
      </CardContent>
    </Card>
  );
}
