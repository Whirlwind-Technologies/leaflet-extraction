"use client";

import { useState, useCallback } from "react";
import Image from "next/image";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  XCircle,
  Edit2,
  AlertTriangle,
  ImageIcon,
  ChevronDown,
  ChevronUp,
  Loader2,
  Folder,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { refreshProductImageUrl } from "@/lib/actions/products";
import type { Product } from "@/lib/types";

interface ProductCardProps {
  product: Product;
  pageImageUrl?: string | null;
  onApprove?: (productId: string) => void;
  onReject?: (productId: string) => void;
  onEdit?: (productId: string) => void;
  isSelected?: boolean;
  onSelect?: (productId: string, selected: boolean) => void;
  isProcessing?: boolean;
  viewMode?: "grid" | "list";
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) return null;

  const percentage = Math.round(confidence * 100);
  let className = "text-xs font-semibold ";

  if (percentage >= 90) {
    className += "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800";
  } else if (percentage >= 75) {
    className += "bg-primary/10 text-primary border-primary/30";
  } else {
    className += "bg-destructive/10 text-destructive border-destructive/30";
  }

  return (
    <Badge variant="outline" className={className}>
      {percentage}% confidence
    </Badge>
  );
}

function ReviewStatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { label: string; className: string }> = {
    pending: { label: "Pending Review", className: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800" },
    auto_approved: { label: "Auto Approved", className: "bg-primary/10 text-primary border-primary/30" },
    approved: { label: "Approved", className: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800" },
    rejected: { label: "Rejected", className: "bg-destructive/10 text-destructive border-destructive/30" },
    needs_correction: { label: "Needs Correction", className: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800" },
    corrected: { label: "Corrected", className: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800" },
  };

  const config = statusConfig[status] || { label: status, className: "bg-muted text-muted-foreground border-border" };

  return (
    <Badge variant="outline" className={`text-xs font-semibold ${config.className}`}>
      {config.label}
    </Badge>
  );
}

function PriorityBadge({ priority }: { priority: number }) {
  if (priority < 50) return null;

  const isHigh = priority >= 70;
  const isUrgent = priority >= 90;

  let className = "text-xs font-semibold ";

  if (isUrgent) {
    className += "bg-destructive/10 text-destructive border-destructive/30";
  } else {
    className += "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800";
  }

  return (
    <Badge variant="outline" className={className}>
      {isUrgent ? "Urgent" : isHigh ? "High Priority" : "Medium"}
    </Badge>
  );
}

function CategoryBadge({ category, confidence }: { category: string | null; confidence: number | null }) {
  if (!category) return null;

  const isLowConfidence = confidence !== null && confidence < 0.8;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium max-w-full min-w-0 overflow-hidden",
        isLowConfidence
          ? "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800"
          : "bg-muted text-muted-foreground border-border"
      )}
      title={confidence !== null ? `${category} (${Math.round(confidence * 100)}%)` : category}
    >
      <Folder className="h-3 w-3 shrink-0" />
      <span className="truncate min-w-0">{category}</span>
      {confidence !== null && (
        <span className="opacity-70 shrink-0 whitespace-nowrap">({Math.round(confidence * 100)}%)</span>
      )}
    </span>
  );
}

/**
 * Convert internal MinIO/S3 URLs to browser-accessible URLs.
 */
function fixMinioUrl(url: string): string {
  return url
    .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
}

