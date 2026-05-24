"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Users,
  Wrench,
  HandCoins,
  Wallet,
  Receipt,
  BarChart3,
  LogOut,
  Sun,
  Moon,
  Boxes,
  Banknote,
  Truck,
  Search,
  Sparkles,
  Activity,
} from "lucide-react";
import { useTheme } from "next-themes";
import { logout } from "@/lib/api";
import { cn } from "@/lib/utils";

const sections: { heading: string; items: { href: string; label: string; icon: any }[] }[] = [
  {
    heading: "الرئيسية",
    items: [
      { href: "/dashboard", label: "لوحة القيادة", icon: LayoutDashboard },
      { href: "/pos", label: "نقطة البيع", icon: ShoppingCart },
    ],
  },
  {
    heading: "العمليات",
    items: [
      { href: "/products", label: "المنتجات", icon: Package },
      { href: "/inventory", label: "المخزون", icon: Boxes },
      { href: "/customers", label: "العملاء", icon: Users },
      { href: "/suppliers", label: "الموردين", icon: Truck },
      { href: "/repairs", label: "الصيانة", icon: Wrench },
    ],
  },
  {
    heading: "المالية",
    items: [
      { href: "/sales", label: "المبيعات", icon: Receipt },
      { href: "/debts", label: "الديون", icon: HandCoins },
      { href: "/expenses", label: "المصروفات", icon: Wallet },
      { href: "/capital", label: "رأس المال", icon: Banknote },
      { href: "/reports", label: "التقارير", icon: BarChart3 },
      { href: "/activity", label: "سجل النشاط", icon: Activity },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  return (
    <aside className="fixed inset-y-0 right-0 w-64 border-l bg-card/95 backdrop-blur-sm flex flex-col">
      {/* Brand */}
      <div className="px-5 py-4 border-b">
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary to-chart-5 text-primary-foreground flex items-center justify-center font-bold shadow-sm">
            K
          </div>
          <div>
            <div className="font-bold tracking-tight">King Store</div>
            <div className="text-[11px] text-muted-foreground -mt-0.5">
              Mobile Shop ERP / POS
            </div>
          </div>
        </Link>
      </div>

      {/* Search trigger (opens command palette) */}
      <button
        onClick={() => {
          const e = new KeyboardEvent("keydown", {
            key: "k",
            ctrlKey: true,
            metaKey: true,
            bubbles: true,
          });
          document.dispatchEvent(e);
        }}
        className="mx-3 mt-3 flex items-center justify-between gap-2 px-3 py-2 rounded-md border bg-muted/40 hover:bg-muted text-xs text-muted-foreground transition-colors"
      >
        <span className="flex items-center gap-2">
          <Search className="h-3.5 w-3.5" />
          بحث / أوامر سريعة
        </span>
        <kbd className="font-mono text-[10px] rounded border bg-background px-1 py-0.5">
          ⌘K
        </kbd>
      </button>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-4">
        {sections.map((section) => (
          <div key={section.heading}>
            <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 px-3 mb-1.5">
              {section.heading}
            </div>
            <div className="space-y-0.5">
              {section.items.map((it) => {
                const active =
                  pathname === it.href ||
                  (it.href !== "/dashboard" && pathname.startsWith(it.href));
                const Icon = it.icon;
                return (
                  <Link
                    key={it.href}
                    href={it.href}
                    className={cn(
                      "relative flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all",
                      active
                        ? "bg-primary/10 text-primary font-semibold"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground",
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-y-1 right-0 w-1 rounded-l bg-primary"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{it.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t space-y-1.5">
        <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-3 mb-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-primary mb-0.5">
            <Sparkles className="h-3 w-3" /> الحساب التجريبي
          </div>
          <div className="text-[11px] text-muted-foreground leading-relaxed">
            النسخة الكاملة جاهزة للعرض. كل البيانات تجريبية.
          </div>
        </div>
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground hover:bg-accent rounded-md transition-colors"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          <span>{theme === "dark" ? "وضع نهاري" : "وضع ليلي"}</span>
        </button>
        <button
          onClick={() => {
            logout();
            window.location.href = "/login";
          }}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
        >
          <LogOut className="h-4 w-4" />
          <span>تسجيل الخروج</span>
        </button>
      </div>
    </aside>
  );
}
