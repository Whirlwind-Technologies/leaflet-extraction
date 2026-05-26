"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import Link from "next/link";
import LandingNav from "@/components/landing/LandingNav";
import LandingFooter from "@/components/landing/LandingFooter";
import {
  Search,
  BookOpen,
  Sparkles,
  Settings,
  HelpCircle,
  MessageCircle,
  ChevronDown,
  Upload,
  Eye,
  CheckCircle2,
  Cpu,
  ClipboardList,
  Download,
  BarChart3,
  Webhook,
  KeyRound,
  Users,
  Bell,
  Mail,
  Menu,
  X,
} from "lucide-react";
import { SUPPORT_EMAIL } from "@/lib/constants";

/* ---------------------------------------------------------------------------
 * Types
 * --------------------------------------------------------------------------- */

/** A single content block within a subsection (paragraph, list, or step list). */
interface ContentBlock {
  type: "paragraph" | "list" | "steps";
  text?: string;
  items?: string[];
}

/** A subsection with a title, icon, and content blocks. */
interface Subsection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: ContentBlock[];
}

/** A FAQ item with question and answer. */
interface FaqItem {
  question: string;
  answer: string;
}

/** A top-level section in the help center. */
interface Section {
  id: string;
  title: string;
  icon: React.ReactNode;
  subsections?: Subsection[];
  faqItems?: FaqItem[];
  contactContent?: boolean;
}

/* ---------------------------------------------------------------------------
 * Data
 * --------------------------------------------------------------------------- */

