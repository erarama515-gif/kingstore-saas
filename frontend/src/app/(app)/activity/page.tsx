"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  ShoppingCart,
  Truck,
  Wallet,
  Banknote,
  RotateCcw,
  Wrench,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader, TableSkeleton } from "@/components/ui/data-table";
import { formatMoney, formatDate } from "@/lib/utils";

type ActivityEvent = {
  id: string;
  entry_date: string;
  posted_at: string | null;
  source: string;
  source_ref: string | null;
  reference: string | null;
  description: string | null;
  branch_id: string | null;
  amount: string;
};

const FILTERS: { value: string | null; label: string }[] = [
  { value: null,        label: "الكل" },
  { value: "sale",      label: "مبيعات" },
  { value: "purchase",  label: "مشتريات" },
  { value: "expense",   label: "مصروفات" },
  { value: "capital",   label: "رأس مال" },
  { value: "repair",    label: "صيانة" },
  { value: "inventory", label: "مخزون" },
  { value: "reversal",  label: "ارتجاع" },
];

const META: Record<string, { icon: any; label: string; tone: string }> = {
  sale:      { icon: ShoppingCart, label: "فاتورة بيع",     tone: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  purchase:  { icon: Truck,        label: "فاتورة شراء",     tone: "bg-sky-500/10 text-sky-600 dark:text-sky-400" },
  expense:   { icon: Wallet,       label: "مصروف",           tone: "bg-red-500/10 text-red-600 dark:text-red-400" },
  capital:   { icon: Banknote,     label: "حركة رأس مال",   tone: "bg-purple-500/10 text-purple-600 dark:text-purple-400" },
  reversal:  { icon: RotateCcw,    label: "قيد عكسي",       tone: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  repair:    { icon: Wrench,       label: "صيانة",           tone: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
  inventory: { icon: FileText,     label: "تعديل مخزون",     tone: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400" },
  manual:    { icon: FileText,     label: "قيد يدوي",        tone: "bg-muted text-muted-foreground" },
};

function metaFor(src: string) {
  return META[src] || META.manual;
}

function relTime(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60_000);
  if (m < 1) return "الآن";
  if (m < 60) return `منذ ${m} دقيقة`;
  const h = Math.floor(m / 60);
  if (h < 24) return `منذ ${h} ساعة`;
  const d = Math.floor(h / 24);
  if (d < 30) return `منذ ${d} يوم`;
  return formatDate(iso);
}

function sourceLink(ev: ActivityEvent): string | null {
  if (!ev.source_ref) return null;
  // source_ref like "sale:<uuid>" — extract uuid for deep link
  const [kind, ref] = ev.source_ref.split(":");
  if (kind === "sale" && ref) return `/sales/${ref}`;
  return null;
}

export default function ActivityPage() {
  const [filter, setFilter] = React.useState<string | null>(null);

  const { data, isLoading } = useQuery<{ data: ActivityEvent[] }>({
    queryKey: ["activity-feed", filter],
    queryFn: async () =>
      (
        await api.get("/accounting/activity", {
          params: { source: filter || undefined, limit: 100 },
        })
      ).data,
    refetchInterval: 30_000,
  });

  const events = data?.data || [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="سجل النشاط"
        description="آخر العمليات في النظام — مبيعات، مصاريف، صيانة، حركات مخزون"
      />

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
              filter === f.value
                ? "bg-primary text-primary-foreground"
                : "hover:bg-muted"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <TableSkeleton rows={8} />
      ) : events.length === 0 ? (
        <Card className="card-elevated">
          <CardContent className="py-16 flex flex-col items-center text-center gap-2">
            <Activity className="h-12 w-12 text-muted-foreground/40" />
            <div className="font-semibold">لا يوجد نشاط مسجل بعد لهذا التصنيف.</div>
            <div className="text-sm text-muted-foreground">
              ابدأ بإجراء عملية بيع أو مصروف لتظهر هنا.
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="card-elevated">
          <CardContent className="p-0">
            <motion.ul
              initial="hidden"
              animate="show"
              variants={{ hidden: {}, show: { transition: { staggerChildren: 0.02 } } }}
              className="divide-y"
            >
              {events.map((ev) => {
                const m = metaFor(ev.source);
                const Icon = m.icon;
                const link = sourceLink(ev);
                const Row = (
                  <li className={link ? "hover:bg-muted/40 cursor-pointer transition-colors" : ""}>
                    <motion.div
                      variants={{ hidden: { opacity: 0, x: 6 }, show: { opacity: 1, x: 0 } }}
                      className="px-4 py-3 flex items-center gap-3"
                    >
                      <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${m.tone}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm">{m.label}</span>
                          {ev.reference && (
                            <code className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
                              {ev.reference}
                            </code>
                          )}
                          <span className="text-xs text-muted-foreground">
                            {relTime(ev.posted_at)}
                          </span>
                        </div>
                        {ev.description && (
                          <div className="text-xs text-muted-foreground truncate mt-0.5">
                            {ev.description}
                          </div>
                        )}
                      </div>
                      <div className="text-left shrink-0">
                        <div className="text-sm font-bold tabular">
                          {formatMoney(ev.amount)}
                        </div>
                        <div className="text-[10px] text-muted-foreground tabular">
                          {formatDate(ev.entry_date)}
                        </div>
                      </div>
                    </motion.div>
                  </li>
                );
                return link ? (
                  <Link key={ev.id} href={link} className="block">
                    {Row}
                  </Link>
                ) : (
                  <React.Fragment key={ev.id}>{Row}</React.Fragment>
                );
              })}
            </motion.ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
