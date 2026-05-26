"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Copy,
  Check,
  Key,
  FileText,
  FileSpreadsheet,
  Upload,
  Package,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Zap,
  Shield,
  Clock,
  Code2,
  BookOpen,
  ExternalLink,
  Menu,
  Tag,
  BarChart3,
  Bell,
  Store,
  Users,
  Globe,
  Lock,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Dynamic domain -- never hardcode
// ---------------------------------------------------------------------------
const APP_DOMAIN =
  process.env.NEXT_PUBLIC_APP_DOMAIN || "leafxtract.com";
const BASE_URL = `https://${APP_DOMAIN}/api/v1`;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
type AuthType = "both" | "jwt" | "public" | "api_key";

interface ParamDef {
  name: string;
  type: string;
  required: boolean;
  description: string;
  default?: string;
  enum?: string[];
}

interface RequestBodyDef {
  contentType: string;
  fields: ParamDef[];
  example?: string;
}

interface ResponseDef {
  status: number;
  description: string;
  example?: string; // JSON string
}

interface Endpoint {
  method: HttpMethod;
  path: string;
  title: string;
  description: string;
  auth: AuthType;
  parameters?: ParamDef[];
  queryParams?: ParamDef[];
  requestBody?: RequestBodyDef;
  responses?: ResponseDef[];
  curl?: string;
  python?: string;
  javascript?: string;
}

interface EndpointSection {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  endpoints: Endpoint[];
}

interface NavSection {
  id: string;
  title: string;
}

// ---------------------------------------------------------------------------
// Method & auth badge colors
// ---------------------------------------------------------------------------
const methodColors: Record<HttpMethod, string> = {
  GET: "bg-green-100 text-green-800 dark:bg-green-900/60 dark:text-green-300",
  POST: "bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300",
  PUT: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/60 dark:text-yellow-300",
  DELETE: "bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-300",
  PATCH: "bg-purple-100 text-purple-800 dark:bg-purple-900/60 dark:text-purple-300",
};

function AuthBadge({ auth }: { auth: AuthType }) {
  switch (auth) {
    case "both":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/60 dark:text-green-300 border-green-200 dark:border-green-800 text-[10px]">
          API Key + JWT
        </Badge>
      );
    case "jwt":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300 border-amber-200 dark:border-amber-800 text-[10px]">
          JWT Only
        </Badge>
      );
    case "api_key":
      return (
        <Badge className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900/60 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800 text-[10px]">
          API Key
        </Badge>
      );
    case "public":
      return (
        <Badge className="bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700 text-[10px]">
          Public
        </Badge>
      );
  }
}

