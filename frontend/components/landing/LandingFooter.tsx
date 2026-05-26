"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback } from "react";

export default function LandingFooter() {

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
    <footer className="bg-white text-[#6B7280] border-t border-gray-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="flex flex-col md:flex-row md:justify-between gap-12">
          {/* Brand */}
          <div className="col-span-1">
            <div className="flex items-center space-x-2 mb-3">
              <Image
                src="/LandingBranding.svg"
                alt="LeafXtract"
                width={160}
                height={80}
                className="h-20 w-auto"
              />
            </div>
            <p className="text-sm text-[#9CA3AF] leading-relaxed font-light">
              AI-powered platform for automated product data extraction <br /> from retail leaflets.
            </p>
          </div>

          {/* Product */}
          <div>
            <h3 className="text-[#2D3748] font-normal mb-5 text-sm">Product</h3>
            <ul className="space-y-3 text-sm font-light">
              <li>
                <a
                  href="#features"
                  onClick={(e) => scrollToHash(e, "#features")}
                  className="hover:text-[#2D3748] transition-colors">
                  Features
                </a>
              </li>
              <li>
                <Link href="/dashboard" className="hover:text-[#2D3748] transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link href="/api-docs" className="hover:text-[#2D3748] transition-colors">
                  API Documentation
                </Link>
              </li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h3 className="text-[#2D3748] font-normal mb-5 text-sm">Company</h3>
            <ul className="space-y-3 text-sm font-light">
              <li>
                <Link href="#contact" className="hover:text-[#2D3748] transition-colors">
                  Contact
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-[#2D3748] transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-[#2D3748] transition-colors">
                  Terms of Service
                </Link>
              </li>
            </ul>
          </div>

          {/* Support */}
          <div>
            <h3 className="text-[#2D3748] font-normal mb-5 text-sm mr-20">Support</h3>
            <ul className="space-y-3 text-sm font-light">
              <li>
                <Link href="/help" className="hover:text-[#2D3748] transition-colors">
                  Help Center
                </Link>
              </li>
              <li>
                <Link href="/login" className="hover:text-[#2D3748] transition-colors">
                  Sign In
                </Link>
              </li>
              <li>
                <Link href="/register" className="hover:text-[#2D3748] transition-colors">
                  Register
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-gray-100 mt-12 pt-8 text-sm text-[#9CA3AF] text-center font-light">
          <p>&copy; {new Date().getFullYear()} LeafXtract. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}