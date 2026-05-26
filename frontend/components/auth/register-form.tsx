"use client";

import { useActionState, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2, ArrowRight, Check } from "lucide-react";
import { register } from "@/lib/actions/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ActionResult } from "@/lib/types";

const initialState: ActionResult = {
  success: false,
};

type FormData = {
  organizationName: string;
  businessEmail: string;
  businessPhone: string;
  fullName: string;
  email: string;
  password: string;
};

export function RegisterForm() {
  const router = useRouter();
  const [state, formAction, isPending] = useActionState(register, initialState);
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<FormData>({
    organizationName: "",
    businessEmail: "",
    businessPhone: "",
    fullName: "",
    email: "",
    password: "",
  });

  useEffect(() => {
    if (state.success) {
      // Check if registration is pending approval
      if (state.data && typeof state.data === 'object' && 'pending' in state.data && state.data.pending) {
        toast.success("Registration submitted successfully!");
        router.push("/register/pending");
      } else {
        toast.success("Account created successfully!");
        router.push("/dashboard");
        router.refresh();
      }
    } else if (state.error) {
      toast.error(state.error);
    }
  }, [state, router]);

  const updateFormData = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const nextStep = () => {
    setCurrentStep(2);
  };

  const prevStep = () => {
    setCurrentStep(1);
  };

  return (
    <div className="space-y-6">
      {/* Form */}
      <form action={formAction} className="space-y-8">
        {/* Hidden field - always business */}
        <input type="hidden" name="accountType" value="business" />

        {/* Step 1: Company Information */}
        {currentStep === 1 && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <div>
              <h3 className="text-2xl font-light text-[#2D3748] mb-3">
                Let&apos;s start with your <span className="font-normal">company</span>
              </h3>
              <p className="text-[#6B7280] font-light">
                We&apos;ll need some basic information about your business
              </p>
            </div>

            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="organizationName" className="text-sm font-normal text-[#2D3748]">
                  Company Name
                </Label>
                <Input
                  id="organizationName"
                  name="organizationName"
                  type="text"
                  placeholder="Acme Corporation"
                  required
                  value={formData.organizationName}
                  onChange={(e) => updateFormData("organizationName", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="businessEmail" className="text-sm font-normal text-[#2D3748]">
                  Company Email
                </Label>
                <Input
                  id="businessEmail"
                  name="businessEmail"
                  type="email"
                  placeholder="contact@acme.com"
                  required
                  value={formData.businessEmail}
                  onChange={(e) => updateFormData("businessEmail", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="businessPhone" className="text-sm font-normal text-[#2D3748]">
                  Company Phone <span className="text-[#9CA3AF] font-light">(Optional)</span>
                </Label>
                <Input
                  id="businessPhone"
                  name="businessPhone"
                  type="tel"
                  placeholder="+1 (555) 123-4567"
                  value={formData.businessPhone}
                  onChange={(e) => updateFormData("businessPhone", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                />
              </div>
            </div>

            <Button
              type="button"
              onClick={nextStep}
              className="w-full h-12 bg-[#4A5568] hover:bg-[#5B8DBE] text-white font-normal rounded-xl shadow-sm transition-all duration-300 text-base group"
            >
              Continue
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
          </div>
        )}

        {/* Step 2: Account Owner Details */}
        {currentStep === 2 && (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* Hidden fields for step 1 data */}
            <input type="hidden" name="organizationName" value={formData.organizationName} />
            <input type="hidden" name="businessEmail" value={formData.businessEmail} />
            <input type="hidden" name="businessPhone" value={formData.businessPhone} />

            {/* Completed company info */}
            <div className="bg-[#F9FAFB] rounded-xl p-4 border border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-[#5B8DBE] flex items-center justify-center flex-shrink-0">
                  <Check className="h-4 w-4 text-white" strokeWidth={2.5} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-normal text-[#2D3748] truncate">{formData.organizationName}</p>
                  <p className="text-xs text-[#9CA3AF] font-light truncate">{formData.businessEmail}</p>
                </div>
                <button
                  type="button"
                  onClick={prevStep}
                  className="text-xs text-[#5B8DBE] hover:text-[#4A7AA8] font-normal transition-colors"
                >
                  Edit
                </button>
              </div>
            </div>

            <div>
              <h3 className="text-2xl font-light text-[#2D3748] mb-3">
                Now, tell us about <span className="font-normal">yourself</span>
              </h3>
              <p className="text-[#6B7280] font-light">
                You&apos;ll be the account owner with full access
              </p>
            </div>

            <div className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="fullName" className="text-sm font-normal text-[#2D3748]">
                  Full Name
                </Label>
                <Input
                  id="fullName"
                  name="fullName"
                  type="text"
                  placeholder="John Doe"
                  required
                  autoComplete="name"
                  value={formData.fullName}
                  onChange={(e) => updateFormData("fullName", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-normal text-[#2D3748]">
                  Your Email Address
                </Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  value={formData.email}
                  onChange={(e) => updateFormData("email", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                />
                <p className="text-xs text-[#9CA3AF] font-light">
                  You&apos;ll use this to sign in
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-normal text-[#2D3748]">
                  Create Password
                </Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="••••••••••"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={formData.password}
                  onChange={(e) => updateFormData("password", e.target.value)}
                  className="h-12 rounded-xl border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE] font-light text-base"
                />
                <p className="text-xs text-[#9CA3AF] font-light">
                  At least 8 characters with uppercase, lowercase, and number
                </p>
              </div>
            </div>

            {/* Business Registration Notice */}
            <div className="rounded-xl border border-[#D1D5DB] bg-[#F9FAFB] p-5">
              <p className="text-sm text-[#4A5568] font-light leading-relaxed">
                <strong className="font-normal text-[#2D3748]">Almost there!</strong> Your account will be reviewed by our team within 24 hours. We&apos;ll send you an email once approved.
              </p>
            </div>

            <Button
              type="submit"
              className="w-full h-12 bg-[#4A5568] hover:bg-[#5B8DBE] text-white font-normal rounded-xl shadow-sm transition-all duration-300 text-base"
              disabled={isPending}
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating your account...
                </>
              ) : (
                "Create Account"
              )}
            </Button>
          </div>
        )}
      </form>
    </div>
  );
}
