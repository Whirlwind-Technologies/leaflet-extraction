"use client"

import { LoginForm } from "@/components/auth/login-form";
import { FileText, Zap, Target, Shield } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef } from "react";

export default function LoginPage() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = 0.4;
    }
  }, []);

  return (
    <div className="h-screen overflow-hidden grid grid-cols-1 lg:grid-cols-2">
      {/* Left Column - Branding */}
      <div className="hidden lg:flex flex-col justify-start px-12 pt-3 relative h-screen">
        <div className="absolute inset-0">
          <video
            ref={videoRef}
            src="LTAnimation20Percent.mp4"
            loop
            muted
            autoPlay
            controls={false}
          >
          </video>
        </div>

        <div className="relative z-10 flex flex-col items-start text-left gap-10 pl-20">
          {/* Logo */}
          <Link href="/">
            <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={160}
              height={40}
              className="h-10 w-auto"
            />
          </Link>

          {/* Hero Text */}
          <div className="max-w-md">
            <h1 className="text-4xl md:text-5xl font-light mb-2 text-[#2D3748] leading-tight">
              <span className="font-normal">Transform</span> <span className="font-light">Your</span>
              <br />
              <span className="font-normal text-[#5B8DBE]">Data Extraction</span>
            </h1>
            <p className="text-lg text-[#6B7280] font-light leading-relaxed">
              AI-powered platform that automatically extracts structured product data from retail leaflets with 95%+ accuracy.
            </p>
            <br />

            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Zap className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    Lightning Fast
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Process multi-page leaflets in minutes
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Target className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    95%+ Accuracy
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Industry-leading precision
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Shield className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    Secure & Reliable
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Enterprise-grade security
                  </p>
                </div>
              </div>
            </div>
            <br />
          </div>
        </div>
        {/* Footer */}
        <div className="relative z-10 mt-auto pb-2">
          <p className="text-sm text-[#9CA3AF] font-normal">
            &copy; {new Date().getFullYear()} LeafXtract. All rights reserved.
          </p>
        </div>
      </div>

      {/* Right Column - Login Form */}
      <div className="flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <Link href="/" className="flex lg:hidden items-center justify-center space-x-3 mb-12">
            <div className="bg-[#2D3748] p-2.5 rounded-xl shadow-sm">
              <FileText className="h-6 w-6 text-white" strokeWidth={1.5} />
            </div>
            <span className="text-2xl font-normal text-[#2D3748] tracking-tight">
              LEAFXTRACT
            </span>
          </Link>

          {/* Welcome Text */}
          <div className="mb-10">
            <h1 className="text-3xl md:text-4xl font-light mb-3 text-[#2D3748]">
              <span className="font-normal">Welcome </span>
              <span className="font-light text-[#2F79C5]">Back</span>
            </h1>
            <p className="text-[#6B7280] font-light">Sign in to continue to your dashboard</p>
          </div>

          {/* Form */}
          <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm">
            <LoginForm />
          </div>

          {/* Footer Link */}
          <p className="text-center mt-8 text-sm text-[#6B7280] font-light">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-[#5B8DBE] hover:text-[#4A7AA8] font-normal transition-colors">
              Create one now
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
