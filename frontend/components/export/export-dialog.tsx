"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Download,
  FileSpreadsheet,
  FileJson,
  FileText,
  ImageIcon,
  Link2,
  ImageOff,
  Loader2,
  CheckCircle,
  AlertCircle,
  Info,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { brandColors as colors } from "@/lib/brand-colors";
import { exportProductsPreview, exportProducts } from "@/lib/actions/products";
import { getAccessToken } from "@/lib/actions/auth";
import { useExportPoll } from "@/hooks/use-export-poll";
import type {
  ExportFormat,
  ExportImageStorage,
  ExportMode,
  ProductExportRequest,
  ProductExportFilters,
  ReviewQueueExportFilters,
  ExportPreviewResponse,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: ExportMode;
  /** Current page filters for mode="filtered" */
  filters?: ProductExportFilters;
  /** Explicit product IDs for mode="selected" */
  selectedIds?: string[];
  /** Filters for mode="review_queue" */
  reviewQueueFilters?: ReviewQueueExportFilters;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FormatOption({
  value,
  label,
  description,
  icon: Icon,
  isSelected,
}: {
  value: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  isSelected: boolean;
}) {
  return (
    <Label
      htmlFor={`format-${value}`}
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
        isSelected
          ? "border-primary bg-primary/5"
          : "border-border hover:bg-muted/50"
      )}
    >
      <RadioGroupItem value={value} id={`format-${value}`} className="mt-0.5" />
      <div className="flex-1 space-y-0.5">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{label}</span>
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </Label>
  );
}

function ImageOption({
  value,
  label,
  description,
  icon: Icon,
  isSelected,
}: {
  value: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  isSelected: boolean;
}) {
  return (
    <Label
      htmlFor={`image-${value}`}
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
        isSelected
          ? "border-primary bg-primary/5"
          : "border-border hover:bg-muted/50"
      )}
    >
      <RadioGroupItem value={value} id={`image-${value}`} className="mt-0.5" />
      <div className="flex-1 space-y-0.5">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{label}</span>
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </Label>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function modeLabel(mode: ExportMode): string {
  switch (mode) {
    case "all":
      return "all products";
    case "filtered":
      return "filtered products";
    case "selected":
      return "selected products";
    case "review_queue":
      return "review queue";
  }
}

function buildRequest(
  mode: ExportMode,
  format: ExportFormat,
  imageStorage: ExportImageStorage,
  filters?: ProductExportFilters,
  selectedIds?: string[],
  reviewQueueFilters?: ReviewQueueExportFilters
): ProductExportRequest {
  const base: ProductExportRequest = { format, image_storage: imageStorage, mode };

  switch (mode) {
    case "all":
      return base;
    case "filtered":
      return { ...base, filters: filters ?? { sort_by: "created_at", sort_order: "desc" } };
    case "selected":
      return { ...base, product_ids: selectedIds };
    case "review_queue":
      return { ...base, review_queue_filters: reviewQueueFilters };
  }
}

function formatExtension(format: ExportFormat): string {
  switch (format) {
    case "csv":
      return ".csv";
    case "excel":
      return ".xlsx";
    case "json":
      return ".json";
  }
}

