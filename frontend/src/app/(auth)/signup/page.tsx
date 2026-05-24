"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { signup, setTokens } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    tenant_name: "",
    tenant_slug: "",
    default_branch_name: "الفرع الرئيسي",
    default_branch_code: "MAIN",
    owner_name: "",
    owner_email: "",
    owner_username: "",
    owner_password: "",
  });

  function up(k: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((s) => ({ ...s, [k]: e.target.value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const slug =
        form.tenant_slug ||
        form.tenant_name
          .toLowerCase()
          .replace(/[^a-z0-9-]+/g, "-")
          .replace(/^-|-$/g, "");
      const data = await signup({ ...form, tenant_slug: slug });
      setTokens(data.tokens);
      toast.success("تم إنشاء الحساب — مرحبًا بك!");
      router.replace("/dashboard");
    } catch (err: any) {
      toast.error(err?.response?.data?.error?.message || "حدث خطأ أثناء التسجيل");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-muted/30 py-10">
      <Card className="w-full max-w-xl shadow-xl">
        <CardHeader>
          <CardTitle>إنشاء حساب جديد</CardTitle>
          <CardDescription>
            ابدأ تجربتك مع King Store — الحساب التجريبي مجاني وكامل.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm">اسم المحل</label>
                <Input value={form.tenant_name} onChange={up("tenant_name")} required />
              </div>
              <div className="space-y-2">
                <label className="text-sm">معرّف (slug)</label>
                <Input
                  value={form.tenant_slug}
                  onChange={up("tenant_slug")}
                  placeholder="auto-generated"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm">اسم الفرع</label>
                <Input
                  value={form.default_branch_name}
                  onChange={up("default_branch_name")}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm">كود الفرع</label>
                <Input
                  value={form.default_branch_code}
                  onChange={up("default_branch_code")}
                  required
                />
              </div>
            </div>

            <div className="border-t pt-4 space-y-3">
              <div className="text-sm font-medium text-muted-foreground">
                بيانات المالك
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-sm">الاسم</label>
                  <Input value={form.owner_name} onChange={up("owner_name")} required />
                </div>
                <div className="space-y-2">
                  <label className="text-sm">البريد الإلكتروني</label>
                  <Input
                    type="email"
                    value={form.owner_email}
                    onChange={up("owner_email")}
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-sm">اسم المستخدم</label>
                  <Input
                    value={form.owner_username}
                    onChange={up("owner_username")}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm">كلمة المرور</label>
                  <Input
                    type="password"
                    value={form.owner_password}
                    onChange={up("owner_password")}
                    minLength={8}
                    required
                  />
                </div>
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "جاري الإنشاء..." : "إنشاء الحساب والدخول"}
            </Button>
            <div className="text-center text-sm text-muted-foreground pt-1">
              لديك حساب بالفعل؟{" "}
              <Link href="/login" className="text-primary hover:underline">
                سجل دخول
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
