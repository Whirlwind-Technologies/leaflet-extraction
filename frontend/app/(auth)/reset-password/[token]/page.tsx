"use client";

import { use, useState, useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { FileText, CheckCircle } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { resetPassword } from "@/lib/actions/auth";
import { toast } from "sonner";
import type { ActionResult } from "@/lib/types";

const initialState: ActionResult<Record<string, never>> = {
  success: false,
};

export default function ResetPasswordPage({ params }: { params: Promise<{ token: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [state, formAction, isPending] = useActionState(resetPassword, initialState);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  useEffect(() => {
    if (state.success) {
      toast.success("Password reset successfully!");
      setTimeout(() => {
        router.push("/login");
      }, 2000);
    } else if (state.error) {
      toast.error(state.error);
    }
  }, [state, router]);

  const handleSubmit = (formData: FormData) => {
    if (password !== passwordConfirm) {
      toast.error("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    formData.append("token", resolvedParams.token);
    formAction(formData);
  };

  if (state.success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
        <div className="w-full max-w-md">
          <Link href="/" className="flex items-center justify-center space-x-3 mb-12">
             <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={320}
              height={80}
              className="h-20 w-auto"
            />
          </Link>

          <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-xl bg-green-100">
              <CheckCircle className="h-8 w-8 text-green-600" strokeWidth={1.5} />
            </div>
            <h1 className="text-2xl font-light mb-3 text-[#2D3748]">
              <span className="font-normal">Password</span> Reset!
            </h1>
            <p className="text-[#6B7280] font-light mb-6">
              Your password has been successfully reset. Redirecting to login...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
      <div className="w-full max-w-md">
        <Link href="/" className="flex items-center justify-center space-x-3 mb-12">
          <div className="bg-[#2D3748] p-2.5 rounded-xl shadow-sm">
            <FileText className="h-6 w-6 text-white" strokeWidth={1.5} />
          </div>
          <span className="text-2xl font-normal text-[#2D3748] tracking-tight">
            LEAFXTRACT
          </span>
        </Link>

        <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-light mb-3 text-[#2D3748]">
              <span className="font-normal">Reset</span> Password
            </h1>
            <p className="text-[#6B7280] font-light">
              Enter your new password below.
            </p>
          </div>

          <form action={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-normal text-[#2D3748]">
                New Password
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
              />
              <p className="text-xs text-[#6B7280] font-light">
                Min. 8 chars with uppercase, lowercase & digit
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="passwordConfirm" className="text-sm font-normal text-[#2D3748]">
                Confirm Password
              </Label>
              <Input
                id="passwordConfirm"
                name="passwordConfirm"
                type="password"
                placeholder="••••••••"
                required
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
              />
              <p className="text-xs text-[#6B7280] font-light">
                Re-enter your password
              </p>
            </div>

            <Button
              type="submit"
              className="w-full h-12 bg-[#2D3748] hover:bg-[#5B8DBE] text-white font-normal rounded-xl transition-all duration-300 text-base"
              disabled={isPending}
            >
              {isPending ? "Resetting..." : "Reset Password"}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <Link
              href="/login"
              className="text-sm text-[#6B7280] hover:text-[#5B8DBE] font-light transition-colors"
            >
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
