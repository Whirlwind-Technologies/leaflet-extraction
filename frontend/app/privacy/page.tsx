import { Metadata } from "next";
import Link from "next/link";
import LandingNav from "@/components/landing/LandingNav";
import LandingFooter from "@/components/landing/LandingFooter";
import { SUPPORT_EMAIL } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Privacy Policy - LeafXtract",
  description:
    "Learn how LeafXtract handles your data, what we collect, and how we protect your privacy.",
};

const sections = [
  { id: "introduction", label: "Introduction" },
  { id: "information-we-collect", label: "Information We Collect" },
  { id: "how-we-use-your-data", label: "How We Use Your Data" },
  { id: "data-storage-security", label: "Data Storage & Security" },
  { id: "third-party-data-sharing", label: "Third-Party Data Sharing" },
  { id: "data-retention", label: "Data Retention" },
  { id: "your-rights", label: "Your Rights" },
  { id: "cookies-tracking", label: "Cookies & Tracking" },
  { id: "changes-to-this-policy", label: "Changes to This Policy" },
  { id: "contact", label: "Contact" },
];

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <LandingNav />

      <main className="flex-1">
        {/* Header */}
        <section className="bg-[#F5F5F7] border-b border-gray-100">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
            <h1 className="text-4xl sm:text-5xl tracking-tight mb-4">
              <span className="font-normal text-[#1F3C52]">Privacy </span>
              <span className="font-normal text-[#2F79C5]">Policy</span>
            </h1>
            <p className="text-[#6B7280] font-light text-base">
              Last updated: February 2026
            </p>
          </div>
        </section>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
          {/* Table of Contents */}
          <nav className="mb-14 p-8 bg-[#F9FAFB] rounded-2xl">
            <h2 className="text-md font-normal text-[#2D3748] uppercase tracking-wider mb-5">
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
                LeafXtract is an AI-powered SaaS platform for extracting
                structured product data from promotional PDF leaflets. We are
                committed to protecting your privacy and handling your data
                responsibly. This Privacy Policy explains what information we
                collect, how we use it, how we protect it, and what rights you
                have regarding your data.
              </p>
            </section>

            {/* 2. Information We Collect */}
            <section id="information-we-collect">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                2. Information We Collect
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We collect the following types of information when you use our
                platform:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Account information
                    </strong>{" "}
                    &mdash; your name, email address, and a securely hashed
                    version of your password.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Uploaded content
                    </strong>{" "}
                    &mdash; PDF leaflets you upload, extracted product data, and
                    generated page images.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Usage data
                    </strong>{" "}
                    &mdash; processing timestamps, API usage metrics, and
                    feature usage analytics.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Technical data
                    </strong>{" "}
                    &mdash; browser type, IP address, and device information
                    collected automatically during your visits.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      AI interaction data
                    </strong>{" "}
                    &mdash; VLM API requests and responses generated during the
                    extraction processing of your leaflets.
                  </span>
                </li>
              </ul>
            </section>

            {/* 3. How We Use Your Data */}
            <section id="how-we-use-your-data">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                3. How We Use Your Data
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We use the information we collect for the following purposes:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Processing and extracting product data from your uploaded
                    leaflets.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Providing analytics and reporting on your extraction results.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Improving our AI extraction accuracy and overall service
                    quality.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>Account management and customer support.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>Security monitoring and fraud prevention.</span>
                </li>
              </ul>
            </section>

            {/* 4. Data Storage & Security */}
            <section id="data-storage-security">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                4. Data Storage & Security
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We take the security of your data seriously and employ
                industry-standard measures to protect it:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Data is stored in encrypted PostgreSQL databases with
                    strict access controls.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Files are stored in AWS S3 with server-side encryption
                    (AES-256).
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Passwords are hashed using bcrypt, a one-way hashing
                    algorithm, and are never stored in plain text.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    API keys are encrypted with Fernet symmetric encryption
                    before being stored in our database.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Authentication is managed via JWT-based tokens with
                    automatic rotation.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    All data in transit is protected with HTTPS/TLS encryption.
                  </span>
                </li>
              </ul>
            </section>

            {/* 5. Third-Party Data Sharing */}
            <section id="third-party-data-sharing">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                5. Third-Party Data Sharing
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We share data with third parties only when necessary to provide
                our service:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      VLM providers
                    </strong>{" "}
                    (Anthropic Claude, OpenAI, Google Gemini) receive page
                    images solely for the purpose of AI extraction processing.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Cloud infrastructure providers
                    </strong>{" "}
                    (AWS) host our platform and store your files.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We do <strong className="font-normal">not</strong> sell your
                    data to third parties.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We do <strong className="font-normal">not</strong> use your
                    data for training AI models.
                  </span>
                </li>
              </ul>
            </section>

            {/* 6. Data Retention */}
            <section id="data-retention">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                6. Data Retention
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We retain your data according to the following schedule:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Account data
                    </strong>{" "}
                    &mdash; retained while your account is active. Deleted upon
                    request.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Uploaded leaflets and extracted data
                    </strong>{" "}
                    &mdash; retained until you delete them from the platform.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Processing logs
                    </strong>{" "}
                    &mdash; retained for 90 days, then automatically purged.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Export files
                    </strong>{" "}
                    &mdash; automatically deleted after 24 hours.
                  </span>
                </li>
              </ul>
            </section>

            {/* 7. Your Rights */}
            <section id="your-rights">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                7. Your Rights
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                You have the following rights regarding your personal data:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Access
                    </strong>{" "}
                    &mdash; request a copy of all data we hold about you.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Export
                    </strong>{" "}
                    &mdash; download your data in CSV, Excel, or JSON format at
                    any time.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Deletion
                    </strong>{" "}
                    &mdash; request deletion of your account and all associated
                    data.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Correction
                    </strong>{" "}
                    &mdash; update or correct your personal information through
                    your account settings.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Portability
                    </strong>{" "}
                    &mdash; export your data in standard, machine-readable
                    formats.
                  </span>
                </li>
              </ul>
            </section>

            {/* 8. Cookies & Tracking */}
            <section id="cookies-tracking">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                8. Cookies & Tracking
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed mb-4">
                We use a minimal set of cookies to operate the platform:
              </p>
              <ul className="space-y-3 text-[#4A5568] font-light leading-relaxed">
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    <strong className="font-normal text-[#2D3748]">
                      Essential cookies
                    </strong>{" "}
                    for authentication (JWT tokens) and session management.
                    These are required for the platform to function.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We do <strong className="font-normal">not</strong> use
                    third-party tracking cookies.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    We do <strong className="font-normal">not</strong> use
                    advertising cookies.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#5B8DBE] mt-1.5 flex-shrink-0">
                    &bull;
                  </span>
                  <span>
                    Optional analytics cookies may be used if explicitly enabled
                    by you.
                  </span>
                </li>
              </ul>
            </section>

            {/* 9. Changes to This Policy */}
            <section id="changes-to-this-policy">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                9. Changes to This Policy
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                We may update this Privacy Policy from time to time to reflect
                changes in our practices, technology, legal requirements, or
                other factors. When we make significant changes, we will notify
                you via the email address associated with your account.
                Continued use of the platform after such notification
                constitutes acceptance of the updated policy. We encourage you
                to review this page periodically.
              </p>
            </section>

            {/* 10. Contact */}
            <section id="contact">
              <h2 className="text-2xl font-normal text-[#2D3748] mb-4">
                10. Contact
              </h2>
              <p className="text-[#4A5568] font-light leading-relaxed">
                For privacy-related inquiries, you can reach us via the{" "}
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
                  href="/terms"
                  className="text-[#5B8DBE] hover:underline font-normal"
                >
                  Terms of Service
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
