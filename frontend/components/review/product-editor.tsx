"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Move,
  Square,
  Check,
  X,
  Save,
  AlertTriangle,
  Calculator,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { reviewProduct, updateProduct, updateProductOptimistic, reExtractProductImage, refreshProductImageUrl } from "@/lib/actions/products";
import type { ReviewData } from "@/lib/actions/products";
import { toast } from "sonner";
import { BoundingBoxCanvas } from "./bounding-box-canvas";
import { DiscountCalculator } from "./discount-calculator";
import { CategorySelect } from "./category-select";
import type { Product, BoundingBox, ProductNavigationContext } from "@/lib/types";

interface ProductEditorProps {
  product: Product;
  pageImageUrl: string | null;
  pageWidth: number;
  pageHeight: number;
  navigation?: ProductNavigationContext;
  onNavigate?: (productId: string) => void;
  onReviewSubmit?: (productId: string, reviewData: ReviewData) => void;
  isLoadingNav?: boolean;
  reviewedInSession?: number;
}

type EditorMode = "pan" | "edit-bbox";

/**
 * Convert internal MinIO URLs to browser-accessible URLs
 */
function getAccessibleUrl(url: string | null | undefined): string | null {
  if (!url) return null;

  // Handle various internal Docker/container hostnames
  return url
    .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/https:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/http:\/\/127\.0\.0\.1:9000/g, "http://localhost:9000")
    .replace(/http:\/\/host\.docker\.internal:9000/g, "http://localhost:9000");
}

