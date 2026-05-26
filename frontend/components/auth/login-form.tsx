"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { login } from "@/lib/actions/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import type { ActionResult } from "@/lib/types";

interface LoginData {
  pending?: boolean;
}

const initialState: ActionResult<LoginData> = {
  success: false,
};

export function LoginForm() {
  const router = useRouter();
  const [state, formAction, isPending] = useActionState(login, initialState);

  useEffect(() => {
    if (state.success) {
      toast.success("Welcome back!");
      router.push("/dashboard");
      router.refresh();
    } else if (state.error) {
      // Check if it's a pending approval error
      if (state.data?.pending) {
        toast.info(state.error);
        router.push("/register/pending");
      } else {
        toast.error(state.error);
      }
    }
  }, [state, router]);

  return (
    <form action={formAction} className="space-y-6">
      <div className="space-y-5">
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

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password" className="text-sm font-normal text-[#2D3748]">
              Password
            </Label>
            <Link href="/forgot-password" className="text-xs text-[#5B8DBE] hover:text-[#4A7AA8] font-normal transition-colors">
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            name="password"
            type="password"
            placeholder="Enter your password"
            required
            autoComplete="current-password"
            className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
          />
        </div>
      </div>

      {/* Remember Me */}
      <div className="flex items-center space-x-2">
        <Checkbox
          id="remember"
          name="remember"
          className="border-gray-300 data-[state=checked]:bg-[#5B8DBE] data-[state=checked]:border-[#5B8DBE]"
        />
        <Label
          htmlFor="remember"
          className="text-sm font-light text-[#6B7280] cursor-pointer select-none"
        >
          Remember me
        </Label>
      </div>

      <Button
        type="submit"
        className="w-full h-12 bg-[#4A5568] hover:bg-[#5B8DBE] text-white font-normal rounded-xl transition-all duration-300 text-base"
        disabled={isPending}
      >
        {isPending ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Signing in...
          </>
        ) : (
          "Sign In"
        )}
      </Button>
    </form>
  );
}
