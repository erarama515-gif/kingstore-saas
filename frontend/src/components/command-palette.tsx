"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Boxes,
  Users,
  Truck,
  Wrench,
  Receipt,
  BarChart3,
  HandCoins,
  Wallet,
  Moon,
  Sun,
  LogOut,
  Search,
  Activity,
  Banknote,
  Smartphone,
} from "lucide-react";
import { useTheme } from "next-themes";
import { api, clearTokens } from "@/lib/api";

/**
 * Smart command palette with backend search.
 *
 * Empty query → quick navigation + actions.
 * Typed query → live search across products, customers, sales, repairs.
 * 250ms debounce; results grouped by entity type.
 */
export function CommandPalette() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [debounced, setDebounced] = React.useState("");

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (
        e.key === "/" &&
        !["INPUT", "TEXTAREA"].includes(
          (e.target as HTMLElement | null)?.tagName ?? ""
        )
      ) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Reset query on close
  React.useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  // Debounce
  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);

  // Backend searches (only when there's at least 1 char typed)
  const products = useQuery({
    queryKey: ["palette-products", debounced],
    queryFn: async () =>
      (
        await api.get("/products/", {
          params: { q: debounced, per_page: 6 },
        })
      ).data.data as any[],
    enabled: open && debounced.length >= 1,
  });

  const customers = useQuery({
    queryKey: ["palette-customers", debounced],
    queryFn: async () =>
      (await api.get("/customers/", { params: { q: debounced, per_page: 6 } })).data.data as any[],
    enabled: open && debounced.length >= 1,
  });

  const repairs = useQuery({
    queryKey: ["palette-repairs", debounced],
    queryFn: async () =>
      (await api.get("/repairs/", { params: { per_page: 30 } })).data.data as any[],
    enabled: open && debounced.length >= 1,
    select: (rows: any[]) =>
      rows.filter((r) => {
        const q = debounced.toLowerCase();
        return (
          r.ticket_number?.toLowerCase().includes(q) ||
          r.customer_name?.toLowerCase().includes(q) ||
          r.device_model?.toLowerCase().includes(q) ||
          r.imei?.toLowerCase().includes(q)
        );
      }).slice(0, 6),
  });

  function go(path: string) {
    setOpen(false);
    router.push(path);
  }

  const hasQuery = debounced.length >= 1;

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-background/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        />
      )}
      <Command.Dialog
        open={open}
        onOpenChange={setOpen}
        label="Command Palette"
        // cmdk does its own client-side filtering. Disable it because we're
        // showing backend search results that already match the query.
        shouldFilter={false}
        className="fixed left-1/2 top-[15%] z-50 w-[92vw] max-w-2xl -translate-x-1/2
                   rounded-xl border bg-popover text-popover-foreground shadow-2xl
                   animate-fade-in"
      >
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder="ابحث عن منتج، عميل، فاتورة، تذكرة صيانة، IMEI... أو اكتب أمرًا"
            className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground text-sm"
          />
          <kbd className="hidden sm:inline rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            Esc
          </kbd>
        </div>
        <Command.List className="max-h-[60vh] overflow-y-auto p-2">
          {/* Empty state with hint */}
          {!hasQuery && (
            <>
              <Command.Group heading="الانتقال السريع" className="text-xs text-muted-foreground px-2 pt-2 pb-1">
                <Item icon={LayoutDashboard} label="لوحة القيادة"        onSelect={() => go("/dashboard")} />
                <Item icon={ShoppingCart}    label="نقطة البيع (POS)"    onSelect={() => go("/pos")} />
                <Item icon={Package}         label="المنتجات"            onSelect={() => go("/products")} />
                <Item icon={Boxes}           label="المخزون"             onSelect={() => go("/inventory")} />
                <Item icon={Users}           label="العملاء"             onSelect={() => go("/customers")} />
                <Item icon={Truck}           label="الموردين"            onSelect={() => go("/suppliers")} />
                <Item icon={Receipt}         label="الفواتير"            onSelect={() => go("/sales")} />
                <Item icon={HandCoins}       label="الديون"              onSelect={() => go("/debts")} />
                <Item icon={Wallet}          label="المصاريف"            onSelect={() => go("/expenses")} />
                <Item icon={Wrench}          label="الصيانة"             onSelect={() => go("/repairs")} />
                <Item icon={BarChart3}       label="التقارير"            onSelect={() => go("/reports")} />
                <Item icon={Activity}        label="سجل النشاط"          onSelect={() => go("/activity")} />
                <Item icon={Banknote}        label="رأس المال"           onSelect={() => go("/capital")} />
              </Command.Group>

              <Command.Group heading="إعدادات" className="text-xs text-muted-foreground px-2 pt-3 pb-1">
                <Item
                  icon={theme === "dark" ? Sun : Moon}
                  label={theme === "dark" ? "وضع النهار" : "الوضع الليلي"}
                  onSelect={() => {
                    setTheme(theme === "dark" ? "light" : "dark");
                    setOpen(false);
                  }}
                />
                <Item
                  icon={LogOut}
                  label="تسجيل الخروج"
                  danger
                  onSelect={() => {
                    clearTokens();
                    setOpen(false);
                    router.replace("/login");
                  }}
                />
              </Command.Group>
            </>
          )}

          {/* Search results */}
          {hasQuery && (
            <>
              {(products.data?.length ?? 0) > 0 && (
                <Command.Group
                  heading={`المنتجات (${products.data!.length})`}
                  className="text-xs text-muted-foreground px-2 pt-2 pb-1"
                >
                  {products.data!.map((p: any) => (
                    <Item
                      key={p.id}
                      icon={Package}
                      label={p.name}
                      hint={p.code || p.barcode || ""}
                      sub={`${formatMoney(p.price)} · ${p.category}`}
                      onSelect={() => go("/products")}
                    />
                  ))}
                </Command.Group>
              )}

              {(customers.data?.length ?? 0) > 0 && (
                <Command.Group
                  heading={`العملاء (${customers.data!.length})`}
                  className="text-xs text-muted-foreground px-2 pt-2 pb-1"
                >
                  {customers.data!.map((c: any) => (
                    <Item
                      key={c.id}
                      icon={Users}
                      label={c.name}
                      hint={c.phone || ""}
                      sub={
                        Number(c.debt_cached) > 0
                          ? `مديونية ${formatMoney(c.debt_cached)}`
                          : `إنفاق إجمالي ${formatMoney(c.total_spent_cached || 0)}`
                      }
                      onSelect={() => go(`/customers/${c.id}`)}
                    />
                  ))}
                </Command.Group>
              )}

              {(repairs.data?.length ?? 0) > 0 && (
                <Command.Group
                  heading={`الصيانة (${repairs.data!.length})`}
                  className="text-xs text-muted-foreground px-2 pt-2 pb-1"
                >
                  {repairs.data!.map((r: any) => (
                    <Item
                      key={r.id}
                      icon={Smartphone}
                      label={`${r.device_model} — ${r.customer_name}`}
                      hint={r.ticket_number}
                      sub={r.imei ? `IMEI: ${r.imei}` : r.problem?.slice(0, 50)}
                      onSelect={() => go("/repairs")}
                    />
                  ))}
                </Command.Group>
              )}

              {(products.data?.length ?? 0) === 0 &&
                (customers.data?.length ?? 0) === 0 &&
                (repairs.data?.length ?? 0) === 0 &&
                !products.isFetching && (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    لا توجد نتائج لـ "{debounced}"
                  </div>
                )}

              {(products.isFetching || customers.isFetching || repairs.isFetching) && (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  جاري البحث...
                </div>
              )}
            </>
          )}
        </Command.List>
        <div className="flex items-center justify-between border-t px-4 py-2 text-[11px] text-muted-foreground">
          <span>
            اضغط <kbd className="rounded bg-muted px-1 font-mono">↑↓</kbd> للتنقل،{" "}
            <kbd className="rounded bg-muted px-1 font-mono">⏎</kbd> للتنفيذ
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded bg-muted px-1 font-mono">⌘</kbd>
            <kbd className="rounded bg-muted px-1 font-mono">K</kbd>
          </span>
        </div>
      </Command.Dialog>
    </>
  );
}

function Item({
  icon: Icon,
  label,
  onSelect,
  hint,
  sub,
  danger,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onSelect: () => void;
  hint?: string;
  sub?: string;
  danger?: boolean;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      // Use the label as the value so cmdk's keyboard nav still routes properly.
      value={label + " " + (hint || "") + " " + (sub || "")}
      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm cursor-pointer
                  data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground
                  ${danger ? "text-red-600 dark:text-red-400" : ""}`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="truncate">{label}</div>
        {sub && (
          <div className="text-[11px] text-muted-foreground truncate">{sub}</div>
        )}
      </div>
      {hint && (
        <kbd className="hidden sm:inline rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground shrink-0">
          {hint}
        </kbd>
      )}
    </Command.Item>
  );
}

function formatMoney(v: any): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ج.م";
}