const SECTIONS: Section[] = [
  /* ---- 1. Getting Started ---- */
  {
    id: "getting-started",
    title: "Getting Started",
    icon: <BookOpen className="h-4 w-4" strokeWidth={1.5} />,
    subsections: [
      {
        id: "creating-an-account",
        title: "Creating an Account",
        icon: <Users className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Visit the registration page and fill in your details.",
              "Personal accounts require administrator approval before you can log in.",
              "Business accounts go through a separate approval process.",
              "You will receive an email once your account is approved.",
            ],
          },
        ],
      },
      {
        id: "uploading-your-first-leaflet",
        title: "Uploading Your First Leaflet",
        icon: <Upload className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Navigate to the Upload page from the dashboard.",
              "Upload a PDF file (up to 100 MB) of a promotional leaflet.",
              "Optionally specify retailer, country, and currency.",
              "Multi-page PDFs and ZIP archives of images are supported.",
              'Click "Process" to start extraction.',
            ],
          },
        ],
      },
      {
        id: "understanding-the-extraction-process",
        title: "Understanding the Extraction Process",
        icon: <Cpu className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "steps",
            items: [
              "PDF Processing (30-60 s): Pages are converted to high-resolution images.",
              "AI Extraction (2-4 min): Our AI analyzes each page to identify products, prices, and promotions.",
              "Validation (1-5 s): Extracted data is automatically validated for accuracy.",
              "Image Extraction (30-90 s): Individual product images are cropped from page images.",
            ],
          },
          {
            type: "paragraph",
            text: "Products with high confidence (>90%) are auto-approved; others are queued for review.",
          },
        ],
      },
      {
        id: "reviewing-and-approving-products",
        title: "Reviewing and Approving Products",
        icon: <Eye className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Navigate to a leaflet's detail page to see all extracted products.",
              "Click on a product to open the review editor.",
              "The left panel shows the page image with the product's bounding box highlighted.",
              "The right panel shows extracted data fields you can edit.",
              "Use keyboard shortcuts: A (approve), R (reject), S (save draft), Alt+Arrow (navigate).",
              "Approved products are ready for export.",
            ],
          },
        ],
      },
    ],
  },

  /* ---- 2. Features ---- */
  {
    id: "features",
    title: "Features",
    icon: <Sparkles className="h-4 w-4" strokeWidth={1.5} />,
    subsections: [
      {
        id: "ai-powered-extraction",
        title: "AI-Powered Extraction",
        icon: <Cpu className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Uses Vision-Language Models (VLMs) to understand page layouts.",
              "Detects product cards, prices, discounts, and promotional badges.",
              "Supports multiple languages (Slovenian, Croatian, Serbian, and more).",
              "No template setup required -- works with any retailer format.",
              "95%+ accuracy on well-formatted leaflets.",
            ],
          },
        ],
      },
      {
        id: "product-review-workflow",
        title: "Product Review Workflow",
        icon: (
          <ClipboardList
            className="h-5 w-5 text-[#5B8DBE]"
            strokeWidth={1.5}
          />
        ),
        content: [
          {
            type: "list",
            items: [
              "Auto-approval: Products above 90% confidence are automatically approved.",
              "Review queue: Lower-confidence products are flagged for human review.",
              "Inline editing: Edit any field directly in the review interface.",
              "Batch operations: Approve or reject multiple products at once.",
              "Review history: Track all changes made to each product.",
            ],
          },
        ],
      },
      {
        id: "export-options",
        title: "Export Options",
        icon: (
          <Download className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
        ),
        content: [
          {
            type: "list",
            items: [
              "CSV: Standard comma-separated values, compatible with Excel and Google Sheets.",
              "Excel: Native .xlsx format with formatted headers.",
              "JSON: Structured data format for API integrations.",
              "Export all products, filtered subsets, or selected items.",
              "Product images can be included as URLs or base64 data.",
            ],
          },
        ],
      },
      {
        id: "analytics-dashboard",
        title: "Analytics Dashboard",
        icon: (
          <BarChart3 className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
        ),
        content: [
          {
            type: "list",
            items: [
              "Processing statistics: leaflets processed, products extracted, accuracy rates.",
              "Date range filtering with customizable time periods.",
              "Quality metrics: auto-approval rate, review times, confidence distributions.",
            ],
          },
        ],
      },
      {
        id: "api-access-and-webhooks",
        title: "API Access and Webhooks",
        icon: (
          <Webhook className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
        ),
        content: [
          {
            type: "list",
            items: [
              "RESTful API with JWT authentication.",
              "API keys for B2B integrations.",
              "Webhooks for real-time notifications (extraction complete, products approved, etc.).",
              "Full API documentation available at /api-docs.",
            ],
          },
        ],
      },
    ],
  },

  /* ---- 3. Settings & Configuration ---- */
  {
    id: "settings",
    title: "Settings & Configuration",
    icon: <Settings className="h-4 w-4" strokeWidth={1.5} />,
    subsections: [
      {
        id: "adding-your-own-ai-provider",
        title: "Adding Your Own AI Provider",
        icon: <Cpu className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Navigate to Settings > AI Providers.",
              'Click "Add Provider" and select your provider (Anthropic, OpenAI, Google, Azure, AWS).',
              "Enter your API key (encrypted and stored securely).",
              "Set monthly budget limits to control costs.",
              "Test the connection before saving.",
            ],
          },
        ],
      },
      {
        id: "managing-organization-members",
        title: "Managing Organization Members",
        icon: <Users className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Navigate to Settings > Organization.",
              "Invite team members by email.",
              "Assign roles: Owner, Admin, Member.",
              "Manage permissions and access levels.",
            ],
          },
        ],
      },
      {
        id: "configuring-webhooks",
        title: "Configuring Webhooks",
        icon: <Bell className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />,
        content: [
          {
            type: "list",
            items: [
              "Navigate to Settings > Webhooks.",
              "Add webhook URL and select events to listen for.",
              "Webhooks use HMAC-SHA256 signatures for security.",
              "Failed deliveries are retried automatically (up to 3 times).",
              "View delivery logs for debugging.",
            ],
          },
        ],
      },
      {
        id: "api-key-management",
        title: "API Key Management",
        icon: (
          <KeyRound className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
        ),
        content: [
          {
            type: "list",
            items: [
              "Navigate to Settings > API Keys.",
              "Generate new API keys for external integrations.",
              "Keys can be revoked at any time.",
              "Use the X-API-Key header for authentication.",
            ],
          },
        ],
      },
    ],
  },

  /* ---- 4. FAQ ---- */
  {
    id: "faq",
    title: "FAQ",
    icon: <HelpCircle className="h-4 w-4" strokeWidth={1.5} />,
    faqItems: [
      {
        question: "What file formats are supported?",
        answer:
          "Currently, LeafXtract supports PDF files and ZIP archives containing images (PNG, JPG). PDFs can be single or multi-page (up to 50 pages). Maximum file size is 100 MB.",
      },
      {
        question: "How accurate is the extraction?",
        answer:
          "Our AI achieves 95%+ accuracy on well-formatted promotional leaflets. Accuracy depends on image quality, layout complexity, and language. Products with lower confidence are flagged for human review.",
      },
      {
        question: "How long does processing take?",
        answer:
          "A typical leaflet (4-50 pages) takes 2-4 minutes to process. This includes page conversion, AI extraction, validation, and image cropping. You will see real-time progress updates.",
      },
      {
        question: "What happens if the extraction is wrong?",
        answer:
          "Products that do not meet the confidence threshold are automatically queued for review. You can edit any field, adjust bounding boxes, and re-extract product images. All changes are tracked in the review history.",
      },
      {
        question: "Is my data secure?",
        answer:
          "Yes. All data is encrypted at rest and in transit. Passwords are hashed with bcrypt, API keys are encrypted with Fernet. We follow industry best practices for data security. See our Privacy Policy for details.",
      },
      {
        question: "How do I export my data?",
        answer:
          'Navigate to any leaflet or the products page and click "Export." Choose your format (CSV, Excel, JSON), select which products to include, and download. Large exports are processed in the background.',
      },
      {
        question: "What VLM providers are supported?",
        answer:
          "LeafXtract supports Anthropic Claude (primary), OpenAI GPT-4V, Google Gemini, Azure OpenAI, and AWS Bedrock. You can add your own API keys in Settings > AI Providers.",
      },
      {
        question: "Can I use LeafXtract with my own AI provider?",
        answer:
          "Yes! Add your own provider API key in Settings to use your preferred model. The platform handles the rest -- prompt engineering, image processing, and response parsing.",
      },
      {
        question: "How do I delete my account?",
        answer:
          "Contact support or navigate to Settings > Account. Account deletion removes all your data, including uploaded leaflets and extracted products. This action is irreversible.",
      },
    ],
  },

  /* ---- 5. Contact Support ---- */
  {
    id: "contact-support",
    title: "Contact Support",
    icon: <MessageCircle className="h-4 w-4" strokeWidth={1.5} />,
    contactContent: true,
  },
];

