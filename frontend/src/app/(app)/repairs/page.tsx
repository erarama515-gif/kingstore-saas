"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import {
  DndContext,
  PointerSensor,
  DragOverlay,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  closestCorners,
} from "@dnd-kit/core";
import type { DragEndEvent, DragStartEvent } from "@dnd-kit/core";
import {
  Plus,
  X,
  Check,
  Truck,
  Wrench,
  Clock,
  CheckCircle2,
  PackageCheck,
  Phone,
  Smartphone,
  AlertTriangle,
  LayoutGrid,
  List as ListIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/data-table";
import { formatMoney, formatDate } from "@/lib/utils";

type Status = "received" | "in_progress" | "done" | "delivered" | "canceled";

type Repair = {
  id: string;
  ticket_number: string;
  customer_name: string;
  customer_phone: string | null;
  device_model: string;
  imei: string | null;
  problem: string;
  estimated_cost: string;
  actual_cost: string;
  status: Status;
  date_in: string;
  date_delivered: string | null;
};

const COLUMNS: { id: Status; label: string; icon: any; tone: string }[] = [
  { id: "received",    label: "مستلمة",          icon: Clock,         tone: "border-sky-500/40 bg-sky-500/5" },
  { id: "in_progress", label: "قيد الإصلاح",     icon: Wrench,        tone: "border-amber-500/40 bg-amber-500/5" },
  { id: "done",        label: "جاهزة للتسليم",   icon: CheckCircle2,  tone: "border-emerald-500/40 bg-emerald-500/5" },
  { id: "delivered",   label: "مسلّمة",          icon: PackageCheck,  tone: "border-muted-foreground/30 bg-muted/30" },
];

// SLA thresholds (days since intake) per status before we flag urgency
const SLA_DAYS: Record<Status, number> = {
  received: 1,
  in_progress: 3,
  done: 1,
  delivered: 0,
  canceled: 0,
};

function ageDays(d: string): number {
  return Math.floor((Date.now() - new Date(d).getTime()) / (1000 * 60 * 60 * 24));
}

function priorityFor(r: Repair): "ok" | "warn" | "urgent" {
  if (r.status === "delivered" || r.status === "canceled") return "ok";
  const days = ageDays(r.date_in);
  const sla = SLA_DAYS[r.status];
  if (days > sla * 2) return "urgent";
  if (days > sla) return "warn";
  return "ok";
}

export default function RepairsPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [delivering, setDelivering] = React.useState<Repair | null>(null);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [view, setView] = React.useState<"kanban" | "list">("kanban");

  const list = useQuery<{ data: Repair[] }>({
    queryKey: ["repairs"],
    queryFn: async () => (await api.get("/repairs/", { params: { per_page: 200 } })).data,
    refetchInterval: 30_000,
  });

  const advance = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: Status }) =>
      (await api.patch(`/repairs/${id}/status`, { status })).data.data,
    // Optimistic update — UI moves instantly, rollback on error
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ["repairs"] });
      const prev = qc.getQueryData<{ data: Repair[] }>(["repairs"]);
      qc.setQueryData<{ data: Repair[] }>(["repairs"], (old) => ({
        ...(old || { data: [] }),
        data: (old?.data || []).map((r) => (r.id === id ? { ...r, status } : r)),
      }));
      return { prev };
    },
    onError: (err: any, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(["repairs"], ctx.prev);
      toast.error(err?.response?.data?.error?.message || "فشل تحديث الحالة");
    },
    onSuccess: () => {
      toast.success("تم تحديث حالة التذكرة");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["repairs"] }),
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  const repairs = list.data?.data || [];
  const byStatus: Record<Status, Repair[]> = {
    received: [], in_progress: [], done: [], delivered: [], canceled: [],
  };
  for (const r of repairs) byStatus[r.status]?.push(r);

  const activeRepair = repairs.find((r) => r.id === activeId);

  function onDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }

  function onDragEnd(e: DragEndEvent) {
    setActiveId(null);
    const ticketId = String(e.active.id);
    const targetCol = e.over?.id as Status | undefined;
    if (!targetCol || !COLUMNS.some((c) => c.id === targetCol)) return;
    const ticket = repairs.find((r) => r.id === ticketId);
    if (!ticket || ticket.status === targetCol) return;

    // "Delivered" needs the deliver dialog (cost + payment) — open it instead.
    if (targetCol === "delivered") {
      setDelivering(ticket);
      return;
    }
    advance.mutate({ id: ticketId, status: targetCol });
  }

  // KPI strip
  const k = React.useMemo(() => {
    const open = repairs.filter((r) => r.status !== "delivered" && r.status !== "canceled");
    const urgent = open.filter((r) => priorityFor(r) === "urgent").length;
    const todayDelivered = repairs.filter(
      (r) =>
        r.status === "delivered" &&
        r.date_delivered === new Date().toISOString().slice(0, 10),
    ).length;
    const inProgress = byStatus.in_progress.length;
    const totalValue = open.reduce(
      (a, r) => a + Number(r.actual_cost || r.estimated_cost || 0),
      0,
    );
    return { open: open.length, urgent, inProgress, todayDelivered, totalValue };
  }, [repairs, byStatus.in_progress.length]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="مركز الصيانة"
        description="لوحة كانبان لكل تذاكر الصيانة — اسحب التذكرة بين الأعمدة لتغيير حالتها"
        action={
          <div className="flex gap-2">
            <div className="flex border rounded-lg overflow-hidden">
              <button
                onClick={() => setView("kanban")}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 ${
                  view === "kanban" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" /> كانبان
              </button>
              <button
                onClick={() => setView("list")}
                className={`px-3 py-1.5 text-xs flex items-center gap-1.5 ${
                  view === "list" ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                }`}
              >
                <ListIcon className="h-3.5 w-3.5" /> قائمة
              </button>
            </div>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> تذكرة جديدة
            </Button>
          </div>
        }
      />

      {/* KPI strip */}
      <motion.div
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05 } } }}
        className="grid grid-cols-2 lg:grid-cols-5 gap-3"
      >
        <Kpi icon={Wrench}       label="مفتوحة"          value={String(k.open)} />
        <Kpi icon={Wrench}       label="قيد الإصلاح"     value={String(k.inProgress)} tone="warn" />
        <Kpi icon={CheckCircle2} label="جاهزة للتسليم"   value={String(byStatus.done.length)} tone="success" />
        <Kpi icon={AlertTriangle} label="تجاوزت SLA"     value={String(k.urgent)} tone={k.urgent > 0 ? "danger" : "default"} />
        <Kpi icon={Truck}        label="تسليمات اليوم"    value={String(k.todayDelivered)} />
      </motion.div>

      {view === "kanban" ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {COLUMNS.map((col) => (
              <KanbanColumn
                key={col.id}
                column={col}
                tickets={byStatus[col.id]}
                onDeliver={(t) => setDelivering(t)}
              />
            ))}
          </div>
          <DragOverlay>
            {activeRepair && <RepairCard repair={activeRepair} dragging />}
          </DragOverlay>
        </DndContext>
      ) : (
        <ListView repairs={repairs} onDeliver={setDelivering} />
      )}

      {createOpen && (
        <CreateDialog
          onClose={() => setCreateOpen(false)}
          onSaved={() => {
            setCreateOpen(false);
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

// ---------- Kanban column ----------

function KanbanColumn({
  column,
  tickets,
  onDeliver,
}: {
  column: (typeof COLUMNS)[number];
  tickets: Repair[];
  onDeliver: (r: Repair) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const Icon = column.icon;
  return (
    <div
      ref={setNodeRef}
      className={`rounded-xl border-2 border-dashed ${column.tone} p-3 transition-all ${
        isOver ? "ring-2 ring-primary scale-[1.01]" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2 font-semibold">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <span>{column.label}</span>
        </div>
        <span className="text-xs bg-background border rounded-full px-2 py-0.5 tabular">
          {tickets.length}
        </span>
      </div>
      <div className="space-y-2 min-h-[60px] max-h-[68vh] overflow-y-auto pr-1">
        <AnimatePresence>
          {tickets.length === 0 && (
            <div className="text-center text-xs text-muted-foreground py-8 italic">
              فاضي
            </div>
          )}
          {tickets.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.18 }}
            >
              <RepairCard repair={t} onDeliver={onDeliver} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ---------- Repair card ----------

function RepairCard({
  repair,
  dragging,
  onDeliver,
}: {
  repair: Repair;
  dragging?: boolean;
  onDeliver?: (r: Repair) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: repair.id,
  });
  const priority = priorityFor(repair);
  const days = ageDays(repair.date_in);
  const cost = Number(repair.actual_cost || repair.estimated_cost || 0);

  const priorityRibbon =
    priority === "urgent" ? "border-r-4 border-red-500" :
    priority === "warn"   ? "border-r-4 border-amber-500" :
                            "border-r-4 border-emerald-500/50";

  const style: React.CSSProperties = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    opacity: isDragging && !dragging ? 0.4 : 1,
  };

  return (
    <div
      ref={dragging ? undefined : setNodeRef}
      style={style}
      {...(dragging ? {} : attributes)}
      {...(dragging ? {} : listeners)}
      className={`bg-card border rounded-lg p-3 shadow-sm cursor-grab active:cursor-grabbing ${priorityRibbon} ${
        dragging ? "shadow-2xl ring-2 ring-primary" : "hover:shadow-md"
      } transition-all`}
    >
      <div className="flex items-start justify-between gap-2">
        <code className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">
          {repair.ticket_number}
        </code>
        {priority === "urgent" && (
          <span className="pill pill-danger text-[10px]">
            <AlertTriangle className="h-3 w-3" /> متأخرة
          </span>
        )}
        {priority === "warn" && (
          <span className="pill pill-warn text-[10px]">
            <Clock className="h-3 w-3" /> {days} يوم
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center gap-2 text-sm font-semibold">
        <Smartphone className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="truncate">{repair.device_model}</span>
      </div>
      <div className="text-xs text-muted-foreground line-clamp-2 mt-0.5 min-h-[2rem]">
        {repair.problem}
      </div>

      <div className="mt-2 pt-2 border-t flex items-center justify-between text-xs">
        <div className="min-w-0">
          <div className="font-medium truncate">{repair.customer_name}</div>
          {repair.customer_phone && (
            <div className="flex items-center gap-1 text-muted-foreground tabular" dir="ltr">
              <Phone className="h-2.5 w-2.5" /> {repair.customer_phone}
            </div>
          )}
        </div>
        <div className="text-left shrink-0">
          <div className="font-bold tabular text-primary">{formatMoney(cost)}</div>
          <div className="text-[10px] text-muted-foreground tabular">
            {formatDate(repair.date_in)}
          </div>
        </div>
      </div>

      {(repair.status === "done" || repair.status === "in_progress") && onDeliver && (
        <Button
          size="sm"
          variant="success"
          className="w-full mt-2 h-7 text-xs"
          onClick={(e) => {
            e.stopPropagation();
            onDeliver(repair);
          }}
        >
          <Truck className="h-3 w-3" /> تسليم وتحصيل
        </Button>
      )}
    </div>
  );
}

// ---------- List view (fallback) ----------

function ListView({
  repairs,
  onDeliver,
}: {
  repairs: Repair[];
  onDeliver: (r: Repair) => void;
}) {
  return (
    <Card className="card-elevated">
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-muted-foreground text-xs uppercase tracking-wider">
              <tr>
                <th className="text-right p-3">رقم</th>
                <th className="text-right p-3">العميل</th>
                <th className="text-right p-3">الجهاز</th>
                <th className="text-right p-3">الحالة</th>
                <th className="text-right p-3">العمر</th>
                <th className="text-right p-3">السعر</th>
                <th className="text-right p-3">إجراء</th>
              </tr>
            </thead>
            <tbody>
              {repairs.map((r) => {
                const days = ageDays(r.date_in);
                const col = COLUMNS.find((c) => c.id === r.status);
                return (
                  <tr key={r.id} className="border-t hover:bg-muted/30">
                    <td className="p-3">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                        {r.ticket_number}
                      </code>
                    </td>
                    <td className="p-3">{r.customer_name}</td>
                    <td className="p-3">{r.device_model}</td>
                    <td className="p-3">
                      <span className="pill pill-info">{col?.label || r.status}</span>
                    </td>
                    <td className="p-3 tabular">{days} يوم</td>
                    <td className="p-3 tabular">
                      {formatMoney(r.actual_cost || r.estimated_cost)}
                    </td>
                    <td className="p-3">
                      {(r.status === "done" || r.status === "in_progress") && (
                        <Button
                          size="sm"
                          variant="success"
                          onClick={() => onDeliver(r)}
                        >
                          <Truck className="h-3 w-3" /> تسليم
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------- KPI ----------

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
    warn:    "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    danger:  "bg-red-500/10 text-red-600 dark:text-red-400",
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

// ---------- Dialogs ----------

function CreateDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [branchId, setBranchId] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    customer_name: "",
    customer_phone: "",
    device_model: "",
    imei: "",
    problem: "",
    estimated_cost: "0",
    notes: "",
  });
  React.useEffect(() => {
    api.get("/auth/me").then((r) => setBranchId(r.data.data?.user?.default_branch_id));
  }, []);

  const m = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("لا يوجد فرع نشط");
      const body: any = { ...form, branch_id: branchId };
      if (!body.imei) delete body.imei;
      return (await api.post("/repairs/", body)).data.data;
    },
    onSuccess: () => {
      toast.success("تم استلام التذكرة");
      onSaved();
    },
    onError: (err: any) =>
      toast.error(err?.response?.data?.error?.message || "فشل الحفظ"),
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
        <CardContent className="p-6 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold">
              <Wrench className="h-5 w-5 text-primary" /> تذكرة صيانة جديدة
            </div>
            <button onClick={onClose} className="p-1 hover:bg-muted rounded">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="اسم العميل *">
              <Input
                value={form.customer_name}
                onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
                required autoFocus
              />
            </Field>
            <Field label="الهاتف">
              <Input
                value={form.customer_phone}
                onChange={(e) => setForm({ ...form, customer_phone: e.target.value })}
                dir="ltr"
              />
            </Field>
            <Field label="الجهاز *" cols={2}>
              <Input
                value={form.device_model}
                onChange={(e) => setForm({ ...form, device_model: e.target.value })}
                required
              />
            </Field>
            <Field label="IMEI / Serial" cols={2}>
              <Input
                value={form.imei}
                onChange={(e) => setForm({ ...form, imei: e.target.value })}
                dir="ltr"
                placeholder="اختياري"
              />
            </Field>
            <Field label="العطل *" cols={2}>
              <Input
                value={form.problem}
                onChange={(e) => setForm({ ...form, problem: e.target.value })}
                required
              />
            </Field>
            <Field label="تكلفة تقديرية">
              <Input
                type="number"
                step="0.01"
                value={form.estimated_cost}
                onChange={(e) => setForm({ ...form, estimated_cost: e.target.value })}
              />
            </Field>
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <Button variant="outline" onClick={onClose}>إلغاء</Button>
            <Button onClick={() => m.mutate()} disabled={m.isPending}>
              {m.isPending ? "جاري الحفظ..." : "حفظ"}
            </Button>
          </div>
        </CardContent>
      </Card>
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
  const [cost, setCost] = React.useState(
    String(Number(ticket.actual_cost) || Number(ticket.estimated_cost) || 0),
  );
  const [paymentMethod, setPaymentMethod] = React.useState<"cash" | "bank">("cash");
  const [isPaid, setIsPaid] = React.useState(true);

  const m = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/repairs/${ticket.id}/deliver`, {
          actual_cost: cost,
          is_paid: isPaid,
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
    <div
      className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-md card-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <CardContent className="p-6 space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold">تسليم {ticket.ticket_number}</div>
            <button onClick={onClose} className="p-1 hover:bg-muted rounded">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="text-sm text-muted-foreground">
            <div><strong>{ticket.device_model}</strong> — {ticket.customer_name}</div>
          </div>
          <Field label="التكلفة الفعلية">
            <Input
              type="number"
              step="0.01"
              min="0"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              autoFocus
            />
          </Field>
          <Field label="طريقة الدفع">
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as "cash" | "bank")}
              className="h-10 w-full border border-input rounded-md bg-background px-3 text-sm"
            >
              <option value="cash">كاش</option>
              <option value="bank">بنك</option>
            </select>
          </Field>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isPaid}
              onChange={(e) => setIsPaid(e.target.checked)}
            />
            تم تحصيل المبلغ
          </label>
          <div className="flex gap-2 justify-end pt-2">
            <Button variant="outline" onClick={onClose}>إلغاء</Button>
            <Button
              variant="success"
              onClick={() => m.mutate()}
              disabled={m.isPending}
            >
              <Check className="h-4 w-4" />
              {m.isPending ? "جاري التسليم..." : "تسليم وتسجيل"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  cols,
  children,
}: {
  label: string;
  cols?: number;
  children: React.ReactNode;
}) {
  return (
    <div className={`space-y-1.5 ${cols === 2 ? "col-span-2" : ""}`}>
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
