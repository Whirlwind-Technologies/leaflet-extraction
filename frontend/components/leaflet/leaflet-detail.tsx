"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTransition, useEffect, useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  DollarSign,
  Loader2,
  RefreshCw,
  Settings,
  Trash2,
  XCircle,
  AlertTriangle,
  Sparkles,
  ClipboardList,
  Wifi,
  WifiOff,
  RotateCcw,
} from "lucide-react";
import { reprocessLeaflet, deleteLeaflet, getLeafletStatus, getLeaflet } from "@/lib/actions/leaflets";
import { triggerExtraction, clearExtractionData } from "@/lib/actions/products";
import { getPlatformQuota, type PlatformQuota } from "@/lib/actions/settings";
import { dispatchPlatformQuotaChanged } from "@/components/dashboard/vlm-status-banner";
import { getAccessToken } from "@/lib/actions/auth";
import { useProgressWebSocket, type ProgressEvent } from "@/hooks/use-progress-websocket";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ExportMenu } from "@/components/leaflet/export-menu";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { formatBytes, formatDate, formatDateTime, cn } from "@/lib/utils";
import type { Leaflet, LeafletStatus, LeafletProcessingStatus } from "@/lib/types";
import { typography, radius, iconStyles, transitions } from "@/lib/design-system";

interface LeafletDetailProps {
  leaflet: Leaflet;
  productCount?: number;
}

const statusConfig: Record<
  LeafletStatus,
  { icon: typeof Clock; color: string; bg: string; label: string }
