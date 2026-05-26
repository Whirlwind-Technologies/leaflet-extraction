"use client";

import { useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import NextImage from "next/image";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  Eye,
  Edit2,
  ImageIcon,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  List,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  AlertTriangle,
  FileText,
  Folder,
  Download,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { refreshProductImageUrl } from "@/lib/actions/products";
import type { Product, Leaflet, ProductExportFilters } from "@/lib/types";
import { brandColors as colors } from "@/lib/brand-colors";
import { ExportDialog } from "@/components/export/export-dialog";

interface AllProductsListProps {
  products: Product[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
  leaflets: Leaflet[];
  currentLeafletId?: string;
  currentStatus?: string;
  currentCategory?: string;
  hasCompletedLeaflets?: boolean;
}

type ViewMode = "grid" | "table";

/**
 * Convert internal MinIO/S3 URLs to browser-accessible URLs.
 */
function fixMinioUrl(url: string): string {
  return url
    .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
}

function getProductImageSrc(product: Product): string | null {
  // Try the image object first (new format)
  if (product.image?.data) {
    return product.image.data.startsWith("data:")
      ? product.image.data
      : `data:image/png;base64,${product.image.data}`;
  }
  if (product.image?.url) {
    return fixMinioUrl(product.image.url);
  }

  // Fallback to legacy fields
  if (product.image_base64) {
    return product.image_base64.startsWith("data:")
      ? product.image_base64
      : `data:image/png;base64,${product.image_base64}`;
  }
  if (product.image_url) {
    return fixMinioUrl(product.image_url);
  }

  return null;
}

/**
 * Determine whether a product's image comes from S3/MinIO (i.e. a presigned
 * URL that can expire) rather than inline base64 data.
 */
function isFileStoredImage(product: Product): boolean {
  return (
    product.image_storage_type === "file" ||
    product.image?.storage_type === "file" ||
    false
  );
}

/**
 * Hook that resolves the product image src and automatically refreshes
 * expired S3 presigned URLs on load failure.
 */
function useProductImage(product: Product): {
  imageSrc: string | null;
  imageError: boolean;
  onImageError: () => void;
} {
  const [imageError, setImageError] = useState(false);
  const [refreshedUrl, setRefreshedUrl] = useState<string | null>(null);
  const [refreshAttempted, setRefreshAttempted] = useState(false);

  // Reset state when the product changes (adjust state during render pattern)
  const [prevProductId, setPrevProductId] = useState(product.id);
  if (product.id !== prevProductId) {
    setPrevProductId(product.id);
    setImageError(false);
    setRefreshedUrl(null);
    setRefreshAttempted(false);
  }

  const baseSrc = refreshedUrl ?? getProductImageSrc(product);

  const onImageError = useCallback(() => {
    if (isFileStoredImage(product) && !refreshAttempted) {
      setRefreshAttempted(true);
      refreshProductImageUrl(product.id).then((result) => {
        if (result.success && result.data?.image_url) {
          setRefreshedUrl(fixMinioUrl(result.data.image_url));
          setImageError(false);
        } else {
          setImageError(true);
        }
      }).catch(() => {
        setImageError(true);
      });
    } else {
      setImageError(true);
    }
  }, [product, refreshAttempted]);

  return { imageSrc: baseSrc, imageError, onImageError };
}

function StatusBadge({ status }: { status: string }) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case "auto_approved":
        return { label: "Auto Approved", bg: colors.lightBlueTint, color: colors.primaryBrandBlue, icon: Zap };
      case "approved":
        return { label: "Approved", bg: colors.successBg, color: colors.successText, icon: CheckCircle };
      case "pending":
        return { label: "Pending", bg: colors.warningBg, color: colors.warningText, icon: Clock };
      case "rejected":
        return { label: "Rejected", bg: colors.errorBg, color: colors.errorText, icon: XCircle };
      case "needs_correction":
        return { label: "Needs Fix", bg: colors.warningBg, color: colors.warningText, icon: AlertTriangle };
      case "corrected":
        return { label: "Corrected", bg: colors.infoBg, color: colors.infoText, icon: Edit2 };
      default:
        return { label: status, bg: colors.offWhiteBg, color: colors.secondaryText, icon: Clock };
    }
  };

  const cfg = getStatusConfig(status);
  const Icon = cfg.icon;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium"
      style={{ backgroundColor: cfg.bg, color: cfg.color }}
    >
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) return null;

  const percentage = Math.round(confidence * 100);
  const color = percentage >= 90 ? colors.success : percentage >= 75 ? colors.warning : colors.error;

  return (
    <span className="text-xs font-mono" style={{ color }}>
      {percentage}%
    </span>
  );
}

