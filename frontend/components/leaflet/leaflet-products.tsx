"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import NextImage from "next/image";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Search,
  Eye,
  Edit2,
  ImageIcon,
  Package,
  Zap,
  Clock,
  LayoutGrid,
  List,
  ArrowUpDown,
  Filter,
  TrendingDown,
  Tag,
  ShoppingCart,
  Percent,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Folder,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ExportMenu } from "@/components/leaflet/export-menu";
import { getProducts, refreshProductImageUrl } from "@/lib/actions/products";
import type { Product, LeafletPage } from "@/lib/types";

interface LeafletProductsProps {
  products: Product[];
  leafletId: string;
  pages: LeafletPage[];
  /** Server-provided total product count (avoids needing to load all products). */
  totalProducts?: number;
}

type ViewMode = "grid" | "table" | "compact";
type FilterStatus = "all" | "auto_approved" | "approved" | "pending" | "rejected" | "needs_correction";
type SortField = "page" | "name" | "price" | "confidence" | "status";
type SortOrder = "asc" | "desc";

const ITEMS_PER_PAGE = 24;

/** Maps frontend sort field names to backend query parameter values. */
const sortFieldToBackend: Record<SortField, string> = {
  page: "page_number",
  name: "product_name",
  price: "regular_price",
  confidence: "confidence",
  status: "review_status",
};

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
    (product.image?.storage_type === "file") ||
    false
  );
}

/**
 * Hook that resolves the product image src and automatically refreshes
 * expired S3 presigned URLs on load failure.  For base64 images, no
 * refresh is attempted -- they either work or show the placeholder.
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
    // If this is a file-stored image and we haven't tried refreshing yet,
    // attempt to get a fresh presigned URL from the backend.
    if (isFileStoredImage(product) && !refreshAttempted) {
      setRefreshAttempted(true);
      refreshProductImageUrl(product.id).then((result) => {
        if (result.success && result.data?.image_url) {
          setRefreshedUrl(fixMinioUrl(result.data.image_url));
          // Reset error so the <img> re-renders with the new URL
          setImageError(false);
        } else {
          // Refresh failed -- show placeholder
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
  const config: Record<string, { label: string; className: string; icon: typeof CheckCircle }> = {
    auto_approved: { label: "Auto Approved", className: "bg-blue-100 text-blue-700 border-blue-200", icon: Zap },
    approved: { label: "Approved", className: "bg-green-100 text-green-700 border-green-200", icon: CheckCircle },
    pending: { label: "Pending Review", className: "bg-amber-100 text-amber-700 border-amber-200", icon: Clock },
    rejected: { label: "Rejected", className: "bg-red-100 text-red-700 border-red-200", icon: XCircle },
    needs_correction: { label: "Needs Fix", className: "bg-orange-100 text-orange-700 border-orange-200", icon: AlertTriangle },
    corrected: { label: "Corrected", className: "bg-purple-100 text-purple-700 border-purple-200", icon: Edit2 },
  };
  
  const cfg = config[status] || { label: status, className: "bg-gray-100 text-gray-700 border-gray-200", icon: Clock };
  const Icon = cfg.icon;
  
  return (
    <Badge variant="outline" className={cn("text-xs gap-1 font-medium", cfg.className)}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </Badge>
  );
}

function ConfidenceMeter({ confidence, showLabel = true }: { confidence: number | null; showLabel?: boolean }) {
  if (confidence === null) return <span className="text-xs text-muted-foreground">—</span>;
  
  const percentage = Math.round(confidence * 100);
  const color = percentage >= 90 
    ? "bg-green-500" 
    : percentage >= 75 
      ? "bg-amber-500" 
      : "bg-red-500";
  const textColor = percentage >= 90 
    ? "text-green-700" 
    : percentage >= 75 
      ? "text-amber-700" 
      : "text-red-700";
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-2">
            <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
              <div 
                className={cn("h-full transition-all", color)} 
                style={{ width: `${percentage}%` }} 
              />
            </div>
            {showLabel && (
              <span className={cn("text-xs font-mono font-medium", textColor)}>
                {percentage}%
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>Extraction confidence: {percentage}%</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function PriceDisplay({ product }: { product: Product }) {
  const formatPrice = (price: number | null) => {
    if (price === null) return null;
    return price.toFixed(2);
  };

  const currency = product.currency || "";

  if (product.discounted_price === null && product.regular_price === null) {
    return <span className="text-sm text-muted-foreground">No price</span>;
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-2">
        {/* Show discounted_price as main price (whether it's discounted or regular) */}
        {product.discounted_price !== null && (
          <span className="text-lg font-bold text-green-700">
            {currency}{formatPrice(product.discounted_price)}
          </span>
        )}
        {/* Only show regular_price with strikethrough if BOTH prices exist AND are different */}
        {product.regular_price !== null && product.discounted_price !== null && product.regular_price !== product.discounted_price && (
          <span className="text-sm text-muted-foreground line-through">
            {currency}{formatPrice(product.regular_price)}
          </span>
        )}
        {/* If only regular_price exists (no discounted_price), show it as current price */}
        {product.regular_price !== null && product.discounted_price === null && (
          <span className="text-lg font-bold text-green-700">
            {currency}{formatPrice(product.regular_price)}
          </span>
        )}
      </div>
      {product.discount_percentage !== null && product.discount_percentage > 0 && (
        <Badge variant="destructive" className="w-fit text-xs mt-1">
          <Percent className="h-3 w-3 mr-0.5" />
          {parseFloat(product.discount_percentage.toFixed(2))}% OFF
        </Badge>
      )}
    </div>
  );
}

