"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Bell,
  Building2,
  ChevronDown,
  User as UserIcon,
  LogOut,
  Sun,
  Moon,
  Sparkles,
  Plus,
  ShoppingCart,
  Package,
} from "lucide-react";
import { useTheme } from "next-themes";
import { api, clearTokens } from "@/lib/api";

type Me = {
  user: { id: string; name: string; username: string; role: string; default_branch_id: string };
  tenant: { id: string; slug: string; name: string };
};

/**
 * Premium SaaS top bar. Renders inside the (app) layout above page content.
 *
 * Width is responsive — sits to the left of the fixed RTL sidebar.
 */
export function Topbar() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [bellOpen, setBellOpen] = React.useState(false);
  const [quickOpen, setQuickOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  const me = useQuery<Me>({
    queryKey: ["me"],
    queryFn: async () => (await api.get("/auth/me")).data.data,
  });

  // Stock alerts for the bell (low-stock items count)
  const lowStock = useQuery<{ data: any[] }>({
    queryKey: ["low-stock-bell", me.data?.user.default_branch_id],
    queryFn: async () =>
      (
        await api.get("/inventory/stock-levels", {
          params: { branch_id: me.data!.user.default_branch_id, low: 1, per_page: 50 },
        })
      ).data,
    enabled: !!me.data?.user.default_branch_id,
    refetchInterval: 60_000,
  });

  // Close popovers on outside click
  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) {
        setMenuOpen(false);
        setBellOpen(false);
        setQuickOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function openPalette() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        ctrlKey: true,
        metaKey: true,
        bubbles: true,
      }),
    );
  }

  function logout() {
    clearTokens();
    router.replace("/login");
  }

  const initials = (me.data?.user.name || "?").split(" ").slice(0, 2).map((s) => s[0]).join("");
  const lowCount = lowStock.data?.data?.length || 0;

  return (
    <div
      ref={menuRef}
      className="sticky top-0 z-30 surface-glass border-b -mx-6 px-6 py-3 mb-6 flex items-center gap-3"
    >
      {/* Branch */}
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/40 border text-xs">
        <Building2 className="h-3.5 w-3.5 text-primary" />
        <span className="text-muted-foreground">الفرع:</span>
        <span className="font-semibold">الفرع الرئيسي</span>
      </div>

      {/* Search trigger (delegates to command palette) */}
      <button
        onClick={openPalette}
        className="flex-1 max-w-xl flex items-center gap-2 px-3 py-1.5 rounded-md border bg-muted/30 hover:bg-muted/50 text-xs text-muted-foreground transition-colors"
      >
        <Search className="h-3.5 w-3.5" />
        <span>ابحث في النظام، أو شغّل أمرًا...</span>
        <kbd className="ms-auto font-mono text-[10px] rounded border bg-background px-1 py-0.5">
          ⌘K
        </kbd>
      </button>

      {/* Quick actions */}
      <div className="relative">
        <button
          onClick={() => {
            setQuickOpen((o) => !o);
            setMenuOpen(false);
            setBellOpen(false);
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:opacity-90"
        >
          <Plus className="h-3.5 w-3.5" />
          إجراء سريع
          <ChevronDown className="h-3 w-3 opacity-70" />
        </button>
        <AnimatePresence>
          {quickOpen && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute end-0 mt-1 w-56 rounded-lg border bg-popover shadow-lg p-1"
            >
              <QuickItem icon={ShoppingCart} label="فاتورة بيع جديدة" onClick={() => { setQuickOpen(false); router.push("/pos"); }} />
              <QuickItem icon={Package}      label="منتج جديد"        onClick={() => { setQuickOpen(false); router.push("/products"); }} />
              <QuickItem icon={UserIcon}     label="عميل جديد"          onClick={() => { setQuickOpen(false); router.push("/customers"); }} />
              <QuickItem icon={Sparkles}     label="فتح Command Palette" onClick={() => { setQuickOpen(false); openPalette(); }} hint="⌘K" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bell / notifications */}
      <div className="relative">
        <button
          onClick={() => {
            setBellOpen((o) => !o);
            setMenuOpen(false);
            setQuickOpen(false);
          }}
          className="relative h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-muted text-muted-foreground transition-colors"
          aria-label="إشعارات"
        >
          <Bell className="h-4 w-4" />
          {lowCount > 0 && (
            <span className="absolute top-1 end-1 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-background animate-pulse" />
          )}
        </button>
        <AnimatePresence>
          {bellOpen && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute end-0 mt-1 w-80 rounded-lg border bg-popover shadow-lg overflow-hidden"
            >
              <div className="px-4 py-2.5 border-b font-semibold text-sm flex items-center justify-between">
                <span>الإشعارات</span>
                {lowCount > 0 && (
                  <span className="pill pill-warn">{lowCount}</span>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto">
                {lowCount === 0 ? (
                  <div className="px-4 py-8 text-center text-xs text-muted-foreground">
                    لا توجد تنبيهات حالية ✓
                  </div>
                ) : (
                  <Link
                    href="/inventory?low=1"
                    onClick={() => setBellOpen(false)}
                    className="block px-4 py-3 hover:bg-muted/40 border-b text-sm"
                  >
                    <div className="font-medium text-amber-700 dark:text-amber-300">
                      {lowCount} منتج وصل لحد إعادة الطلب
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      اضغط لاستعراض القائمة وتعديل الكميات.
                    </div>
                  </Link>
                )}
              </div>
              <div className="px-3 py-2 border-t text-xs">
                <Link
                  href="/activity"
                  onClick={() => setBellOpen(false)}
                  className="text-primary hover:underline"
                >
                  عرض كل النشاط
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Theme toggle */}
      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className="h-9 w-9 inline-flex items-center justify-center rounded-md hover:bg-muted text-muted-foreground transition-colors"
        aria-label="تبديل الوضع"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      {/* User menu */}
      <div className="relative">
        <button
          onClick={() => {
            setMenuOpen((o) => !o);
            setBellOpen(false);
            setQuickOpen(false);
          }}
          className="flex items-center gap-2 px-1.5 py-1 rounded-md hover:bg-muted transition-colors"
        >
          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-primary to-chart-5 text-primary-foreground flex items-center justify-center text-xs font-bold">
            {initials || "U"}
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="absolute end-0 mt-1 w-64 rounded-lg border bg-popover shadow-lg overflow-hidden"
            >
              <div className="p-4 border-b">
                <div className="font-semibold">{me.data?.user.name}</div>
                <div className="text-xs text-muted-foreground">
                  @{me.data?.user.username} · {me.data?.user.role}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  المتجر: <span className="font-medium text-foreground">{me.data?.tenant.name}</span>
                </div>
              </div>
              <button
                onClick={logout}
                className="w-full px-4 py-2.5 text-right text-sm text-red-600 dark:text-red-400 hover:bg-red-500/10 flex items-center gap-2"
              >
                <LogOut className="h-4 w-4" /> تسجيل الخروج
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function QuickItem({
  icon: Icon,
  label,
  hint,
  onClick,
}: {
  icon: any;
  label: string;
  hint?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2 rounded-md hover:bg-accent text-sm text-right transition-colors"
    >
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="flex-1">{label}</span>
      {hint && (
        <kbd className="font-mono text-[10px] text-muted-foreground rounded border bg-muted px-1">
          {hint}
        </kbd>
      )}
    </button>
  );
}
