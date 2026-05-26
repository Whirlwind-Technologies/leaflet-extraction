"use client";

import { useState, useEffect, useRef, useCallback, FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Send, Mail, MessageSquare, Loader2, CheckCircle2 } from "lucide-react";
import { SUPPORT_EMAIL } from "@/lib/constants";

/** Minimal email format validation (not exhaustive, just catches obvious mistakes). */
function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Loads the reCAPTCHA v3 script dynamically and returns the token.
 * Only called when NEXT_PUBLIC_RECAPTCHA_SITE_KEY is configured.
 */
async function getRecaptchaToken(siteKey: string): Promise<string> {
  // Load the script if not already present
  if (!document.querySelector(`script[src*="recaptcha"]`)) {
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `https://www.google.com/recaptcha/api.js?render=${siteKey}`;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load reCAPTCHA"));
      document.head.appendChild(script);
    });
  }

  // Wait for grecaptcha to be ready
  return new Promise<string>((resolve, reject) => {
    const w = window as unknown as { grecaptcha?: { ready: (cb: () => void) => void; execute: (key: string, opts: { action: string }) => Promise<string> } };
    if (!w.grecaptcha) {
      reject(new Error("reCAPTCHA not available"));
      return;
    }
    w.grecaptcha.ready(() => {
      w.grecaptcha!
        .execute(siteKey, { action: "contact" })
        .then(resolve)
        .catch(reject);
    });
  });
}