// ---------------------------------------------------------------------------
// CodeBlock component
// ---------------------------------------------------------------------------
function CodeBlock({ code }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group">
      <pre className="bg-slate-900 text-slate-100 dark:bg-slate-950 p-4 rounded-lg overflow-x-auto text-sm leading-relaxed">
        <code>{code}</code>
      </pre>
      <Button
        variant="ghost"
        size="sm"
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 hover:bg-slate-700 text-white h-7 w-7 p-0"
        onClick={handleCopy}
        aria-label={copied ? "Copied" : "Copy to clipboard"}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ParamsTable component
// ---------------------------------------------------------------------------
function ParamsTable({
  params,
  title,
  icon,
}: {
  params: ParamDef[];
  title: string;
  icon: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
        {icon} {title}
      </h4>
      <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 dark:bg-slate-800">
              <tr>
                <th className="text-left p-3 font-medium">Name</th>
                <th className="text-left p-3 font-medium">Type</th>
                <th className="text-left p-3 font-medium">Required</th>
                <th className="text-left p-3 font-medium">Description</th>
              </tr>
            </thead>
            <tbody>
              {params.map((param) => (
                <tr
                  key={param.name}
                  className="border-t border-slate-200 dark:border-slate-700"
                >
                  <td className="p-3 font-mono text-blue-600 dark:text-blue-400 text-xs whitespace-nowrap">
                    {param.name}
                  </td>
                  <td className="p-3 text-slate-600 dark:text-slate-400 text-xs whitespace-nowrap">
                    {param.type}
                    {param.enum && (
                      <span className="block text-[10px] text-slate-500 mt-0.5">
                        {param.enum.join(" | ")}
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    {param.required ? (
                      <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                        Required
                      </Badge>
                    ) : (
                      <span className="text-xs text-slate-500">
                        {param.default ? `Default: ${param.default}` : "Optional"}
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-xs">{param.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EndpointCard component
// ---------------------------------------------------------------------------
function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState("curl");

  const hasCurl = !!endpoint.curl;
  const hasPython = !!endpoint.python;
  const hasJs = !!endpoint.javascript;
  const hasExamples = hasCurl || hasPython || hasJs;

  return (
    <Card className="mb-3">
      <button
        className="w-full text-left cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors rounded-t-lg"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <CardHeader className="py-3 px-4 sm:px-6">
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <Badge className={cn(methodColors[endpoint.method], "font-mono text-[11px] px-2 py-0.5 rounded-md")}>
              {endpoint.method}
            </Badge>
            <code className="text-xs sm:text-sm font-mono bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded break-all">
              {endpoint.path}
            </code>
            <AuthBadge auth={endpoint.auth} />
            <div className="ml-auto flex-shrink-0">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-slate-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-slate-400" />
              )}
            </div>
          </div>
          <div className="mt-1.5">
            <CardTitle className="text-sm font-semibold">{endpoint.title}</CardTitle>
            <CardDescription className="text-xs mt-0.5">{endpoint.description}</CardDescription>
          </div>
        </CardHeader>
      </button>

      {isExpanded && (
        <CardContent className="border-t pt-4 space-y-5 px-4 sm:px-6 pb-5">
          {/* Path Parameters */}
          {endpoint.parameters && endpoint.parameters.length > 0 && (
            <ParamsTable
              params={endpoint.parameters}
              title="Path Parameters"
              icon={<Code2 className="h-4 w-4" />}
            />
          )}

          {/* Query Parameters */}
          {endpoint.queryParams && endpoint.queryParams.length > 0 && (
            <ParamsTable
              params={endpoint.queryParams}
              title="Query Parameters"
              icon={<Code2 className="h-4 w-4" />}
            />
          )}

          {/* Request Body */}
          {endpoint.requestBody && (
            <div>
              <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                <Upload className="h-4 w-4" /> Request Body
                <span className="text-xs text-slate-500 font-normal">
                  ({endpoint.requestBody.contentType})
                </span>
              </h4>
              {endpoint.requestBody.fields.length > 0 && (
                <ParamsTable
                  params={endpoint.requestBody.fields}
                  title=""
                  icon={null}
                />
              )}
              {endpoint.requestBody.example && (
                <div className="mt-2">
                  <CodeBlock code={endpoint.requestBody.example} language="json" />
                </div>
              )}
            </div>
          )}

          {/* Responses */}
          {endpoint.responses && endpoint.responses.length > 0 && (
            <div>
              <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                <FileText className="h-4 w-4" /> Response
              </h4>
              <div className="space-y-3">
                {endpoint.responses.map((resp) => (
                  <div key={resp.status}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Badge
                        variant={resp.status < 300 ? "default" : "destructive"}
                        className="text-[10px] px-1.5"
                      >
                        {resp.status}
                      </Badge>
                      <span className="text-xs text-slate-600 dark:text-slate-400">
                        {resp.description}
                      </span>
                    </div>
                    {resp.example && (
                      <CodeBlock code={resp.example} language="json" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Code Examples */}
          {hasExamples && (
            <div>
              <h4 className="font-semibold mb-2 flex items-center gap-2 text-sm">
                <BookOpen className="h-4 w-4" /> Code Examples
              </h4>
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="h-8">
                  {hasCurl && <TabsTrigger value="curl" className="text-xs h-7">cURL</TabsTrigger>}
                  {hasPython && <TabsTrigger value="python" className="text-xs h-7">Python</TabsTrigger>}
                  {hasJs && <TabsTrigger value="javascript" className="text-xs h-7">JavaScript</TabsTrigger>}
                </TabsList>
                {hasCurl && (
                  <TabsContent value="curl">
                    <CodeBlock code={endpoint.curl!} language="bash" />
                  </TabsContent>
                )}
                {hasPython && (
                  <TabsContent value="python">
                    <CodeBlock code={endpoint.python!} language="python" />
                  </TabsContent>
                )}
                {hasJs && (
                  <TabsContent value="javascript">
                    <CodeBlock code={endpoint.javascript!} language="javascript" />
                  </TabsContent>
                )}
              </Tabs>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sidebar navigation items
// ---------------------------------------------------------------------------
const sidebarSections: NavSection[] = [
  { id: "quick-start", title: "Quick Start" },
  { id: "authentication", title: "Authentication" },
  { id: "base-url", title: "Base URL" },
  { id: "leaflets", title: "Leaflets" },
  { id: "products", title: "Products" },
  { id: "export", title: "Export" },
  { id: "categories", title: "Categories" },
  { id: "analytics", title: "Analytics" },
  { id: "webhooks", title: "Webhooks" },
  { id: "api-keys", title: "API Keys" },
  { id: "retailers", title: "Retailers" },
  { id: "auth-endpoints", title: "Auth" },
  { id: "webhook-events", title: "Webhook Events" },
  { id: "errors", title: "Error Reference" },
  { id: "rate-limits", title: "Rate Limits" },
];

// ---------------------------------------------------------------------------
// Endpoint data
// ---------------------------------------------------------------------------

const leafletEndpoints: Endpoint[] = [
  {
    method: "POST",
    path: "/leaflets/upload",
    title: "Upload Leaflet",
    description: "Upload a PDF leaflet for product extraction. Max file size 100MB.",
    auth: "both",
    requestBody: {
      contentType: "multipart/form-data",
      fields: [
        { name: "file", type: "File", required: true, description: "PDF file (max 100MB)" },
        { name: "retailer_name", type: "string", required: false, description: "Retailer name for context" },
        { name: "country", type: "string", required: false, description: "Country code (e.g., SI, HR, RS)" },
        { name: "currency", type: "string", required: false, description: "Currency code (e.g., EUR)" },
        { name: "auto_extract", type: "boolean", required: false, default: "true", description: "Start extraction immediately" },
      ],
      example: undefined,
    },
    responses: [
      {
        status: 201,
        description: "Leaflet created",
        example: JSON.stringify({
          id: "550e8400-e29b-41d4-a716-446655440000",
          leaflet_id: "LEAF_2025_000123",
          status: "uploaded",
          filename: "promo-leaflet.pdf",
          page_count: null,
          retailer_name: "Mercator",
          country: "SI",
          currency: "EUR",
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/leaflets/upload" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -F "file=@leaflet.pdf" \\
  -F "retailer_name=Mercator" \\
  -F "country=SI"`,
    python: `import requests

response = requests.post(
    "${BASE_URL}/leaflets/upload",
    headers={"X-API-Key": "lxk_your_api_key"},
    files={"file": ("leaflet.pdf", open("leaflet.pdf", "rb"), "application/pdf")},
    data={"retailer_name": "Mercator", "country": "SI"},
)

leaflet = response.json()
print(f"Leaflet ID: {leaflet['leaflet_id']}")`,
    javascript: `const formData = new FormData();
formData.append("file", pdfFile);
formData.append("retailer_name", "Mercator");
formData.append("country", "SI");

const response = await fetch("${BASE_URL}/leaflets/upload", {
  method: "POST",
  headers: { "X-API-Key": "lxk_your_api_key" },
  body: formData,
});

const leaflet = await response.json();
console.log("Leaflet ID:", leaflet.leaflet_id);`,
  },
  {
    method: "GET",
    path: "/leaflets",
    title: "List Leaflets",
    description: "Retrieve a paginated list of leaflets with filtering and sorting.",
    auth: "both",
    queryParams: [
      { name: "page", type: "integer", required: false, default: "1", description: "Page number" },
      { name: "page_size", type: "integer", required: false, default: "50", description: "Items per page (1-200)" },
      { name: "status", type: "string", required: false, description: "Filter by status", enum: ["uploaded", "processing", "extracting", "validating", "reviewing", "completed", "failed"] },
      { name: "retailer_name", type: "string", required: false, description: "Filter by retailer name" },
      { name: "search", type: "string", required: false, description: "Search by filename or leaflet ID" },
      { name: "sort_by", type: "string", required: false, default: "created_at", description: "Sort field" },
      { name: "sort_order", type: "string", required: false, default: "desc", description: "Sort direction", enum: ["asc", "desc"] },
    ],
    responses: [
      {
        status: 200,
        description: "Paginated list of leaflets",
        example: JSON.stringify({
          items: [{
            id: "550e8400-e29b-41d4-a716-446655440000",
            leaflet_id: "LEAF_2025_000123",
            status: "completed",
            filename: "promo.pdf",
            page_count: 12,
            product_count: 48,
            auto_approved_count: 38,
            review_required_count: 10,
            retailer_name: "Mercator",
            created_at: "2026-01-15T10:30:00Z"
          }],
          total: 25,
          page: 1,
          page_size: 50,
          total_pages: 1
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/leaflets?page=1&page_size=20&status=completed" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `response = requests.get(
    "${BASE_URL}/leaflets",
    headers={"X-API-Key": "lxk_your_api_key"},
    params={"page": 1, "page_size": 20, "status": "completed"},
)

data = response.json()
print(f"Total leaflets: {data['total']}")
for leaflet in data["items"]:
    print(f"  {leaflet['leaflet_id']}: {leaflet['status']}")`,
    javascript: `const params = new URLSearchParams({
  page: "1",
  page_size: "20",
  status: "completed",
});

const response = await fetch(\`${BASE_URL}/leaflets?\${params}\`, {
  headers: { "X-API-Key": "lxk_your_api_key" },
});

const data = await response.json();
console.log(\`Total leaflets: \${data.total}\`);`,
  },
  {
    method: "GET",
    path: "/leaflets/{leaflet_id}",
    title: "Get Leaflet Details",
    description: "Retrieve detailed information about a specific leaflet including processing stats.",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    responses: [
      {
        status: 200,
        description: "Full leaflet details",
        example: JSON.stringify({
          id: "550e8400-e29b-41d4-a716-446655440000",
          leaflet_id: "LEAF_2025_000123",
          status: "completed",
          filename: "promo.pdf",
          page_count: 12,
          product_count: 48,
          overall_confidence: 0.95,
          auto_approved_count: 38,
          review_required_count: 10,
          retailer_name: "Mercator",
          country: "SI",
          currency: "EUR",
          processing_cost: 0.245,
          api_tokens_used: 45230,
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
      { status: 404, description: "Leaflet not found" },
    ],
    curl: `curl "${BASE_URL}/leaflets/550e8400-e29b-41d4-a716-446655440000" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `response = requests.get(
    f"${BASE_URL}/leaflets/{leaflet_id}",
    headers={"X-API-Key": "lxk_your_api_key"},
)

leaflet = response.json()
print(f"Products: {leaflet['product_count']}, Confidence: {leaflet['overall_confidence']}")`,
    javascript: `const response = await fetch(\`${BASE_URL}/leaflets/\${leafletId}\`, {
  headers: { "X-API-Key": "lxk_your_api_key" },
});

const leaflet = await response.json();
console.log(\`Products: \${leaflet.product_count}\`);`,
  },
  {
    method: "GET",
    path: "/leaflets/{leaflet_id}/status",
    title: "Get Processing Status",
    description: "Get real-time processing status and progress. Useful for polling during extraction.",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    responses: [
      {
        status: 200,
        description: "Current processing status",
        example: JSON.stringify({
          id: "550e8400-e29b-41d4-a716-446655440000",
          status: "extracting",
          progress: 0.45,
          current_step: "Extracting page 5 of 12",
          auto_approved_count: 20,
          review_required_count: 5
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/leaflets/550e8400-e29b-41d4-a716-446655440000/status" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `import time

# Poll until complete
while True:
    response = requests.get(
        f"${BASE_URL}/leaflets/{leaflet_id}/status",
        headers={"X-API-Key": "lxk_your_api_key"},
    )
    status = response.json()
    print(f"Progress: {status['progress'] * 100:.0f}%")

    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(5)`,
    javascript: `async function waitForCompletion(leafletId) {
  while (true) {
    const response = await fetch(
      \`${BASE_URL}/leaflets/\${leafletId}/status\`,
      { headers: { "X-API-Key": "lxk_your_api_key" } }
    );
    const status = await response.json();
    console.log(\`Progress: \${(status.progress * 100).toFixed(0)}%\`);

    if (["completed", "failed"].includes(status.status)) {
      return status;
    }
    await new Promise((r) => setTimeout(r, 5000));
  }
}`,
  },
  {
    method: "GET",
    path: "/leaflets/{leaflet_id}/pages",
    title: "Get Page Images",
    description: "Get page images and thumbnails for a leaflet.",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    curl: `curl "${BASE_URL}/leaflets/550e8400-e29b-41d4-a716-446655440000/pages" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
  {
    method: "POST",
    path: "/leaflets/{leaflet_id}/extract",
    title: "Start Extraction",
    description: "Start or restart product extraction for a leaflet.",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    responses: [
      { status: 200, description: "Extraction started" },
    ],
    curl: `curl -X POST "${BASE_URL}/leaflets/550e8400-e29b-41d4-a716-446655440000/extract" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
  {
    method: "DELETE",
    path: "/leaflets/{leaflet_id}",
    title: "Delete Leaflet",
    description: "Delete a leaflet and all associated data (products, images, pages).",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    responses: [
      { status: 204, description: "Leaflet deleted" },
    ],
    curl: `curl -X DELETE "${BASE_URL}/leaflets/550e8400-e29b-41d4-a716-446655440000" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
];

const productEndpoints: Endpoint[] = [
  {
    method: "GET",
    path: "/products",
    title: "List Products",
    description: "Retrieve products with filtering, search, and pagination.",
    auth: "both",
    queryParams: [
      { name: "page", type: "integer", required: false, default: "1", description: "Page number" },
      { name: "page_size", type: "integer", required: false, default: "50", description: "Items per page (1-200)" },
      { name: "leaflet_id", type: "UUID", required: false, description: "Filter by leaflet" },
      { name: "review_status", type: "string", required: false, description: "Filter by review status", enum: ["auto_approved", "pending", "approved", "rejected"] },
      { name: "search", type: "string", required: false, description: "Search product name, brand, or code" },
      { name: "brand", type: "string", required: false, description: "Filter by brand" },
      { name: "category_id", type: "UUID", required: false, description: "Filter by category" },
      { name: "min_price", type: "float", required: false, description: "Minimum regular price" },
      { name: "max_price", type: "float", required: false, description: "Maximum regular price" },
      { name: "has_discount", type: "boolean", required: false, description: "Filter products with/without discount" },
      { name: "sort_by", type: "string", required: false, default: "created_at", description: "Sort field" },
      { name: "sort_order", type: "string", required: false, default: "desc", description: "Sort direction", enum: ["asc", "desc"] },
    ],
    responses: [
      {
        status: 200,
        description: "Paginated list of products",
        example: JSON.stringify({
          items: [{
            id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            leaflet_id: "550e8400-e29b-41d4-a716-446655440000",
            product_name: "Alpsko Mleko 1L",
            brand: "Ljubljanske mlekarne",
            product_code: "LM-001",
            regular_price: 1.29,
            discounted_price: 0.99,
            discount_percentage: 23.26,
            currency: "EUR",
            review_status: "auto_approved",
            confidence: 0.95,
            page_number: 3
          }],
          total: 150,
          page: 1,
          page_size: 50,
          total_pages: 3
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/products?leaflet_id=550e8400-...&review_status=pending&page_size=20" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `response = requests.get(
    "${BASE_URL}/products",
    headers={"X-API-Key": "lxk_your_api_key"},
    params={
        "leaflet_id": leaflet_id,
        "review_status": "pending",
        "has_discount": True,
        "page_size": 100,
    },
)

products = response.json()["items"]
for p in products:
    print(f"{p['brand']} - {p['product_name']}: {p['discounted_price']} {p['currency']}")`,
    javascript: `const params = new URLSearchParams({
  leaflet_id: leafletId,
  review_status: "pending",
  page_size: "100",
});

const response = await fetch(\`${BASE_URL}/products?\${params}\`, {
  headers: { "X-API-Key": "lxk_your_api_key" },
});

const { items: products, total } = await response.json();
console.log(\`Found \${total} products\`);`,
  },
  {
    method: "GET",
    path: "/products/stats",
    title: "Get Product Statistics",
    description: "Get aggregate product statistics for the current organization.",
    auth: "both",
    responses: [
      {
        status: 200,
        description: "Aggregate statistics",
        example: JSON.stringify({
          total_products: 1500,
          auto_approved: 1100,
          pending_review: 250,
          approved: 120,
          rejected: 30,
          avg_confidence: 0.92
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/products/stats" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
  {
    method: "GET",
    path: "/products/{product_id}",
    title: "Get Product Details",
    description: "Get full details for a single product including bounding box, image data, and field confidence scores.",
    auth: "both",
    parameters: [
      { name: "product_id", type: "UUID", required: true, description: "Product UUID" },
    ],
    responses: [
      {
        status: 200,
        description: "Full product details",
        example: JSON.stringify({
          id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          leaflet_id: "550e8400-e29b-41d4-a716-446655440000",
          page_number: 3,
          brand: "Ljubljanske mlekarne",
          product_code: "LM-001",
          product_name: "Alpsko Mleko 1L",
          quantity: "1",
          units: "L",
          size: "1L",
          regular_price: 1.29,
          discounted_price: 0.99,
          discount_percentage: 23.26,
          currency: "EUR",
          product_id: "3831234567890",
          promotional_info: "25% off this week",
          confidence: 0.95,
          field_confidence: {
            product_name: 0.98,
            regular_price: 0.95,
            discount_percentage: 0.96
          },
          review_status: "auto_approved",
          validation_passed: true,
          validation_errors: [],
          bounding_box: { x: 100, y: 200, width: 300, height: 400 },
          image_url: "https://s3.example.com/products/a1b2c3d4.jpg?...",
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
      { status: 404, description: "Product not found" },
    ],
    curl: `curl "${BASE_URL}/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `response = requests.get(
    f"${BASE_URL}/products/{product_id}",
    headers={"X-API-Key": "lxk_your_api_key"},
)

product = response.json()
print(f"{product['product_name']}: {product['regular_price']} {product['currency']}")
print(f"Confidence: {product['confidence']}")`,
    javascript: `const response = await fetch(\`${BASE_URL}/products/\${productId}\`, {
  headers: { "X-API-Key": "lxk_your_api_key" },
});

const product = await response.json();`,
  },
  {
    method: "PUT",
    path: "/products/{product_id}",
    title: "Update Product",
    description: "Update product data during review. Only include fields to change.",
    auth: "both",
    parameters: [
      { name: "product_id", type: "UUID", required: true, description: "Product UUID" },
    ],
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "product_name", type: "string", required: false, description: "Corrected product name" },
        { name: "brand", type: "string", required: false, description: "Corrected brand" },
        { name: "regular_price", type: "number", required: false, description: "Corrected regular price" },
        { name: "discounted_price", type: "number", required: false, description: "Corrected discounted price" },
      ],
      example: JSON.stringify({
        product_name: "Corrected Product Name",
        regular_price: 1.49,
        discounted_price: 1.09
      }, null, 2),
    },
    responses: [
      { status: 200, description: "Updated product" },
    ],
    curl: `curl -X PUT "${BASE_URL}/products/a1b2c3d4-..." \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"product_name":"Corrected Name","regular_price":1.49}'`,
  },
  {
    method: "POST",
    path: "/products/{product_id}/review",
    title: "Review Product",
    description: "Submit a review decision (approve or reject) for a product.",
    auth: "both",
    parameters: [
      { name: "product_id", type: "UUID", required: true, description: "Product UUID" },
    ],
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "status", type: "string", required: true, description: "Review decision", enum: ["approved", "rejected"] },
        { name: "notes", type: "string", required: false, description: "Review notes" },
      ],
      example: JSON.stringify({
        status: "approved",
        notes: "Verified price against original"
      }, null, 2),
    },
    responses: [
      { status: 200, description: "Review recorded" },
    ],
    curl: `curl -X POST "${BASE_URL}/products/a1b2c3d4-.../review" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"status":"approved","notes":"Verified"}'`,
  },
  {
    method: "POST",
    path: "/products/batch",
    title: "Batch Get Products",
    description: "Fetch multiple products by ID in a single request (max 20).",
    auth: "both",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "product_ids", type: "UUID[]", required: true, description: "Array of product UUIDs (max 20)" },
      ],
      example: JSON.stringify({
        product_ids: ["uuid-1", "uuid-2", "uuid-3"]
      }, null, 2),
    },
    responses: [
      { status: 200, description: "Array of product objects" },
    ],
    curl: `curl -X POST "${BASE_URL}/products/batch" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"product_ids":["uuid-1","uuid-2","uuid-3"]}'`,
  },
  {
    method: "POST",
    path: "/products/{product_id}/refresh-image-url",
    title: "Refresh Image URL",
    description: "Refresh an expired presigned image URL for a product. S3 URLs expire after 24 hours.",
    auth: "both",
    parameters: [
      { name: "product_id", type: "UUID", required: true, description: "Product UUID" },
    ],
    responses: [
      { status: 200, description: "New presigned URL returned" },
    ],
    curl: `curl -X POST "${BASE_URL}/products/a1b2c3d4-.../refresh-image-url" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
];

const exportEndpoints: Endpoint[] = [
  {
    method: "POST",
    path: "/products/export/preview",
    title: "Preview Export",
    description: "Preview an export to see product count and estimated file size without generating the file.",
    auth: "both",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "format", type: "string", required: true, description: "Export format", enum: ["csv", "excel", "json"] },
        { name: "mode", type: "string", required: true, description: "Export mode", enum: ["all", "filtered", "selected", "review_queue"] },
        { name: "filters", type: "object", required: false, description: "Filter criteria (when mode is 'filtered')" },
      ],
      example: JSON.stringify({
        format: "csv",
        mode: "filtered",
        filters: { review_status: "approved", has_discount: true }
      }, null, 2),
    },
    responses: [
      {
        status: 200,
        description: "Export preview",
        example: JSON.stringify({
          product_count: 850,
          leaflet_count: 15,
          estimated_file_size: 245000
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/products/export/preview" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"format":"csv","mode":"all"}'`,
  },
  {
    method: "POST",
    path: "/products/export",
    title: "Create Export",
    description: "Create a product export. For <1000 products, returns a file immediately. For >=1000, creates an async job.",
    auth: "both",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "format", type: "string", required: true, description: "Export format", enum: ["csv", "excel", "json"] },
        { name: "mode", type: "string", required: true, description: "Export mode", enum: ["all", "filtered", "selected", "review_queue"] },
        { name: "filters", type: "object", required: false, description: "Filter criteria" },
        { name: "product_ids", type: "UUID[]", required: false, description: "Product IDs (when mode is 'selected')" },
        { name: "include_images", type: "boolean", required: false, default: "false", description: "Include image URLs in export" },
      ],
      example: JSON.stringify({
        format: "csv",
        mode: "filtered",
        filters: { review_status: "approved" },
        include_images: false
      }, null, 2),
    },
    responses: [
      {
        status: 200,
        description: "Sync response (< 1000 products) -- file stream",
      },
      {
        status: 202,
        description: "Async job created (>= 1000 products)",
        example: JSON.stringify({
          export_id: "660e8400-e29b-41d4-a716-446655440000",
          status: "pending",
          product_count: 2500,
          message: "Export job created. Poll status endpoint for progress."
        }, null, 2),
      },
    ],
    curl: `# Small export (sync -- returns file)
curl -X POST "${BASE_URL}/products/export" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"format":"csv","mode":"all"}' \\
  -o products.csv

# Large export (async -- returns job ID)
curl -X POST "${BASE_URL}/products/export" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"format":"excel","mode":"all","include_images":true}'`,
    python: `# Create export
response = requests.post(
    "${BASE_URL}/products/export",
    headers={"X-API-Key": "lxk_your_api_key"},
    json={"format": "csv", "mode": "all"},
)

if response.status_code == 200:
    # Sync -- save file directly
    with open("products.csv", "wb") as f:
        f.write(response.content)
elif response.status_code == 202:
    # Async -- poll for completion
    job = response.json()
    export_id = job["export_id"]
    print(f"Export job created: {export_id}")`,
    javascript: `const response = await fetch("${BASE_URL}/products/export", {
  method: "POST",
  headers: {
    "X-API-Key": "lxk_your_api_key",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ format: "csv", mode: "all" }),
});

if (response.status === 200) {
  // Sync -- download file
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  // trigger download...
} else if (response.status === 202) {
  // Async -- poll status
  const { export_id } = await response.json();
  console.log("Export job:", export_id);
}`,
  },
  {
    method: "GET",
    path: "/products/export/{export_id}/status",
    title: "Get Export Status",
    description: "Check the status of an async export job.",
    auth: "both",
    parameters: [
      { name: "export_id", type: "UUID", required: true, description: "Export job UUID" },
    ],
    responses: [
      {
        status: 200,
        description: "Export job status",
        example: JSON.stringify({
          export_id: "660e8400-e29b-41d4-a716-446655440000",
          status: "completed",
          progress: 1.0,
          product_count: 2500,
          file_size: 524288,
          created_at: "2026-01-15T10:30:00Z",
          completed_at: "2026-01-15T10:31:15Z",
          expires_at: "2026-01-16T10:31:15Z"
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/products/export/660e8400-.../status" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
  {
    method: "GET",
    path: "/products/export/{export_id}/download",
    title: "Download Export",
    description: "Download a completed export file. Returns a presigned URL (1 hour expiry).",
    auth: "both",
    parameters: [
      { name: "export_id", type: "UUID", required: true, description: "Export job UUID" },
    ],
    responses: [
      {
        status: 200,
        description: "Download URL",
        example: JSON.stringify({
          download_url: "https://s3.example.com/exports/...",
          filename: "products-export-20260115.csv",
          file_size: 524288,
          expires_at: "2026-01-15T11:31:15Z"
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/products/export/660e8400-.../download" \\
  -H "X-API-Key: lxk_your_api_key"`,
    python: `# Poll until complete, then download
import time

while True:
    status_resp = requests.get(
        f"${BASE_URL}/products/export/{export_id}/status",
        headers={"X-API-Key": "lxk_your_api_key"},
    )
    status = status_resp.json()
    if status["status"] == "completed":
        break
    if status["status"] == "failed":
        raise Exception(f"Export failed: {status.get('error_message')}")
    time.sleep(3)

# Download the file
dl_resp = requests.get(
    f"${BASE_URL}/products/export/{export_id}/download",
    headers={"X-API-Key": "lxk_your_api_key"},
)
download_url = dl_resp.json()["download_url"]
file_resp = requests.get(download_url)
with open("products.csv", "wb") as f:
    f.write(file_resp.content)`,
  },
  {
    method: "GET",
    path: "/export/{leaflet_id}",
    title: "Export Single Leaflet (Legacy)",
    description: "Export all products from a single leaflet. For cross-leaflet exports, use POST /products/export.",
    auth: "both",
    parameters: [
      { name: "leaflet_id", type: "UUID", required: true, description: "Leaflet UUID" },
    ],
    queryParams: [
      { name: "format", type: "string", required: false, default: "json", description: "Export format", enum: ["csv", "excel", "json"] },
      { name: "image_storage", type: "string", required: false, default: "url", description: "Image handling mode", enum: ["base64", "url", "both"] },
    ],
    responses: [
      { status: 200, description: "Export file or JSON data" },
    ],
    curl: `# Export as JSON
curl "${BASE_URL}/export/550e8400-.../json" \\
  -H "X-API-Key: lxk_your_api_key" -o export.json

# Export as CSV
curl "${BASE_URL}/export/550e8400-...?format=csv" \\
  -H "X-API-Key: lxk_your_api_key" -o export.csv`,
  },
];

const categoryEndpoints: Endpoint[] = [
  {
    method: "GET",
    path: "/categories",
    title: "List Categories",
    description: "List all product categories used for classification.",
    auth: "both",
    queryParams: [
      { name: "page", type: "integer", required: false, default: "1", description: "Page number" },
      { name: "page_size", type: "integer", required: false, default: "50", description: "Items per page" },
      { name: "search", type: "string", required: false, description: "Search by category name" },
      { name: "parent_id", type: "UUID", required: false, description: "Filter by parent category" },
    ],
    responses: [
      { status: 200, description: "Paginated list of categories" },
    ],
    curl: `curl "${BASE_URL}/categories?page_size=100" \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
  {
    method: "GET",
    path: "/categories/{category_id}",
    title: "Get Category",
    description: "Get details for a specific product category.",
    auth: "both",
    parameters: [
      { name: "category_id", type: "UUID", required: true, description: "Category UUID" },
    ],
    responses: [
      { status: 200, description: "Category details" },
      { status: 404, description: "Category not found" },
    ],
    curl: `curl "${BASE_URL}/categories/a1b2c3d4-..." \\
  -H "X-API-Key: lxk_your_api_key"`,
  },
];

const analyticsEndpoints: Endpoint[] = [
  {
    method: "GET",
    path: "/analytics/summary",
    title: "Get Analytics Summary",
    description: "Get a summary of extraction analytics for a date range.",
    auth: "jwt",
    queryParams: [
      { name: "start_date", type: "string", required: false, description: "Start date (YYYY-MM-DD)" },
      { name: "end_date", type: "string", required: false, description: "End date (YYYY-MM-DD)" },
    ],
    responses: [
      { status: 200, description: "Analytics summary" },
    ],
    curl: `curl "${BASE_URL}/analytics/summary?start_date=2026-01-01&end_date=2026-01-31" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
    python: `response = requests.get(
    "${BASE_URL}/analytics/summary",
    headers={"Authorization": f"Bearer {access_token}"},
    params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
)`,
  },
  {
    method: "GET",
    path: "/analytics/quality",
    title: "Get Quality Metrics",
    description: "Get extraction quality metrics including accuracy and confidence distribution.",
    auth: "jwt",
    responses: [
      { status: 200, description: "Quality metrics" },
    ],
    curl: `curl "${BASE_URL}/analytics/quality" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
];

const webhookEndpoints: Endpoint[] = [
  {
    method: "POST",
    path: "/webhooks",
    title: "Create Webhook",
    description: "Create a new webhook endpoint. The signing secret is only returned at creation time.",
    auth: "jwt",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "url", type: "string", required: true, description: "HTTPS URL to receive events" },
        { name: "events", type: "string[]", required: true, description: "Event types to subscribe to" },
        { name: "description", type: "string", required: false, description: "Human-readable description" },
        { name: "is_active", type: "boolean", required: false, default: "true", description: "Enable immediately" },
      ],
      example: JSON.stringify({
        url: "https://your-server.com/webhooks/leafxtract",
        events: ["leaflet.processing.completed", "product.approved"],
        description: "Production webhook",
        is_active: true
      }, null, 2),
    },
    responses: [
      {
        status: 201,
        description: "Webhook created (includes signing secret)",
        example: JSON.stringify({
          id: "770e8400-e29b-41d4-a716-446655440000",
          url: "https://your-server.com/webhooks/leafxtract",
          events: ["leaflet.processing.completed", "product.approved"],
          description: "Production webhook",
          is_active: true,
          secret: "whsec_abc123...",
          failure_count: 0,
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/webhooks" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://your-server.com/webhooks/leafxtract",
    "events": ["leaflet.processing.completed"],
    "description": "Production webhook"
  }'`,
    python: `response = requests.post(
    "${BASE_URL}/webhooks",
    headers={"Authorization": f"Bearer {access_token}"},
    json={
        "url": "https://your-server.com/webhooks/leafxtract",
        "events": ["leaflet.processing.completed"],
        "description": "Production webhook",
    },
)

webhook = response.json()
secret = webhook["secret"]  # Store this securely -- only shown once
print(f"Webhook secret: {secret}")`,
    javascript: `const response = await fetch("${BASE_URL}/webhooks", {
  method: "POST",
  headers: {
    Authorization: \`Bearer \${accessToken}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    url: "https://your-server.com/webhooks/leafxtract",
    events: ["leaflet.processing.completed"],
  }),
});

const webhook = await response.json();
// Store webhook.secret securely -- only shown once`,
  },
  {
    method: "GET",
    path: "/webhooks",
    title: "List Webhooks",
    description: "List all configured webhooks for your organization.",
    auth: "jwt",
    responses: [
      { status: 200, description: "Array of webhook objects" },
    ],
    curl: `curl "${BASE_URL}/webhooks" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "PATCH",
    path: "/webhooks/{webhook_id}",
    title: "Update Webhook",
    description: "Update a webhook configuration (URL, events, active status).",
    auth: "jwt",
    parameters: [
      { name: "webhook_id", type: "UUID", required: true, description: "Webhook UUID" },
    ],
    curl: `curl -X PATCH "${BASE_URL}/webhooks/770e8400-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"is_active": false}'`,
  },
  {
    method: "DELETE",
    path: "/webhooks/{webhook_id}",
    title: "Delete Webhook",
    description: "Delete a webhook (soft delete).",
    auth: "jwt",
    parameters: [
      { name: "webhook_id", type: "UUID", required: true, description: "Webhook UUID" },
    ],
    responses: [
      { status: 204, description: "Webhook deleted" },
    ],
    curl: `curl -X DELETE "${BASE_URL}/webhooks/770e8400-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "POST",
    path: "/webhooks/{webhook_id}/test",
    title: "Test Webhook",
    description: "Send a test delivery to the webhook URL.",
    auth: "jwt",
    parameters: [
      { name: "webhook_id", type: "UUID", required: true, description: "Webhook UUID" },
    ],
    curl: `curl -X POST "${BASE_URL}/webhooks/770e8400-.../test" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "GET",
    path: "/webhooks/{webhook_id}/deliveries",
    title: "Get Delivery History",
    description: "Get delivery history for a webhook with pagination.",
    auth: "jwt",
    parameters: [
      { name: "webhook_id", type: "UUID", required: true, description: "Webhook UUID" },
    ],
    queryParams: [
      { name: "page", type: "integer", required: false, default: "1", description: "Page number" },
      { name: "page_size", type: "integer", required: false, default: "20", description: "Items per page" },
      { name: "status", type: "string", required: false, description: "Filter by delivery status", enum: ["success", "failed"] },
    ],
    curl: `curl "${BASE_URL}/webhooks/770e8400-.../deliveries?page=1" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
];

const apiKeyEndpoints: Endpoint[] = [
  {
    method: "POST",
    path: "/api-keys",
    title: "Create API Key",
    description: "Create a new API key. The key value is only returned once at creation time -- store it securely.",
    auth: "jwt",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "name", type: "string", required: true, description: "Human-readable name for the key" },
        { name: "expires_at", type: "string", required: false, description: "Expiration date (ISO 8601)" },
      ],
      example: JSON.stringify({
        name: "Production Integration",
        expires_at: "2027-01-15T00:00:00Z"
      }, null, 2),
    },
    responses: [
      {
        status: 201,
        description: "API key created (includes key value -- only shown once)",
        example: JSON.stringify({
          id: "880e8400-e29b-41d4-a716-446655440000",
          name: "Production Integration",
          key: "lxk_abc123def456...",
          prefix: "lxk_abc1",
          created_at: "2026-01-15T10:30:00Z",
          expires_at: "2027-01-15T00:00:00Z"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/api-keys" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Production Integration","expires_at":"2027-01-15T00:00:00Z"}'`,
    python: `response = requests.post(
    "${BASE_URL}/api-keys",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"name": "Production Integration"},
)

key_data = response.json()
api_key = key_data["key"]  # Store securely -- only shown once
print(f"API Key: {api_key}")`,
  },
  {
    method: "GET",
    path: "/api-keys",
    title: "List API Keys",
    description: "List all API keys for the authenticated user (excludes key values).",
    auth: "jwt",
    responses: [
      { status: 200, description: "Array of API key metadata" },
    ],
    curl: `curl "${BASE_URL}/api-keys" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "DELETE",
    path: "/api-keys/{key_id}",
    title: "Revoke API Key",
    description: "Permanently revoke an API key. This cannot be undone.",
    auth: "jwt",
    parameters: [
      { name: "key_id", type: "UUID", required: true, description: "API key UUID" },
    ],
    responses: [
      { status: 204, description: "API key revoked" },
    ],
    curl: `curl -X DELETE "${BASE_URL}/api-keys/880e8400-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
];

const retailerEndpoints: Endpoint[] = [
  {
    method: "GET",
    path: "/retailers",
    title: "List Retailers",
    description: "List all retailers configured for your organization.",
    auth: "jwt",
    curl: `curl "${BASE_URL}/retailers" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "POST",
    path: "/retailers",
    title: "Create Retailer",
    description: "Create a new retailer profile.",
    auth: "jwt",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "name", type: "string", required: true, description: "Retailer name" },
        { name: "country", type: "string", required: false, description: "Country code (e.g., SI, HR)" },
        { name: "currency", type: "string", required: false, description: "Currency code (e.g., EUR)" },
      ],
      example: JSON.stringify({
        name: "Mercator",
        country: "SI",
        currency: "EUR"
      }, null, 2),
    },
    responses: [
      { status: 201, description: "Retailer created" },
    ],
    curl: `curl -X POST "${BASE_URL}/retailers" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Mercator","country":"SI","currency":"EUR"}'`,
  },
  {
    method: "GET",
    path: "/retailers/{retailer_id}",
    title: "Get Retailer",
    description: "Get details for a specific retailer.",
    auth: "jwt",
    parameters: [
      { name: "retailer_id", type: "UUID", required: true, description: "Retailer UUID" },
    ],
    curl: `curl "${BASE_URL}/retailers/a1b2c3d4-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
  {
    method: "PUT",
    path: "/retailers/{retailer_id}",
    title: "Update Retailer",
    description: "Update retailer details.",
    auth: "jwt",
    parameters: [
      { name: "retailer_id", type: "UUID", required: true, description: "Retailer UUID" },
    ],
    curl: `curl -X PUT "${BASE_URL}/retailers/a1b2c3d4-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Mercator Center","country":"SI"}'`,
  },
  {
    method: "DELETE",
    path: "/retailers/{retailer_id}",
    title: "Delete Retailer",
    description: "Delete a retailer.",
    auth: "jwt",
    parameters: [
      { name: "retailer_id", type: "UUID", required: true, description: "Retailer UUID" },
    ],
    responses: [
      { status: 204, description: "Retailer deleted" },
    ],
    curl: `curl -X DELETE "${BASE_URL}/retailers/a1b2c3d4-..." \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
];

const authEndpoints: Endpoint[] = [
  {
    method: "POST",
    path: "/auth/register",
    title: "Register",
    description: "Register a new user account. Account requires admin approval before login.",
    auth: "public",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "email", type: "string", required: true, description: "Email address" },
        { name: "password", type: "string", required: true, description: "Password (min 8 characters)" },
        { name: "full_name", type: "string", required: true, description: "Full name" },
      ],
      example: JSON.stringify({
        email: "user@example.com",
        password: "SecurePass123!",
        full_name: "Jane Doe"
      }, null, 2),
    },
    responses: [
      {
        status: 201,
        description: "Account created (pending approval)",
        example: JSON.stringify({
          id: "uuid",
          email: "user@example.com",
          full_name: "Jane Doe",
          is_active: false,
          is_verified: false,
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/auth/register" \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","password":"SecurePass123!","full_name":"Jane Doe"}'`,
    python: `response = requests.post(
    "${BASE_URL}/auth/register",
    json={
        "email": "user@example.com",
        "password": "SecurePass123!",
        "full_name": "Jane Doe",
    },
)`,
  },
  {
    method: "POST",
    path: "/auth/login",
    title: "Login",
    description: "Authenticate and receive access + refresh tokens.",
    auth: "public",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "email", type: "string", required: true, description: "Email address" },
        { name: "password", type: "string", required: true, description: "Password" },
      ],
      example: JSON.stringify({
        email: "user@example.com",
        password: "SecurePass123!"
      }, null, 2),
    },
    responses: [
      {
        status: 200,
        description: "Authentication tokens",
        example: JSON.stringify({
          access_token: "eyJhbGciOi...",
          refresh_token: "eyJhbGciOi...",
          token_type: "bearer"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","password":"SecurePass123!"}'`,
    python: `response = requests.post(
    "${BASE_URL}/auth/login",
    json={"email": "user@example.com", "password": "SecurePass123!"},
)

tokens = response.json()
access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]`,
    javascript: `const response = await fetch("${BASE_URL}/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "user@example.com", password: "SecurePass123!" }),
});

const { access_token, refresh_token } = await response.json();`,
  },
  {
    method: "POST",
    path: "/auth/refresh",
    title: "Refresh Token",
    description: "Refresh an expired access token using the refresh token.",
    auth: "public",
    requestBody: {
      contentType: "application/json",
      fields: [
        { name: "refresh_token", type: "string", required: true, description: "Refresh token from login" },
      ],
      example: JSON.stringify({
        refresh_token: "eyJhbGciOi..."
      }, null, 2),
    },
    responses: [
      {
        status: 200,
        description: "New token pair",
        example: JSON.stringify({
          access_token: "eyJhbGciOi...",
          refresh_token: "eyJhbGciOi...",
          token_type: "bearer"
        }, null, 2),
      },
    ],
    curl: `curl -X POST "${BASE_URL}/auth/refresh" \\
  -H "Content-Type: application/json" \\
  -d '{"refresh_token":"eyJhbGciOi..."}'`,
  },
  {
    method: "GET",
    path: "/auth/me",
    title: "Get Current User",
    description: "Get the currently authenticated user's profile.",
    auth: "jwt",
    responses: [
      {
        status: 200,
        description: "User profile",
        example: JSON.stringify({
          id: "uuid",
          email: "user@example.com",
          full_name: "Jane Doe",
          is_active: true,
          is_superuser: false,
          created_at: "2026-01-15T10:30:00Z"
        }, null, 2),
      },
    ],
    curl: `curl "${BASE_URL}/auth/me" \\
  -H "Authorization: Bearer \${ACCESS_TOKEN}"`,
  },
];

// ---------------------------------------------------------------------------
// Sidebar Navigation Component
// ---------------------------------------------------------------------------
function SidebarNav({
  activeSection,
  onNavigate,
}: {
  activeSection: string;
  onNavigate?: () => void;
}) {
  const handleClick = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    onNavigate?.();
  };

  return (
    <nav className="space-y-0.5" aria-label="Documentation sections">
      {sidebarSections.map((section) => (
        <button
          key={section.id}
          onClick={() => handleClick(section.id)}
          className={cn(
            "block w-full text-left px-3 py-1.5 text-sm rounded-md transition-colors",
            activeSection === section.id
              ? "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-medium"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/50"
          )}
        >
          {section.title}
        </button>
      ))}
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Endpoint Section Component
// ---------------------------------------------------------------------------
function EndpointSection({
  id,
  title,
  description,
  icon,
  endpoints,
}: EndpointSection) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="text-xl font-bold mb-1 flex items-center gap-2 text-slate-800 dark:text-slate-200">
        {icon}
        {title}
      </h2>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
        {description}
      </p>
      {endpoints.map((endpoint, index) => (
        <EndpointCard key={`${endpoint.method}-${endpoint.path}-${index}`} endpoint={endpoint} />
      ))}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export function ApiDocumentation() {
  const [activeSection, setActiveSection] = useState("quick-start");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  // Scroll-spy via IntersectionObserver
  useEffect(() => {
    const sectionIds = sidebarSections.map((s) => s.id);

    observerRef.current = new IntersectionObserver(
      (entries) => {
        // Find the topmost visible section
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);

        if (visible.length > 0) {
          setActiveSection(visible[0].target.id);
        }
      },
      {
        rootMargin: "-80px 0px -60% 0px",
        threshold: 0,
      }
    );

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observerRef.current?.observe(el);
    });

    return () => {
      observerRef.current?.disconnect();
    };
  }, []);

  return (
    <div className="relative">
      {/* Mobile floating menu button */}
      <div className="lg:hidden fixed bottom-6 right-6 z-40">
        <Dialog open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <DialogTrigger asChild>
            <Button size="lg" className="rounded-full shadow-lg h-12 w-12 p-0">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open navigation menu</span>
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-xs">
            <DialogHeader>
              <DialogTitle>Navigation</DialogTitle>
            </DialogHeader>
            <SidebarNav
              activeSection={activeSection}
              onNavigate={() => setMobileMenuOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex gap-8">
        {/* Desktop sticky sidebar */}
        <aside className="hidden lg:block w-56 xl:w-64 flex-shrink-0">
          <div className="sticky top-20">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3 px-3">
              On This Page
            </h3>
            <ScrollArea className="h-[calc(100vh-10rem)]">
              <SidebarNav activeSection={activeSection} />
            </ScrollArea>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-10">
          {/* Header */}
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight text-slate-800 dark:text-slate-200">
              API <span className="font-normal">Documentation</span>
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Integrate with the LeafXtract platform using our REST API.
              All endpoints are versioned under <code className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-xs font-mono">/api/v1</code>.
            </p>
          </div>

          {/* ================================================================ */}
          {/* QUICK START */}
          {/* ================================================================ */}
          <section id="quick-start" className="scroll-mt-6">
            <Card className="border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Zap className="h-5 w-5 text-blue-600 dark:text-blue-400" strokeWidth={1.5} />
                  Quick Start
                </CardTitle>
                <CardDescription>
                  Get up and running in 3 steps. Each command below is copy-pasteable.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Step 1 */}
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                      1
                    </div>
                    <h4 className="font-semibold text-sm">Get your API key</h4>
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-400 ml-9 mb-2">
                    Create an API key in{" "}
                    <Link
                      href="/settings?tab=api-keys"
                      className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
                    >
                      Settings &rarr; API Keys
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                    . The key starts with <code className="bg-slate-200 dark:bg-slate-700 px-1 rounded text-xs">lxk_</code>.
                  </p>
                </div>

                {/* Step 2 */}
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                      2
                    </div>
                    <h4 className="font-semibold text-sm">List your leaflets</h4>
                  </div>
                  <div className="ml-9">
                    <CodeBlock
                      code={`curl "${BASE_URL}/leaflets" \\
  -H "X-API-Key: lxk_your_api_key"`}
                      language="bash"
                    />
                  </div>
                </div>

                {/* Step 3 */}
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center flex-shrink-0 text-xs font-bold">
                      3
                    </div>
                    <h4 className="font-semibold text-sm">Export your products</h4>
                  </div>
                  <div className="ml-9">
                    <CodeBlock
                      code={`curl -X POST "${BASE_URL}/products/export" \\
  -H "X-API-Key: lxk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"format":"csv","mode":"all"}' \\
  -o products.csv`}
                      language="bash"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* AUTHENTICATION */}
          {/* ================================================================ */}
          <section id="authentication" className="scroll-mt-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  Authentication
                </CardTitle>
                <CardDescription>
                  The API supports two authentication methods. Most B2B integrations use API keys.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="p-4 border rounded-lg">
                    <h4 className="font-semibold text-sm flex items-center gap-2 mb-2">
                      <Shield className="h-4 w-4 text-green-600 dark:text-green-400" />
                      API Key
                      <AuthBadge auth="both" />
                    </h4>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      For server-to-server integrations. Pass your key in the request header:
                    </p>
                    <CodeBlock code={`X-API-Key: lxk_your_api_key`} />
                    <p className="text-xs text-slate-500 mt-2">
                      Create keys in{" "}
                      <Link href="/settings?tab=api-keys" className="text-blue-600 hover:underline">
                        Settings
                      </Link>
                      . Keys start with <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded">lxk_</code>.
                    </p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <h4 className="font-semibold text-sm flex items-center gap-2 mb-2">
                      <Lock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                      JWT Bearer Token
                      <AuthBadge auth="jwt" />
                    </h4>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      For web applications. Obtain a token via <code className="text-xs bg-slate-100 dark:bg-slate-800 px-1 rounded">POST /auth/login</code>:
                    </p>
                    <CodeBlock code={`Authorization: Bearer eyJhbGciOi...`} />
                    <p className="text-xs text-slate-500 mt-2">
                      Access tokens expire after 8 hours. Use the refresh endpoint to get a new one.
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg">
                  <h4 className="font-semibold text-sm mb-2">Which endpoints support which auth?</h4>
                  <div className="space-y-1.5 text-sm">
                    <div className="flex items-center gap-2">
                      <AuthBadge auth="both" />
                      <span className="text-slate-600 dark:text-slate-400">
                        Leaflets, Products, Export, Categories -- accepts either method
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <AuthBadge auth="jwt" />
                      <span className="text-slate-600 dark:text-slate-400">
                        Analytics, Webhooks, API Keys, Retailers, Settings -- JWT only
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <AuthBadge auth="public" />
                      <span className="text-slate-600 dark:text-slate-400">
                        Auth (register, login, refresh) -- no authentication required
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* BASE URL */}
          {/* ================================================================ */}
          <section id="base-url" className="scroll-mt-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Globe className="h-5 w-5" />
                  Base URL
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  All API requests should be made to:
                </p>
                <CodeBlock code={BASE_URL} />
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Interactive API docs (Swagger UI) are available at{" "}
                  <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded">
                    https://{APP_DOMAIN}/docs
                  </code>.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* ENDPOINT SECTIONS */}
          {/* ================================================================ */}

          <EndpointSection
            id="leaflets"
            title="Leaflets"
            description="Upload PDF leaflets, track processing status, and manage your leaflet library."
            icon={<FileText className="h-5 w-5" />}
            endpoints={leafletEndpoints}
          />

          <EndpointSection
            id="products"
            title="Products"
            description="Access extracted product data with filtering, search, review, and batch operations."
            icon={<Package className="h-5 w-5" />}
            endpoints={productEndpoints}
          />

          <EndpointSection
            id="export"
            title="Export"
            description="Export products in CSV, Excel, or JSON format. Supports sync (<1000 products) and async (>=1000) modes."
            icon={<FileSpreadsheet className="h-5 w-5" />}
            endpoints={exportEndpoints}
          />

          <EndpointSection
            id="categories"
            title="Categories"
            description="Browse the product category taxonomy used for classification (352 categories)."
            icon={<Tag className="h-5 w-5" />}
            endpoints={categoryEndpoints}
          />

          <EndpointSection
            id="analytics"
            title="Analytics"
            description="Access extraction analytics, quality metrics, and cost data. JWT authentication only."
            icon={<BarChart3 className="h-5 w-5" />}
            endpoints={analyticsEndpoints}
          />

          <EndpointSection
            id="webhooks"
            title="Webhooks"
            description="Configure webhook endpoints to receive real-time event notifications. JWT authentication only."
            icon={<Webhook className="h-5 w-5" />}
            endpoints={webhookEndpoints}
          />

          <EndpointSection
            id="api-keys"
            title="API Keys"
            description="Manage API keys for programmatic access (B2B integrations). JWT authentication only."
            icon={<Key className="h-5 w-5" />}
            endpoints={apiKeyEndpoints}
          />

          <EndpointSection
            id="retailers"
            title="Retailers"
            description="Manage retailer profiles used for extraction context. JWT authentication only."
            icon={<Store className="h-5 w-5" />}
            endpoints={retailerEndpoints}
          />

          <EndpointSection
            id="auth-endpoints"
            title="Auth"
            description="User registration, login, token refresh, and profile management."
            icon={<Users className="h-5 w-5" />}
            endpoints={authEndpoints}
          />

          {/* ================================================================ */}
          {/* WEBHOOK EVENTS */}
          {/* ================================================================ */}
          <section id="webhook-events" className="scroll-mt-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bell className="h-5 w-5" />
                  Webhook Events Reference
                </CardTitle>
                <CardDescription>
                  All 10 event types your webhook can subscribe to. Each delivery includes an{" "}
                  <code className="text-xs bg-slate-100 dark:bg-slate-800 px-1 rounded">X-Webhook-Signature</code>{" "}
                  header for verification (HMAC-SHA256).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Event types table */}
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-100 dark:bg-slate-800">
                        <tr>
                          <th className="text-left p-3 font-medium">Event</th>
                          <th className="text-left p-3 font-medium">Trigger</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["leaflet.uploaded", "A new leaflet has been uploaded"],
                          ["leaflet.processing.started", "PDF processing has begun"],
                          ["leaflet.processing.completed", "All extraction stages finished successfully"],
                          ["leaflet.processing.failed", "Processing failed with an error"],
                          ["leaflet.review.required", "Products need human review"],
                          ["leaflet.review.completed", "All product reviews are done"],
                          ["leaflet.export.ready", "An export file is available for download"],
                          ["product.updated", "A product's data was modified"],
                          ["product.approved", "A product was approved during review"],
                          ["product.rejected", "A product was rejected during review"],
                        ].map(([event, trigger]) => (
                          <tr
                            key={event}
                            className="border-t border-slate-200 dark:border-slate-700"
                          >
                            <td className="p-3 font-mono text-xs text-blue-600 dark:text-blue-400 whitespace-nowrap">
                              {event}
                            </td>
                            <td className="p-3 text-slate-600 dark:text-slate-400 text-xs">
                              {trigger}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Example payloads */}
                <div>
                  <h4 className="font-semibold text-sm mb-2">Example Payload: leaflet.processing.completed</h4>
                  <CodeBlock
                    code={JSON.stringify({
                      event: "leaflet.processing.completed",
                      timestamp: "2026-01-15T10:35:00Z",
                      data: {
                        leaflet_id: "550e8400-e29b-41d4-a716-446655440000",
                        leaflet_code: "LEAF_2025_000123",
                        status: "completed",
                        total_products: 48,
                        auto_approved: 38,
                        review_required: 10,
                        processing_time_seconds: 185,
                        processing_cost: 0.245
                      }
                    }, null, 2)}
                    language="json"
                  />
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-2">Example Payload: product.approved</h4>
                  <CodeBlock
                    code={JSON.stringify({
                      event: "product.approved",
                      timestamp: "2026-01-15T11:00:00Z",
                      data: {
                        product_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        leaflet_id: "550e8400-e29b-41d4-a716-446655440000",
                        product_name: "Alpsko Mleko 1L",
                        review_status: "approved",
                        reviewed_by: "user-uuid"
                      }
                    }, null, 2)}
                    language="json"
                  />
                </div>

                {/* Signature verification */}
                <div>
                  <h4 className="font-semibold text-sm mb-2">Verifying Webhook Signatures</h4>
                  <Tabs defaultValue="python">
                    <TabsList className="h-8">
                      <TabsTrigger value="python" className="text-xs h-7">Python</TabsTrigger>
                      <TabsTrigger value="javascript" className="text-xs h-7">JavaScript</TabsTrigger>
                    </TabsList>
                    <TabsContent value="python">
                      <CodeBlock
                        code={`import hashlib
import hmac

def verify_webhook_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your handler:
signature = request.headers["X-Webhook-Signature"]
is_valid = verify_webhook_signature(request.body, signature, webhook_secret)
if not is_valid:
    return Response(status_code=401)`}
                        language="python"
                      />
                    </TabsContent>
                    <TabsContent value="javascript">
                      <CodeBlock
                        code={`const crypto = require("crypto");

function verifySignature(payload, signature, secret) {
  const expected =
    "sha256=" + crypto.createHmac("sha256", secret).update(payload).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}

// In your handler:
const signature = req.headers["x-webhook-signature"];
const isValid = verifySignature(req.body, signature, webhookSecret);
if (!isValid) {
  return res.status(401).send("Invalid signature");
}`}
                        language="javascript"
                      />
                    </TabsContent>
                  </Tabs>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* ERROR REFERENCE */}
          {/* ================================================================ */}
          <section id="errors" className="scroll-mt-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertCircle className="h-5 w-5" />
                  Error Reference
                </CardTitle>
                <CardDescription>
                  All API errors follow a consistent JSON structure.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <CodeBlock
                  code={JSON.stringify({
                    detail: {
                      code: "VALIDATION_ERROR",
                      message: "Human-readable error description",
                      errors: [
                        { field: "regular_price", message: "Price must be positive" }
                      ]
                    }
                  }, null, 2)}
                  language="json"
                />

                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-100 dark:bg-slate-800">
                        <tr>
                          <th className="text-left p-3 font-medium">Status</th>
                          <th className="text-left p-3 font-medium">Code</th>
                          <th className="text-left p-3 font-medium">Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          [400, "BAD_REQUEST", "Malformed request syntax"],
                          [401, "AUTHENTICATION_ERROR", "Missing or invalid authentication"],
                          [403, "AUTHORIZATION_ERROR", "Insufficient permissions (or platform quota exhausted)"],
                          [404, "NOT_FOUND", "Resource does not exist"],
                          [409, "DUPLICATE_ERROR", "Resource already exists (e.g., duplicate webhook URL)"],
                          [422, "VALIDATION_ERROR", "Input validation failed (see errors array for field details)"],
                          [429, "RATE_LIMIT_EXCEEDED", "Too many requests -- check Retry-After header"],
                          [500, "PROCESSING_ERROR", "Internal server error"],
                          [502, "EXTERNAL_API_ERROR", "VLM provider returned an error"],
                        ].map(([status, code, desc]) => (
                          <tr
                            key={String(status)}
                            className="border-t border-slate-200 dark:border-slate-700"
                          >
                            <td className="p-3">
                              <Badge
                                variant={Number(status) < 400 ? "default" : "destructive"}
                                className="font-mono text-[10px]"
                              >
                                {status}
                              </Badge>
                            </td>
                            <td className="p-3 font-mono text-xs">{code}</td>
                            <td className="p-3 text-xs text-slate-600 dark:text-slate-400">{desc}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-2">Handling Errors</h4>
                  <Tabs defaultValue="python">
                    <TabsList className="h-8">
                      <TabsTrigger value="python" className="text-xs h-7">Python</TabsTrigger>
                      <TabsTrigger value="javascript" className="text-xs h-7">JavaScript</TabsTrigger>
                    </TabsList>
                    <TabsContent value="python">
                      <CodeBlock
                        code={`response = requests.get(
    f"${BASE_URL}/leaflets/{leaflet_id}",
    headers={"X-API-Key": "lxk_your_api_key"},
)

if response.status_code == 404:
    error = response.json()["detail"]
    print(f"Error: {error['message']}")
elif response.status_code == 401:
    # API key invalid or expired -- check your key
    pass
elif response.status_code == 429:
    # Rate limited -- wait and retry
    retry_after = int(response.headers.get("Retry-After", "60"))
    time.sleep(retry_after)
elif response.status_code >= 500:
    # Server error -- retry with exponential backoff
    pass`}
                        language="python"
                      />
                    </TabsContent>
                    <TabsContent value="javascript">
                      <CodeBlock
                        code={`try {
  const response = await fetch(\`${BASE_URL}/leaflets/\${leafletId}\`, {
    headers: { "X-API-Key": "lxk_your_api_key" },
  });

  if (!response.ok) {
    const { detail } = await response.json();
    switch (detail.code) {
      case "NOT_FOUND":
        console.error(\`Not found: \${detail.message}\`);
        break;
      case "RATE_LIMIT_EXCEEDED":
        const retryAfter = response.headers.get("Retry-After") || "60";
        await new Promise((r) => setTimeout(r, parseInt(retryAfter) * 1000));
        // retry...
        break;
      default:
        console.error(\`API Error: \${detail.code} - \${detail.message}\`);
    }
  }
} catch (error) {
  console.error("Network error:", error);
}`}
                        language="javascript"
                      />
                    </TabsContent>
                  </Tabs>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* RATE LIMITS */}
          {/* ================================================================ */}
          <section id="rate-limits" className="scroll-mt-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Rate Limits
                </CardTitle>
                <CardDescription>
                  The API applies rate limits per endpoint group to prevent abuse.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-100 dark:bg-slate-800">
                        <tr>
                          <th className="text-left p-3 font-medium">Endpoint Group</th>
                          <th className="text-left p-3 font-medium">Limit</th>
                          <th className="text-left p-3 font-medium">Window</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["/auth/login", "Configurable", "Per-IP"],
                          ["/auth/register", "Configurable", "Per-IP"],
                          ["/leaflets/upload", "10 requests", "60 seconds"],
                          ["/contact", "Per-email + Per-IP + Global", "1 hour"],
                          ["General API", "Configurable", "Per-user"],
                        ].map(([endpoint, limit, window]) => (
                          <tr
                            key={endpoint}
                            className="border-t border-slate-200 dark:border-slate-700"
                          >
                            <td className="p-3 font-mono text-xs">{endpoint}</td>
                            <td className="p-3 text-xs">{limit}</td>
                            <td className="p-3 text-xs text-slate-600 dark:text-slate-400">{window}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="font-semibold text-sm text-amber-800 dark:text-amber-200">
                        Rate Limit Response Headers
                      </h4>
                      <p className="text-xs text-amber-700 dark:text-amber-300 mt-1 mb-2">
                        When rate limited, the response includes:
                      </p>
                      <CodeBlock
                        code={`HTTP/1.1 429 Too Many Requests
Retry-After: 60`}
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-2">Best Practices</h4>
                  <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1.5 list-disc list-inside">
                    <li>Implement exponential backoff when receiving 429 responses</li>
                    <li>Cache responses where possible to reduce API calls</li>
                    <li>Use webhooks for event-driven architectures instead of polling</li>
                    <li>Use batch endpoints (e.g., <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded text-xs">POST /products/batch</code>) to reduce request count</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* ================================================================ */}
          {/* SUPPORT FOOTER */}
          {/* ================================================================ */}
          <Card className="bg-slate-50 dark:bg-slate-800/50">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-sm">Need help?</h3>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                    Interactive API docs with full schemas are available at{" "}
                    <code className="bg-slate-200 dark:bg-slate-700 px-1 rounded">
                      https://{APP_DOMAIN}/docs
                    </code>
                  </p>
                </div>
                <div className="flex gap-2">
                  <Link href="/settings?tab=api-keys">
                    <Button variant="outline" size="sm">
                      <Key className="h-3.5 w-3.5 mr-1.5" />
                      Manage API Keys
                    </Button>
                  </Link>
                  <Link href="/help">
                    <Button variant="outline" size="sm">
                      <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                      Help Center
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
