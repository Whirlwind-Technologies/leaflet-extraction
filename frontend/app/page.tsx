import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/actions/auth";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import LandingNav from "@/components/landing/LandingNav";
import LandingFooter from "@/components/landing/LandingFooter";
import ContactSection from "@/components/landing/ContactSection";
import {
  Target,
  Clock,
  FileText,
  Download,
  Cpu,
  Database,
  Shield,
} from "lucide-react";

export default async function HomePage() {
  const user = await getCurrentUser();

  // If user is logged in, redirect to dashboard
  if (user) {
    redirect("/dashboard");
  }

  // Otherwise, show landing page
  return (
    <div className="min-h-screen flex flex-col bg-[#F5F5F7]">
      <LandingNav />
      <main className="flex-1">
        <div className="flex flex-col">
          {/* Hero Section - Minimal, Spacious Design */}
          <section className="relative bg-white from-[#FAFAFA] via-[#F5F5F7] to-[#EEEEEE] min-h-[630px] flex items-center overflow-hidden">
            {/* Subtle background pattern */}
            <div className="absolute inset-0 opacity-30">
              <div className="absolute top-20 right-10 w-96 h-96 bg-gradient-to-br from-[#E8E8EA] to-transparent rounded-full blur-3xl"></div>
              <div className="absolute bottom-20 left-10 w-96 h-96 bg-gradient-to-br from-[#D8D8DA] to-transparent rounded-full blur-3xl"></div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full pb-24 relative z-10">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
                {/* Left: Content */}
                <div>
                  <div className="inline-block mb-3">
                    <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider">
                      AI-Powered Platform
                    </span>
                  </div>

                  <h1 className="text-3xl md:text-5xl font-light mb-6 leading-[1.1] tracking-tight">
                    <span className="text-[#2D3748] font-normal">Intelligent Solutions for</span>
                    <br />
                    <span className="text-[#2D3748] font-normal">Your </span>
                    <span className="text-[#2F79C5] font-normal">Data Extraction</span>
                  </h1>

                  <p className="text-lg md:text-xl text-[#6B7280] mb-10 leading-relaxed font-normal max-w-xl">
                    Specialized in AI-powered leaflet processing. From product detection to structured data export - fully automated.
                  </p>

                  <div className="flex flex-col sm:flex-row gap-4 items-start">
                    <Link href="#features">
                      <Button
                        size="lg"
                        variant="ghost"
                        className="text-white font-normal text-base bg-[#2F79C5] hover:bg-[#1F3C52] hover:text-white"
                      >
                        Discover Our Expertise
                      </Button>
                    </Link>
                  </div>
                </div>

                {/* Right: Abstract Visual Element */}
                <div className="hidden lg:flex items-center justify-center">
                  <Image src="/Group-80.svg" alt="" width={400} height={400} />
                </div>
              </div>
            </div>
          </section>

          {/* Services Badge Section */}
          <section id="services" className="py-16 bg-gradient-to-br">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="mb-5 text-center">
                <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider">
                  Our Services
                </span>
              </div>

              <h2 className="text-4xl md:text-5xl font-light mb-6 text-[#2D3748] max-w-3xl mx-auto text-center">
                <span className="font-normal">Empowering your business</span>
                <br />
                <span className="font-light text-[#2F79C5]">with our know-how.</span>
              </h2>

              <p className="text-lg text-[#6B7280] font-light leading-relaxed max-w-2xl mx-auto text-center mb-16">
                Our team of experts provide guidance and drive digital transformation in various fields.
              </p>

              {/* Service Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="bg-[#F9FAFB] rounded-2xl p-10 hover:shadow-lg transition-all duration-300">
                  <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center mb-6 shadow-sm">
                    <Cpu className="h-7 w-7 text-[#2D3748]" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-xl font-normal text-[#2F79C5] mb-3">
                    AI-Powered Extraction
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Advanced vision models automatically detect products, prices, and promotional data from any retail leaflet.
                  </p>
                </div>

                <div className="bg-[#F9FAFB] rounded-2xl p-10 hover:shadow-lg transition-all duration-300">
                  <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center mb-6 shadow-sm">
                    <Database className="h-7 w-7 text-[#2D3748]" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-xl font-normal text-[#2F79C5] mb-3">
                    Structured Data Output
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Export clean, structured product data in JSON, CSV, or Excel format ready for integration.
                  </p>
                </div>

                <div className="bg-[#F9FAFB] rounded-2xl p-10 hover:shadow-lg transition-all duration-300">
                  <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center mb-6 shadow-sm">
                    <Shield className="h-7 w-7 text-[#2D3748]" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-xl font-normal text-[#2F79C5] mb-3">
                    Enterprise-Grade Security
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Complete data isolation, encryption, and compliance with industry security standards.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Key Capabilities Section */}
          <section id="features" className="py-24 bg-white">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="mb-5 text-left">
                <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider">
                  CORE PLATFORM FEATURES
                </span>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-16 items-center">
                {/* Left: Stats/Features */}
                <div>
                  <h2 className="text-4xl md:text-5xl font-light mb-8 text-[#2D3748]">
                    <span className="font-normal">Platform</span> <span className="font-nomral text-[#2F79C5]">Capabilities.</span>
                  </h2>
                  <div className="space-y-8">
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm">
                        <Target className="h-6 w-6 text-[#5B8DBE]" strokeWidth={1.5} />
                      </div>
                      <div>
                        <h3 className="text-lg font-normal text-[#2D3748]">
                          95%+ Accuracy Rate
                        </h3>
                        <p className="text-[#6B7280] font-light leading-relaxed">
                          State-of-the-art vision models deliver exceptional accuracy, reducing manual review by 90%.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm">
                        <Clock className="h-6 w-6 text-[#5B8DBE]" strokeWidth={1.5} />
                      </div>
                      <div>
                        <h3 className="text-lg font-normal text-[#2D3748]">
                          Lightning Fast Processing
                        </h3>
                        <p className="text-[#6B7280] font-light leading-relaxed">
                          Process multi-page leaflets in minutes. What used to take hours now takes seconds.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm">
                        <FileText className="h-6 w-6 text-[#5B8DBE]" strokeWidth={1.5} />
                      </div>
                      <div>
                        <h3 className="text-lg font-normal text-[#2D3748]">
                          Multi-Page Support
                        </h3>
                        <p className="text-[#6B7280] font-light leading-relaxed">
                          Handle complex leaflets with automatic segmentation and product grouping across pages.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-sm">
                        <Download className="h-6 w-6 text-[#5B8DBE]" strokeWidth={1.5} />
                      </div>
                      <div>
                        <h3 className="text-lg font-normal text-[#2D3748]">
                          Flexible Export Options
                        </h3>
                        <p className="text-[#6B7280] font-light leading-relaxed">
                          Export to JSON, CSV, or Excel. Integrate seamlessly via our REST API.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Stats Box */}
                <div className="bg-white rounded-2xl p-6 shadow-md max-w-md mx-auto w-full">
                  <h3 className="text-2xl font-normal text-[#2D3748] mb-5">
                    Performance Metrics
                  </h3>

                  <div className="space-y-10">
                    <div>
                      <div className="flex items-end justify-between mb-3">
                        <span className="text-sm font-normal text-[#6B7280] uppercase tracking-wider">
                          Processing Speed
                        </span>
                        <span className="text-3xl font-normal text-[#2F79C5]">90%</span>
                      </div>
                      <div className="w-full bg-[#E5E7EB] rounded-full h-1.5">
                        <div className="bg-gradient-to-r from-[#7B8FA1] to-[#5B8DBE] h-1.5 rounded-full w-[90%] transition-all duration-1000"></div>
                      </div>
                      <p className="text-xs text-[#9CA3AF] mt-2 font-light">faster than manual processing</p>
                    </div>

                    <div>
                      <div className="flex items-end justify-between mb-3">
                        <span className="text-sm font-normal text-[#6B7280] uppercase tracking-wider">
                          Accuracy Rate
                        </span>
                        <span className="text-3xl font-normal text-[#2F79C5]">95%+</span>
                      </div>
                      <div className="w-full bg-[#E5E7EB] rounded-full h-1.5">
                        <div className="bg-gradient-to-r from-[#7B8FA1] to-[#5B8DBE] h-1.5 rounded-full w-[95%] transition-all duration-1000"></div>
                      </div>
                      <p className="text-xs text-[#9CA3AF] mt-2 font-light">industry-leading precision</p>
                    </div>

                    <div>
                      <div className="flex items-end justify-between mb-3">
                        <span className="text-sm font-normal text-[#6B7280] uppercase tracking-wider">
                          Cost Reduction
                        </span>
                        <span className="text-3xl font-normal text-[#2F79C5]">80%</span>
                      </div>
                      <div className="w-full bg-[#E5E7EB] rounded-full h-1.5">
                        <div className="bg-gradient-to-r from-[#7B8FA1] to-[#5B8DBE] h-1.5 rounded-full w-[80%] transition-all duration-1000"></div>
                      </div>
                      <p className="text-xs text-[#9CA3AF] mt-2 font-light">operational savings</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* How It Works Section */}
          <section id="process" className="py-24 bg-gradient-to-br">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="text-center mb-20">
                <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider mb-6">
                  Simple Process
                </span>

                <h2 className="text-4xl md:text-5xl font-light mb-3 text-[#2D3748]">
                  <span className="font-normal">Three Steps</span> <span className="font-light text-[#2F79C5]">to Structured Data</span>
                </h2>

                <p className="text-lg text-[#6B7280] font-light max-w-2xl mx-auto">
                  From PDF upload to actionable insights in minutes
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-[#7B8FA1] to-[#5B8DBE] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-sm">
                    <span className="text-2xl font-light text-white">1</span>
                  </div>
                  <h3 className="text-xl font-normal text-[#2D3748] mb-4">
                    Upload Leaflet
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Simply drag and drop your PDF leaflet. Multi-page documents are fully supported.
                  </p>
                </div>

                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-[#7B8FA1] to-[#5B8DBE] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-sm">
                    <span className="text-2xl font-light text-white">2</span>
                  </div>
                  <h3 className="text-xl font-normal text-[#2D3748] mb-4">
                    AI Processing
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Our AI automatically extracts products, prices, brands, and promotional information.
                  </p>
                </div>

                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-[#7B8FA1] to-[#5B8DBE] rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-sm">
                    <span className="text-2xl font-light text-white">3</span>
                  </div>
                  <h3 className="text-xl font-normal text-[#2D3748] mb-4">
                    Export Data
                  </h3>
                  <p className="text-[#6B7280] font-light leading-relaxed">
                    Review, edit, and export to JSON, CSV, or Excel. Integrate via REST API.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* CTA Section */}
          <section className="py-24 relative">
            <Image
              src="/Landing-Join-BG.svg"
              alt=""
              fill
              className="object-cover"
            />
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
              <h2 className="text-4xl md:text-5xl font-light mb-6 text-[#2D3748]">
                <span className="font-normal text-white">Ready to Transform</span>
                <br />
                <span className="font-light text-white">Your Leaflet Processing?</span>
              </h2>

              <p className="text-lg text-white font-light mb-5 max-w-3xl mx-auto leading-relaxed">
                Join businesses using AI to automate product data extraction and reduce operational costs.
              </p>

              <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
                <Link href="/register">
                  <Button
                    size="lg"
                    className="bg-[#4BAE62] hover:bg-[#1F3C52] text-white font-normal px-10 py-6 text-base rounded-lg shadow-sm transition-all duration-300"
                  >
                    Get Started Today
                  </Button>
                </Link>
              </div>
            </div>
          </section>

          {/* Contact Form Section */}
          <ContactSection />
        </div>
      </main>
      <LandingFooter />
    </div>
  );
}