/* ---------------------------------------------------------------------------
 * Helpers
 * --------------------------------------------------------------------------- */

/**
 * Collect all searchable text from a section into a single lowercase string
 * so we can do a fast substring match for the client-side search.
 */
function sectionSearchableText(section: Section): string {
  const parts: string[] = [section.title];

  if (section.subsections) {
    for (const sub of section.subsections) {
      parts.push(sub.title);
      for (const block of sub.content) {
        if (block.text) parts.push(block.text);
        if (block.items) parts.push(...block.items);
      }
    }
  }

  if (section.faqItems) {
    for (const faq of section.faqItems) {
      parts.push(faq.question, faq.answer);
    }
  }

  if (section.contactContent) {
    parts.push(
      "contact support",
      "question not answered",
      "get in touch",
      SUPPORT_EMAIL
    );
  }

  return parts.join(" ").toLowerCase();
}

/**
 * Check whether a single FAQ item matches the query.
 */
function faqItemMatches(item: FaqItem, query: string): boolean {
  const haystack = `${item.question} ${item.answer}`.toLowerCase();
  return haystack.includes(query);
}

/**
 * Check whether a subsection matches the query.
 */
function subsectionMatches(sub: Subsection, query: string): boolean {
  const parts: string[] = [sub.title];
  for (const block of sub.content) {
    if (block.text) parts.push(block.text);
    if (block.items) parts.push(...block.items);
  }
  return parts.join(" ").toLowerCase().includes(query);
}

/* ---------------------------------------------------------------------------
 * Sub-Components
 * --------------------------------------------------------------------------- */

