"use client";

import { useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";

export default function LandingNav() {
  /** Smooth-scroll to a hash target, accounting for the sticky nav height. */
  const scrollToHash = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, hash: string) => {
      e.preventDefault();
      const target = document.querySelector(hash);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        // Update URL hash without a page jump
        window.history.pushState(null, "", hash);
      }
    },
    []
  );

  return (
    <nav className="bg-gradient-to-br backdrop-blur-md sticky top-0 z-50 border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-3">
            <Image
              src="/LX-Login-Logo.svg"
              alt="LeafXtract"
              width={96}
              height={48}
              className="h-12 w-auto"
            />
          </Link>

          {/* Navigation Links */}
          {/* Navigation Links + Auth Buttons */}
          <div className="hidden md:flex items-center space-x-12">
            <Link href="/" className="text-[#6B7280] hover:text-[#2D3748] transition-colors text-sm font-normal">
              Home
            </Link>
            <a
              href="#services"
              onClick={(e) => scrollToHash(e, "#services")}
              className="text-[#6B7280] hover:text-[#2D3748] transition-colors text-sm font-normal cursor-pointer"
            >
              Services
            </a>
            <a
              href="#features"
              onClick={(e) => scrollToHash(e, "#features")}
              className="text-[#6B7280] hover:text-[#2D3748] transition-colors text-sm font-normal cursor-pointer"
            >
              Features
            </a>
            <a
              href="#contact"
              onClick={(e) => scrollToHash(e, "#contact")}
              className="text-[#6B7280] hover:text-[#2D3748] transition-colors text-sm font-normal cursor-pointer"
            >
              Contact
            </a>
          </div>

            {/* Auth Buttons */}
            <div className="flex items-center space-x-4">
              <Link href="/login">
                <Button
                  variant="ghost"
                  className="font-normal bg-white px-6 transition-all duration-300 hover:shadow-sm"
                >
                  Sign In
                </Button>
              </Link>
              <Link href="/register">
                <Button
                  className="bg-[#2F79C5] hover:bg-[#1F3C52] hover:text-white text-white font-normal px-6 rounded-md shadow-sm transition-all duration-300" 
                >
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
    </nav>
  );
}
