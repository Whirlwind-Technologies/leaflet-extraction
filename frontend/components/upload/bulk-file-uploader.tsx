"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import {
  CheckCircle2,
  File,
  Loader2,
  Trash2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { bulkUploadLeaflets } from "@/lib/actions/leaflets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { brandColors as colors } from "@/lib/brand-colors";
import { RetailerSelect } from "@/components/retailers/retailer-select";
import { QuickAddRetailerModal } from "@/components/retailers/quick-add-retailer-modal";
import type { Retailer } from "@/lib/types";

interface FileWithStatus {
  id: string;
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  leafletId?: string;
  error?: string;
  progress?: number;
}

interface UploadMetadata {
  retailer: string;
  country: string;
  language: string;
  currency: string;
  validFrom: string;
  validUntil: string;
}

const MAX_FILES = 20;
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export function BulkFileUploader() {
  const router = useRouter();
  const [files, setFiles] = useState<FileWithStatus[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);
  const [showAddRetailerModal, setShowAddRetailerModal] = useState(false);
  const [metadata, setMetadata] = useState<UploadMetadata>({
    retailer: "",
    country: "",
    language: "",
    currency: "",
    validFrom: "",
    validUntil: "",
  });

  const handleRetailerSelect = (retailer: Retailer | null) => {
    if (retailer) {
      setMetadata((prev) => ({
        ...prev,
        retailer: retailer.name,
        country: retailer.country || prev.country,
        currency: retailer.currency || prev.currency,
        language: retailer.language || prev.language,
      }));
    } else {
      setMetadata((prev) => ({ ...prev, retailer: "" }));
    }
  };

  const handleRetailerAdded = (retailer: Retailer) => {
    setMetadata((prev) => ({
      ...prev,
      retailer: retailer.name,
      country: retailer.country || "",
      currency: retailer.currency || "",
      language: retailer.language || "",
    }));
    setShowAddRetailerModal(false);
  };

  const generateId = () => Math.random().toString(36).substring(2, 9);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const currentCount = files.length;
      const availableSlots = MAX_FILES - currentCount;

      if (availableSlots <= 0) {
        toast.error(`Maximum ${MAX_FILES} files allowed`);
        return;
      }

      const filesToAdd = acceptedFiles.slice(0, availableSlots);
      const skipped = acceptedFiles.length - filesToAdd.length;

      if (skipped > 0) {
        toast.warning(`${skipped} file(s) skipped. Maximum ${MAX_FILES} files allowed.`);
      }

      const newFiles: FileWithStatus[] = [];
      const errors: string[] = [];

      filesToAdd.forEach((file) => {
        if (file.type !== "application/pdf") {
          errors.push(`${file.name}: Not a PDF file`);
          return;
        }
        if (file.size > MAX_FILE_SIZE) {
          errors.push(`${file.name}: File too large (max 100MB)`);
          return;
        }
        // Check for duplicates
        const isDuplicate = files.some((f) => f.file.name === file.name);
        if (isDuplicate) {
          errors.push(`${file.name}: Already added`);
          return;
        }

        newFiles.push({
          id: generateId(),
          file,
          status: "pending",
        });
      });

      if (errors.length > 0) {
        toast.error(
          <div className="space-y-1">
            <div className="font-medium">Some files were rejected:</div>
            {errors.slice(0, 3).map((err, i) => (
              <div key={i} className="text-sm">{err}</div>
            ))}
            {errors.length > 3 && (
              <div className="text-sm">...and {errors.length - 3} more</div>
            )}
          </div>
        );
      }

      if (newFiles.length > 0) {
        setFiles((prev) => [...prev, ...newFiles]);
        toast.success(`Added ${newFiles.length} file(s)`);
      }
    },
    [files]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxSize: MAX_FILE_SIZE,
    disabled: isUploading,
  });

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const clearAll = () => {
    if (!isUploading) {
      setFiles([]);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error("Please add at least one file");
      return;
    }

    // Validate required fields
    if (!metadata.retailer || !metadata.country || !metadata.currency || !metadata.language || !metadata.validFrom || !metadata.validUntil) {
      toast.error("Please fill in all required fields");
      return;
    }

    const pendingFiles = files.filter((f) => f.status === "pending");
    if (pendingFiles.length === 0) {
      toast.info("No pending files to upload");
      return;
    }

    setIsUploading(true);
    setOverallProgress(0);

    // Mark all pending files as uploading
    setFiles((prev) =>
      prev.map((f) =>
        f.status === "pending" ? { ...f, status: "uploading" as const } : f
      )
    );

    try {
      const formData = new FormData();

      // Add all pending files
      pendingFiles.forEach((f) => {
        formData.append("files", f.file);
      });

      // Add metadata
      if (metadata.retailer) formData.append("retailer", metadata.retailer);
      if (metadata.country) formData.append("country", metadata.country);
      if (metadata.language) formData.append("language", metadata.language);
      if (metadata.currency) formData.append("currency", metadata.currency);
      if (metadata.validFrom) formData.append("valid_from", new Date(metadata.validFrom).toISOString());
      if (metadata.validUntil) formData.append("valid_until", new Date(metadata.validUntil).toISOString());
      formData.append("auto_process", "true");

      // Use server action for upload
      const actionResult = await bulkUploadLeaflets(formData);

      if (!actionResult.success || !actionResult.data) {
        throw new Error(actionResult.error || "Upload failed");
      }

      const result = actionResult.data;

      // Update file statuses based on results
      setFiles((prev) =>
        prev.map((f) => {
          const uploadResult = result.results.find(
            (r) => r.filename === f.file.name
          );
          if (uploadResult) {
            return {
              ...f,
              status: uploadResult.success ? "success" : "error",
              leafletId: uploadResult.leaflet_id || undefined,
              error: uploadResult.error || undefined,
            };
          }
          return f;
        })
      );

      setOverallProgress(100);

      if (result.successful === result.total) {
        toast.success(`All ${result.successful} leaflets uploaded successfully!`);
      } else if (result.successful > 0) {
        toast.warning(
          `${result.successful} uploaded, ${result.failed} failed`
        );
      } else {
        toast.error("All uploads failed");
      }
    } catch (error) {
      console.error("Bulk upload failed:", error);

      // Mark all uploading files as error
      setFiles((prev) =>
        prev.map((f) =>
          f.status === "uploading"
            ? { ...f, status: "error" as const, error: "Upload failed" }
            : f
        )
      );

      toast.error("Bulk upload failed. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const successCount = files.filter((f) => f.status === "success").length;
  const errorCount = files.filter((f) => f.status === "error").length;
  const pendingCount = files.filter((f) => f.status === "pending").length;

  const getFileStatusStyles = (status: string) => {
    switch (status) {
      case "success":
        return { bg: colors.successBg, border: colors.successBorder, iconBg: colors.successBg };
      case "error":
        return { bg: colors.errorBg, border: colors.errorBorder, iconBg: colors.errorBg };
      case "uploading":
        return { bg: colors.lightBlueTint, border: colors.primaryBrandBlue, iconBg: colors.lightBlueTint };
      default:
        return { bg: colors.offWhiteBg, border: colors.borderGray, iconBg: colors.offWhiteBg };
    }
  };

  return (
    <div className="space-y-6">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isUploading ? "opacity-50 cursor-not-allowed" : ""
        }`}
        style={{
          borderColor: isDragActive
            ? colors.primaryBrandBlue
            : files.length > 0
            ? colors.primaryBrandBlue
            : colors.borderGray,
          backgroundColor: isDragActive
            ? colors.lightBlueTint
            : files.length > 0
            ? colors.lightBlueTint
            : "transparent",
        }}
      >
        <input {...getInputProps()} />
        <Upload className="h-12 w-12 mx-auto mb-4" style={{ color: colors.secondaryText }} />
        <p className="text-lg font-medium" style={{ color: colors.primaryText }}>
          {isDragActive
            ? "Drop your PDFs here"
            : "Drag & drop multiple PDF leaflets"}
        </p>
        <p className="text-sm mt-1" style={{ color: colors.secondaryText }}>
          or click to browse (max {MAX_FILES} files, 100MB each)
        </p>
        {files.length > 0 && (
          <p className="text-sm mt-2" style={{ color: colors.primaryBrandBlue }}>
            {files.length} file(s) added ({MAX_FILES - files.length} slots remaining)
          </p>
        )}
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium" style={{ color: colors.primaryText }}>Files to Upload</h3>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                {successCount > 0 && (
                  <span
                    className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{ backgroundColor: colors.successBg, color: colors.successText }}
                  >
                    {successCount} uploaded
                  </span>
                )}
                {errorCount > 0 && (
                  <span
                    className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{ backgroundColor: colors.errorBg, color: colors.errorText }}
                  >
                    {errorCount} failed
                  </span>
                )}
                {pendingCount > 0 && (
                  <span
                    className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{ backgroundColor: colors.offWhiteBg, color: colors.secondaryText }}
                  >
                    {pendingCount} pending
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAll}
                disabled={isUploading}
              >
                <Trash2 className="h-4 w-4 mr-1" style={{ color: colors.secondaryText }} />
                Clear All
              </Button>
            </div>
          </div>

          <div className="max-h-64 overflow-y-auto space-y-2 pr-2">
            {files.map((fileWithStatus) => {
              const statusStyles = getFileStatusStyles(fileWithStatus.status);
              return (
                <div
                  key={fileWithStatus.id}
                  className="flex items-center justify-between p-3 rounded-lg border"
                  style={{
                    backgroundColor: statusStyles.bg,
                    borderColor: statusStyles.border,
                  }}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div
                      className="h-10 w-10 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: statusStyles.iconBg }}
                    >
                      {fileWithStatus.status === "success" ? (
                        <CheckCircle2 className="h-5 w-5" style={{ color: colors.success }} />
                      ) : fileWithStatus.status === "error" ? (
                        <XCircle className="h-5 w-5" style={{ color: colors.error }} />
                      ) : fileWithStatus.status === "uploading" ? (
                        <Loader2 className="h-5 w-5 animate-spin" style={{ color: colors.primaryBrandBlue }} />
                      ) : (
                        <File className="h-5 w-5" style={{ color: colors.secondaryText }} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate" style={{ color: colors.primaryText }}>
                        {fileWithStatus.file.name}
                      </p>
                      <div className="flex items-center gap-2 text-sm" style={{ color: colors.secondaryText }}>
                        <span>{(fileWithStatus.file.size / 1024 / 1024).toFixed(2)} MB</span>
                        {fileWithStatus.status === "success" && fileWithStatus.leafletId && (
                          <span style={{ color: colors.success }}>
                            • ID: {fileWithStatus.leafletId}
                          </span>
                        )}
                        {fileWithStatus.status === "error" && fileWithStatus.error && (
                          <span style={{ color: colors.error }}>
                            • {fileWithStatus.error}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {fileWithStatus.status === "success" && fileWithStatus.leafletId && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push(`/leaflets/${fileWithStatus.leafletId}`)}
                      >
                        View
                      </Button>
                    )}
                    {fileWithStatus.status === "pending" && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeFile(fileWithStatus.id)}
                        disabled={isUploading}
                      >
                        <X className="h-4 w-4" style={{ color: colors.secondaryText }} />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Metadata Fields */}
      <div className="grid grid-cols-3 md:grid-cols-3 gap-3">
        <div className="space-y-3 col-span-3 md:col-span-3">
          <Label htmlFor="retailer" style={{ color: colors.primaryText }}>
            Retailer <span className="text-red-500">*</span>
          </Label>
          <RetailerSelect
            value={metadata.retailer}
            onSelect={handleRetailerSelect}
            onAddNew={() => setShowAddRetailerModal(true)}
            disabled={isUploading}
          />
          <p className="text-xs text-slate-500">
            Select a retailer to auto-fill country, currency, and language for all files
          </p>
        </div>
        <div className="space-y-3">
          <Label htmlFor="country" style={{ color: colors.primaryText }}>
            Country <span className="text-red-500">*</span>
          </Label>
          <Input
            id="country"
            value={metadata.country}
            onChange={(e) => setMetadata(prev => ({ ...prev, country: e.target.value.toUpperCase() }))}
            placeholder="e.g., US"
            maxLength={2}
            disabled={isUploading}
            style={{ borderColor: colors.borderGray }}
            required
          />
        </div>
        <div className="space-y-3">
          <Label htmlFor="language" style={{ color: colors.primaryText }}>
            Language <span className="text-red-500">*</span>
          </Label>
          <Input
            id="language"
            value={metadata.language}
            onChange={(e) => setMetadata(prev => ({ ...prev, language: e.target.value.toLowerCase() }))}
            placeholder="e.g., en"
            maxLength={5}
            disabled={isUploading}
            style={{ borderColor: colors.borderGray }}
            required
          />
        </div>
        <div className="space-y-3">
          <Label htmlFor="currency" style={{ color: colors.primaryText }}>
            Currency <span className="text-red-500">*</span>
          </Label>
          <Input
            id="currency"
            value={metadata.currency}
            onChange={(e) => setMetadata(prev => ({ ...prev, currency: e.target.value.toUpperCase() }))}
            placeholder="e.g., USD"
            maxLength={3}
            disabled={isUploading}
            style={{ borderColor: colors.borderGray }}
            required
          />
        </div>
      </div>

      {/* Validity date fields */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-3">
          <Label htmlFor="validFrom" style={{ color: colors.primaryText }}>
            Valid From <span className="text-red-500">*</span>
          </Label>
          <Input
            id="validFrom"
            type="date"
            value={metadata.validFrom}
            onChange={(e) => setMetadata(prev => ({ ...prev, validFrom: e.target.value }))}
            disabled={isUploading}
            style={{ borderColor: colors.borderGray }}
            required
          />
        </div>
        <div className="space-y-3">
          <Label htmlFor="validUntil" style={{ color: colors.primaryText }}>
            Valid Until <span className="text-red-500">*</span>
          </Label>
          <Input
            id="validUntil"
            type="date"
            value={metadata.validUntil}
            onChange={(e) => setMetadata(prev => ({ ...prev, validUntil: e.target.value }))}
            disabled={isUploading}
            style={{ borderColor: colors.borderGray }}
            required
          />
        </div>
      </div>

      {/* Upload Progress */}
      {isUploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm" style={{ color: colors.primaryText }}>
            <span>Uploading...</span>
            <span>{overallProgress}%</span>
          </div>
          <Progress value={overallProgress} />
        </div>
      )}

      {/* Submit Button */}
      <div className="flex gap-4">
        <Button
          onClick={handleUpload}
          className="flex-1"
          size="lg"
          disabled={pendingCount === 0 || isUploading}
          style={{
            backgroundColor: colors.primaryBrandBlue,
            color: "white",
          }}
        >
          {isUploading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Uploading {pendingCount} file(s)...
            </>
          ) : (
            <>
              <Upload className="mr-2 h-4 w-4" />
              Upload {pendingCount} file(s)
            </>
          )}
        </Button>
        {successCount > 0 && (
          <Button
            variant="outline"
            size="lg"
            onClick={() => router.push("/dashboard")}
            style={{ borderColor: colors.borderGray, color: colors.primaryText }}
          >
            View Dashboard
          </Button>
        )}
      </div>

      {/* Help Text */}
      <p className="text-sm text-center" style={{ color: colors.secondaryText }}>
        All files will be processed automatically after upload. You can track progress on the dashboard.
      </p>

      {/* Quick Add Retailer Modal */}
      <QuickAddRetailerModal
        open={showAddRetailerModal}
        onOpenChange={setShowAddRetailerModal}
        onSuccess={handleRetailerAdded}
      />
    </div>
  );
}
