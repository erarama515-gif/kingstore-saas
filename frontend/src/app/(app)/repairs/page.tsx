"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X, ChevronLeft, Check, Truck } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataTable, PageHeader } from "@/components/ui/data-table";
import { formatMoney, formatDate } from "@/lib/utils";

type Repair = {
  id: string;
  ticket_number: string;
  customer_name: string;
  customer_phone: string | null;
  device_model: string;
  problem: string;
  estimated_cost: string;
  actual_cost: string;
  status: "received" | "in_progress" | "done" | "delivered" | "canceled";
  date_in: string;
};

const STATUS_LABELS = {
  received: { label: "استلام", color: "bg-blue-100 text-blue-800" },
  in_progress: { label: "جاري", color: "bg-amber-100 text-amber-800" },
  done: { label: "جاهز", color: "bg-emerald-100 text-emerald-800" },
  delivered: { label: "تم التسليم", color: "bg-gray-100 text-gray-700" },
  canceled: { label: "ملغاة", color: "bg-red-100 text-red-800" },
};

export default function RepairsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [delivering, setDelivering] = useState<Repair | null>(null);

  const list = useQuery<{ data: Repair[] }>({
    queryKey: ["repairs"],
    queryFn: async () => (await api.get("/repairs/", { params: { per_page: 100 } })).data,
  });

  const advance = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) =>
      (await api.patch(`/repairs/${id}/status`, { status })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repairs"] }),
  });

  return (
    <div>
      <PageHeader
        title="الصيانة"
        description="إدارة تذاكر صيانة الأجهزة"
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> تذكرة جديدة
          </Button>
        }
      />

      <DataTable<Repair>
        rows={list.data?.data || []}
        columns={[
          { header: "رقم", render: (r) => <code>{r.ticket_number}</code> },
          { header: "العميل", render: (r) => r.customer_name },
          { header: "الجهاز", render: (r) => r.device_model },
          { header: "العطل", render: (r) => <span className="truncate">{r.problem}</span> },
          { header: "تاريخ الاستلام", render: (r) => formatDate(r.date_in) },
          {
            header: "السعر",
            render: (r) =>
              formatMoney(
                Number(r.actual_cost) > 0 ? r.actual_cost : r.estimated_cost,
              ),
          },
          {
            header: "الحالة",
            render: (r) => {
              const s = STATUS_LABELS[r.status];
              return (
                <span className={`px-2 py-1 text-xs rounded ${s.color}`}>
                  {s.label}
                </span>
              );
            },
          },
          {
            header: "تحكم",
            render: (r) => (
              <div className="flex gap-1">
                {r.status === "received" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => advance.mutate({ id: r.id, status: "in_progress" })}
                  >
                    <ChevronLeft className="h-3 w-3" /> بدء
                  </Button>
                )}
                {r.status === "in_progress" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => advance.mutate({ id: r.id, status: "done" })}
                  >
                    <Check className="h-3 w-3" /> جاهز
                  </Button>
                )}
                {(r.status === "done" || r.status === "received") && (
                  <Button size="sm" variant="success" onClick={() => setDelivering(r)}>
                    <Truck className="h-3 w-3" /> تسليم
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />

      {open && (
        <RepairDialog
          onClose={() => setOpen(false)}
          onSaved={() => {
            setOpen(false);
            qc.invalidateQueries({ queryKey: ["repairs"] });
          }}
        />
      )}
      {delivering && (
        <DeliverDialog
          ticket={delivering}
          onClose={() => setDelivering(null)}
          onDone={() => {
            setDelivering(null);
            qc.invalidateQueries({ queryKey: ["repairs"] });
            qc.invalidateQueries({ queryKey: ["dashboard"] });
          }}
        />
      )}
    </div>
  );
}

function RepairDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [branchId, setBranchId] = useState<string | null>(null);
  const [form, setForm] = useState({
    customer_name: "",
    customer_phone: "",
    device_model: "",
    problem: "",
    estimated_cost: "0",
    notes: "",
  });
  useState(() => {
    api.get("/auth/me").then((r) => setBranchId(r.data.data?.user?.default_branch_id));
    return null;
  });
  const m = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("لا يوجد فرع نشط");
      return (await api.post("/repairs/", { ...form, branch_id: branchId })).data.data;
    },
    onSuccess: () => {
      toast.success("تم استلام التذكرة");
      onSaved();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل الحفظ"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg w-full max-w-lg p-6 shadow-2xl space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">تذكرة صيانة جديدة</h2>
          <button onClick={onClose} className="hover:bg-muted p-1 rounded">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <label className="text-sm">اسم العميل</label>
            <Input
              value={form.customer_name}
              onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm">الهاتف</label>
            <Input
              value={form.customer_phone}
              onChange={(e) => setForm({ ...form, customer_phone: e.target.value })}
            />
          </div>
          <div className="space-y-2 col-span-2">
            <label className="text-sm">الجهاز</label>
            <Input
              value={form.device_model}
              onChange={(e) => setForm({ ...form, device_model: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2 col-span-2">
            <label className="text-sm">العطل</label>
            <Input
              value={form.problem}
              onChange={(e) => setForm({ ...form, problem: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm">تكلفة تقديرية</label>
            <Input
              type="number"
              step="0.01"
              value={form.estimated_cost}
              onChange={(e) => setForm({ ...form, estimated_cost: e.target.value })}
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button onClick={() => m.mutate()} disabled={m.isPending}>
            حفظ
          </Button>
        </div>
      </div>
    </div>
  );
}

function DeliverDialog({
  ticket,
  onClose,
  onDone,
}: {
  ticket: Repair;
  onClose: () => void;
  onDone: () => void;
}) {
  const [cost, setCost] = useState(
    String(Number(ticket.actual_cost) || Number(ticket.estimated_cost) || 0),
  );
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "bank">("cash");

  const m = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/repairs/${ticket.id}/deliver`, {
          actual_cost: cost,
          is_paid: true,
          payment_method: paymentMethod,
        })
      ).data,
    onSuccess: () => {
      toast.success("تم تسليم التذكرة وتسجيل الإيرادات");
      onDone();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل التسليم"),
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg w-full max-w-sm p-6 shadow-2xl space-y-3">
        <h2 className="text-lg font-bold">تسليم {ticket.ticket_number}</h2>
        <div className="space-y-2">
          <label className="text-sm">التكلفة الفعلية</label>
          <Input
            type="number"
            step="0.01"
            min="0"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm">طريقة الدفع</label>
          <select
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value as "cash" | "bank")}
            className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
          >
            <option value="cash">كاش</option>
            <option value="bank">بنك</option>
          </select>
        </div>
        <div className="flex gap-2 justify-end pt-2">
          <Button variant="outline" onClick={onClose}>إلغاء</Button>
          <Button variant="success" onClick={() => m.mutate()} disabled={m.isPending}>
            تسليم وتسجيل
          </Button>
        </div>
      </div>
    </div>
  );
}