> = {
  pending: { icon: Clock, color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", label: "Pending" },
  uploading: { icon: Loader2, color: "text-[#5B8DBE]", bg: "bg-[#5B8DBE]/10", label: "Uploading" },
  processing: { icon: Loader2, color: "text-[#5B8DBE]", bg: "bg-[#5B8DBE]/10", label: "Processing" },
  extracting: { icon: Loader2, color: "text-[#5B8DBE]", bg: "bg-[#5B8DBE]/10", label: "Extracting" },
  validating: { icon: AlertTriangle, color: "text-[#F59E0B]", bg: "bg-[#F59E0B]/10", label: "Ready for Extraction" },
  reviewing: { icon: Clock, color: "text-[#5B8DBE]", bg: "bg-[#5B8DBE]/10", label: "Needs Review" },
  completed: { icon: CheckCircle, color: "text-[#10B981]", bg: "bg-[#10B981]/10", label: "Completed" },
  failed: { icon: XCircle, color: "text-[#EF4444]", bg: "bg-[#EF4444]/10", label: "Failed" },
  cancelled: { icon: XCircle, color: "text-[#6B7280]", bg: "bg-[#6B7280]/10", label: "Cancelled" },
};

// Map processing step codes to user-friendly display names
const processingStepLabels: Record<string, string> = {
  queued: "Queued for processing",
  pdf_conversion: "Converting PDF to images",
  start_extraction: "Starting extraction",
  extracting: "Extracting products",
  extracting_products: "Extracting products from pages",
  running_ocr: "Running OCR on pages",
  awaiting_extraction: "Ready for product extraction",
  awaiting_vlm_configuration: "Awaiting AI provider configuration",
  saving_products: "Saving extracted products",
  validating: "Validating extracted data",
  reconciling: "Reconciling products across pages",
  extracting_images: "Extracting product images",
  credits_exhausted: "API credits exhausted",
  completed: "Processing completed",
  failed: "Processing failed",
};

// Max polling duration: 10 minutes (extended since WebSocket is primary)
const MAX_POLL_DURATION_MS = 10 * 60 * 1000;
// Poll interval: 5 seconds (fallback to polling if WebSocket fails)
const POLL_INTERVAL_MS = 5000;

/**
 * Get user-friendly display message for processing step
 */
function getProcessingStepLabel(step: string | undefined | null, message?: string): string {
  // Prioritize step code mapping first
  if (step && processingStepLabels[step]) {
    return processingStepLabels[step];
  }

  // If there's a custom message and no step match, use the message
  if (message && message.trim()) {
    // Check if message starts with a known step code
    const stepMatch = Object.keys(processingStepLabels).find(key =>
      message.toLowerCase().startsWith(key.toLowerCase())
    );
    if (stepMatch) {
      // Use the friendly label for the matched step
      return processingStepLabels[stepMatch];
    }
    // Otherwise return the message as-is (it's already user-friendly from WebSocket)
    return message;
  }

  // Default fallback
  return step || "Processing...";
}

export function LeafletDetail({ leaflet: initialLeaflet, productCount = 0 }: LeafletDetailProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [status, setStatus] = useState<LeafletProcessingStatus | null>(null);
  const [leaflet, setLeaflet] = useState(initialLeaflet);
  const [isPollingTimeout, setIsPollingTimeout] = useState(false);
  const [wsMessage, setWsMessage] = useState<string>("");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showReExtractDialog, setShowReExtractDialog] = useState(false);
  const [platformLimitError, setPlatformLimitError] = useState<{
    limit: number;
    used: number;
    actionUrl: string;
    actionText: string;
  } | null>(null);
  const [platformQuota, setPlatformQuota] = useState<PlatformQuota | null>(null);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const pollStartTimeRef = useRef<number | null>(null);

  const isProcessing =
    leaflet.status === "processing" ||
    leaflet.status === "extracting" ||
    leaflet.status === "validating" ||
    // Keep WebSocket active briefly for completed status to receive final events
    (leaflet.status === "completed" && !leaflet.processing_completed_at);

  // Fetch auth token and platform quota on mount
  useEffect(() => {
    getAccessToken().then(t => setAuthToken(t));
    getPlatformQuota().then(q => setPlatformQuota(q));
  }, []);

  // Derived: is extraction blocked by platform limit?
  const isQuotaExhausted = platformQuota !== null
    && !platformQuota.is_unlimited
    && platformQuota.remaining !== null
    && platformQuota.remaining <= 0;

  // Sync local state when props change (after router.refresh())
  // Using the React-recommended "adjust state during render" pattern instead of useEffect
  const [prevInitialLeaflet, setPrevInitialLeaflet] = useState(initialLeaflet);
  if (
    initialLeaflet.status !== prevInitialLeaflet.status ||
    initialLeaflet.processing_completed_at !== prevInitialLeaflet.processing_completed_at ||
    initialLeaflet.progress !== prevInitialLeaflet.progress
  ) {
    setPrevInitialLeaflet(initialLeaflet);
    setLeaflet(initialLeaflet);
  }

  // WebSocket for real-time progress
  const handleProgress = useCallback((event: ProgressEvent) => {
    setWsMessage(event.message);
    if (event.progress >= 0) {
      setStatus(prev => prev ? { ...prev, progress: event.progress, message: event.message } : null);
    }
  }, []);

  const handleComplete = useCallback(async (event: ProgressEvent) => {
    setWsMessage(event.message);
    toast.success("Processing complete!");
    dispatchPlatformQuotaChanged();

    // Refresh to get final data (products, images, completion time, etc.)
    router.refresh();

    // Wait a bit for refresh to complete, then fetch the latest leaflet data
    setTimeout(async () => {
      try {
        const updatedLeaflet = await getLeaflet(initialLeaflet.leaflet_id);
        if (updatedLeaflet) {
          setLeaflet(updatedLeaflet);
        }
      } catch (error) {
        console.error("Failed to fetch updated leaflet:", error);
      }
    }, 1000);
  }, [router, initialLeaflet.leaflet_id]);

  const handleError = useCallback((event: ProgressEvent) => {
    setWsMessage(event.message);

    // Check for platform limit reached error
    if (event.data?.error_code === "PLATFORM_LIMIT_REACHED") {
      const limit = (event.data.limit as number) ?? 10;
      const used = (event.data.used as number) ?? limit;
      setPlatformLimitError({
        limit,
        used,
        actionUrl: (event.data.action_url as string) ?? "/settings?tab=ai-providers",
        actionText: (event.data.action_text as string) ?? "Add AI Provider",
      });
      // Update local quota state with the real numbers from the error
      // so that any quota display on this page reflects the truth
      setPlatformQuota({
        limit,
        used,
        remaining: 0,
        has_own_provider: false,
        is_unlimited: false,
      });
      // Notify other components (e.g. Settings page) that quota has changed
      // so they refetch fresh data instead of showing stale numbers
      dispatchPlatformQuotaChanged();
      // Don't show generic toast for this specific error
      return;
    }

    toast.error(event.message);
  }, []);

  const {
    progress: wsProgress,
    isConnected: wsConnected,
    isReconnecting: wsReconnecting,
  } = useProgressWebSocket(
    (isProcessing && authToken) ? leaflet.leaflet_id : null,
    {
      token: authToken,
      onProgress: handleProgress,
      onComplete: handleComplete,
      onError: handleError,
    }
  );

  // Fallback polling for status updates when WebSocket is not connected
  useEffect(() => {
    if (!isProcessing || wsConnected) {
      pollStartTimeRef.current = null;
      return;
    }

    // Initialize poll start time
    if (pollStartTimeRef.current === null) {
      pollStartTimeRef.current = Date.now();
    }

    const pollStatus = async () => {
      // Check if we've been polling too long
      if (pollStartTimeRef.current && Date.now() - pollStartTimeRef.current > MAX_POLL_DURATION_MS) {
        setIsPollingTimeout(true);
        return;
      }

      const newStatus = await getLeafletStatus(leaflet.leaflet_id);
      if (newStatus) {
        setStatus(newStatus);
        // Update leaflet status from polling
        if (newStatus.status !== leaflet.status) {
          setLeaflet((prev) => ({ ...prev, status: newStatus.status, progress: newStatus.progress }));
          if (newStatus.status === "completed") {
            toast.success("Processing completed!");
            router.refresh();
            // Fetch updated leaflet data to get completion time and products
            setTimeout(async () => {
              try {
                const response = await fetch(`/api/v1/leaflets/${leaflet.leaflet_id}`);
                if (response.ok) {
                  const updatedLeaflet = await response.json();
                  setLeaflet(updatedLeaflet);
                }
              } catch (error) {
                console.error("Failed to fetch updated leaflet:", error);
              }
            }, 1000);
          } else if (newStatus.status === "reviewing") {
            toast.success("Extraction completed! Ready for review");
            router.refresh();
            // Fetch updated leaflet data to get completion time and products
            setTimeout(async () => {
              try {
                const response = await fetch(`/api/v1/leaflets/${leaflet.leaflet_id}`);
                if (response.ok) {
                  const updatedLeaflet = await response.json();
                  setLeaflet(updatedLeaflet);
                }
              } catch (error) {
                console.error("Failed to fetch updated leaflet:", error);
              }
            }, 1000);
          } else if (newStatus.status === "failed") {
            toast.error("Processing failed");
            router.refresh();
          }
        }
      }
    };

    pollStatus();
    const interval = setInterval(pollStatus, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [leaflet.leaflet_id, leaflet.status, isProcessing, router, wsConnected]);

  const handleReprocess = () => {
    setIsPollingTimeout(false);
    pollStartTimeRef.current = null;
    startTransition(async () => {
      const result = await reprocessLeaflet(leaflet.leaflet_id);
      if (result.success) {
        toast.success("Reprocessing started");
        setLeaflet((prev) => ({ ...prev, status: "processing", progress: 0 }));
        router.refresh();
      } else {
        toast.error(result.error || "Failed to reprocess");
      }
    });
  };

  const handleDelete = () => {
    startTransition(async () => {
      const result = await deleteLeaflet(leaflet.leaflet_id);
      if (result.success) {
        toast.success("Leaflet deleted");
        router.push("/dashboard");
      } else {
        toast.error(result.error || "Failed to delete");
      }
      setShowDeleteDialog(false);
    });
  };

  const handleReExtract = () => {
    startTransition(async () => {
      const clearResult = await clearExtractionData(leaflet.leaflet_id);
      if (!clearResult.success) {
        toast.error(clearResult.error || "Failed to clear extraction data");
        setShowReExtractDialog(false);
        return;
      }
      toast.success(
        `Cleared ${clearResult.data?.products_deleted || 0} products. Starting re-extraction...`
      );
      const extractResult = await triggerExtraction(leaflet.leaflet_id);
      if (extractResult.success) {
        toast.success("Re-extraction started");
        router.refresh();
      } else {
        toast.error(extractResult.error || "Failed to start extraction");
      }
      setShowReExtractDialog(false);
    });
  };

  const config = statusConfig[leaflet.status];
  const StatusIcon = config.icon;
  // Use WebSocket progress if connected and valid, otherwise fall back to polling/initial
  const displayProgress = wsConnected && wsProgress >= 0 
    ? wsProgress 
    : (status?.progress ?? leaflet.progress);

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-10">
        <div>
          <Link
            href="/dashboard"
            className={`inline-flex items-center gap-2 text-[#6B7280] hover:text-[#5B8DBE] mb-6 ${transitions.DEFAULT}`}
          >
            <ArrowLeft className="h-4 w-4" strokeWidth={iconStyles.strokeWidth} />
            Back to Dashboard
          </Link>
          <h1 className="text-2xl font-light text-[#2D3748] mb-1 tracking-tight">
            {leaflet.filename}
          </h1>
          <div className="flex items-center gap-3">
            <span className={`${typography.body.small.size} text-[#9CA3AF]`}>
              {leaflet.leaflet_id}
            </span>
            <span
              className={`inline-flex items-center gap-2 px-4 py-1.5 ${radius.full} text-sm font-medium ${config.bg} ${config.color}`}
            >
              <StatusIcon
                className={`h-4 w-4 ${isProcessing && !isPollingTimeout ? "animate-spin" : ""}`}
                strokeWidth={iconStyles.strokeWidth}
              />
              {isPollingTimeout ? "Stalled" : config.label}
            </span>
            {/* WebSocket connection indicator */}
            {isProcessing && (
              <span 
                className={`inline-flex items-center gap-1 text-xs ${
                  wsConnected ? "text-green-600" : wsReconnecting ? "text-yellow-600" : "text-gray-400"
                }`}
                title={wsConnected ? "Real-time updates connected" : wsReconnecting ? "Reconnecting..." : "Using polling"}
              >
                {wsConnected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                {wsConnected ? "Live" : wsReconnecting ? "Reconnecting" : "Polling"}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Refresh button */}
          <Button
            variant="outline"
            onClick={() => router.refresh()}
            title="Refresh page"
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Refresh
          </Button>

          {/* View All Products button - for completed leaflets with products */}
          {(leaflet.status === "completed" || leaflet.status === "reviewing") && productCount > 0 && (
            <Link href={`/leaflets/${leaflet.id}?tab=products`}>
              <Button variant="default">
                <CheckCircle className="mr-2 h-4 w-4" />
                View {productCount} Products
              </Button>
            </Link>
          )}
          
          {/* Review pending products */}
          {(leaflet.status === "reviewing" || leaflet.status === "completed") && (
            <Link href={`/review?leaflet_id=${leaflet.id}`}>
              <Button variant="outline">
                <ClipboardList className="mr-2 h-4 w-4" />
                Review Queue
              </Button>
            </Link>
          )}
          
          {/* Extract button for ready leaflets */}
          {(leaflet.status === "extracting" && leaflet.current_step === "awaiting_extraction") && (
            isQuotaExhausted ? (
              <Link href="/settings?tab=ai-providers">
                <Button variant="default" className="bg-red-600 hover:bg-red-700">
                  <Settings className="mr-2 h-4 w-4" />
                  Add AI Provider to Extract
                </Button>
              </Link>
            ) : (
              <Button
                variant="default"
                onClick={async () => {
                  const result = await triggerExtraction(leaflet.leaflet_id);
                  if (result.success) {
                    toast.success("Product extraction started");
                    router.refresh();
                  } else {
                    toast.error(result.error || "Failed to start extraction");
                  }
                }}
                disabled={isPending}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Extract Products
                {platformQuota && !platformQuota.is_unlimited && platformQuota.remaining !== null && (
                  <span className="ml-1.5 text-xs opacity-80">
                    ({platformQuota.remaining} free left)
                  </span>
                )}
              </Button>
            )
          )}
          
          {leaflet.status === "completed" && (
            <ExportMenu 
              leafletId={leaflet.leaflet_id} 
              productCount={productCount}
            />
          )}
          {/* Reprocess button for completed or reviewing leaflets */}
          {(leaflet.status === "completed" || leaflet.status === "reviewing") && (
            isQuotaExhausted ? (
              <Link href="/settings?tab=ai-providers">
                <Button
                  variant="outline"
                  title="Platform AI limit reached. Add your own AI provider to reprocess."
                >
                  <Settings className="mr-2 h-4 w-4" />
                  Add Provider to Reprocess
                </Button>
              </Link>
            ) : (
              <Button
                variant="outline"
                onClick={() => setShowReExtractDialog(true)}
                disabled={isPending}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
                Reprocess
              </Button>
            )
          )}
          <Button
            variant="outline"
            className="text-destructive hover:text-destructive"
            onClick={() => setShowDeleteDialog(true)}
            disabled={isPending}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Timeout warning */}
      {isPollingTimeout && (
        <Card className="mb-6 border-yellow-500 bg-yellow-50 dark:border-yellow-900/50 dark:bg-yellow-950/30">
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-medium text-yellow-800 dark:text-yellow-200">Processing Stalled</h3>
                <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                  The background worker may not be running. Check the Celery worker logs or click Reprocess to try again.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Awaiting VLM configuration message */}
      {(leaflet.status === "validating" && leaflet.current_step === "awaiting_vlm_configuration") && (
        <Card className="mb-6 border-amber-500 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30">
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-medium text-amber-800 dark:text-amber-200">AI Provider Required</h3>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                  {leaflet.status_message || "PDF processed successfully. Configure an AI provider to extract products."}
                </p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Link href="/settings?tab=ai-providers">
                    <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white">
                      Configure AI Provider
                    </Button>
                  </Link>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    className="border-amber-600 text-amber-700 hover:bg-amber-100 dark:border-amber-500 dark:text-amber-300"
                    onClick={async () => {
                      const result = await triggerExtraction(leaflet.leaflet_id);
                      if (result.success) {
                        toast.success("Product extraction started");
                        router.refresh();
                      } else {
                        toast.error(result.error || "Failed to start extraction");
                      }
                    }}
                    disabled={isPending}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    Try Extract Anyway
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Platform AI Limit Reached */}
      {platformLimitError && (
        <Card className="mb-6 border-red-300 bg-red-50">
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-medium text-red-800">
                  Platform AI Limit Reached
                </h3>
                <p className="text-sm text-red-700 mt-1">
                  Your organization has used all {platformLimitError.limit} free extractions
                  with the platform AI provider.
                </p>
                <p className="text-sm text-red-600 mt-2">
                  After adding your provider, you can re-extract this leaflet.
                </p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Link href={platformLimitError.actionUrl}>
                    <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white">
                      <Settings className="mr-2 h-4 w-4" />
                      {platformLimitError.actionText}
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress bar for processing */}
      {isProcessing && !isPollingTimeout && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">
                {getProcessingStepLabel(
                  status?.current_step || leaflet.current_step,
                  wsMessage
                )}
              </span>
              <span className="text-sm text-muted-foreground">
                {Math.round(displayProgress * 100)}%
              </span>
            </div>
            <Progress value={displayProgress * 100} className="h-2" />
          </CardContent>
        </Card>
      )}

      {/* Info grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 mb-10">
        <InfoCard label="Retailer" value={leaflet.retailer || "Unknown"} />
        <InfoCard label="Country" value={leaflet.country || "Unknown"} />
        <InfoCard label="Pages" value={leaflet.page_count?.toString() || "0"} />
        <InfoCard label="Products" value={productCount.toString()} highlight={productCount > 0} />
        <InfoCard label="File Size" value={formatBytes(leaflet.file_size)} />
        {leaflet.valid_from && (
          <InfoCard label="Valid From" value={formatDate(leaflet.valid_from)} />
        )}
        {leaflet.valid_until && (
          <InfoCard label="Valid Until" value={formatDate(leaflet.valid_until)} />
        )}
      </div>

      {/* Success message with extraction summary */}
      {leaflet.status === "completed" && productCount > 0 && (
        <Card className="mb-6 border-green-500 bg-green-50">
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-medium text-green-800">Extraction Complete!</h3>
                <p className="text-sm text-green-700 mt-1">
                  Successfully extracted {productCount} products from {leaflet.page_count} pages.
                  Click the tabs below to view all products, or use the buttons above to review and export.
                </p>
                <div className="flex gap-2 mt-4">
                  <Link href={`/leaflets/${leaflet.id}?tab=products`}>
                    <Button size="sm" variant="default" className="bg-green-600 hover:bg-green-700">
                      View All Products
                    </Button>
                  </Link>
                  <Link href={`/review?leaflet_id=${leaflet.id}`}>
                    <Button size="sm" variant="outline" className="border-green-600 text-green-700 hover:bg-green-100">
                      Open Review Queue
                    </Button>
                  </Link>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error message */}
      {leaflet.status === "failed" && leaflet.status_message && (
        <Card className={`mb-6 ${
          leaflet.current_step === "credits_exhausted"
            ? "border-orange-500 bg-orange-50 dark:border-orange-900/50 dark:bg-orange-950/30"
            : leaflet.current_step === "platform_limit_reached"
            ? (isQuotaExhausted ? "border-red-300 bg-red-50" : "border-amber-300 bg-amber-50")
            : "border-destructive"
        }`}>
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              {leaflet.current_step === "credits_exhausted" ? (
                <DollarSign className="h-5 w-5 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-0.5" />
              ) : leaflet.current_step === "platform_limit_reached" ? (
                <AlertTriangle className={`h-5 w-5 flex-shrink-0 mt-0.5 ${isQuotaExhausted ? "text-red-600" : "text-amber-600"}`} />
              ) : (
                <XCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <h3 className={`font-medium ${
                  leaflet.current_step === "credits_exhausted"
                    ? "text-orange-800 dark:text-orange-200"
                    : leaflet.current_step === "platform_limit_reached"
                    ? (isQuotaExhausted ? "text-red-800" : "text-amber-800")
                    : "text-destructive"
                }`}>
                  {leaflet.current_step === "credits_exhausted"
                    ? "API Credits Exhausted"
                    : leaflet.current_step === "platform_limit_reached"
                    ? (isQuotaExhausted ? "Platform AI Limit Reached" : "Extraction Previously Blocked")
                    : "Processing Failed"}
                </h3>
                <p className={`text-sm mt-1 ${
                  leaflet.current_step === "credits_exhausted"
                    ? "text-orange-700 dark:text-orange-300"
                    : leaflet.current_step === "platform_limit_reached"
                    ? (isQuotaExhausted ? "text-red-700" : "text-amber-700")
                    : "text-muted-foreground"
                }`}>
                  {leaflet.current_step === "platform_limit_reached" && !isQuotaExhausted
                    ? "This extraction was previously blocked, but you now have quota available. Click retry to extract."
                    : leaflet.status_message}
                </p>

                {leaflet.current_step === "platform_limit_reached" && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    {isQuotaExhausted ? (
                      <Link href="/settings?tab=ai-providers">
                        <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white">
                          <Settings className="mr-2 h-4 w-4" />
                          Add AI Provider
                        </Button>
                      </Link>
                    ) : (
                      <Button
                        size="sm"
                        className="bg-amber-600 hover:bg-amber-700 text-white"
                        onClick={handleReprocess}
                        disabled={isPending}
                      >
                        <RefreshCw className={`mr-2 h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
                        Retry Extraction
                        {platformQuota && !platformQuota.is_unlimited && platformQuota.remaining !== null && (
                          <span className="ml-1.5 text-xs opacity-80">
                            ({platformQuota.remaining} free left)
                          </span>
                        )}
                      </Button>
                    )}
                  </div>
                )}

                {leaflet.current_step === "credits_exhausted" && (
                  <div className="flex flex-wrap gap-2 mt-4">
                    <a
                      href="https://console.anthropic.com/settings/billing"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button size="sm" className="bg-orange-600 hover:bg-orange-700 text-white">
                        <DollarSign className="mr-2 h-4 w-4" />
                        Add Anthropic Credits
                      </Button>
                    </a>
                    <Link href="/settings?tab=vlm-providers">
                      <Button size="sm" variant="outline" className="border-orange-600 text-orange-700 hover:bg-orange-100">
                        <Settings className="mr-2 h-4 w-4" />
                        Configure Another Provider
                      </Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleReprocess}
                      disabled={isPending}
                    >
                      <RefreshCw className={`mr-2 h-4 w-4 ${isPending ? "animate-spin" : ""}`} />
                      Retry Extraction
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Timestamps */}
      <Card>
        <CardContent className="p-6">
          <h3 className="font-medium mb-4">Timeline</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{formatDateTime(leaflet.created_at)}</span>
            </div>
            {leaflet.processing_started_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Processing Started</span>
                <span>{formatDateTime(leaflet.processing_started_at)}</span>
              </div>
            )}
            {leaflet.processing_completed_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Completed</span>
                <span>{formatDateTime(leaflet.processing_completed_at)}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="h-12 w-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <AlertDialogTitle className="text-xl">Delete Leaflet</AlertDialogTitle>
            </div>
            <AlertDialogDescription asChild>
              <div className="text-base space-y-3 pt-2">
                <div>
                  Are you sure you want to delete <span className="font-semibold text-gray-900">{leaflet.filename}</span>?
                </div>
                {productCount > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="text-red-800 text-sm font-medium">
                      This will permanently delete {productCount} extracted product{productCount !== 1 ? 's' : ''}.
                    </div>
                  </div>
                )}
                <div className="text-sm text-gray-600">
                  This action cannot be undone.
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel disabled={isPending} className="mt-0">
              Cancel
            </AlertDialogCancel>
            <Button
              onClick={handleDelete}
              disabled={isPending}
              variant="destructive"
              className="bg-red-600 hover:bg-red-700"
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete Permanently'
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reprocess Confirmation Dialog */}
      <AlertDialog open={showReExtractDialog} onOpenChange={setShowReExtractDialog}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="h-12 w-12 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <RefreshCw className="h-6 w-6 text-amber-600" />
              </div>
              <AlertDialogTitle className="text-xl">Reprocess Products</AlertDialogTitle>
            </div>
            <AlertDialogDescription asChild>
              <div className="text-base space-y-3 pt-2">
                <div>
                  This will clear all extracted products and re-run extraction for <span className="font-semibold text-gray-900">{leaflet.filename}</span>.
                </div>
                {productCount > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <div className="text-amber-800 text-sm font-medium">
                      This will permanently delete {productCount} extracted product{productCount !== 1 ? 's' : ''} before reprocessing.
                    </div>
                  </div>
                )}
                <div className="text-sm text-gray-600">
                  The AI will re-analyze all pages and extract products again. This is useful if extraction settings have changed or if you want to improve results.
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel disabled={isPending} className="mt-0">
              Cancel
            </AlertDialogCancel>
            <Button
              onClick={handleReExtract}
              disabled={isPending}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Reprocessing...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Continue Reprocess
                </>
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function InfoCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`bg-[#F9FAFB] ${radius.lg} p-6 ${highlight ? "ring-2 ring-[#5B8DBE]/20" : ""}`}>
      <p className={`${typography.body.small.size} ${typography.body.small.weight} text-[#6B7280] mb-2`}>
        {label}
      </p>
      <p className={cn(`${typography.h4.size} ${typography.h4.weight} text-[#2D3748]`, highlight && "text-[#5B8DBE]")}>
        {value}
      </p>
    </div>
  );
}