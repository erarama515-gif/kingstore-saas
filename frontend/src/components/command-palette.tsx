"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
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
} from "lucide-react";
import { useTheme } from "next-themes";
import { clearTokens } from "@/lib/api";

/**
 * Enterprise-style command palette (Cmd/Ctrl+K). Powered by cmdk.
 *
 * Mounts globally inside the (app) layout so any page can open it; the
 * shortcut is wired here. Keep the command list focused — too many entries
 * hurt the experience.
 */
export function CommandPalette() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Mac: ⌘K, others: Ctrl+K. Also support "/" anywhere outside inputs.
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

  function go(path: string) {
    setOpen(false);
    router.push(path);
  }

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
        className="fixed left-1/2 top-[20%] z-50 w-[92vw] max-w-xl -translate-x-1/2
                   rounded-xl border bg-popover text-popover-foreground shadow-2xl
                   animate-fade-in"
      >
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Command.Input
            placeholder="ابحث... أو نفّذ أمرًا (اضغط Esc للإغلاق)"
            className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground text-sm"
          />
          <kbd className="hidden sm:inline rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            Esc
          </kbd>
        </div>
        <Command.List className="max-h-[60vh] overflow-y-auto p-2">
          <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
            لا توجد نتائج.
          </Command.Empty>

          <Command.Group heading="الانتقال" className="text-xs text-muted-foreground px-2 pt-2 pb-1">
            <Item icon={LayoutDashboard} label="لوحة القيادة" onSelect={() => go("/dashboard")} />
            <Item icon={ShoppingCart}    label="نقطة البيع (POS)" onSelect={() => go("/pos")} hint="Ctrl+P" />
            <Item icon={Package}         label="المنتجات" onSelect={() => go("/products")} />
            <Item icon={Boxes}           label="المخزون" onSelect={() => go("/inventory")} />
            <Item icon={Users}           label="العملاء" onSelect={() => go("/customers")} />
            <Item icon={Truck}           label="الموردين" onSelect={() => go("/suppliers")} />
            <Item icon={Receipt}         label="الفواتير" onSelect={() => go("/sales")} />
            <Item icon={HandCoins}       label="الديون" onSelect={() => go("/debts")} />
            <Item icon={Wallet}          label="المصاريف" onSelect={() => go("/expenses")} />
            <Item icon={Wrench}          label="الصيانة" onSelect={() => go("/repairs")} />
            <Item icon={BarChart3}       label="التقارير" onSelect={() => go("/reports")} />
            <Item icon={Wallet}          label="رأس المال" onSelect={() => go("/capital")} />
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
        </Command.List>
        <div className="flex items-center justify-between border-t px-4 py-2 text-[11px] text-muted-foreground">
          <span>اضغط <kbd className="rounded bg-muted px-1 font-mono">↑↓</kbd> للتنقل، <kbd className="rounded bg-muted px-1 font-mono">⏎</kbd> للتنفيذ</span>
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
  danger,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onSelect: () => void;
  hint?: string;
  danger?: boolean;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm cursor-pointer
                  data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground
                  ${danger ? "text-red-600 dark:text-red-400" : ""}`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1">{label}</span>
      {hint && (
        <kbd className="hidden sm:inline rounded border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
          {hint}
        </kbd>
      )}
    </Command.Item>
  );
}
