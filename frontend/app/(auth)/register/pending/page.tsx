import { Clock, Mail, CheckCircle2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SUPPORT_EMAIL } from "@/lib/constants";

export default function PendingApprovalPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] p-4">
      <div className="w-full max-w-2xl">
        {/* Logo */}
        <Link href="/" className="flex items-center justify-center space-x-3 mb-8">
           <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={160}
              height={40}
              className="h-10 w-auto"
            />
        </Link>

        {/* Main Card */}
        <div className="bg-white rounded-2xl border border-gray-100 p-8 md:p-12 shadow-lg">
          {/* Success Icon */}
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-[#5B8DBE]/10 rounded-full flex items-center justify-center">
              <CheckCircle2 className="h-10 w-10 text-[#5B8DBE]" strokeWidth={1.5} />
            </div>
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-light text-center mb-4 text-[#2D3748]">
            <span className="font-normal">Registration</span> Submitted
          </h1>

          {/* Description */}
          <p className="text-center text-[#6B7280] font-light text-lg mb-8">
            Thank you for registering your business with LeafXtract!
          </p>

          {/* Status Info */}
          <div className="space-y-6 mb-10">
            <div className="flex items-start gap-4 p-4 bg-[#F9FAFB] rounded-xl border border-gray-100">
              <div className="flex-shrink-0 w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm">
                <Clock className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-base font-normal text-[#2D3748] mb-1">
                  Pending Approval
                </h3>
                <p className="text-sm text-[#6B7280] font-light leading-relaxed">
                  Your business registration is currently under review by our team. This process typically takes 24-48 hours.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-[#F9FAFB] rounded-xl border border-gray-100">
              <div className="flex-shrink-0 w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm">
                <Mail className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-base font-normal text-[#2D3748] mb-1">
                  We&apos;ll Notify You
                </h3>
                <p className="text-sm text-[#6B7280] font-light leading-relaxed">
                  Once your account is approved, you&apos;ll receive an email notification. You&apos;ll then be able to sign in and start using the platform.
                </p>
              </div>
            </div>
          </div>

          {/* Next Steps */}
          <div className="bg-[#5B8DBE]/5 rounded-xl p-6 mb-8">
            <h3 className="text-lg font-normal text-[#2D3748] mb-3">
              What happens next?
            </h3>
            <ul className="space-y-2 text-sm text-[#6B7280] font-light">
              <li className="flex items-start gap-2">
                <span className="text-[#5B8DBE] mt-1">•</span>
                <span>Our team will review your business information</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#5B8DBE] mt-1">•</span>
                <span>You&apos;ll receive an email once your account is approved</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#5B8DBE] mt-1">•</span>
                <span>Sign in with your credentials to access your dashboard</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-[#5B8DBE] mt-1">•</span>
                <span>Start uploading and extracting product data from leaflets</span>
              </li>
            </ul>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              asChild
              variant="outline"
              className="h-12 rounded-xl border-gray-200 hover:bg-gray-50"
            >
              <Link href="/">
                Return to Home
              </Link>
            </Button>
            <Button
              asChild
              className="h-12 bg-[#4A5568] hover:bg-[#5B8DBE] text-white rounded-xl"
            >
              <Link href="/login">
                Go to Login
              </Link>
            </Button>
          </div>
        </div>

        {/* Help Text */}
        <p className="text-center mt-6 text-sm text-[#6B7280] font-light">
          Questions about your registration?{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-[#5B8DBE] hover:text-[#4A7AA8] font-normal transition-colors">
            Contact Support
          </a>
        </p>
      </div>
    </div>
  );
}