export function ProductEditor({
  product,
  pageImageUrl,
  pageWidth,
  pageHeight,
  navigation,
  onNavigate,
  onReviewSubmit,
  isLoadingNav = false,
  reviewedInSession = 0,
}: ProductEditorProps) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  
  // State for editor
  const [mode, setMode] = useState<EditorMode>("pan");
  const [zoom, setZoom] = useState(0.5);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isReExtracting, setIsReExtracting] = useState(false);
  const [showCalculator, setShowCalculator] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectNotes, setRejectNotes] = useState("");

  // Track current product image (can be updated after re-extraction)
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(
    product.image?.url || product.image_url || null
  );
  const [currentImageBase64, setCurrentImageBase64] = useState<string | null>(
    product.image?.data || product.image_base64 || null
  );
  // Timestamp to force image reload after re-extraction (cache busting)
  // Initialize with 0 to avoid hydration mismatch (Date.now() differs between server/client)
  const [imageTimestamp, setImageTimestamp] = useState<number>(0);
  // Track if we've already tried to refresh the URL (to prevent infinite loops)
  const [hasTriedRefresh, setHasTriedRefresh] = useState<boolean>(false);
  const [isRefreshingUrl, setIsRefreshingUrl] = useState<boolean>(false);
  
  // Handle image URL refresh when presigned URL expires
  const handleImageUrlRefresh = async () => {
    if (hasTriedRefresh || isRefreshingUrl || !currentImageUrl) return;

    setIsRefreshingUrl(true);
    setHasTriedRefresh(true);

    console.log("Attempting to refresh expired image URL for product:", product.id);

    try {
      const result = await refreshProductImageUrl(product.id);
      if (result.success && result.data?.image_url) {
        console.log("Image URL refreshed successfully");
        setCurrentImageUrl(result.data.image_url);
        setImageTimestamp(Date.now()); // Force reload
        toast.success("Image URL refreshed");
      } else {
        console.error("Failed to refresh image URL:", result.error);
        toast.error("Failed to refresh image URL");
      }
    } catch (error) {
      console.error("Error refreshing image URL:", error);
    } finally {
      setIsRefreshingUrl(false);
    }
  };

  // Form state
  const [formData, setFormData] = useState({
    brand: product.brand || "",
    product_code: product.product_code || "",
    product_name: product.product_name || "",
    quantity: product.quantity?.toString() || "",
    units: product.units || "",
    regular_price: product.regular_price?.toString() || "",
    discounted_price: product.discounted_price?.toString() || "",
    discount_percentage: product.discount_percentage?.toString() || "",
    currency: product.currency || "",
    promotional_info: product.promotional_info || "",
    category: product.category || product.suggested_category || "",
  });
  
  // Bounding box state
  const [boundingBox, setBoundingBox] = useState<BoundingBox>(product.bounding_box);
  const [bboxChanged, setBboxChanged] = useState(false);
  const originalBboxRef = useRef<BoundingBox>(product.bounding_box);
  const [, setCropPreview] = useState<string | null>(null);

  // Keep a ref to the current bounding box for the focus function
  const boundingBoxRef = useRef(boundingBox);
  useEffect(() => {
    boundingBoxRef.current = boundingBox;
  }, [boundingBox]);

  // Reset state when product changes (replaces key-based remount)
  const prevProductIdRef = useRef(product.id);
  useEffect(() => {
    if (prevProductIdRef.current === product.id) return;
    prevProductIdRef.current = product.id;

    // Reset form data
    setFormData({
      brand: product.brand || "",
      product_code: product.product_code || "",
      product_name: product.product_name || "",
      quantity: product.quantity?.toString() || "",
      units: product.units || "",
      regular_price: product.regular_price?.toString() || "",
      discounted_price: product.discounted_price?.toString() || "",
      discount_percentage: product.discount_percentage?.toString() || "",
      currency: product.currency || "",
      promotional_info: product.promotional_info || "",
      category: product.category || product.suggested_category || "",
    });

    // Reset editing state
    setIsDirty(false);
    setIsSaving(false);
    setIsReExtracting(false);
    setIsRefreshingUrl(false);
    setBboxChanged(false);
    setBoundingBox(product.bounding_box);
    originalBboxRef.current = product.bounding_box;
    setCropPreview(null);
    setShowCalculator(false);
    setShowRejectDialog(false);
    setRejectReason("");
    setRejectNotes("");

    // Reset image state
    setCurrentImageUrl(product.image?.url || product.image_url || null);
    setCurrentImageBase64(product.image?.data || product.image_base64 || null);
    setHasTriedRefresh(false);
    setImageTimestamp(0);

    // Do NOT reset zoom/pan/mode — preserve user's view preference

    // Update bounding box ref for focus function
    boundingBoxRef.current = product.bounding_box;

    // Focus on the new product's bounding box
    // Use a short delay to let the state update settle
    setTimeout(() => {
      handleFocusProduct();
    }, 50);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.id, product]);

  const accessiblePageUrl = getAccessibleUrl(pageImageUrl);
  
  // Handle form field changes
  const handleFieldChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setIsDirty(true);
  };
  
  // Handle bounding box changes
  const handleBoundingBoxChange = (newBbox: BoundingBox) => {
    setBoundingBox(newBbox);
    setBboxChanged(true);
    setIsDirty(true);
  };

  // Zoom controls
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.25, 0.25));

  // Fit entire image to view
  const handleFitToView = useCallback(() => {
    const containerWidth = containerRef.current?.clientWidth || 800;
    const containerHeight = containerRef.current?.clientHeight || 600;

    // Calculate zoom to fit entire image with some padding
    const padding = 40; // pixels of padding around image
    const availableWidth = containerWidth - padding * 2;
    const availableHeight = containerHeight - padding * 2;

    const idealZoom = Math.min(
      availableWidth / pageWidth,
      availableHeight / pageHeight,
      1 // Don't zoom in beyond 100%
    );

    // Center the image
    const scaledWidth = pageWidth * idealZoom;
    const scaledHeight = pageHeight * idealZoom;

    setZoom(idealZoom);
    setPan({
      x: (containerWidth - scaledWidth) / 2,
      y: (containerHeight - scaledHeight) / 2,
    });
  }, [pageWidth, pageHeight]);

  // Focus on product - uses ref to get current bbox without triggering re-renders
  const handleFocusProduct = useCallback(() => {
    const containerWidth = containerRef.current?.clientWidth || 800;
    const containerHeight = containerRef.current?.clientHeight || 600;
    const bbox = boundingBoxRef.current;

    const bboxCenterX = bbox.x + bbox.width / 2;
    const bboxCenterY = bbox.y + bbox.height / 2;

    const idealZoom = Math.min(
      containerWidth / (bbox.width * 1.5),
      containerHeight / (bbox.height * 1.5),
      2
    );

    setZoom(idealZoom);
    setPan({
      x: containerWidth / 2 - bboxCenterX * idealZoom,
      y: containerHeight / 2 - bboxCenterY * idealZoom,
    });
  }, []);

  // Initial fit to view - only run once on mount
  const initialFocusDone = useRef(false);
  useEffect(() => {
    if (!initialFocusDone.current) {
      // Small delay to ensure container is rendered
      const timer = setTimeout(() => {
        handleFitToView();
        initialFocusDone.current = true;
      }, 100);

      return () => clearTimeout(timer);
    }
  }, [handleFitToView]);

  // Keyboard shortcuts for mode switching (P = pan, B = edit-bbox)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) {
        return;
      }
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        setMode("pan");
      } else if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        setMode("edit-bbox");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Calculate discount when prices change
  const calculateDiscount = useCallback(() => {
    const regular = parseFloat(formData.regular_price);
    const discounted = parseFloat(formData.discounted_price);
    
    if (regular > 0 && discounted > 0 && regular > discounted) {
      const percentage = ((regular - discounted) / regular) * 100;
      setFormData(prev => ({
        ...prev,
        discount_percentage: percentage.toString(),
      }));
      setIsDirty(true);
    }
  }, [formData.regular_price, formData.discounted_price]);
  
  // Save changes - returns true if successful, false otherwise
  // skipReviewHistory: when true, don't create a review history entry (used when review will be submitted separately)
  const handleSave = async (showToast: boolean = true, skipReviewHistory: boolean = false): Promise<boolean> => {
    setIsSaving(true);
    const needsReExtract = bboxChanged;

    try {
      const updates: Record<string, unknown> = {};

      // Add changed fields
      if (formData.brand !== (product.brand || "")) updates.brand = formData.brand || null;
      if (formData.product_code !== (product.product_code || "")) updates.product_code = formData.product_code || null;
      if (formData.product_name !== product.product_name) updates.product_name = formData.product_name;
      if (formData.quantity !== (product.quantity?.toString() || "")) updates.quantity = formData.quantity ? parseFloat(formData.quantity) : null;
      if (formData.units !== (product.units || "")) updates.units = formData.units || null;
      if (formData.regular_price !== (product.regular_price?.toString() || "")) updates.regular_price = formData.regular_price ? parseFloat(formData.regular_price) : null;
      if (formData.discounted_price !== (product.discounted_price?.toString() || "")) updates.discounted_price = formData.discounted_price ? parseFloat(formData.discounted_price) : null;
      if (formData.discount_percentage !== (product.discount_percentage?.toString() || "")) updates.discount_percentage = formData.discount_percentage ? parseFloat(formData.discount_percentage) : null;
      if (formData.currency !== (product.currency || "")) updates.currency = formData.currency || null;
      if (formData.promotional_info !== (product.promotional_info || "")) updates.promotional_info = formData.promotional_info || null;
      if (formData.category !== (product.category || product.suggested_category || "")) updates.category = formData.category || null;

      // Add bounding box if changed
      if (bboxChanged) {
        updates.bounding_box = boundingBox;
      }

      // Use optimistic (no revalidation) when in multi-product review session
      const updateFn = onReviewSubmit ? updateProductOptimistic : updateProduct;
      const result = await updateFn(product.id, updates, { skipReviewHistory });

      if (result.success) {
        setIsDirty(false);
        setBboxChanged(false);

        // Re-extract image if bounding box changed - MUST await this
        if (needsReExtract) {
          if (showToast) toast.info("Re-extracting product image with new bounding box...");
          const reExtractResult = await reExtractProductImage(product.id);
          if (reExtractResult.success && reExtractResult.data) {
            // Update local image state with new image data
            setCurrentImageUrl(reExtractResult.data.image_url);
            setCurrentImageBase64(reExtractResult.data.image_base64);
            // Update timestamp to force image reload (cache busting)
            setImageTimestamp(Date.now());
            if (showToast) toast.success("Product saved and image re-extracted");
          } else if (reExtractResult.success) {
            // Success but no data returned, refresh to get new data
            if (showToast) toast.success("Product saved and image re-extracted");
            router.refresh();
          } else {
            if (showToast) toast.warning("Product saved but image re-extraction failed: " + (reExtractResult.error || "Unknown error"));
          }
        } else {
          if (showToast) toast.success("Product saved successfully");
        }
        return true;
      } else {
        toast.error(result.error || "Failed to save product");
        return false;
      }
    } catch {
      toast.error("An error occurred while saving");
      return false;
    } finally {
      setIsSaving(false);
    }
  };
  
  // Re-extract product image
  const handleReExtractImage = async () => {
    setIsReExtracting(true);
    try {
      const result = await reExtractProductImage(product.id);
      if (result.success && result.data) {
        // Update local image state with new image data
        setCurrentImageUrl(result.data.image_url);
        setCurrentImageBase64(result.data.image_base64);
        // Update timestamp to force image reload (cache busting)
        setImageTimestamp(Date.now());
        toast.success("Product image re-extracted");
      } else if (result.success) {
        // Success but no data returned, refresh to get new data
        toast.success("Product image re-extracted");
        router.refresh();
      } else {
        toast.error(result.error || "Failed to re-extract image");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setIsReExtracting(false);
    }
  };
  
  // Shared navigation helper: go to next product or fall back to previous page
  const navigateAfterReview = useCallback(() => {
    if (navigation?.nextProductId && onNavigate) {
      onNavigate(navigation.nextProductId);
    } else {
      router.back();
    }
  }, [navigation, onNavigate, router]);

  // Approve product (saves and approves in one action)
  const handleApprove = async () => {
    setIsSaving(true);
    const hadChanges = isDirty;

    try {
      // Save first if there are changes (don't show individual save toast)
      // Pass skipReviewHistory=true because the review action will create the history entry
      if (hadChanges) {
        const saveSuccess = await handleSave(false, true);
        if (!saveSuccess) {
          // Save failed, error toast already shown by handleSave
          return;
        }
      }

      const reviewData: ReviewData = {
        action: hadChanges ? "corrected" : "approved",
      };

      if (onReviewSubmit) {
        // Optimistic: enqueue review and navigate immediately
        onReviewSubmit(product.id, reviewData);
        toast.success(hadChanges ? "Product saved and approved" : "Product approved");
        navigateAfterReview();
      } else {
        // Synchronous: await review completion
        const result = await reviewProduct(product.id, reviewData);

        if (result.success) {
          toast.success(hadChanges ? "Product saved and approved" : "Product approved");
          navigateAfterReview();
        } else {
          toast.error(result.error || "Failed to submit review");
        }
      }
    } catch {
      toast.error("An error occurred during review submission");
    } finally {
      setIsSaving(false);
    }
  };

  // Reject product
  const handleReject = async (reason?: string) => {
    setIsSaving(true);
    try {
      const reviewData: ReviewData = {
        action: "rejected",
        ...(reason && { notes: reason }),
      };

      if (onReviewSubmit) {
        // Optimistic: enqueue review and navigate immediately
        onReviewSubmit(product.id, reviewData);
        toast.success("Product rejected");
        setShowRejectDialog(false);
        setRejectReason("");
        setRejectNotes("");
        navigateAfterReview();
      } else {
        // Synchronous: await review completion
        const result = await reviewProduct(product.id, reviewData);

        if (result.success) {
          toast.success("Product rejected");
          setShowRejectDialog(false);
          setRejectReason("");
          setRejectNotes("");
          navigateAfterReview();
        } else {
          toast.error(result.error || "Failed to reject product");
        }
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setIsSaving(false);
    }
  };

  // Navigation helpers
  const hasNav = navigation && navigation.totalCount > 1 && !!onNavigate;

  const navigateTo = (productId: string) => {
    if (isDirty) {
      const confirmed = window.confirm("You have unsaved changes. Discard and navigate?");
      if (!confirmed) return;
    }
    onNavigate?.(productId);
  };

  const handleApproveAndNext = async () => {
    setIsSaving(true);
    const hadChanges = isDirty;

    try {
      if (hadChanges) {
        const saveSuccess = await handleSave(false, true);
        if (!saveSuccess) return;
      }

      const reviewData: ReviewData = {
        action: hadChanges ? "corrected" : "approved",
      };

      if (onReviewSubmit) {
        // Optimistic: enqueue review and navigate immediately
        onReviewSubmit(product.id, reviewData);
        toast.success(hadChanges ? "Product saved and approved" : "Product approved");
        navigateAfterReview();
      } else {
        // Synchronous: await review completion
        const result = await reviewProduct(product.id, reviewData);

        if (result.success) {
          toast.success(hadChanges ? "Product saved and approved" : "Product approved");
          navigateAfterReview();
        } else {
          toast.error(result.error || "Failed to submit review");
        }
      }
    } catch {
      toast.error("An error occurred during review submission");
    } finally {
      setIsSaving(false);
    }
  };

  // Keyboard shortcuts for navigation (Alt+Left / Alt+Right)
  useEffect(() => {
    if (!hasNav) return;

    const handleNavKeyDown = (e: KeyboardEvent) => {
      if (isLoadingNav) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) {
        return;
      }
      if (e.altKey && e.key === "ArrowLeft" && navigation?.prevProductId) {
        e.preventDefault();
        navigateTo(navigation.prevProductId);
      } else if (e.altKey && e.key === "ArrowRight" && navigation?.nextProductId) {
        e.preventDefault();
        navigateTo(navigation.nextProductId);
      }
    };
    window.addEventListener("keydown", handleNavKeyDown);
    return () => window.removeEventListener("keydown", handleNavKeyDown);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasNav, navigation?.prevProductId, navigation?.nextProductId, isDirty, isLoadingNav]);

  // Keyboard shortcuts for review actions (A = approve, R = reject, S = save)
  const reviewHandlersRef = useRef({
    approve: handleApprove,
    approveAndNext: handleApproveAndNext,
    save: handleSave,
    isSaving,
    isDirty,
    hasNav,
    nextProductId: navigation?.nextProductId,
    showRejectDialog,
  });
  useEffect(() => {
    reviewHandlersRef.current = {
      approve: handleApprove,
      approveAndNext: handleApproveAndNext,
      save: handleSave,
      isSaving,
      isDirty,
      hasNav,
      nextProductId: navigation?.nextProductId,
      showRejectDialog,
    };
  });
  useEffect(() => {
    const handleReviewKeyDown = (e: KeyboardEvent) => {
      // Skip when focus is in form inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      // Skip when a dialog is open
      if (reviewHandlersRef.current.showRejectDialog) return;
      // Skip when saving
      if (reviewHandlersRef.current.isSaving) return;

      const handlers = reviewHandlersRef.current;

      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        if (handlers.hasNav && handlers.nextProductId) {
          handlers.approveAndNext();
        } else {
          handlers.approve();
        }
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        setShowRejectDialog(true);
      } else if (e.key === "s" || e.key === "S") {
        if (handlers.isDirty) {
          e.preventDefault();
          handlers.save(true);
        }
      }
    };
    window.addEventListener("keydown", handleReviewKeyDown);
    return () => window.removeEventListener("keydown", handleReviewKeyDown);
  }, []);

  return (
    <div className="flex h-full">
      {/* Image Viewer with Bounding Box Editor */}
      <div className="flex-1 flex flex-col bg-gray-900 relative overflow-hidden">
        {/* Toolbar */}
        <div className="absolute top-4 left-4 z-20 flex gap-2 bg-background/90 rounded-lg p-2 shadow-lg">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.back()}
            title="Go back"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          
          <Separator orientation="vertical" className="h-8" />
          
          <Button
            variant={mode === "pan" ? "secondary" : "ghost"}
            size="icon"
            onClick={() => setMode("pan")}
            title="Pan mode (P)"
          >
            <Move className="h-4 w-4" />
          </Button>
          <Button
            variant={mode === "edit-bbox" ? "secondary" : "ghost"}
            size="icon"
            onClick={() => setMode("edit-bbox")}
            title="Edit bounding box (B)"
          >
            <Square className="h-4 w-4" />
          </Button>
          
          <Separator orientation="vertical" className="h-8" />
          
          <Button
            variant="ghost"
            size="icon"
            onClick={handleZoomOut}
            title="Zoom out (-)"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="flex items-center justify-center w-12 text-sm font-mono">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleZoomIn}
            title="Zoom in (+)"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          
          <Separator orientation="vertical" className="h-8" />
          
          <Button
            variant="ghost"
            size="icon"
            onClick={handleFitToView}
            title="Fit to view (R)"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleFocusProduct}
            title="Focus on product (F)"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>
        
        {/* Canvas */}
        <div
          ref={containerRef}
          className="flex-1 overflow-hidden"
        >
          {accessiblePageUrl ? (
            <BoundingBoxCanvas
              imageUrl={accessiblePageUrl}
              imageWidth={pageWidth}
              imageHeight={pageHeight}
              boundingBox={boundingBox}
              onBoundingBoxChange={handleBoundingBoxChange}
              zoom={zoom}
              pan={pan}
              onPanChange={setPan}
              mode={mode}
              onZoomChange={setZoom}
              onCropPreview={setCropPreview}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              No page image available
            </div>
          )}
        </div>
        
        {/* Mode indicator */}
        {mode === "edit-bbox" && (
          <div className="absolute bottom-4 left-4 bg-primary text-primary-foreground px-3 py-1 rounded-full text-sm">
            Draw: click + drag • Resize: drag corners • Move: drag inside • Nudge: arrow keys • Pan: hold Space + drag
          </div>
        )}
      </div>
      
      {/* Right Panel - Form */}
      <div className="w-[420px] border-l border-border bg-background flex flex-col overflow-hidden">
        {/* Navigation bar */}
        {hasNav && (
          <div className="px-4 py-2 border-b border-border bg-muted/50 flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigation.prevProductId && navigateTo(navigation.prevProductId)}
              disabled={!navigation.prevProductId || isSaving || isLoadingNav}
              title="Previous product (Alt+Left)"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Prev
            </Button>
            <span className="text-sm text-muted-foreground font-medium">
              {navigation.currentIndex + 1} of {navigation.totalCount}
              {reviewedInSession > 0 && (
                <span className="ml-2 text-emerald-600 dark:text-emerald-400">
                  ({reviewedInSession} reviewed)
                </span>
              )}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigation.nextProductId && navigateTo(navigation.nextProductId)}
              disabled={!navigation.nextProductId || isLoadingNav}
              title="Next product (Alt+Right)"
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        )}

        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-foreground">Edit Product</h2>
            <div className="flex items-center gap-2">
              {product.validation_passed ? (
                <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800">
                  Valid
                </Badge>
              ) : (
                <Badge variant="destructive" className="bg-destructive/10 text-destructive border-destructive/20">
                  <AlertTriangle className="h-3 w-3 mr-1" />
                  Issues
                </Badge>
              )}
              <Badge variant="outline">
                Page {product.page_number}
              </Badge>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            Confidence: {product.confidence ? `${Math.round(product.confidence * 100)}%` : "N/A"}
          </p>
        </div>
        
        {/* Scrollable form area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Product Image Preview */}
          {(currentImageBase64 || currentImageUrl) && (
            <Card>
              <CardHeader className="py-2">
                <CardTitle className="text-sm flex items-center justify-between">
                  Extracted Image
                  <div className="flex gap-1">
                    {/* Show refresh URL button only for URL-based images */}
                    {currentImageUrl && !currentImageBase64 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleImageUrlRefresh}
                        disabled={isRefreshingUrl}
                        className="text-muted-foreground hover:text-primary"
                        title="Refresh expired image URL"
                      >
                        <RefreshCw className={cn("h-3 w-3", isRefreshingUrl && "animate-spin")} />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleReExtractImage}
                      disabled={isReExtracting}
                      className="text-primary"
                    >
                      <RefreshCw className={cn("h-3 w-3 mr-1", isReExtracting && "animate-spin")} />
                      Re-extract
                    </Button>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <div className="relative aspect-video bg-muted rounded overflow-hidden">
                  {currentImageBase64 ? (
                    <Image
                      key={`base64-${imageTimestamp}`}
                      src={currentImageBase64.startsWith("data:") ? currentImageBase64 : `data:image/png;base64,${currentImageBase64}`}
                      alt={product.product_name || "Product image"}
                      fill
                      className="object-contain p-2"
                      unoptimized
                      onError={(e) => {
                        console.error("Failed to load base64 image");
                        e.currentTarget.style.display = "none";
                      }}
                    />
                  ) : currentImageUrl ? (
                    <>
                      {isRefreshingUrl ? (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                          <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                          Refreshing...
                        </div>
                      ) : (
                        <Image
                          key={`url-${imageTimestamp}`}
                          src={getAccessibleUrl(currentImageUrl) || ""}
                          alt={product.product_name || "Product image"}
                          fill
                          className="object-contain p-2"
                          unoptimized
                          onError={(e) => {
                            console.error("Failed to load image URL:", currentImageUrl);
                            // Try to refresh the presigned URL if it might have expired
                            if (!hasTriedRefresh) {
                              handleImageUrlRefresh();
                            } else {
                              // Already tried refresh, hide the image
                              e.currentTarget.style.display = "none";
                            }
                          }}
                        />
                      )}
                    </>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Product Fields */}
          <Card>
            <CardHeader className="py-2">
              <CardTitle className="text-sm">Product Details</CardTitle>
            </CardHeader>
            <CardContent className="py-2 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <Label className="text-xs text-muted-foreground">Product Name *</Label>
                  <Input
                    value={formData.product_name}
                    onChange={(e) => handleFieldChange("product_name", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Brand</Label>
                  <Input
                    value={formData.brand}
                    onChange={(e) => handleFieldChange("brand", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Product Code</Label>
                  <Input
                    value={formData.product_code}
                    onChange={(e) => handleFieldChange("product_code", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div className="col-span-2">
                  <Label className="text-xs text-muted-foreground flex items-center gap-2">
                    Category
                    {product.category_confidence !== null && (
                      <Badge
                        variant={product.category_confidence >= 0.80 ? "outline" : "destructive"}
                        className="text-xs"
                      >
                        {Math.round((product.category_confidence || 0) * 100)}% conf
                      </Badge>
                    )}
                  </Label>

                  <CategorySelect
                    value={formData.category}
                    onValueChange={(value) => handleFieldChange("category", value)}
                    placeholder="Select category"
                  />

                  {/* Show alternatives if AI was uncertain */}
                  {product.category_alternatives && product.category_alternatives.length > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      AI alternatives: {product.category_alternatives.map(a => a.category).join(", ")}
                    </div>
                  )}
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Quantity</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.quantity}
                    onChange={(e) => handleFieldChange("quantity", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Units</Label>
                  <Input
                    value={formData.units}
                    onChange={(e) => handleFieldChange("units", e.target.value)}
                    placeholder="g, kg, ml, L, pcs..."
                    className="h-8"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Pricing */}
          <Card>
            <CardHeader className="py-2">
              <CardTitle className="text-sm flex items-center justify-between">
                Pricing
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowCalculator(!showCalculator)}
                  className="text-primary"
                >
                  <Calculator className="h-3 w-3 mr-1" />
                  Calculator
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="py-2 space-y-3">
              {showCalculator && (
                <DiscountCalculator
                  regularPrice={formData.regular_price}
                  discountedPrice={formData.discounted_price}
                  discountPercentage={formData.discount_percentage}
                  onApply={(values: { regularPrice: string; discountedPrice: string; discountPercentage: string }) => {
                    setFormData(prev => ({
                      ...prev,
                      regular_price: values.regularPrice,
                      discounted_price: values.discountedPrice,
                      discount_percentage: values.discountPercentage,
                    }));
                    setIsDirty(true);
                    setShowCalculator(false);
                  }}
                />
              )}

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-xs text-muted-foreground">Regular Price</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.regular_price}
                    onChange={(e) => handleFieldChange("regular_price", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Discounted Price</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.discounted_price}
                    onChange={(e) => handleFieldChange("discounted_price", e.target.value)}
                    className="h-8"
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Discount %</Label>
                  <div className="flex gap-1">
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.discount_percentage}
                      onChange={(e) => handleFieldChange("discount_percentage", e.target.value)}
                      className="h-8"
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0 text-primary"
                      onClick={calculateDiscount}
                      title="Calculate from prices"
                    >
                      <Calculator className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Currency</Label>
                <Input
                  value={formData.currency}
                  onChange={(e) => handleFieldChange("currency", e.target.value)}
                  placeholder="EUR, USD, GBP..."
                  className="h-8 w-24"
                />
              </div>
            </CardContent>
          </Card>
          
          {/* Promotional Info */}
          <Card>
            <CardHeader className="py-2">
              <CardTitle className="text-sm">Promotional Info</CardTitle>
            </CardHeader>
            <CardContent className="py-2">
              <textarea
                value={formData.promotional_info}
                onChange={(e) => handleFieldChange("promotional_info", e.target.value)}
                className="w-full h-20 px-3 py-2 text-sm rounded-md resize-none border border-input bg-background"
                placeholder="Any badges, deals, or conditions..."
              />
            </CardContent>
          </Card>
          
          {/* Validation Errors */}
          {product.validation_errors && product.validation_errors.length > 0 && (
            <Card className="border-destructive/50">
              <CardHeader className="py-2">
                <CardTitle className="text-sm flex items-center gap-2 text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                  Validation Issues
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <ul className="text-sm space-y-1">
                  {product.validation_errors.map((error, idx) => (
                    <li key={idx} className="text-destructive">
                      <span className="font-medium">{error.field}:</span> {error.message}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          
          {/* Confidence Details */}
          {product.field_confidence && (
            <Card>
              <CardHeader className="py-2">
                <CardTitle className="text-sm">Field Confidence</CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(product.field_confidence).map(([field, conf]) => (
                    conf !== null && (
                      <div key={field} className="flex justify-between">
                        <span className="capitalize text-muted-foreground">
                          {field.replace(/_/g, " ")}
                        </span>
                        <span
                          className={cn(
                            "font-mono",
                            conf >= 0.9 ? "text-emerald-600 dark:text-emerald-400" :
                            conf >= 0.75 ? "text-amber-600 dark:text-amber-400" :
                            "text-destructive"
                          )}
                        >
                          {Math.round(conf * 100)}%
                        </span>
                      </div>
                    )
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        
        {/* Action Buttons */}
        <div className="p-4 bg-background border-t border-border">
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 min-w-0 border-destructive/50 text-destructive hover:bg-destructive/10"
              onClick={() => setShowRejectDialog(true)}
              disabled={isSaving}
              title="Reject product (R)"
            >
              <X className="h-4 w-4 mr-1.5 shrink-0" />
              <span className="truncate">
                {hasNav && navigation.nextProductId ? "Reject & Next" : "Reject"}
              </span>
            </Button>

            {isDirty && (
              <Button
                variant="secondary"
                className="min-w-0"
                onClick={() => handleSave(true)}
                disabled={isSaving}
                title="Save changes (S)"
              >
                <Save className="h-4 w-4 mr-1.5 shrink-0" />
                Save
              </Button>
            )}

            <Button
              className="flex-1 min-w-0"
              onClick={hasNav && navigation.nextProductId ? handleApproveAndNext : handleApprove}
              disabled={isSaving}
              title="Approve product (A)"
            >
              <Check className="h-4 w-4 mr-1.5 shrink-0" />
              <span className="truncate">
                {isDirty
                  ? (hasNav && navigation.nextProductId ? "Approve & Next" : "Save & Approve")
                  : (hasNav && navigation.nextProductId ? "Approve & Next" : "Approve")}
              </span>
            </Button>
          </div>
        </div>

        {/* Reject Reason Dialog */}
        <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Reject Product</DialogTitle>
              <DialogDescription>
                Select a reason for rejecting this product. This helps improve future extraction quality.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="reject-reason">Reason</Label>
                <Select
                  value={rejectReason}
                  onValueChange={(value) => {
                    setRejectReason(value);
                    if (value !== "Other") {
                      setRejectNotes("");
                    }
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a reason..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Incorrect data">Incorrect data</SelectItem>
                    <SelectItem value="Duplicate product">Duplicate product</SelectItem>
                    <SelectItem value="Not a product">Not a product</SelectItem>
                    <SelectItem value="Unreadable">Unreadable</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {rejectReason && (
                <div className="space-y-2">
                  <Label htmlFor="reject-notes">
                    Additional notes {rejectReason === "Other" ? "(required)" : "(optional)"}
                  </Label>
                  <Textarea
                    id="reject-notes"
                    value={rejectNotes}
                    onChange={(e) => setRejectNotes(e.target.value)}
                    placeholder="Add any details about why this product is being rejected..."
                    className="min-h-20 resize-none"
                  />
                </div>
              )}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setShowRejectDialog(false);
                  setRejectReason("");
                  setRejectNotes("");
                }}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  const fullReason = rejectNotes
                    ? `${rejectReason}: ${rejectNotes}`
                    : rejectReason;
                  handleReject(fullReason || undefined);
                }}
                disabled={
                  isSaving ||
                  !rejectReason ||
                  (rejectReason === "Other" && !rejectNotes.trim())
                }
              >
                {isSaving ? "Rejecting..." : "Confirm Reject"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}