/**
 * Get product image source - handles both URLs and base64 data.
 */
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
  if (product.thumbnail_url) {
    return fixMinioUrl(product.thumbnail_url);
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

export function ProductCard({
  product,
  onApprove,
  onReject,
  onEdit,
  isSelected,
  onSelect,
  isProcessing,
  viewMode = "grid",
}: ProductCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const { imageSrc: thumbnailSrc, imageError, onImageError } = useProductImage(product);
  const needsReview = product.review_status === "pending" || product.review_status === "needs_correction";
  
  // List view
  if (viewMode === "list") {
    return (
      <Card
        className={cn(
          "bg-card rounded-lg shadow-md transition-all hover:shadow-xl hover:-translate-y-1",
          isProcessing && "opacity-60",
          !product.validation_passed ? "border-destructive" : needsReview ? "border-gray-400 dark:border-gray-500" : "",
          isSelected && "ring-2 ring-primary"
        )}
      >
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            {/* Checkbox */}
            {onSelect && (
              <input
                type="checkbox"
                checked={isSelected}
                onChange={(e) => onSelect(product.id, e.target.checked)}
                className="h-4 w-4 rounded border-input"
                disabled={isProcessing}
              />
            )}

            {/* Thumbnail */}
            <div className="w-12 h-12 bg-muted rounded overflow-hidden flex-shrink-0">
              {thumbnailSrc && !imageError ? (
                <Image
                  src={thumbnailSrc}
                  alt={product.product_name}
                  width={48}
                  height={48}
                  className="object-cover w-full h-full"
                  unoptimized
                  onError={onImageError}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <ImageIcon className="h-4 w-4 text-muted-foreground" />
                </div>
              )}
            </div>

            {/* Product info */}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-sm truncate text-foreground">{product.product_name}</h3>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {product.brand && <span>{product.brand}</span>}
                {product.product_code && <span>• {product.product_code}</span>}
                <span>• Page {product.page_number}</span>
              </div>
            </div>

            {/* Price */}
            <div className="text-right">
              {product.discounted_price !== null && (
                <span className="font-bold text-primary">
                  {product.currency || "€"} {product.discounted_price.toFixed(2)}
                </span>
              )}
              {product.discounted_price === null && product.regular_price !== null && (
                <span className="font-bold text-primary">
                  {product.currency || "€"} {product.regular_price.toFixed(2)}
                </span>
              )}
              {product.discount_percentage !== null && product.discount_percentage > 0 && (
                <Badge variant="destructive" className="ml-2 text-xs">
                  -{parseFloat(product.discount_percentage.toFixed(2))}%
                </Badge>
              )}
            </div>

            {/* Badges */}
            <div className="flex items-center gap-2 min-w-0 flex-shrink overflow-hidden">
              <ReviewStatusBadge status={product.review_status} />
              <PriorityBadge priority={product.review_priority} />
              <CategoryBadge category={product.category} confidence={product.category_confidence} />
              <ConfidenceBadge confidence={product.confidence} />
            </div>

            {/* Actions */}
            {needsReview && (
              <div className="flex items-center gap-2">
                {onEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(product.id)}
                    disabled={isProcessing}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                )}
                {onReject && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onReject(product.id)}
                    disabled={isProcessing}
                    className="border-destructive/50 text-destructive hover:bg-destructive/10"
                  >
                    {isProcessing ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <XCircle className="h-3 w-3" />
                    )}
                  </Button>
                )}
                {onApprove && (
                  <Button
                    size="sm"
                    onClick={() => onApprove(product.id)}
                    disabled={isProcessing}
                  >
                    {isProcessing ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <CheckCircle className="h-3 w-3" />
                    )}
                  </Button>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }
  
  // Grid view (default)
  return (
    <Card
      className={cn(
        "bg-card rounded-xl shadow-md transition-all hover:shadow-xl hover:-translate-y-1 overflow-hidden",
        isProcessing && "opacity-60",
        !product.validation_passed ? "border-destructive" : needsReview ? "border-amber-500 dark:border-amber-600" : "",
        isSelected && "ring-2 ring-primary"
      )}
    >
      <div className="p-4 sm:p-6 pb-3">
        <div className="flex items-start gap-2 sm:gap-3 min-w-0">
          {/* Checkbox */}
          {onSelect && (
            <input
              type="checkbox"
              checked={isSelected}
              onChange={(e) => onSelect(product.id, e.target.checked)}
              className="h-4 w-4 mt-0.5 rounded border-input flex-shrink-0"
              disabled={isProcessing}
            />
          )}

          {/* Thumbnail - appears first on mobile for better layout */}
          <div className="w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 bg-muted rounded overflow-hidden flex-shrink-0 order-last sm:order-none">
            {thumbnailSrc && !imageError ? (
              <Image
                src={thumbnailSrc}
                alt={product.product_name}
                width={64}
                height={64}
                className="object-cover w-full h-full"
                unoptimized
                onError={onImageError}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ImageIcon className="h-5 w-5 sm:h-6 sm:w-6 text-muted-foreground" />
              </div>
            )}
          </div>

          {/* Product info - takes available space */}
          <div className="flex-1 min-w-0 overflow-hidden">
            <h3 className="font-semibold text-sm line-clamp-2 mb-2 text-foreground" title={product.product_name}>
              {product.product_name}
            </h3>
            <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
              {product.brand && (
                <span className="text-xs text-muted-foreground truncate max-w-[80px] sm:max-w-none">{product.brand}</span>
              )}
              <ReviewStatusBadge status={product.review_status} />
              <PriorityBadge priority={product.review_priority} />
              <CategoryBadge category={product.category} confidence={product.category_confidence} />
              <ConfidenceBadge confidence={product.confidence} />
            </div>
          </div>
        </div>
      </div>

      <CardContent className="p-4 sm:p-6 pt-3">
        {/* Pricing */}
        <div className="flex items-baseline gap-2 mb-3">
          {product.discounted_price !== null && (
            <span className="text-xl font-bold text-primary">
              {product.currency || "€"} {product.discounted_price.toFixed(2)}
            </span>
          )}
          {product.discounted_price === null && product.regular_price !== null && (
            <span className="text-xl font-bold text-primary">
              {product.currency || "€"} {product.regular_price.toFixed(2)}
            </span>
          )}
          {product.regular_price !== null && product.discounted_price !== null && product.regular_price !== product.discounted_price && (
            <span className="text-sm line-through text-muted-foreground">
              {product.currency || "€"} {product.regular_price.toFixed(2)}
            </span>
          )}
          {product.discount_percentage !== null && product.discount_percentage > 0 && (
            <Badge variant="destructive" className="text-xs">
              -{parseFloat(product.discount_percentage.toFixed(2))}%
            </Badge>
          )}
        </div>

        {/* Quick info */}
        <div className="text-xs space-y-1 mb-4 text-muted-foreground">
          {product.quantity && product.units && (
            <p>{product.quantity} {product.units}</p>
          )}
          {product.product_code && (
            <p>Code: {product.product_code}</p>
          )}
          <p>Page {product.page_number}</p>
        </div>

        {/* Validation warnings */}
        {!product.validation_passed && product.validation_errors?.length > 0 && (
          <div className="mb-3 p-3 rounded-lg text-xs bg-destructive/10 border border-destructive/30">
            <div className="flex items-center gap-1 font-semibold mb-1 text-destructive">
              <AlertTriangle className="h-3 w-3" />
              Validation Issues
            </div>
            <ul className="space-y-0.5 text-destructive">
              {product.validation_errors.slice(0, 2).map((error, idx) => (
                <li key={idx}>{error.message}</li>
              ))}
              {product.validation_errors.length > 2 && (
                <li>+{product.validation_errors.length - 2} more...</li>
              )}
            </ul>
          </div>
        )}

        {/* Uncertainty flags */}
        {product.uncertainty_flags?.length > 0 && (
          <div className="mb-3 p-3 rounded-lg text-xs bg-amber-50 border border-amber-200 dark:bg-amber-950 dark:border-amber-800">
            <div className="flex items-center gap-1 font-semibold mb-1 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-3 w-3" />
              Uncertainties
            </div>
            <ul className="space-y-0.5 text-amber-700 dark:text-amber-300">
              {product.uncertainty_flags.map((flag: string, idx: number) => (
                <li key={idx}>{flag.replace(/_/g, " ")}</li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Expand/collapse details */}
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs"
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? (
            <>
              <ChevronUp className="h-3 w-3 mr-1" /> Hide Details
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3 mr-1" /> Show Details
            </>
          )}
        </Button>
        
        {showDetails && (
          <div className="mt-3 pt-3 border-t text-xs space-y-2">
            {product.promotional_info && (
              <p><strong>Promo:</strong> {product.promotional_info}</p>
            )}
            {product.product_id && (
              <p><strong>Barcode:</strong> {product.product_id}</p>
            )}
            {product.size && (
              <p><strong>Size:</strong> {product.size}</p>
            )}
            {product.suggested_category && (
              <p>
                <strong>AI Category:</strong> {product.suggested_category}
                {product.category_confidence !== null && (
                  <span className="text-muted-foreground ml-1">
                    ({Math.round(product.category_confidence * 100)}% confidence)
                  </span>
                )}
              </p>
            )}
            {product.category && product.category !== product.suggested_category && (
              <p><strong>Confirmed Category:</strong> {product.category}</p>
            )}
            {product.category_alternatives && product.category_alternatives.length > 0 && (
              <div>
                <strong>Alternative Categories:</strong>
                <div className="flex flex-wrap gap-1 mt-1">
                  {product.category_alternatives.slice(0, 3).map((alt, idx) => (
                    <span key={idx} className="text-muted-foreground">
                      {alt.category} ({Math.round(alt.confidence * 100)}%)
                    </span>
                  ))}
                </div>
              </div>
            )}
            <p><strong>Bounding Box:</strong> ({product.bounding_box?.x}, {product.bounding_box?.y}) - {product.bounding_box?.width}×{product.bounding_box?.height}</p>
            {product.field_confidence && (
              <div>
                <strong>Field Confidence:</strong>
                <div className="grid grid-cols-2 gap-1 mt-1">
                  {Object.entries(product.field_confidence).map(([field, score]) => (
                    score !== null && (
                      <span key={field} className="text-muted-foreground capitalize">
                        {field.replace(/_/g, " ")}: {Math.round((score as number) * 100)}%
                      </span>
                    )
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        
        {/* Action buttons */}
        {needsReview && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
            {onApprove && (
              <Button
                size="sm"
                variant="default"
                className="flex-1"
                onClick={() => onApprove(product.id)}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <CheckCircle className="h-4 w-4 mr-1" />
                )}
                Approve
              </Button>
            )}
            {onEdit && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onEdit(product.id)}
                disabled={isProcessing}
              >
                <Edit2 className="h-4 w-4" />
              </Button>
            )}
            {onReject && (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => onReject(product.id)}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}