export default function ContactSection() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [timestamp, setTimestamp] = useState<number>(0);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const formRef = useRef<HTMLFormElement>(null);

  // Set timestamp on mount for bot detection
  useEffect(() => {
    setTimestamp(Math.floor(Date.now() / 1000));
  }, []);

  const handleSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setErrorMessage("");

      // Client-side validation
      const trimmedName = name.trim();
      const trimmedEmail = email.trim();
      const trimmedMessage = message.trim();

      if (!trimmedName || !trimmedEmail || !trimmedMessage) {
        setErrorMessage("Please fill in all required fields.");
        return;
      }

      if (!isValidEmail(trimmedEmail)) {
        setErrorMessage("Please enter a valid email address.");
        return;
      }

      if (trimmedName.length > 100) {
        setErrorMessage("Name must be 100 characters or less.");
        return;
      }

      if (trimmedMessage.length > 2000) {
        setErrorMessage("Message must be 2000 characters or less.");
        return;
      }

      setIsSubmitting(true);

      try {
        // Optional reCAPTCHA v3
        let recaptcha_token: string | undefined;
        const recaptchaSiteKey = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY;
        if (recaptchaSiteKey) {
          try {
            recaptcha_token = await getRecaptchaToken(recaptchaSiteKey);
          } catch {
            // If reCAPTCHA fails, proceed without it -- the backend
            // should treat a missing token as optional
          }
        }

        const apiUrl =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

        const response = await fetch(`${apiUrl}/api/v1/contact`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: trimmedName,
            email: trimmedEmail,
            message: trimmedMessage,
            website, // honeypot -- should be empty for real users
            timestamp,
            recaptcha_token,
          }),
        });

        if (response.ok) {
          setIsSuccess(true);
        } else if (response.status === 429) {
          setErrorMessage("Too many submissions. Please try again later.");
        } else if (response.status === 400) {
          const data = await response.json().catch(() => null);
          setErrorMessage(
            data?.detail || "Invalid submission. Please check your inputs."
          );
        } else {
          setErrorMessage("Something went wrong. Please try again.");
        }
      } catch {
        setErrorMessage("Something went wrong. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [name, email, message, website, timestamp]
  );

  return (
    <section id="contact" className="py-24 bg-gradient-to-br">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left: Description */}
          <div className="lg:sticky lg:top-32">
            <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider mb-6">
              Get in Touch
            </span>

            <h2 className="text-4xl md:text-5xl font-light mb-6">
              <span className="font-normal text-[#2D3748]">Contact</span>{" "}
              <span className="font-light text-[#2F7C95]">Us</span>
            </h2>

            <p className="text-lg text-[#6B7280] font-light leading-relaxed mb-10 max-w-lg">
              Have a question or want to learn more? We&apos;d love to hear from you.
              Fill out the form and our team will get back to you shortly.
            </p>

            <div className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-[#F9FAFB] rounded-xl flex items-center justify-center">
                  <Mail
                    className="h-5 w-5 text-[#5B8DBE]"
                    strokeWidth={1.5}
                  />
                </div>
                <div>
                  <p className="text-sm font-normal text-[#2D3748]">Email</p>
                  <p className="text-sm text-[#6B7280] font-light">
                    {SUPPORT_EMAIL}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-[#F9FAFB] rounded-xl flex items-center justify-center">
                  <MessageSquare
                    className="h-5 w-5 text-[#5B8DBE]"
                    strokeWidth={1.5}
                  />
                </div>
                <div>
                  <p className="text-sm font-normal text-[#2D3748]">
                    Response Time
                  </p>
                  <p className="text-sm text-[#6B7280] font-light">
                    We typically respond within 24 hours
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="bg-[#F9FAFB] rounded-2xl p-8 md:p-10">
            {isSuccess ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center mb-6 shadow-sm">
                  <CheckCircle2
                    className="h-8 w-8 text-green-500"
                    strokeWidth={1.5}
                  />
                </div>
                <h3 className="text-2xl font-normal text-[#2D3748] mb-3">
                  Thank you!
                </h3>
                <p className="text-[#6B7280] font-light max-w-sm">
                  We&apos;ve received your message and will get back to you shortly.
                </p>
              </div>
            ) : (
              <form
                ref={formRef}
                onSubmit={handleSubmit}
                noValidate
                className="space-y-6"
              >
                {/* Honeypot field -- hidden from real users */}
                <div
                  aria-hidden="true"
                  style={{
                    position: "absolute",
                    left: "-9999px",
                    opacity: 0,
                    pointerEvents: "none",
                  }}
                >
                  <label htmlFor="website">Website</label>
                  <input
                    type="text"
                    id="website"
                    name="website"
                    tabIndex={-1}
                    autoComplete="off"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                  />
                </div>

                {/* Name */}
                <div className="space-y-2">
                  <Label
                    htmlFor="contact-name"
                    className="text-sm font-normal text-[#2D3748]"
                  >
                    Name <span className="text-red-400">*</span>
                  </Label>
                  <Input
                    id="contact-name"
                    type="text"
                    required
                    maxLength={100}
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-white border-gray-200 focus-visible:border-[#5B8DBE] focus-visible:ring-[#5B8DBE]/20"
                  />
                </div>

                {/* Email */}
                <div className="space-y-2">
                  <Label
                    htmlFor="contact-email"
                    className="text-sm font-normal text-[#2D3748]"
                  >
                    Email <span className="text-red-400">*</span>
                  </Label>
                  <Input
                    id="contact-email"
                    type="email"
                    required
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-white border-gray-200 focus-visible:border-[#5B8DBE] focus-visible:ring-[#5B8DBE]/20"
                  />
                </div>

                {/* Message */}
                <div className="space-y-2">
                  <Label
                    htmlFor="contact-message"
                    className="text-sm font-normal text-[#2D3748]"
                  >
                    Message <span className="text-red-400">*</span>
                  </Label>
                  <Textarea
                    id="contact-message"
                    required
                    maxLength={2000}
                    rows={5}
                    placeholder="Tell us how we can help..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-white border-gray-200 focus-visible:border-[#5B8DBE] focus-visible:ring-[#5B8DBE]/20 min-h-[120px]"
                  />
                  <p className="text-xs text-[#9CA3AF] font-light text-right">
                    {message.length}/2000
                  </p>
                </div>

                {/* Error message */}
                {errorMessage && (
                  <div className="rounded-lg bg-red-50 border border-red-100 px-4 py-3">
                    <p className="text-sm text-red-600 font-light">
                      {errorMessage}
                    </p>
                  </div>
                )}

                {/* Submit */}
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  size="lg"
                  className="w-full bg-[#4A5568] hover:bg-[#5B8DBE] text-white font-normal px-10 py-6 text-base rounded-xl shadow-sm transition-all duration-300"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      Send Message
                      <Send className="ml-2 h-5 w-5" />
                    </>
                  )}
                </Button>
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
