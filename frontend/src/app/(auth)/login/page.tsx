"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { login, setTokens } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await login(username.trim(), password);
      setTokens(data.tokens);
      toast.success("تم تسجيل الدخول");
      router.replace("/dashboard");
    } catch (err: any) {
      toast.error(err?.response?.data?.error?.message || "بيانات الدخول غير صحيحة");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-muted/30">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="text-center space-y-3">
          <div className="mx-auto w-14 h-14 rounded-xl bg-primary text-primary-foreground flex items-center justify-center text-2xl font-bold">
            K
          </div>
          <CardTitle>King Store</CardTitle>
          <CardDescription>تسجيل الدخول إلى نظام إدارة المحل</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">اسم المستخدم</label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="admin"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">كلمة المرور</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "جاري الدخول..." : "تسجيل الدخول"}
            </Button>
            <div className="text-center text-sm text-muted-foreground pt-2">
              ليس لديك حساب؟{" "}
              <Link href="/signup" className="text-primary hover:underline">
                أنشئ حساب جديد
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