export function AllProductsList({
  products,
  totalCount,
  currentPage,
  pageSize,
  leaflets,
  currentLeafletId,
  currentStatus,
  currentCategory,
  hasCompletedLeaflets = false,
}: AllProductsListProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportMode, setExportMode] = useState<"all" | "filtered" | "selected">("all");

  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!(currentLeafletId || currentStatus || currentCategory);

  // Get unique categories from products for the filter dropdown
  const categories = Array.from(
    new Set(products.map(p => p.category).filter((c): c is string => c !== null && c !== undefined))
  ).sort();

  // Build edit query string for navigation context
  const editQueryString = (() => {
    const params = new URLSearchParams();
    if (currentLeafletId) params.set("leaflet_id", currentLeafletId);
    if (currentStatus) params.set("status", currentStatus);
    return params.toString();
  })();

  // Build export filters from current page state
  const currentExportFilters: ProductExportFilters | undefined = hasFilters
    ? {
        ...(currentLeafletId ? { leaflet_id: currentLeafletId } : {}),
        ...(currentStatus ? { review_status: [currentStatus] } : {}),
        ...(currentCategory ? { category: currentCategory } : {}),
        sort_by: "created_at",
        sort_order: "desc" as const,
      }
    : undefined;

  // Filter locally by search (server already filters by leaflet_id and status)
  const filteredProducts = products.filter(p => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        p.product_name.toLowerCase().includes(query) ||
        p.brand?.toLowerCase().includes(query) ||
        p.product_code?.toLowerCase().includes(query)
      );
    }
    return true;
  });

  const updateFilters = (key: string, value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.set("page", "1"); // Reset to first page
    router.push(`/products?${params.toString()}`);
  };

  const goToPage = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", page.toString());
    router.push(`/products?${params.toString()}`);
  };

  // Selection handlers
  const toggleProduct = (productId: string) => {
    setSelectedProducts(prev => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedProducts.size === filteredProducts.length) {
      setSelectedProducts(new Set());
    } else {
      setSelectedProducts(new Set(filteredProducts.map(p => p.id)));
    }
  };

  const clearSelection = () => {
    setSelectedProducts(new Set());
  };

  // Export handlers
  const handleExportClick = () => {
    if (selectedProducts.size > 0) {
      setExportMode("selected");
    } else if (hasFilters) {
      setExportMode("filtered");
    } else {
      setExportMode("all");
    }
    setExportDialogOpen(true);
  };

  const handleExportSelected = () => {
    setExportMode("selected");
    setExportDialogOpen(true);
  };

  // Export button label
  const exportLabel = (() => {
    if (selectedProducts.size > 0) {
      return `Export Selected (${selectedProducts.size})`;
    }
    if (hasFilters) {
      return `Export Filtered (${totalCount})`;
    }
    return "Export All";
  })();

  // Show helpful message if no products but have completed leaflets
  if (products.length === 0 && !currentLeafletId && !currentStatus) {
    return (
      <Card style={{ borderColor: colors.borderGray }}>
        <CardContent className="py-12 text-center">
          <ImageIcon className="h-12 w-12 mx-auto mb-4" style={{ color: colors.secondaryText }} />
          <h3 className="text-lg font-medium mb-2" style={{ color: colors.primaryText }}>No Products Found</h3>
          {hasCompletedLeaflets ? (
            <div className="space-y-2" style={{ color: colors.secondaryText }}>
              <p>Leaflet processing completed but no products were extracted.</p>
              <p className="text-sm">This could mean:</p>
              <ul className="text-sm text-left max-w-md mx-auto mt-2 space-y-1">
                <li>- The VLM extraction task hasn&apos;t run yet (check Celery workers)</li>
                <li>- The PDF pages didn&apos;t contain recognizable products</li>
                <li>- There was an error during extraction (check logs)</li>
              </ul>
              <div className="mt-4">
                <Link href="/dashboard">
                  <Button variant="outline" style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
                    <FileText className="h-4 w-4 mr-2" />
                    View Leaflets
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <p style={{ color: colors.secondaryText }}>
              Upload a leaflet to start extracting products.
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card style={{ borderColor: colors.borderGray }}>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4 md:items-center">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: colors.secondaryText }} />
              <Input
                placeholder="Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            {/* Leaflet filter */}
            <Select
              value={currentLeafletId || "all"}
              onValueChange={(value) => updateFilters("leaflet_id", value === "all" ? null : value)}
            >
              <SelectTrigger className="min-w-[200px]" style={{ borderColor: colors.borderGray }}>
                <SelectValue placeholder="All Leaflets" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Leaflets</SelectItem>
                {leaflets.map(leaflet => (
                  <SelectItem key={leaflet.id} value={leaflet.id}>
                    {leaflet.filename} ({leaflet.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Status filter */}
            <div className="flex gap-2">
              {[
                { value: "", label: "All" },
                { value: "approved", label: "Approved" },
                { value: "pending", label: "Pending" },
                { value: "rejected", label: "Rejected" },
              ].map(({ value, label }) => (
                <Button
                  key={value}
                  variant={(currentStatus || "") === value ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => updateFilters("status", value || null)}
                  style={(currentStatus || "") !== value ? { borderColor: colors.borderGray, color: colors.primaryText } : {}}
                >
                  {label}
                </Button>
              ))}
            </div>

            {/* Category filter */}
            {categories.length > 0 && (
              <Select
                value={currentCategory || "all"}
                onValueChange={(value) => updateFilters("category", value === "all" ? null : value)}
              >
                <SelectTrigger className="min-w-[180px]" style={{ borderColor: colors.borderGray }}>
                  <Folder className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                  <SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map(category => (
                    <SelectItem key={category} value={category}>
                      {category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* View mode toggle */}
            <div className="flex gap-1 border rounded-md p-1" style={{ borderColor: colors.borderGray }}>
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="icon"
                className="h-8 w-8"
                onClick={() => setViewMode("grid")}
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "table" ? "secondary" : "ghost"}
                size="icon"
                className="h-8 w-8"
                onClick={() => setViewMode("table")}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>

            {/* Export button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportClick}
              disabled={totalCount === 0}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              <Download className="h-4 w-4 mr-2" />
              {exportLabel}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Products Display */}
      {filteredProducts.length === 0 ? (
        <Card style={{ borderColor: colors.borderGray }}>
          <CardContent className="py-12 text-center">
            <ImageIcon className="h-12 w-12 mx-auto mb-4" style={{ color: colors.secondaryText }} />
            <h3 className="text-lg font-medium mb-2" style={{ color: colors.primaryText }}>No Products Found</h3>
            <p style={{ color: colors.secondaryText }}>
              {products.length === 0
                ? "No products have been extracted yet."
                : "No products match your search criteria."}
            </p>
          </CardContent>
        </Card>
      ) : viewMode === "grid" ? (
        <>
          {/* Select all for grid view */}
          <div className="flex items-center gap-3">
            <Checkbox
              checked={
                filteredProducts.length > 0 &&
                selectedProducts.size === filteredProducts.length
              }
              onCheckedChange={toggleSelectAll}
              aria-label="Select all products on this page"
            />
            <span className="text-sm text-muted-foreground">
              Select all ({filteredProducts.length})
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
            {filteredProducts.map(product => (
              <ProductCard
                key={product.id}
                product={product}
                editQueryString={editQueryString}
                isSelected={selectedProducts.has(product.id)}
                onToggleSelect={toggleProduct}
              />
            ))}
          </div>
        </>
      ) : (
        <Card style={{ borderColor: colors.borderGray }}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
                  <th className="p-3 w-10">
                    <Checkbox
                      checked={
                        filteredProducts.length > 0 &&
                        selectedProducts.size === filteredProducts.length
                      }
                      onCheckedChange={toggleSelectAll}
                      aria-label="Select all products on this page"
                    />
                  </th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Product</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Brand</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Category</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Price</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Leaflet</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Page</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Status</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Confidence</th>
                  <th className="text-left p-3 font-medium" style={{ color: colors.primaryText }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map(product => (
                  <ProductTableRow
                    key={product.id}
                    product={product}
                    leaflet={leaflets.find(l => l.id === product.leaflet_id)}
                    editQueryString={editQueryString}
                    isSelected={selectedProducts.has(product.id)}
                    onToggleSelect={toggleProduct}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Selection bar */}
      {selectedProducts.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
          <Card
            className="shadow-lg border-2"
            style={{ borderColor: colors.primaryBrandBlue }}
          >
            <CardContent className="p-3 px-5">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Checkbox checked={true} aria-hidden="true" />
                  <span
                    className="text-sm font-medium whitespace-nowrap"
                    style={{ color: colors.primaryText }}
                  >
                    {selectedProducts.size} selected
                  </span>
                </div>

                <Button
                  size="sm"
                  onClick={handleExportSelected}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export Selected
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearSelection}
                  className="text-muted-foreground"
                >
                  <X className="h-4 w-4 mr-1" />
                  Clear
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm" style={{ color: colors.secondaryText }}>
            Showing {(currentPage - 1) * pageSize + 1} to{" "}
            {Math.min(currentPage * pageSize, totalCount)} of {totalCount} products
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage === 1}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }

                return (
                  <Button
                    key={pageNum}
                    variant={currentPage === pageNum ? "default" : "outline"}
                    size="sm"
                    onClick={() => goToPage(pageNum)}
                    className="w-8"
                    style={currentPage === pageNum
                      ? { backgroundColor: colors.primaryBrandBlue, color: "white" }
                      : { borderColor: colors.borderGray, color: colors.primaryText }
                    }
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage === totalPages}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Export Dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onOpenChange={setExportDialogOpen}
        mode={exportMode}
        filters={currentExportFilters}
        selectedIds={
          exportMode === "selected" ? Array.from(selectedProducts) : undefined
        }
      />
    </div>
  );
}

function ProductCard({
  product,
  editQueryString,
  isSelected,
  onToggleSelect,
}: {
  product: Product;
  editQueryString?: string;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const { imageSrc, imageError, onImageError } = useProductImage(product);

  return (
    <Card
      className={cn(
        "overflow-hidden transition-all hover:shadow-lg group relative",
        !product.validation_passed && "border-orange-300 bg-orange-50/30",
        isSelected && "ring-2 ring-primary"
      )}
      style={{ borderColor: product.validation_passed && !isSelected ? colors.borderGray : undefined }}
    >
      {/* Selection checkbox overlay */}
      <div className="absolute top-2 right-2 z-10">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onToggleSelect(product.id)}
          aria-label={`Select ${product.product_name}`}
          className="bg-white/90 shadow-sm"
        />
      </div>

      {/* Image */}
      <div className="aspect-[4/3] relative overflow-hidden" style={{ backgroundColor: colors.offWhiteBg }}>
        {imageSrc && !imageError ? (
          <NextImage
            src={imageSrc}
            alt={product.product_name || "Product"}
            fill
            className="object-contain p-2 transition-transform group-hover:scale-105"
            unoptimized
            onError={onImageError}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon className="h-12 w-12" style={{ color: colors.secondaryText, opacity: 0.3 }} />
          </div>
        )}

        {/* Overlay badges */}
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          <span
            className="inline-flex items-center px-2 py-1 rounded text-xs font-medium"
            style={{ backgroundColor: colors.offWhiteBg, color: colors.secondaryText }}
          >
            Page {product.page_number}
          </span>
        </div>

        {/* Validation warning */}
        {!product.validation_passed && (
          <div className="absolute bottom-2 right-2">
            <span
              className="inline-flex items-center px-2 py-1 rounded text-xs"
              style={{ backgroundColor: colors.errorBg, color: colors.error }}
            >
              <AlertTriangle className="h-3 w-3" />
            </span>
          </div>
        )}
      </div>

      <CardContent className="p-4">
        {/* Status & Confidence */}
        <div className="flex items-center justify-between mb-3">
          <StatusBadge status={product.review_status} />
          <ConfidenceBadge confidence={product.confidence} />
        </div>

        {/* Product info */}
        <h3 className="font-semibold text-sm line-clamp-2 mb-1 min-h-[2.5rem]" style={{ color: colors.primaryText }} title={product.product_name}>
          {product.product_name}
        </h3>

        {product.brand && (
          <p className="text-xs mb-1" style={{ color: colors.secondaryText }}>{product.brand}</p>
        )}

        {/* Category badge */}
        {product.category && (
          <div className="mb-2">
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs"
              style={{ backgroundColor: colors.offWhiteBg, color: colors.secondaryText }}
            >
              <Folder className="h-3 w-3" />
              {product.category}
            </span>
          </div>
        )}

        {/* Price */}
        <div className="mb-3">
          <div className="flex items-baseline gap-2">
            {/* Show discounted_price as main price when discount exists */}
            {product.discounted_price !== null && (
              <span className="text-lg font-bold" style={{ color: colors.success }}>
                {product.currency || ""} {product.discounted_price.toFixed(2)}
              </span>
            )}
            {/* Only show regular_price with strikethrough if BOTH prices exist AND are different */}
            {product.regular_price !== null && product.discounted_price !== null && product.regular_price !== product.discounted_price && (
              <span className="text-sm line-through" style={{ color: colors.secondaryText }}>
                {product.currency || ""} {product.regular_price.toFixed(2)}
              </span>
            )}
            {/* If only regular_price exists (no discounted_price), show it as current price */}
            {product.regular_price !== null && product.discounted_price === null && (
              <span className="text-lg font-bold" style={{ color: colors.success }}>
                {product.currency || ""} {product.regular_price.toFixed(2)}
              </span>
            )}
          </div>
          {product.discount_percentage !== null && product.discount_percentage > 0 && (
            <span
              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-1"
              style={{ backgroundColor: colors.errorBg, color: colors.error }}
            >
              -{parseFloat(product.discount_percentage.toFixed(2))}% OFF
            </span>
          )}
        </div>

        {/* Quick info */}
        {(product.quantity || product.product_code) && (
          <div className="text-xs space-y-0.5 mb-3 border-t pt-2" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>
            {product.quantity && product.units && (
              <p>{product.quantity} {product.units}</p>
            )}
            {product.product_code && (
              <p className="font-mono">SKU: {product.product_code}</p>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="flex-1" style={{ borderColor: colors.borderGray, color: colors.primaryText }} asChild>
            <Link href={`/products/${product.id}`}>
              <Eye className="h-3.5 w-3.5 mr-1" />
              View
            </Link>
          </Button>
          <Button variant="outline" size="sm" className="flex-1" style={{ borderColor: colors.borderGray, color: colors.primaryText }} asChild>
            <Link href={`/products/${product.id}/edit${editQueryString ? `?${editQueryString}` : ""}`}>
              <Edit2 className="h-3.5 w-3.5 mr-1" />
              Edit
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ProductTableRow({
  product,
  leaflet,
  editQueryString,
  isSelected,
  onToggleSelect,
}: {
  product: Product;
  leaflet?: Leaflet;
  editQueryString?: string;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const { imageSrc, imageError, onImageError } = useProductImage(product);

  return (
    <tr
      className={cn(
        "border-b transition-colors",
        isSelected && "bg-primary/5"
      )}
      style={{ borderColor: colors.borderGray }}
      onMouseEnter={(e) => {
        if (!isSelected) e.currentTarget.style.backgroundColor = colors.hoverGray;
      }}
      onMouseLeave={(e) => {
        if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
      }}
    >
      <td className="p-3 w-10">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onToggleSelect(product.id)}
          aria-label={`Select ${product.product_name}`}
        />
      </td>
      <td className="p-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded overflow-hidden flex-shrink-0" style={{ backgroundColor: colors.offWhiteBg }}>
            {imageSrc && !imageError ? (
              <NextImage
                src={imageSrc}
                alt=""
                width={40}
                height={40}
                className="object-contain w-full h-full p-1"
                unoptimized
                onError={onImageError}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ImageIcon className="h-4 w-4" style={{ color: colors.secondaryText }} />
              </div>
            )}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-sm truncate max-w-[200px]" style={{ color: colors.primaryText }} title={product.product_name}>
              {product.product_name}
            </p>
            {product.product_code && (
              <p className="text-xs" style={{ color: colors.secondaryText }}>{product.product_code}</p>
            )}
          </div>
        </div>
      </td>
      <td className="p-3" style={{ color: colors.secondaryText }}>
        {product.brand || "\u2014"}
      </td>
      <td className="p-3">
        {product.category ? (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs"
            style={{ backgroundColor: colors.offWhiteBg, color: colors.secondaryText }}
          >
            <Folder className="h-3 w-3" />
            {product.category}
          </span>
        ) : (
          <span style={{ color: colors.secondaryText }}>{"\u2014"}</span>
        )}
      </td>
      <td className="p-3">
        <div className="flex items-center gap-1">
          {product.discounted_price !== null && (
            <span className="font-medium" style={{ color: colors.success }}>
              {product.currency || ""} {product.discounted_price.toFixed(2)}
            </span>
          )}
          {product.discounted_price === null && product.regular_price !== null && (
            <span className="font-medium" style={{ color: colors.success }}>
              {product.currency || ""} {product.regular_price.toFixed(2)}
            </span>
          )}
          {product.discount_percentage !== null && product.discount_percentage > 0 && (
            <span
              className="inline-flex items-center px-1.5 py-0.5 rounded text-xs"
              style={{ backgroundColor: colors.errorBg, color: colors.error }}
            >
              -{parseFloat(product.discount_percentage.toFixed(2))}%
            </span>
          )}
        </div>
      </td>
      <td className="p-3">
        {leaflet ? (
          <Link
            href={`/leaflets/${leaflet.id}`}
            className="text-xs flex items-center gap-1 hover:underline"
            style={{ color: colors.primaryBrandBlue }}
          >
            <FileText className="h-3 w-3" />
            {leaflet.filename.slice(0, 20)}...
          </Link>
        ) : (
          <span className="text-xs" style={{ color: colors.secondaryText }}>{"\u2014"}</span>
        )}
      </td>
      <td className="p-3" style={{ color: colors.secondaryText }}>
        {product.page_number}
      </td>
      <td className="p-3">
        <StatusBadge status={product.review_status} />
      </td>
      <td className="p-3">
        <ConfidenceBadge confidence={product.confidence} />
      </td>
      <td className="p-3">
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
            <Link href={`/products/${product.id}`}>
              <Eye className="h-4 w-4" style={{ color: colors.primaryText }} />
            </Link>
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
            <Link href={`/products/${product.id}/edit${editQueryString ? `?${editQueryString}` : ""}`}>
              <Edit2 className="h-4 w-4" style={{ color: colors.primaryText }} />
            </Link>
          </Button>
        </div>
      </td>
    </tr>
  );
}
