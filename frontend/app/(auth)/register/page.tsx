"use client";

import { RegisterForm } from "@/components/auth/register-form";
import { FileText, Users, Globe, Shield } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef } from "react";

export default function RegisterPage() {
   const videoRef = useRef<HTMLVideoElement>(null);
  
    useEffect(() => {
      if (videoRef.current) {
        videoRef.current.playbackRate = 0.4;
      }
    }, []);
  
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2">
      {/* Left Column - Branding */}
      <div className="hidden lg:flex flex-col justify-start px-12 pt-3 relative">
        <div className="absolute inset-0">
          <video
            ref={videoRef}
            src="LTAnimation20Percent.mp4"
            loop
            muted
            autoPlay
            controls={false}
            className="w-full h-full object-cover"
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
              <span className="font-normal">Built for</span>
              <br />
              <span className="font-normal text-[#5B8DBE]">Business Teams</span>
            </h1>
            <p className="text-lg text-[#6B7280] font-light leading-relaxed">
              Join retail companies and e-commerce platforms using AI to automate product data extraction. Perfect for teams of any size.
            </p>
            <br />

            {/* Features */}
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Users className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    Team Collaboration
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Invite unlimited team members with role-based access
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Globe className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    Multi-Language Support
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Process leaflets in any language or currency
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-sm">
                  <Shield className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-base text-[#2D3748] mb-1 font-normal">
                    Enterprise Security
                  </h3>
                  <p className="text-sm text-[#6B7280] font-light">
                    Complete data isolation and encryption
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

      {/* Right Column - Registration Form */}
      <div className="flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-lg">
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
              <span className="font-normal">Create Your</span> <span className="font-light text-[#2F79C5]">Business Account</span>
            </h1>
            <p className="text-[#6B7280] font-light">Start extracting product data with your team</p>
          </div>

          {/* Form */}
          <div className="bg-white rounded-2xl border border-gray-100 p-8 shadow-sm">
            <RegisterForm />
          </div>

          {/* Footer Link */}
          <p className="text-center mt-8 text-sm text-[#6B7280] font-light">
            Already have an account?{" "}
            <Link href="/login" className="text-[#5B8DBE] hover:text-[#4A7AA8] font-normal transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
