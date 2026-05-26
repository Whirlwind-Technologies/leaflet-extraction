"use client";

import { useCallback, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { File, Loader2, Upload, X } from "lucide-react";
import { uploadLeaflet, prepareUpload, confirmUpload, deleteLeaflet } from "@/lib/actions/leaflets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { brandColors as colors } from "@/lib/brand-colors";
import { RetailerSelect } from "@/components/retailers/retailer-select";
import { QuickAddRetailerModal } from "@/components/retailers/quick-add-retailer-modal";
import type { Retailer } from "@/lib/types";

interface UploadMetadata {
  retailer: string;
  country: string;
  language: string;
  currency: string;
  validFrom: string;
  validUntil: string;
}

export function FileUploader() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showAddRetailerModal, setShowAddRetailerModal] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStage, setUploadStage] = useState<string>("");
  const [metadata, setMetadata] = useState<UploadMetadata>({
    retailer: "",
    country: "",
    language: "",
    currency: "",
    validFrom: "",
    validUntil: "",
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
      const isZip = file.type === "application/zip" ||
        file.type === "application/x-zip-compressed" ||
        file.type === "application/octet-stream" ||
        file.name.toLowerCase().endsWith(".zip");

      if (!isPdf && !isZip) {
        toast.error("Please upload a PDF or ZIP file");
        return;
      }
      if (file.size > 100 * 1024 * 1024) {
        toast.error("File size must be less than 100MB");
        return;
      }
      setSelectedFile(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/zip": [".zip"],
      "application/x-zip-compressed": [".zip"],
    },
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024,
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedFile) {
      toast.error("Please select a file");
      return;
    }

    // Validate required fields
    if (!metadata.retailer || !metadata.country || !metadata.currency || !metadata.language || !metadata.validFrom || !metadata.validUntil) {
      toast.error("Please fill in all required fields");
      return;
    }

    // Use direct S3 upload for faster uploads
    startTransition(async () => {
      try {
        // Step 1: Prepare upload (get presigned URL)
        setUploadStage("Preparing...");
        setUploadProgress(5);

        const prepareFormData = new FormData();
        prepareFormData.append("filename", selectedFile.name);
        prepareFormData.append("file_size", selectedFile.size.toString());
        if (metadata.retailer) prepareFormData.append("retailer", metadata.retailer);
        if (metadata.country) prepareFormData.append("country", metadata.country);
        if (metadata.language) prepareFormData.append("language", metadata.language);
        if (metadata.currency) prepareFormData.append("currency", metadata.currency);
        if (metadata.validFrom) prepareFormData.append("valid_from", new Date(metadata.validFrom).toISOString());
        if (metadata.validUntil) prepareFormData.append("valid_until", new Date(metadata.validUntil).toISOString());

        const prepareResult = await prepareUpload(prepareFormData);

        if (!prepareResult.success || !prepareResult.data) {
          toast.error(prepareResult.error || "Failed to prepare upload");
          setUploadProgress(0);
          setUploadStage("");
          return;
        }

        const { leaflet_id, upload_url, upload_fields } = prepareResult.data;

        // Step 2: Upload directly to S3
        //
        // Some backends (e.g. local storage mode) don't support direct
        // uploads. They signal this with upload_url == null or
        // supported === false. In those cases skip straight to the
        // server-side upload — and crucially delete the pending leaflet
        // record `prepareUpload` just created, so we don't accumulate
        // orphaned rows.
        const directUploadSupported = Boolean(upload_url) && (prepareResult.data as { supported?: boolean }).supported !== false;

        let s3UploadAttempted = false;
        if (directUploadSupported) {
          setUploadStage("Uploading to storage...");
          setUploadProgress(20);
          try {
            const s3FormData = new FormData();
            // Add all presigned fields first
            Object.entries(upload_fields).forEach(([key, value]) => {
              s3FormData.append(key, value);
            });
            // Add the file last (required by S3)
            s3FormData.append("file", selectedFile);

            // Note: CORS may block reading the response even if upload succeeds
            // We'll verify via confirm-upload which checks if file exists in S3
            await fetch(upload_url as string, {
              method: "POST",
              body: s3FormData,
            });
            s3UploadAttempted = true;
          } catch (s3Error) {
            // CORS error or network issue
            console.warn("S3 direct upload error (may still have succeeded):", s3Error);
            s3UploadAttempted = true; // Upload may have succeeded despite CORS blocking response
          }

          setUploadProgress(60);

          // Step 3: Verify upload via confirm-upload (checks if file exists in S3)
          // This works even if CORS blocked reading the S3 response
          if (s3UploadAttempted) {
            setUploadStage("Verifying upload...");
            const confirmResult = await confirmUpload(leaflet_id);

            if (confirmResult.success && confirmResult.data) {
              // S3 upload succeeded!
              setUploadProgress(100);
              setUploadStage("Complete!");
              toast.success(`Leaflet uploaded! ID: ${leaflet_id}`);
              router.push(`/leaflets/${leaflet_id}`);
              return;
            }
            // File not in S3, fall back to traditional upload
            console.warn("S3 upload verification failed, falling back to server upload");
          }
        }

        // Fallback path: the direct upload didn't complete. Clean up the
        // pending leaflet record from prepareUpload before submitting a
        // fresh one via the server upload — otherwise we leave behind an
        // orphaned row for every fallback.
        try {
          await deleteLeaflet(leaflet_id);
        } catch (cleanupError) {
          console.warn("Failed to clean up orphaned pending leaflet", cleanupError);
        }

        setUploadStage("Uploading via server...");
        setUploadProgress(30);

        const fallbackFormData = new FormData();
        fallbackFormData.append("file", selectedFile);
        if (metadata.retailer) fallbackFormData.append("retailer", metadata.retailer);
        if (metadata.country) fallbackFormData.append("country", metadata.country);
        if (metadata.language) fallbackFormData.append("language", metadata.language);
        if (metadata.currency) fallbackFormData.append("currency", metadata.currency);
        if (metadata.validFrom) fallbackFormData.append("valid_from", new Date(metadata.validFrom).toISOString());
        if (metadata.validUntil) fallbackFormData.append("valid_until", new Date(metadata.validUntil).toISOString());

        const fallbackResult = await uploadLeaflet(fallbackFormData);

        if (fallbackResult.success && fallbackResult.data) {
          setUploadProgress(100);
          setUploadStage("Complete!");
          toast.success(`Leaflet uploaded! ID: ${fallbackResult.data.leaflet_id}`);
          router.push(`/leaflets/${fallbackResult.data.leaflet_id}`);
        } else {
          toast.error(fallbackResult.error || "Upload failed");
          setUploadProgress(0);
          setUploadStage("");
        }

      } catch (error) {
        console.error("Upload error:", error);
        toast.error("An unexpected error occurred during upload");
        setUploadProgress(0);
        setUploadStage("");
      }
    });
  };

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl mx-auto">
        {/* Dropzone */}
        <div
          {...getRootProps()}
          className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors"
          style={{
            borderColor: isDragActive
              ? colors.primaryBrandBlue
              : selectedFile
                ? colors.success
                : colors.borderGray,
            backgroundColor: isDragActive
              ? colors.lightBlueTint
              : selectedFile
                ? colors.successBg
                : "transparent",
          }}
        >
          <input {...getInputProps()} />

          {selectedFile ? (
            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-3">
                <div
                  className="h-12 w-12 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: colors.successBg }}
                >
                  <File className="h-6 w-6" style={{ color: colors.success }} />
                </div>
                <div className="text-left">
                  <p className="font-medium" style={{ color: colors.primaryText }}>{selectedFile.name}</p>
                  <p className="text-sm" style={{ color: colors.secondaryText }}>
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                }}
              >
                <X className="h-5 w-5" style={{ color: colors.secondaryText }} />
              </Button>
            </div>
          ) : (
            <>
              <Upload className="h-12 w-12 mx-auto mb-4" style={{ color: colors.secondaryText }} />
              <p className="text-lg font-medium" style={{ color: colors.primaryText }}>
                {isDragActive
                  ? "Drop your file here"
                  : "Drag & drop your PDF or ZIP file"}
              </p>
              <p className="text-sm mt-1" style={{ color: colors.secondaryText }}>
                PDF leaflet or ZIP archive with page images (max 100MB)
              </p>
            </>
          )}
        </div>

        {/* Metadata fields */}
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-3 col-span-3">
            <Label htmlFor="retailer" style={{ color: colors.primaryText }}>Retailer <span className="text-red-500">*</span></Label>
            <RetailerSelect
              value={metadata.retailer}
              onSelect={handleRetailerSelect}
              onAddNew={() => setShowAddRetailerModal(true)}
              disabled={isPending}
            />
            <p className="text-xs text-slate-500">
              Select a retailer to auto-fill country, currency, and language
            </p>
          </div>
          <div className="space-y-3">
            <Label htmlFor="country" style={{ color: colors.primaryText }}>
              Country <span className="text-red-500">*</span>
            </Label>
            <Input
              id="country"
              value={metadata.country}
              onChange={(e) =>
                setMetadata(prev => ({ ...prev, country: e.target.value.toUpperCase() }))
              }
              placeholder="e.g., US"
              maxLength={2}
              style={{ borderColor: colors.borderGray }}
              disabled={isPending}
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
              onChange={(e) =>
                setMetadata(prev => ({ ...prev, currency: e.target.value.toUpperCase() }))
              }
              placeholder="e.g., USD"
              maxLength={3}
              style={{ borderColor: colors.borderGray }}
              disabled={isPending}
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
              onChange={(e) =>
                setMetadata(prev => ({ ...prev, language: e.target.value.toLowerCase() }))
              }
              placeholder="e.g., en"
              maxLength={5}
              style={{ borderColor: colors.borderGray }}
              disabled={isPending}
              required
            />
          </div>
        </div>

        {/* Validity date fields */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-3">
            <Label htmlFor="validFrom" style={{ color: colors.primaryText }}>
              Valid From <span className="text-red-500">*</span>
            </Label>
            <Input
              id="validFrom"
              type="date"
              value={metadata.validFrom}
              onChange={(e) =>
                setMetadata(prev => ({ ...prev, validFrom: e.target.value }))
              }
              style={{ borderColor: colors.borderGray }}
              disabled={isPending}
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
              onChange={(e) =>
                setMetadata(prev => ({ ...prev, validUntil: e.target.value }))
              }
              style={{ borderColor: colors.borderGray }}
              disabled={isPending}
              required
            />
          </div>
        </div>

        {/* Upload Progress */}
        {isPending && uploadProgress > 0 && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span style={{ color: colors.secondaryText }}>{uploadStage}</span>
              <span style={{ color: colors.primaryText }}>{uploadProgress}%</span>
            </div>
            <Progress value={uploadProgress} className="h-2" />
          </div>
        )}

        {/* Submit button */}
        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={!selectedFile || isPending}
          style={{
            backgroundColor: colors.primaryBrandBlue,
            color: "white",
          }}
        >
          {isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {uploadStage || "Uploading..."}
            </>
          ) : (
            <>
              <Upload className="mr-2 h-4 w-4" />
              Upload & Process
            </>
          )}
        </Button>
      </form>

      {/* Quick Add Retailer Modal */}
      <QuickAddRetailerModal
        open={showAddRetailerModal}
        onOpenChange={setShowAddRetailerModal}
        onSuccess={handleRetailerAdded}
      />
    </>
  );
}