function StatsCard({ 
  label, 
  value, 
  icon: Icon, 
  className,
  subValue 
}: { 
  label: string; 
  value: number | string; 
  icon: typeof Package;
  className?: string;
  subValue?: string;
}) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-muted">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <div className="text-2xl font-bold">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
          {subValue && (
            <div className="text-xs text-muted-foreground mt-0.5">{subValue}</div>
          )}
        </div>
      </div>
    </Card>
  );
}

export function LeafletProducts({ products: initialProducts, leafletId, pages, totalProducts }: LeafletProductsProps) {
  const router = useRouter();
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [pageFilter, setPageFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sortField, setSortField] = useState<SortField>("page");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [currentPage, setCurrentPage] = useState(1);

  // Products loaded so far from the server. Starts with the initial page
  // passed as props; additional pages are fetched on demand when the user
  // navigates beyond what is already loaded.
  const [allProducts, setAllProducts] = useState<Product[]>(initialProducts);
  const [serverTotal, setServerTotal] = useState<number>(totalProducts ?? initialProducts.length);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Track the next server page to fetch.  We use an explicit counter rather
  // than deriving it from allProducts.length because deduplication can cause
  // the array length to diverge from the number of pages already fetched.
  // The initial products correspond to page 1, so the next page is 2.
  const [nextServerPage, setNextServerPage] = useState(2);

  // Track whether all products have been fetched from the server
  const allLoaded = allProducts.length >= serverTotal;

  // Fetch the next batch of products from the server when the user paginates
  // beyond the currently loaded set.
  const SERVER_PAGE_SIZE = 50;

  // Standalone fetch helper that takes sort params as explicit arguments,
  // avoiding stale-closure issues when sort state changes between renders.
  const fetchProductPage = useCallback(async (
    page: number,
    field: SortField,
    order: SortOrder,
  ) => {
    return getProducts({
      leafletId,
      pageSize: SERVER_PAGE_SIZE,
      page,
      sortBy: sortFieldToBackend[field],
      sortOrder: order,
    });
  }, [leafletId]);

  const loadMoreProducts = useCallback(async () => {
    if (allLoaded || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const data = await fetchProductPage(nextServerPage, sortField, sortOrder);

      // Always advance the page counter so we never re-fetch the same page,
      // even when deduplication removes some products from the batch.
      // Cap at max possible page to prevent overflow for very large leaflets.
      setNextServerPage(prev => Math.min(prev + 1, Math.ceil(serverTotal / SERVER_PAGE_SIZE) + 1));

      if (data.products.length > 0) {
        setAllProducts(prev => {
          // Deduplicate in case of concurrent fetches or backend sort drift
          const existingIds = new Set(prev.map(p => p.id));
          const newProducts = data.products.filter(p => !existingIds.has(p.id));
          return [...prev, ...newProducts];
        });
      }
      if (data.total) {
        setServerTotal(data.total);
      }
    } catch (error) {
      console.error("Failed to load more products:", error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [allLoaded, isLoadingMore, nextServerPage, fetchProductPage, sortField, sortOrder, serverTotal]);

  // Get unique categories from loaded products
  const categories = useMemo(() => {
    const cats = new Set<string>();
    allProducts.forEach(p => {
      if (p.category) cats.add(p.category);
    });
    return Array.from(cats).sort();
  }, [allProducts]);

  // Calculate stats from loaded products
  // Use serverTotal for the headline "total" so it is accurate even before
  // all products are loaded.
  const stats = useMemo(() => ({
    total: serverTotal,
    autoApproved: allProducts.filter(p => p.review_status === "auto_approved").length,
    approved: allProducts.filter(p => p.review_status === "approved").length,
    pending: allProducts.filter(p => p.review_status === "pending").length,
    needsCorrection: allProducts.filter(p => p.review_status === "needs_correction").length,
    rejected: allProducts.filter(p => p.review_status === "rejected").length,
    avgConfidence: allProducts.length > 0
      ? allProducts.reduce((sum, p) => sum + (p.confidence || 0), 0) / allProducts.length
      : 0,
    validationPassed: allProducts.filter(p => p.validation_passed).length,
    withDiscount: allProducts.filter(p => p.discount_percentage && p.discount_percentage > 0).length,
    avgDiscount: allProducts.filter(p => p.discount_percentage && p.discount_percentage > 0).length > 0
      ? allProducts
          .filter(p => p.discount_percentage && p.discount_percentage > 0)
          .reduce((sum, p) => sum + (p.discount_percentage || 0), 0) /
        allProducts.filter(p => p.discount_percentage && p.discount_percentage > 0).length
      : 0,
  }), [allProducts, serverTotal]);

  // Filter and sort loaded products
  const filteredProducts = useMemo(() => {
    let result = [...allProducts];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(p =>
        p.product_name.toLowerCase().includes(query) ||
        p.brand?.toLowerCase().includes(query) ||
        p.product_code?.toLowerCase().includes(query)
      );
    }

    // Status filter
    if (statusFilter !== "all") {
      result = result.filter(p => p.review_status === statusFilter);
    }

    // Page filter
    if (pageFilter !== "all") {
      result = result.filter(p => p.page_number === parseInt(pageFilter));
    }

    // Category filter
    if (categoryFilter !== "all") {
      result = result.filter(p => p.category === categoryFilter);
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "page":
          comparison = a.page_number - b.page_number;
          if (comparison === 0) comparison = a.bounding_box.y - b.bounding_box.y;
          break;
        case "name":
          comparison = a.product_name.localeCompare(b.product_name);
          break;
        case "price":
          comparison = (a.discounted_price || a.regular_price || 0) - (b.discounted_price || b.regular_price || 0);
          break;
        case "confidence":
          comparison = (a.confidence || 0) - (b.confidence || 0);
          break;
        case "status":
          comparison = a.review_status.localeCompare(b.review_status);
          break;
      }
      return sortOrder === "asc" ? comparison : -comparison;
    });

    return result;
  }, [allProducts, searchQuery, statusFilter, pageFilter, categoryFilter, sortField, sortOrder]);

  // Pagination (client-side, over loaded + filtered products)
  const totalPages = Math.ceil(filteredProducts.length / ITEMS_PER_PAGE);
  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredProducts.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredProducts, currentPage]);

  // When the user reaches the last page of loaded products and there are
  // more on the server, automatically fetch the next batch.
  useEffect(() => {
    const endOfCurrentView = currentPage * ITEMS_PER_PAGE;
    if (endOfCurrentView >= filteredProducts.length && !allLoaded) {
      loadMoreProducts();
    }
  }, [currentPage, filteredProducts.length, allLoaded, loadMoreProducts]);

  // Reset page when filters change
  const handleFilterChange = () => {
    setCurrentPage(1);
  };

  if (allProducts.length === 0 && serverTotal === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-16 text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
            <Package className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-2">No Products Extracted Yet</h3>
          <p className="text-muted-foreground mb-4 max-w-md mx-auto">
            Products will appear here after extraction is complete. The AI will analyze 
            each page and extract product information.
          </p>
          
          <Button variant="outline" className="mt-6" onClick={() => router.refresh()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh Page
          </Button>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard
          label="Total Products"
          value={stats.total}
          icon={ShoppingCart}
        />
        <StatsCard
          label="Pending Review"
          value={stats.pending}
          icon={Clock}
          className={stats.pending > 0 ? "bg-amber-50 border-amber-100" : ""}
        />
        <StatsCard
          label="Avg Confidence"
          value={`${Math.round(stats.avgConfidence * 100)}%`}
          icon={Tag}
          className={stats.avgConfidence >= 0.9 ? "bg-green-50 border-green-100" : ""}
        />
        <StatsCard
          label="With Discounts"
          value={stats.withDiscount}
          icon={TrendingDown}
          subValue={stats.avgDiscount > 0 ? `Avg: ${parseFloat(stats.avgDiscount.toFixed(2))}% off` : undefined}
        />
      </div>
      
      {/* Filters & Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, brand, or code..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); handleFilterChange(); }}
                className="pl-10"
              />
            </div>
            
            {/* Filters */}
            <div className="flex flex-wrap gap-2">
              <Select 
                value={statusFilter} 
                onValueChange={(v) => { setStatusFilter(v as FilterStatus); handleFilterChange(); }}
              >
                <SelectTrigger className="w-[150px]">
                  <Filter className="h-4 w-4 mr-2" />
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="auto_approved">Auto Approved</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="needs_correction">Needs Fix</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
              
              <Select
                value={pageFilter}
                onValueChange={(v) => { setPageFilter(v); handleFilterChange(); }}
              >
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="Page" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Pages</SelectItem>
                  {pages.map(page => (
                    <SelectItem key={page.page_number} value={page.page_number.toString()}>
                      Page {page.page_number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {categories.length > 0 && (
                <Select
                  value={categoryFilter}
                  onValueChange={(v) => { setCategoryFilter(v); handleFilterChange(); }}
                >
                  <SelectTrigger className="w-[160px]">
                    <Folder className="h-4 w-4 mr-2" />
                    <SelectValue placeholder="Category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Categories</SelectItem>
                    {categories.map(cat => (
                      <SelectItem key={cat} value={cat}>
                        {cat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              <Select
                value={`${sortField}-${sortOrder}`} 
                onValueChange={async (v) => {
                  const [field, order] = v.split("-") as [SortField, SortOrder];
                  setSortField(field);
                  setSortOrder(order);
                  setCurrentPage(1);
                  // Do NOT clear allProducts/nextServerPage before the fetch --
                  // that would cause filteredProducts.length to drop to 0 and
                  // trigger the auto-load-more useEffect, racing with this fetch.
                  setIsLoadingMore(true);
                  try {
                    const data = await fetchProductPage(1, field, order);
                    // Replace products and reset page counter AFTER fetch succeeds
                    setAllProducts(data.products || []);
                    if (data.total) setServerTotal(data.total);
                    setNextServerPage(2);
                  } catch (error) {
                    console.error("Failed to re-fetch products with new sort:", error);
                  } finally {
                    setIsLoadingMore(false);
                  }
                }}
              >
                <SelectTrigger className="w-[160px]">
                  <ArrowUpDown className="h-4 w-4 mr-2" />
                  <SelectValue placeholder="Sort" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="page-asc">Page (Asc)</SelectItem>
                  <SelectItem value="page-desc">Page (Desc)</SelectItem>
                  <SelectItem value="name-asc">Name (A-Z)</SelectItem>
                  <SelectItem value="name-desc">Name (Z-A)</SelectItem>
                  <SelectItem value="price-asc">Price (Low-High)</SelectItem>
                  <SelectItem value="price-desc">Price (High-Low)</SelectItem>
                  <SelectItem value="confidence-desc">Confidence (High)</SelectItem>
                  <SelectItem value="confidence-asc">Confidence (Low)</SelectItem>
                </SelectContent>
              </Select>
              
              {/* View Mode Toggle */}
              <div className="flex border rounded-md">
                <Button
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("grid")}
                  className="rounded-r-none"
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === "table" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("table")}
                  className="rounded-none border-x"
                >
                  <List className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === "compact" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("compact")}
                  className="rounded-l-none"
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Products Display */}
      {viewMode === "grid" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
          {paginatedProducts.map(product => (
            <ProductGridCard key={product.id} product={product} pageFilter={pageFilter} />
          ))}
        </div>
      )}
      
      {viewMode === "compact" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {paginatedProducts.map(product => (
            <ProductCompactCard key={product.id} product={product} />
          ))}
        </div>
      )}
      
      {viewMode === "table" && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="p-3 text-left text-sm font-medium">Product</th>
                  <th className="p-3 text-left text-sm font-medium">Brand</th>
                  <th className="p-3 text-left text-sm font-medium">Category</th>
                  <th className="p-3 text-left text-sm font-medium">Price</th>
                  <th className="p-3 text-left text-sm font-medium">Page</th>
                  <th className="p-3 text-left text-sm font-medium">Status</th>
                  <th className="p-3 text-left text-sm font-medium">Confidence</th>
                  <th className="p-3 text-left text-sm font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedProducts.map(product => (
                  <ProductTableRow key={product.id} product={product} pageFilter={pageFilter} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      
      {/* Loading skeletons for server-side pagination */}
      {/* Show fewer skeletons than ITEMS_PER_PAGE for cleaner loading UX */}
      {isLoadingMore && viewMode === "grid" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={`skeleton-${i}`} className="overflow-hidden">
              <div className="aspect-[4/3] bg-muted animate-pulse" />
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="h-5 w-24 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-16 bg-muted rounded animate-pulse" />
                </div>
                <div className="h-4 w-full bg-muted rounded animate-pulse" />
                <div className="h-4 w-2/3 bg-muted rounded animate-pulse" />
                <div className="h-6 w-20 bg-muted rounded animate-pulse" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {isLoadingMore && viewMode === "compact" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={`skeleton-${i}`} className="overflow-hidden">
              <div className="aspect-square bg-muted animate-pulse" />
              <div className="p-2 space-y-1">
                <div className="h-3 w-full bg-muted rounded animate-pulse" />
                <div className="h-3 w-12 bg-muted rounded animate-pulse" />
              </div>
            </Card>
          ))}
        </div>
      )}
      {isLoadingMore && viewMode === "table" && (
        <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading more products...
        </div>
      )}

      {/* Load More button when products remain on the server */}
      {!allLoaded && (
        <div className="flex justify-center pt-2">
          <Button
            variant="outline"
            onClick={loadMoreProducts}
            disabled={isLoadingMore}
            className="gap-2"
          >
            {isLoadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : <Package className="h-4 w-4" />}
            {isLoadingMore ? "Loading..." : `Load More Products (${serverTotal - allProducts.length} remaining)`}
            {!isLoadingMore && (
              <span className="text-xs text-muted-foreground">
                ({allProducts.length} of {serverTotal} loaded)
              </span>
            )}
          </Button>
        </div>
      )}

      {/* Pagination & Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
        <p className="text-sm text-muted-foreground">
          Showing {Math.min(((currentPage - 1) * ITEMS_PER_PAGE) + 1, filteredProducts.length)}{filteredProducts.length > 0 ? ` - ${Math.min(currentPage * ITEMS_PER_PAGE, filteredProducts.length)}` : ""} of {serverTotal} products
          {!allLoaded && ` (${allProducts.length} loaded)`}
          {filteredProducts.length !== allProducts.length && allProducts.length > 0 && ` (${filteredProducts.length} matching filters)`}
        </p>
        
        <div className="flex items-center gap-4">
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
          
          {/* Actions */}
          <div className="flex gap-2">
            {stats.pending > 0 && (
              <Button variant="outline" size="sm" asChild>
                <Link href={`/review?leaflet_id=${leafletId}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  Review {stats.pending} Pending
                </Link>
              </Button>
            )}
            <ExportMenu
              leafletId={leafletId}
              productCount={serverTotal}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductGridCard({ product, pageFilter }: { product: Product; pageFilter: string }) {
  const { imageSrc, imageError, onImageError } = useProductImage(product);

  return (
    <Card className={cn(
      "overflow-hidden transition-all hover:shadow-lg group",
      !product.validation_passed && "border-orange-300 bg-orange-50/30"
    )}>
      {/* Image */}
      <div className="aspect-[4/3] bg-gradient-to-b from-muted/50 to-muted relative overflow-hidden">
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
            <ImageIcon className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}
        
        {/* Overlay badges */}
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          <Badge variant="secondary" className="text-xs font-medium">
            Page {product.page_number}
          </Badge>
        </div>
        
        {/* Validation warning */}
        {!product.validation_passed && (
          <div className="absolute top-2 right-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="destructive" className="text-xs">
                    <AlertTriangle className="h-3 w-3" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Has validation issues</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
      </div>
      
      <CardContent className="p-4">
        {/* Status & Confidence */}
        <div className="flex items-center justify-between mb-3">
          <StatusBadge status={product.review_status} />
          <ConfidenceMeter confidence={product.confidence} />
        </div>
        
        {/* Product info */}
        <h3 className="font-semibold text-sm line-clamp-2 mb-1 min-h-[2.5rem]" title={product.product_name}>
          {product.product_name}
        </h3>
        
        {product.brand && (
          <p className="text-xs text-muted-foreground mb-1">{product.brand}</p>
        )}

        {/* Category badge */}
        {product.category && (
          <Badge variant="outline" className="text-xs mb-2 gap-1">
            <Folder className="h-3 w-3" />
            {product.category}
          </Badge>
        )}

        {/* Price */}
        <div className="mb-3">
          <PriceDisplay product={product} />
        </div>
        
        {/* Quick info */}
        {(product.quantity || product.product_code) && (
          <div className="text-xs text-muted-foreground space-y-0.5 mb-3 border-t pt-2">
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
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <Link href={`/products/${product.id}`}>
              <Eye className="h-3.5 w-3.5 mr-1" />
              View
            </Link>
          </Button>
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <Link href={`/products/${product.id}/edit?leaflet_id=${product.leaflet_id}${pageFilter !== "all" ? `&page_number=${pageFilter}` : ""}`}>
              <Edit2 className="h-3.5 w-3.5 mr-1" />
              Edit
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ProductCompactCard({ product }: { product: Product }) {
  const { imageSrc, imageError, onImageError } = useProductImage(product);

  return (
    <Link href={`/products/${product.id}`}>
      <Card className={cn(
        "overflow-hidden transition-all hover:shadow-md cursor-pointer h-full",
        !product.validation_passed && "border-orange-300"
      )}>
        <div className="aspect-square bg-muted relative">
          {imageSrc && !imageError ? (
            <NextImage
              src={imageSrc}
              alt={product.product_name || "Product"}
              fill
              className="object-contain p-1"
              unoptimized
              onError={onImageError}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <ImageIcon className="h-6 w-6 text-muted-foreground/30" />
            </div>
          )}
          
          <div className="absolute bottom-1 right-1">
            <Badge variant="secondary" className="text-[10px] px-1 py-0">
              P{product.page_number}
            </Badge>
          </div>
        </div>
        
        <div className="p-2">
          <p className="text-xs font-medium line-clamp-1" title={product.product_name}>
            {product.product_name}
          </p>
          {(product.discounted_price !== null || product.regular_price !== null) && (
            <p className="text-xs font-bold text-green-700 mt-0.5">
              {product.currency || ""} {((product.discounted_price ?? product.regular_price) as number).toFixed(2)}
            </p>
          )}
        </div>
      </Card>
    </Link>
  );
}

function ProductTableRow({ product, pageFilter }: { product: Product; pageFilter: string }) {
  const { imageSrc, imageError, onImageError } = useProductImage(product);

  return (
    <tr className={cn(
      "border-b hover:bg-muted/50 transition-colors",
      !product.validation_passed && "bg-orange-50/50"
    )}>
      <td className="p-3">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-muted rounded-lg overflow-hidden flex-shrink-0">
            {imageSrc && !imageError ? (
              <NextImage
                src={imageSrc}
                alt=""
                width={48}
                height={48}
                className="object-contain w-full h-full p-1"
                unoptimized
                onError={onImageError}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ImageIcon className="h-5 w-5 text-muted-foreground/30" />
              </div>
            )}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-sm truncate max-w-[250px]" title={product.product_name}>
              {product.product_name}
            </p>
            {product.product_code && (
              <p className="text-xs text-muted-foreground font-mono">{product.product_code}</p>
            )}
          </div>
        </div>
      </td>
      <td className="p-3">
        <span className="text-sm text-muted-foreground">{product.brand || "—"}</span>
      </td>
      <td className="p-3">
        {product.category ? (
          <Badge variant="outline" className="text-xs gap-1">
            <Folder className="h-3 w-3" />
            {product.category}
          </Badge>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
      </td>
      <td className="p-3">
        <PriceDisplay product={product} />
      </td>
      <td className="p-3">
        <Badge variant="outline">{product.page_number}</Badge>
      </td>
      <td className="p-3">
        <StatusBadge status={product.review_status} />
      </td>
      <td className="p-3">
        <ConfidenceMeter confidence={product.confidence} />
      </td>
      <td className="p-3">
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
            <Link href={`/products/${product.id}`}>
              <Eye className="h-4 w-4" />
            </Link>
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
            <Link href={`/products/${product.id}/edit?leaflet_id=${product.leaflet_id}${pageFilter !== "all" ? `&page_number=${pageFilter}` : ""}`}>
              <Edit2 className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </td>
    </tr>
  );
}