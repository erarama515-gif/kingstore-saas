"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Wallet, Boxes, TrendingUp, Plus, Minus } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { formatMoney, formatDate } from "@/lib/utils";

type Summary = {
  liquid_cash: string;
  inventory_value: string;
  total_working_capital: string;
  owner_capital: string;
  owner_drawings: string;
  net_owner_equity: string;
};

type Movement = {
  id: string;
  entry_date: string;
  reference: string | null;
  description: string | null;
  lines: { account_id: string; debit: string; credit: string; description: string | null }[];
};

export default function CapitalPage() {
  const qc = useQueryClient();
  const summary = useQuery<Summary>({
    queryKey: ["capital-summary"],
    queryFn: async () => (await api.get("/capital/summary")).data.data,
  });

  const movements = useQuery<{ data: Movement[] }>({
    queryKey: ["capital-movements"],
    queryFn: async () => (await api.get("/capital/movements", { params: { per_page: 50 } })).data,
  });

  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");

  const mInject = useMutation({
    mutationFn: async () =>
      (await api.post("/capital/inject", { amount, description })).data,
    onSuccess: () => {
      toast.success("تم ضخ السيولة");
      setAmount(""); setDescription("");
      qc.invalidateQueries({ queryKey: ["capital-summary"] });
      qc.invalidateQueries({ queryKey: ["capital-movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.error?.message || "فشل"),
  });

  const mWithdraw = useMutation({
    mutationFn: async () =>
      (await api.post("/capital/withdraw", { amount, description })).data,
    onSuccess: () => {
      toast.success("تم السحب");
      setAmount(""); setDescription("");
      qc.invalidateQueries({ queryKey: ["capital-summary"] });
      qc.invalidateQueries({ queryKey: ["capital-movements"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.error?.message || "فشل"),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="رأس المال" description="إدارة السيولة وحركات المالك" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Kpi
          title="السيولة النقدية"
          value={formatMoney(summary.data?.liquid_cash || 0)}
          icon={Wallet}
          tone="success"
        />
        <Kpi
          title="قيمة المخزون"
          value={formatMoney(summary.data?.inventory_value || 0)}
          icon={Boxes}
        />
        <Kpi
          title="إجمالي رأس المال"
          value={formatMoney(summary.data?.total_working_capital || 0)}
          icon={TrendingUp}
          tone="success"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>حركة جديدة</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1 space-y-2">
              <label className="text-sm">البيان</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="مثل: ضخ سيولة من المالك"
              />
            </div>
            <div className="w-40 space-y-2">
              <label className="text-sm">المبلغ</label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <Button
              variant="success"
              onClick={() => mInject.mutate()}
              disabled={mInject.isPending || !amount || !description}
            >
              <Plus className="h-4 w-4" /> ضخ سيولة
            </Button>
            <Button
              variant="destructive"
              onClick={() => mWithdraw.mutate()}
              disabled={mWithdraw.isPending || !amount || !description}
            >
              <Minus className="h-4 w-4" /> سحب استثماري
            </Button>
          </div>
        </CardContent>
      </Card>

      <DataTable<Movement>
        rows={movements.data?.data || []}
        columns={[
          { header: "التاريخ", render: (m) => formatDate(m.entry_date) },
          { header: "البيان", render: (m) => m.description || "—" },
          {
            header: "النوع",
            render: (m) =>
              m.reference === "cap_in" ? (
                <span className="text-emerald-600">إيداع</span>
              ) : (
                <span className="text-red-600">سحب</span>
              ),
          },
          {
            header: "المبلغ",
            render: (m) => {
              const amt = m.lines.reduce(
                (s, l) => s + Math.max(Number(l.debit), Number(l.credit)),
                0,
              ) / 2 || 0;
              // Each entry has 2 lines that sum to amt twice — pick max of either side
              const real = Math.max(
                ...m.lines.map((l) => Math.max(Number(l.debit), Number(l.credit))),
              );
              return <span className="font-bold">{formatMoney(real)}</span>;
            },
          },
        ]}
      />
    </div>
  );
}

function Kpi({
  title,
  value,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "success";
}) {
  return (
    <Card>
      <CardContent className="p-5 flex items-start justify-between">
        <div>
          <div className="text-sm text-muted-foreground">{title}</div>
          <div
            className={`text-2xl font-bold mt-1 ${tone === "success" ? "text-emerald-600" : ""}`}
          >
            {value}
          </div>
        </div>
        <Icon className="h-8 w-8 text-muted-foreground/40" />
      </CardContent>
    </Card>
  );
}