// ---------------------------------------------------------------------------
// Dialog states
// ---------------------------------------------------------------------------
type DialogState =
  | "configure"
  | "loading"
  | "exporting"
  | "polling"
  | "success"
  | "error";

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ExportDialog({
  open,
  onOpenChange,
  mode,
  filters,
  selectedIds,
  reviewQueueFilters,
}: ExportDialogProps) {
  // Form state
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [imageStorage, setImageStorage] = useState<ExportImageStorage>("url");

  // Preview state
  const [preview, setPreview] = useState<ExportPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Export state
  const [dialogState, setDialogState] = useState<DialogState>("configure");
  const [exportError, setExportError] = useState<string | null>(null);

  // Async export polling
  const [asyncExportId, setAsyncExportId] = useState<string | null>(null);
  const pollResult = useExportPoll(asyncExportId);

  const isLargeExport = (preview?.product_count ?? 0) >= 1000;

  // ---------------------------------------------------------------------------
  // Load preview on open
  // ---------------------------------------------------------------------------
  const loadPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError(null);

    const request = buildRequest(mode, format, imageStorage, filters, selectedIds, reviewQueueFilters);
    const result = await exportProductsPreview(request);

    if (result.success && result.data) {
      setPreview(result.data);
    } else {
      setPreviewError(result.error || "Failed to load preview");
    }
    setPreviewLoading(false);
  }, [mode, format, imageStorage, filters, selectedIds, reviewQueueFilters]);

  useEffect(() => {
    if (open) {
      // Reset state
      setDialogState("configure");
      setExportError(null);
      setAsyncExportId(null);
      setPreview(null);
      loadPreview();
    }
  }, [open, loadPreview]);

  // ---------------------------------------------------------------------------
  // Watch poll result transitions
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!asyncExportId) return;

    if (pollResult.status === "completed") {
      setDialogState("success");
      // Auto-trigger download if URL is available
      if (pollResult.downloadUrl) {
        triggerDownload(pollResult.downloadUrl);
      }
    } else if (pollResult.status === "failed") {
      setDialogState("error");
      setExportError(pollResult.error || "Export failed");
    }
  }, [asyncExportId, pollResult.status, pollResult.downloadUrl, pollResult.error]);

  // ---------------------------------------------------------------------------
  // Trigger file download
  // ---------------------------------------------------------------------------
  const triggerDownload = (url: string) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  // ---------------------------------------------------------------------------
  // Handle export
  // ---------------------------------------------------------------------------
  const handleExport = async () => {
    if (!preview || preview.product_count === 0) {
      toast.error("No products to export");
      return;
    }

    setDialogState("exporting");
    setExportError(null);

    const request = buildRequest(mode, format, imageStorage, filters, selectedIds, reviewQueueFilters);

    const result = await exportProducts(request);

    if (!result.success) {
      setDialogState("error");
      setExportError(result.error || "Export failed");
      return;
    }

    const data = result.data;

    if (data?.async && data.exportId) {
      // Async export -- start polling
      setAsyncExportId(data.exportId);
      setDialogState("polling");
    } else {
      // Synchronous export -- download file via direct API call client-side
      setDialogState("loading");
      try {
        const token = await getAccessToken();
        const apiBase =
          typeof window !== "undefined"
            ? (process.env.NEXT_PUBLIC_API_URL || "")
            : "";

        const downloadResponse = await fetch(`${apiBase}/api/v1/products/export`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(request),
        });

        if (!downloadResponse.ok) {
          throw new Error(`Export failed: ${downloadResponse.statusText}`);
        }

        const blob = await downloadResponse.blob();
        const contentDisposition = downloadResponse.headers.get("Content-Disposition");
        let filename = `products_export${formatExtension(format)}`;

        if (contentDisposition) {
          const match = contentDisposition.match(/filename="?([^"]+)"?/);
          if (match) {
            filename = match[1];
          }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        setDialogState("success");
        toast.success("Export downloaded successfully");
      } catch (err) {
        console.error("Download error:", err);
        setDialogState("error");
        setExportError(
          err instanceof Error ? err.message : "Failed to download export"
        );
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const showConfigureView = dialogState === "configure";
  const showLoadingView = dialogState === "loading" || dialogState === "exporting";
  const showPollingView = dialogState === "polling";
  const showSuccessView = dialogState === "success";
  const showErrorView = dialogState === "error";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Export Products
          </DialogTitle>
          <DialogDescription>
            Export {modeLabel(mode)} to a downloadable file.
          </DialogDescription>
        </DialogHeader>

        {/* ----------------------------------------------------------------- */}
        {/* Preview Summary */}
        {/* ----------------------------------------------------------------- */}
        <div
          className="rounded-lg border p-4"
          style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray }}
        >
          {previewLoading ? (
            <div className="flex items-center gap-3">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Calculating export size...
              </span>
            </div>
          ) : previewError ? (
            <div className="flex items-center gap-3">
              <AlertCircle className="h-4 w-4" style={{ color: colors.error }} />
              <span className="text-sm" style={{ color: colors.error }}>
                {previewError}
              </span>
            </div>
          ) : preview ? (
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium" style={{ color: colors.primaryText }}>
                  {preview.product_count.toLocaleString()} product
                  {preview.product_count !== 1 ? "s" : ""} from{" "}
                  {preview.leaflet_count.toLocaleString()} leaflet
                  {preview.leaflet_count !== 1 ? "s" : ""}
                </p>
                <p className="text-xs text-muted-foreground">
                  Estimated size: {preview.estimated_file_size}
                </p>
              </div>
              {mode === "selected" && selectedIds && (
                <Badge variant="secondary">
                  {selectedIds.length} selected
                </Badge>
              )}
            </div>
          ) : null}
        </div>

        {/* Large export warning */}
        {isLargeExport && !showPollingView && !showSuccessView && (
          <div
            className="flex items-start gap-3 rounded-lg border p-3"
            style={{ backgroundColor: colors.infoBg, borderColor: colors.infoBorder }}
          >
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" style={{ color: colors.info }} />
            <p className="text-xs" style={{ color: colors.infoText }}>
              Large export -- this will be processed in the background. You can
              close this dialog and come back later.
            </p>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Configure view */}
        {/* ----------------------------------------------------------------- */}
        {showConfigureView && (
          <>
            <Separator />

            {/* Format selection */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">File Format</Label>
              <RadioGroup
                value={format}
                onValueChange={(v) => setFormat(v as ExportFormat)}
                className="gap-2"
              >
                <FormatOption
                  value="csv"
                  label="CSV"
                  description="Comma-separated values, compatible with Excel and Google Sheets"
                  icon={FileSpreadsheet}
                  isSelected={format === "csv"}
                />
                <FormatOption
                  value="excel"
                  label="Excel"
                  description="Multi-sheet workbook with formatting and embedded images"
                  icon={FileText}
                  isSelected={format === "excel"}
                />
                <FormatOption
                  value="json"
                  label="JSON"
                  description="Structured data for API integrations and development"
                  icon={FileJson}
                  isSelected={format === "json"}
                />
              </RadioGroup>
            </div>

            <Separator />

            {/* Image storage selection */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Product Images</Label>
              <RadioGroup
                value={imageStorage}
                onValueChange={(v) => setImageStorage(v as ExportImageStorage)}
                className="gap-2"
              >
                <ImageOption
                  value="url"
                  label="Include Image URLs"
                  description="Links to product images (URLs expire after 24 hours)"
                  icon={Link2}
                  isSelected={imageStorage === "url"}
                />
                <ImageOption
                  value="base64"
                  label="Include Base64 Images"
                  description="Embedded image data (larger file size)"
                  icon={ImageIcon}
                  isSelected={imageStorage === "base64"}
                />
                <ImageOption
                  value="none"
                  label="No Images"
                  description="Data only, smallest file size"
                  icon={ImageOff}
                  isSelected={imageStorage === "none"}
                />
              </RadioGroup>
            </div>
          </>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Loading / exporting view */}
        {/* ----------------------------------------------------------------- */}
        {showLoadingView && (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="text-center space-y-1">
              <p className="text-sm font-medium" style={{ color: colors.primaryText }}>
                Preparing your export...
              </p>
              <p className="text-xs text-muted-foreground">
                This may take a moment for large datasets.
              </p>
            </div>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Polling view (async export) */}
        {/* ----------------------------------------------------------------- */}
        {showPollingView && (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div className="text-center space-y-1">
              <p className="text-sm font-medium" style={{ color: colors.primaryText }}>
                Export is being prepared...
              </p>
              <p className="text-xs text-muted-foreground">
                {pollResult.data?.product_count
                  ? `Processing ${pollResult.data.product_count.toLocaleString()} products.`
                  : "Processing your export."}{" "}
                You will be notified when it is ready.
              </p>
              {pollResult.status && (
                <Badge variant="outline" className="mt-2">
                  {pollResult.status === "pending"
                    ? "Queued"
                    : pollResult.status === "processing"
                    ? "Processing"
                    : pollResult.status}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Success view */}
        {/* ----------------------------------------------------------------- */}
        {showSuccessView && (
          <div className="flex flex-col items-center gap-4 py-8">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: colors.successBg }}
            >
              <CheckCircle className="h-6 w-6" style={{ color: colors.success }} />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-medium" style={{ color: colors.primaryText }}>
                {asyncExportId ? "Export is ready!" : "Download started!"}
              </p>
              <p className="text-xs text-muted-foreground">
                {preview
                  ? `${preview.product_count.toLocaleString()} products exported as ${format.toUpperCase()}`
                  : "Your export has been completed."}
              </p>
              {pollResult.data?.file_size && (
                <p className="text-xs text-muted-foreground">
                  File size: {pollResult.data.file_size}
                </p>
              )}
            </div>
            {pollResult.downloadUrl && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => triggerDownload(pollResult.downloadUrl!)}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Download Again
              </Button>
            )}
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Error view */}
        {/* ----------------------------------------------------------------- */}
        {showErrorView && (
          <div className="flex flex-col items-center gap-4 py-8">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: colors.errorBg }}
            >
              <AlertCircle className="h-6 w-6" style={{ color: colors.error }} />
            </div>
            <div className="text-center space-y-1">
              <p className="text-sm font-medium" style={{ color: colors.primaryText }}>
                Export failed
              </p>
              <p className="text-xs" style={{ color: colors.error }}>
                {exportError || "An unexpected error occurred"}
              </p>
            </div>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Footer */}
        {/* ----------------------------------------------------------------- */}
        <DialogFooter>
          {showConfigureView && (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleExport}
                disabled={
                  previewLoading ||
                  !!previewError ||
                  !preview ||
                  preview.product_count === 0
                }
              >
                <Download className="h-4 w-4 mr-2" />
                Export{" "}
                {preview
                  ? `${preview.product_count.toLocaleString()} Product${preview.product_count !== 1 ? "s" : ""}`
                  : ""}
              </Button>
            </>
          )}

          {showLoadingView && (
            <Button variant="outline" disabled>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Exporting...
            </Button>
          )}

          {showPollingView && (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          )}

          {showSuccessView && (
            <Button onClick={() => onOpenChange(false)}>Done</Button>
          )}

          {showErrorView && (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Close
              </Button>
              <Button
                onClick={() => {
                  setDialogState("configure");
                  setAsyncExportId(null);
                }}
              >
                Try Again
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
