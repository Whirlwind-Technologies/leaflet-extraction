import { Metadata } from "next";
import Link from "next/link";
import LandingNav from "@/components/landing/LandingNav";
import LandingFooter from "@/components/landing/LandingFooter";
import { SUPPORT_EMAIL } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Terms of Service - LeafXtract",
  description:
    "Terms and conditions governing your use of the LeafXtract platform.",
};

const sections = [
  { id: "introduction", label: "Introduction" },
  { id: "account-responsibilities", label: "Account Responsibilities" },
  { id: "acceptable-use", label: "Acceptable Use" },
  { id: "intellectual-property", label: "Intellectual Property" },
  { id: "service-availability", label: "Service Availability" },
  { id: "api-usage", label: "API Usage" },
  { id: "limitation-of-liability", label: "Limitation of Liability" },
  { id: "termination", label: "Termination" },
  { id: "changes-to-these-terms", label: "Changes to These Terms" },
  { id: "governing-law", label: "Governing Law" },
  { id: "contact", label: "Contact" },
];

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <LandingNav />

      <main className="flex-1">
        {/* Header */}
        <section className="bg-[#F5F5F7] border-b border-gray-100">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
            <h1 className="text-4xl sm:text-5xl tracking-tight mb-4">
              <span className="font-normal text-[#1F3C52]">Terms of </span>
              <span className="font-normal text-[#2F79C5]">Service</span>
            </h1>
            <p className="text-[#6B7280] font-light text-base">
              Last updated: February 2026
            </p>
          </div>
        </section>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
          {/* Table of Contents */}
          <nav className="mb-14 p-8 bg-[#F9FAFB] rounded-2xl">
            <h2 className="text-md font-normal text-[#1F3C52] uppercase tracking-wider mb-5">
              Table of Contents
            </h2>
            <ol className="space-y-2.5">
              {sections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="text-[#6B7280] hover:text-[#5B8DBE] transition-colors text-sm font-light"
                  >
                    {index + 1}. {section.label}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          {/* Content */}
          <div className="space-y-14">
            {/* 1. Introduction */}
            <section id="introduction">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                1. Introduction
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                These Terms of Service (&ldquo;Terms&rdquo;) govern your access
                to and use of the LeafXtract platform, including all associated
                services, APIs, and documentation. By creating an account or
                using our platform, you agree to be bound by these Terms. If you
                do not agree, you may not use the service.
              </p>
            </section>

            {/* 2. Account Responsibilities */}
            <section id="account-responsibilities">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                2. Account Responsibilities
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                When you create an account on LeafXtract, you agree to the
                following:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must provide accurate and complete registration
                    information.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You are responsible for maintaining the security of your
                    account, including your password and any API keys.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must not share your account credentials with others.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must be 18 years of age or older to create an account.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Account approval by an administrator may be required before
                    you can access all features of the platform.
                  </span>
                </li>
              </ul>
            </section>

            {/* 3. Acceptable Use */}
            <section id="acceptable-use">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                3. Acceptable Use
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                You agree to use LeafXtract only for lawful purposes and in
                accordance with these Terms:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You may upload promotional leaflets and retail materials for
                    the purpose of data extraction.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must not upload illegal, harmful, or copyrighted content
                    that you do not have the rights to process.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must not attempt to reverse-engineer, decompile, or
                    otherwise abuse the AI extraction service.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must not use automated tools to spam, scrape, or
                    overwhelm the service beyond normal usage patterns.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You must comply with all applicable local, national, and
                    international laws and regulations.
                  </span>
                </li>
              </ul>
            </section>

            {/* 4. Intellectual Property */}
            <section id="intellectual-property">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                4. Intellectual Property
              </h2>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You retain full ownership of all data you upload and all
                    product data extracted from your leaflets.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    LeafXtract owns the platform, AI models, extraction
                    algorithms, and all service infrastructure.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You grant LeafXtract a limited, non-exclusive license to
                    process your uploaded content solely for the purpose of
                    providing the extraction service to you.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    This license terminates immediately when you delete your
                    data or your account.
                  </span>
                </li>
              </ul>
            </section>

            {/* 5. Service Availability */}
            <section id="service-availability">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                5. Service Availability
              </h2>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We strive for high availability but do not guarantee 100%
                    uptime. Occasional downtime may occur for maintenance or
                    unforeseen circumstances.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    The service is provided &ldquo;as is&rdquo; during
                    beta and development phases without warranties of any kind.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We may perform scheduled maintenance with advance notice
                    whenever possible.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We reserve the right to modify, suspend, or discontinue
                    features of the platform with reasonable notice.
                  </span>
                </li>
              </ul>
            </section>

            {/* 6. API Usage */}
            <section id="api-usage">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                6. API Usage
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                Access to the LeafXtract API is subject to the following
                conditions:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    API access is subject to rate limiting and fair use policies.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    API keys are personal to your account and must not be shared
                    with unauthorized parties.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Excessive or abusive usage may result in throttling or
                    temporary suspension of API access.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Webhook endpoints configured in your account must be
                    accessible and respond within 30 seconds.
                  </span>
                </li>
              </ul>
            </section>

            {/* 7. Limitation of Liability */}
            <section id="limitation-of-liability">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                7. Limitation of Liability
              </h2>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    LeafXtract is not liable for the accuracy of extracted data.
                    AI extraction is a best-effort process, and all results
                    should be verified before use in critical applications.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We are not liable for indirect, incidental, special, or
                    consequential damages arising from your use of the platform.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Our total liability to you is limited to the aggregate fees
                    you have paid to LeafXtract in the 12 months preceding the
                    claim.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We are not liable for data loss resulting from user error,
                    including accidental deletion of leaflets or products.
                  </span>
                </li>
              </ul>
            </section>

            {/* 8. Termination */}
            <section id="termination">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                8. Termination
              </h2>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You may delete your account at any time through your account
                    settings.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We may suspend or terminate accounts that violate these
                    Terms, with notice where reasonably possible.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Upon termination, your data will be retained for 30 days to
                    allow you to export it, after which it will be permanently
                    deleted.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    You may request immediate deletion of all your data at any
                    time, which will be processed without the 30-day retention
                    period.
                  </span>
                </li>
              </ul>
            </section>

            {/* 9. Changes to These Terms */}
            <section id="changes-to-these-terms">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                9. Changes to These Terms
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                We may update these Terms of Service from time to time.
                Significant changes will be communicated via the email address
                associated with your account. Your continued use of the platform
                after such changes constitutes acceptance of the updated Terms.
                We encourage you to review this page periodically.
              </p>
            </section>

            {/* 10. Governing Law */}
            <section id="governing-law">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                10. Governing Law
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                These Terms are governed by and construed in accordance with the
                laws of the European Union and the Republic of Slovenia. Any
                disputes arising from these Terms or your use of the platform
                shall be subject to the exclusive jurisdiction of the courts of
                the Republic of Slovenia.
              </p>
            </section>

            {/* 11. Contact */}
            <section id="contact">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                11. Contact
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                Questions about these Terms? Contact us via the{" "}
                <Link
                  href="/#contact"
                  className="text-[#5B8DBE] hover:underline"
                >
                  contact form on our home page
                </Link>{" "}
                or by emailing{" "}
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="text-[#5B8DBE] hover:underline"
                >
                  {SUPPORT_EMAIL}
                </a>
                .
              </p>
            </section>

            {/* Divider and cross-link */}
            <div className="border-t border-gray-100 pt-10 mt-14">
              <p className="text-[#6B7280] font-light text-sm">
                See also our{" "}
                <Link
                  href="/privacy"
                  className="text-[#5B8DBE] hover:underline font-normal"
                >
                  Privacy Policy
                </Link>
                .
              </p>

              <a
                href="#"
                className="inline-block mt-6 text-sm text-[#6B7280] hover:text-[#5B8DBE] transition-colors font-light"
              >
                Back to top
              </a>
            </div>
          </div>
        </div>
      </main>

      <LandingFooter />
    </div>
  );
}
