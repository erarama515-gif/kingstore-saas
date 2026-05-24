"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { formatMoney, formatNumber } from "@/lib/utils";

type Level = {
  id: string | null;
  product_id: string;
  branch_id: string;
  qty_on_hand: number;
  avg_cost: string;
};

type InventorySummary = {
  total_items_on_hand: number;
  distinct_skus: number;
  low_stock_skus: number;
  out_of_stock_skus: number;
  total_inventory_value: string;
  by_category: Record<string, string>;
};

export default function InventoryPage() {
  const [branchId, setBranchId] = useState<string | null>(null);
  useEffect(() => {
    api.get("/auth/me").then((r) => setBranchId(r.data.data?.user?.default_branch_id || null));
  }, []);

  const summary = useQuery<InventorySummary>({
    queryKey: ["inv-summary", branchId],
    queryFn: async () =>
      (await api.get("/reports/inventory-summary", { params: { branch_id: branchId } }))
        .data.data,
    enabled: !!branchId,
  });

  const levels = useQuery<{ data: any[] }>({
    queryKey: ["inv-levels", branchId],
    queryFn: async () =>
      (
        await api.get("/inventory/stock-levels", {
          params: { branch_id: branchId, per_page: 100 },
        })
      ).data,
    enabled: !!branchId,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="المخزون" description="مستوى المخزون وتعديل الكميات" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="إجمالي القطع" value={formatNumber(summary.data?.total_items_on_hand || 0)} />
        <Stat
          label="قيمة المخزون"
          value={formatMoney(summary.data?.total_inventory_value || 0)}
          tone="success"
        />
        <Stat
          label="منخفض المخزون"
          value={formatNumber(summary.data?.low_stock_skus || 0)}
          tone="warn"
        />
        <Stat
          label="منتهي"
          value={formatNumber(summary.data?.out_of_stock_skus || 0)}
          tone="danger"
        />
      </div>

      <AdjustStockSection branchId={branchId} />

      <DataTable<any>
        rows={levels.data?.data || []}
        columns={[
          { header: "المنتج", render: (l) => l.product?.name || l.product_id?.slice(0, 8) },
          { header: "الكمية", render: (l) => <span className="font-bold">{l.qty_on_hand}</span> },
          { header: "متوسط التكلفة", render: (l) => formatMoney(l.avg_cost) },
          {
            header: "قيمة المخزون",
            render: (l) =>
              formatMoney(Number(l.qty_on_hand) * Number(l.avg_cost || 0)),
          },
        ]}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "success" | "warn" | "danger";
}) {
  const tones = {
    default: "",
    success: "text-emerald-600",
    warn: "text-amber-600",
    danger: "text-red-600",
  };
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className={`text-2xl font-bold mt-1 ${tones[tone]}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function AdjustStockSection({ branchId }: { branchId: string | null }) {
  const qc = useQueryClient();
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("1");
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [reason, setReason] = useState("");

  const m = useMutation({
    mutationFn: async () =>
      (
        await api.post("/inventory/adjust", {
          product_id: productId,
          branch_id: branchId,
          qty: Number(qty),
          direction,
          reason,
        })
      ).data,
    onSuccess: () => {
      toast.success("تم تعديل المخزون");
      setProductId(""); setQty("1"); setReason("");
      qc.invalidateQueries({ queryKey: ["inv-levels"] });
      qc.invalidateQueries({ queryKey: ["inv-summary"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.error?.message || "فشل"),
  });

  return (
    <Card>
      <CardContent className="p-5">
        <div className="font-semibold mb-3">تعديل مخزون يدوي</div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
          <Input
            placeholder="معرف المنتج (UUID)"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          />
          <Input
            type="number"
            min={1}
            placeholder="الكمية"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as "in" | "out")}
            className="h-10 border border-input rounded-md bg-background px-3 text-sm"
          >
            <option value="in">دخول</option>
            <option value="out">خروج</option>
          </select>
          <Input
            placeholder="السبب (تالف، عَدّ مخزون...)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="sm:col-span-1"
          />
          <Button
            onClick={() => m.mutate()}
            disabled={m.isPending || !productId || !reason || !branchId}
          >
            تعديل
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
