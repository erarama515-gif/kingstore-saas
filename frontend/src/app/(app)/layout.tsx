"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { loadTokens, me } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    loadTokens();
    me()
      .then(() => setReady(true))
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) {
    return (
      <div className="h-screen flex items-center justify-center text-muted-foreground">
        جاري التحميل...
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Sidebar />
      <main className="mr-64 p-6">{children}</main>
    </div>
  );
}
