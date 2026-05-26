"use client";

import { useState, useActionState, useEffect, useRef } from "react";
import { Mail, ArrowLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { requestPasswordReset } from "@/lib/actions/auth";
import { toast } from "sonner";
import type { ActionResult } from "@/lib/types";

const initialState: ActionResult<Record<string, never>> = {
  success: false,
};

export default function ForgotPasswordPage() {
  const [dismissed, setDismissed] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");
  const [state, formAction, isPending] = useActionState(requestPasswordReset, initialState);
  const prevStateRef = useRef(state);

  const emailSent = state.success && !dismissed;

  useEffect(() => {
    if (prevStateRef.current === state) return;
    prevStateRef.current = state;

    if (state.success) {
      toast.success("Password reset email sent!");
    } else if (state.error) {
      toast.error(state.error);
    }
  }, [state]);

  if (emailSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
        <div className="w-full max-w-md">
          {/* Logo */}
          <Link href="/" className="flex items-center justify-center space-x-3 mb-12">
             <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={320}
              height={80}
              className="h-20 w-auto"
            />
          </Link>

          {/* Success Message */}
          <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-xl bg-green-100">
              <Mail className="h-8 w-8 text-green-600" strokeWidth={1.5} />
            </div>
            <h1 className="text-2xl font-light mb-3 text-[#2D3748]">
              <span className="font-normal">Check Your</span> Email
            </h1>
            <p className="text-[#6B7280] font-light mb-6">
              We&apos;ve sent password reset instructions to <strong className="font-normal text-[#2D3748]">{submittedEmail}</strong>
            </p>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 font-light mb-6">
              <p>
                If you don&apos;t see the email, check your spam folder or{" "}
                <button
                  onClick={() => {
                    setDismissed(true);
                    setSubmittedEmail("");
                  }}
                  className="font-normal text-[#5B8DBE] hover:text-[#4A7AA8] underline"
                >
                  try again
                </button>
                .
              </p>
            </div>
            <Link href="/login">
              <Button className="w-full bg-[#2D3748] hover:bg-[#5B8DBE] text-white font-normal rounded-xl transition-all duration-300">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Login
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center space-x-3 mb-12">
          <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={160}
              height={40}
              className="h-10 w-auto"
            />
        </Link>

        {/* Form Card */}
        <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-light mb-3 text-[#2D3748]">
              <span className="font-normal">Forgot</span> Password?
            </h1>
            <p className="text-[#6B7280] font-light">
              Enter your email address and we&apos;ll send you instructions to reset your password.
            </p>
          </div>

          <form
            action={(formData) => {
              const email = formData.get("email") as string;
              setSubmittedEmail(email);
              formAction(formData);
            }}
            className="space-y-6"
          >
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-normal text-[#2D3748]">
                Email Address
              </Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
              />
            </div>

            <Button
              type="submit"
              className="w-full h-12 bg-[#2D3748] hover:bg-[#5B8DBE] text-white font-normal rounded-xl transition-all duration-300 text-base"
              disabled={isPending}
            >
              {isPending ? "Sending..." : "Send Reset Instructions"}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <Link
              href="/login"
              className="text-sm text-[#6B7280] hover:text-[#5B8DBE] font-light inline-flex items-center gap-2 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
