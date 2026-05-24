"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
} from "lucide-react";
import { useTheme } from "next-themes";
import { logout } from "@/lib/api";
import { cn } from "@/lib/utils";

const items = [
  { href: "/dashboard", label: "الرئيسية", icon: LayoutDashboard },
  { href: "/pos", label: "نقطة البيع", icon: ShoppingCart },
  { href: "/products", label: "المنتجات", icon: Package },
  { href: "/inventory", label: "المخزون", icon: Boxes },
  { href: "/customers", label: "العملاء", icon: Users },
  { href: "/sales", label: "المبيعات", icon: Receipt },
  { href: "/debts", label: "الديون والآجل", icon: HandCoins },
  { href: "/expenses", label: "المصروفات", icon: Wallet },
  { href: "/repairs", label: "الصيانة", icon: Wrench },
  { href: "/capital", label: "رأس المال", icon: Banknote },
  { href: "/reports", label: "التقارير", icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  return (
    <aside className="fixed inset-y-0 right-0 w-64 border-l bg-card flex flex-col">
      <div className="p-5 border-b">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-primary text-primary-foreground flex items-center justify-center font-bold">
            K
          </div>
          <div>
            <div className="font-bold">King Store</div>
            <div className="text-xs text-muted-foreground">ERP / POS</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {items.map((it) => {
          const active = pathname.startsWith(it.href);
          const Icon = it.icon;
          return (
            <Link
              key={it.href}
              href={it.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{it.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t space-y-2">
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground hover:bg-accent rounded-md"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          <span>{theme === "dark" ? "وضع نهاري" : "وضع ليلي"}</span>
        </button>
        <button
          onClick={() => {
            logout();
            window.location.href = "/login";
          }}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 rounded-md"
        >
          <LogOut className="h-4 w-4" />
          <span>تسجيل الخروج</span>
        </button>
      </div>
    </aside>
  );
}