/** Renders a single FAQ accordion item. */
function FaqAccordionItem({
  item,
  isOpen,
  onToggle,
}: {
  item: FaqItem;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-6 py-5 text-left hover:bg-[#F9FAFB] transition-colors"
      >
        <span className="text-[#2D3748] font-normal text-sm pr-4">
          {item.question}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-[#6B7280] flex-shrink-0 transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
          strokeWidth={1.5}
        />
      </button>
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isOpen ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-6 pb-5 text-[#6B7280] text-sm font-light leading-relaxed">
          {item.answer}
        </div>
      </div>
    </div>
  );
}

/** Renders a subsection card with its content blocks. */
function SubsectionCard({ sub }: { sub: Subsection }) {
  return (
    <div id={sub.id} className="scroll-mt-28">
      <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-50">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 bg-[#F9FAFB] rounded-xl flex items-center justify-center flex-shrink-0">
            {sub.icon}
          </div>
          <h3 className="text-lg font-normal text-[#2D3748]">{sub.title}</h3>
        </div>

        <div className="space-y-4">
          {sub.content.map((block, blockIdx) => {
            if (block.type === "paragraph") {
              return (
                <p
                  key={blockIdx}
                  className="text-[#6B7280] text-sm font-light leading-relaxed"
                >
                  {block.text}
                </p>
              );
            }

            if (block.type === "list" && block.items) {
              return (
                <ul key={blockIdx} className="space-y-2.5">
                  {block.items.map((item, itemIdx) => (
                    <li
                      key={itemIdx}
                      className="flex items-start gap-3 text-[#6B7280] text-sm font-light leading-relaxed"
                    >
                      <CheckCircle2
                        className="h-4 w-4 text-[#5B8DBE] flex-shrink-0 mt-0.5"
                        strokeWidth={1.5}
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              );
            }

            if (block.type === "steps" && block.items) {
              return (
                <ol key={blockIdx} className="space-y-3">
                  {block.items.map((item, itemIdx) => (
                    <li
                      key={itemIdx}
                      className="flex items-start gap-3 text-[#6B7280] text-sm font-light leading-relaxed"
                    >
                      <span className="flex-shrink-0 w-6 h-6 bg-[#4A5568] text-white text-xs rounded-lg flex items-center justify-center font-normal mt-0.5">
                        {itemIdx + 1}
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              );
            }

            return null;
          })}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Main Page Component
 * --------------------------------------------------------------------------- */

export default function HelpCenterPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [openFaqIndices, setOpenFaqIndices] = useState<Set<number>>(new Set());
  const [activeSection, setActiveSection] = useState<string>(SECTIONS[0].id);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  /** Refs for each section heading so IntersectionObserver can track them. */
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const normalizedQuery = searchQuery.trim().toLowerCase();

  /* ---- Filter sections/subsections/faq based on search query ---- */

  const filteredSections = useMemo(() => {
    if (!normalizedQuery) return SECTIONS;

    return SECTIONS.map((section) => {
      const sectionText = sectionSearchableText(section);
      const sectionMatchesFull = sectionText.includes(normalizedQuery);

      /* If the whole section matches, return it as-is */
      if (sectionMatchesFull && !section.subsections && !section.faqItems) {
        return section;
      }

      /* Filter subsections individually */
      const filteredSubs = section.subsections?.filter((sub) =>
        subsectionMatches(sub, normalizedQuery)
      );

      /* Filter FAQ items individually */
      const filteredFaq = section.faqItems?.filter((faq) =>
        faqItemMatches(faq, normalizedQuery)
      );

      const hasContent =
        (filteredSubs && filteredSubs.length > 0) ||
        (filteredFaq && filteredFaq.length > 0) ||
        (section.contactContent && sectionMatchesFull);

      if (!hasContent) return null;

      return {
        ...section,
        subsections: filteredSubs,
        faqItems: filteredFaq,
      };
    }).filter(Boolean) as Section[];
  }, [normalizedQuery]);

  /* ---- Intersection Observer for active sidebar highlight ---- */

  useEffect(() => {
    /* Only observe when not searching */
    if (normalizedQuery) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      {
        rootMargin: "-120px 0px -60% 0px",
        threshold: 0,
      }
    );

    /* Observe all section headings */
    for (const section of SECTIONS) {
      const el = sectionRefs.current[section.id];
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, [normalizedQuery]);

  /* ---- Callbacks ---- */

  const handleSidebarClick = useCallback(
    (sectionId: string) => {
      setMobileNavOpen(false);
      const el = document.getElementById(sectionId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
    []
  );

  const toggleFaq = useCallback((index: number) => {
    setOpenFaqIndices((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  /* ---- Sidebar content (shared between desktop and mobile) ---- */

  const sidebarContent = (
    <nav className="space-y-1">
      {SECTIONS.map((section) => {
        const isActive = activeSection === section.id;
        const isVisible = filteredSections.some((s) => s.id === section.id);

        if (normalizedQuery && !isVisible) {
          return null;
        }

        return (
          <button
            key={section.id}
            type="button"
            onClick={() => handleSidebarClick(section.id)}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all duration-150 ${
              isActive
                ? "bg-[#F0F4F8] text-[#2D3748] font-normal"
                : "text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#2D3748] font-light"
            }`}
          >
            <span
              className={`flex-shrink-0 ${
                isActive ? "text-[#5B8DBE]" : "text-[#9CA3AF]"
              }`}
            >
              {section.icon}
            </span>
            <span>{section.title}</span>
          </button>
        );
      })}
    </nav>
  );

  /* ---- Render ---- */

  return (
    <div className="min-h-screen flex flex-col bg-[#F5F5F7]">
      <LandingNav />

      <main className="flex-1">
        {/* Header / Search */}
        <section className="bg-white border-b border-gray-100">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
            <div className="max-w-2xl">
              <span className="inline-flex items-center px-4 py-2 rounded-full bg-[#4A5568] text-white text-xs font-medium uppercase tracking-wider mb-6">
                Help Center
              </span>
              <h1 className="text-3xl md:text-4xl font-light  mb-3">
                <span className="font-normal text-[#1F3C52]">How can we</span>{" "}
                <span className="font-light text-[#2F79C5]">help you?</span>
              </h1>
              <p className="text-[#6B7280] font-light mb-8">
                Find answers to common questions, learn about features, and get
                started with LeafXtract.
              </p>

              {/* Search Input */}
              <div className="relative max-w-lg">
                <Search
                  className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[#9CA3AF]"
                  strokeWidth={1.5}
                />
                <input
                  type="text"
                  placeholder="Search help articles..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 rounded-xl border border-gray-200 bg-[#F9FAFB] text-sm text-[#2D3748] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#5B8DBE]/30 focus:border-[#5B8DBE] transition-all"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
                  >
                    <X className="h-4 w-4" strokeWidth={1.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Two-column layout */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
          <div className="flex gap-10">
            {/* ---------- Desktop Sidebar ---------- */}
            <aside className="hidden lg:block w-64 flex-shrink-0">
              <div className="sticky top-28">{sidebarContent}</div>
            </aside>

            {/* ---------- Mobile Sidebar Toggle ---------- */}
            <div className="lg:hidden fixed bottom-6 right-6 z-40">
              <button
                type="button"
                onClick={() => setMobileNavOpen((v) => !v)}
                className="w-12 h-12 bg-[#4A5568] text-white rounded-full shadow-lg flex items-center justify-center hover:bg-[#5B8DBE] transition-colors"
                aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
              >
                {mobileNavOpen ? (
                  <X className="h-5 w-5" strokeWidth={1.5} />
                ) : (
                  <Menu className="h-5 w-5" strokeWidth={1.5} />
                )}
              </button>
            </div>

            {/* Mobile Sidebar Drawer */}
            {mobileNavOpen && (
              <div className="lg:hidden fixed inset-0 z-30">
                {/* Backdrop */}
                <div
                  className="absolute inset-0 bg-black/20 backdrop-blur-sm"
                  onClick={() => setMobileNavOpen(false)}
                />
                {/* Drawer */}
                <div className="absolute bottom-20 right-6 w-64 bg-white rounded-2xl shadow-2xl border border-gray-100 p-4">
                  <p className="text-xs font-normal text-[#9CA3AF] uppercase tracking-wider px-4 mb-2">
                    Sections
                  </p>
                  {sidebarContent}
                </div>
              </div>
            )}

            {/* ---------- Main Content ---------- */}
            <div className="flex-1 min-w-0">
              {/* No results state */}
              {filteredSections.length === 0 && (
                <div className="bg-white rounded-2xl p-12 text-center shadow-sm border border-gray-50">
                  <Search
                    className="h-10 w-10 text-[#D1D5DB] mx-auto mb-4"
                    strokeWidth={1.5}
                  />
                  <h3 className="text-lg font-normal text-[#2D3748] mb-2">
                    No results found
                  </h3>
                  <p className="text-[#6B7280] text-sm font-light">
                    No articles match &ldquo;{searchQuery}&rdquo;. Try a
                    different search term or{" "}
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="text-[#5B8DBE] hover:underline"
                    >
                      clear the search
                    </button>
                    .
                  </p>
                </div>
              )}

              {/* Render filtered sections */}
              {filteredSections.map((section) => (
                <div
                  key={section.id}
                  id={section.id}
                  ref={(el) => {
                    sectionRefs.current[section.id] = el;
                  }}
                  className="mb-12 scroll-mt-28"
                >
                  {/* Section heading */}
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-8 h-8 bg-[#4A5568] rounded-lg flex items-center justify-center text-white">
                      {section.icon}
                    </div>
                    <h2 className="text-xl font-normal text-[#2D3748]">
                      {section.title}
                    </h2>
                  </div>

                  {/* Subsections */}
                  {section.subsections && (
                    <div className="space-y-6">
                      {section.subsections.map((sub) => (
                        <SubsectionCard key={sub.id} sub={sub} />
                      ))}
                    </div>
                  )}

                  {/* FAQ Accordion */}
                  {section.faqItems && section.faqItems.length > 0 && (
                    <div className="space-y-3">
                      {section.faqItems.map((faq, faqIdx) => (
                        <FaqAccordionItem
                          key={faqIdx}
                          item={faq}
                          isOpen={openFaqIndices.has(faqIdx)}
                          onToggle={() => toggleFaq(faqIdx)}
                        />
                      ))}
                    </div>
                  )}

                  {/* Contact Support */}
                  {section.contactContent && (
                    <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-50">
                      <div className="flex items-center gap-3 mb-5">
                        <div className="w-10 h-10 bg-[#F9FAFB] rounded-xl flex items-center justify-center flex-shrink-0">
                          <Mail
                            className="h-5 w-5 text-[#5B8DBE]"
                            strokeWidth={1.5}
                          />
                        </div>
                        <h3 className="text-lg font-normal text-[#2D3748]">
                          Have a question that is not answered here?
                        </h3>
                      </div>

                      <p className="text-[#6B7280] text-sm font-light leading-relaxed mb-6">
                        Get in touch with our team. We are happy to help with
                        any questions about LeafXtract, your account, or
                        technical issues.
                      </p>

                      <div className="flex flex-col sm:flex-row gap-4">
                        <Link
                          href="/#contact"
                          className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-[#4A5568] text-white text-sm font-normal rounded-xl hover:bg-[#5B8DBE] transition-colors shadow-sm"
                        >
                          <MessageCircle
                            className="h-4 w-4"
                            strokeWidth={1.5}
                          />
                          Get in Touch
                        </Link>
                        <a
                          href={`mailto:${SUPPORT_EMAIL}`}
                          className="inline-flex items-center justify-center gap-2 px-6 py-3 border border-gray-200 text-[#4A5568] text-sm font-normal rounded-xl hover:bg-[#F9FAFB] transition-colors"
                        >
                          <Mail className="h-4 w-4" strokeWidth={1.5} />
                          {SUPPORT_EMAIL}
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      <LandingFooter />
    </div>
  );
}
