"use client";

import { useCallback, useState, useTransition, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Image as ImageIcon, Loader2, Upload, X, ArrowUp, ArrowDown, GripVertical } from "lucide-react";
import NextImage from "next/image";
import { uploadImagesAsLeaflet } from "@/lib/actions/leaflets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { brandColors as colors } from "@/lib/brand-colors";
import { RetailerSelect } from "@/components/retailers/retailer-select";
import { QuickAddRetailerModal } from "@/components/retailers/quick-add-retailer-modal";
import type { Retailer } from "@/lib/types";

interface ImageFile {
  id: string;
  file: File;
  preview: string;
  status: "pending" | "uploading" | "success" | "error";
}

interface UploadMetadata {
  retailer: string;
  country: string;
  language: string;
  currency: string;
  validFrom: string;
  validUntil: string;
}

export function ImageUploader() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [images, setImages] = useState<ImageFile[]>([]);
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

  // Clean up object URLs on unmount
  useEffect(() => {
    return () => {
      images.forEach((img) => URL.revokeObjectURL(img.preview));
    };
  }, [images]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const validImages = acceptedFiles.filter((file) => {
      const isImage = file.type.startsWith("image/");
      const isValidSize = file.size <= 20 * 1024 * 1024; // 20MB max per image
      if (!isImage) {
        toast.error(`${file.name}: Not a valid image file`);
        return false;
      }
      if (!isValidSize) {
        toast.error(`${file.name}: File too large (max 20MB)`);
        return false;
      }
      return true;
    });

    const newImages: ImageFile[] = validImages.map((file) => ({
      id: crypto.randomUUID(),
      file,
      preview: URL.createObjectURL(file),
      status: "pending",
    }));

    setImages((prev) => {
      const combined = [...prev, ...newImages];
      if (combined.length > 100) {
        toast.warning(`Maximum 100 images allowed. Only first 100 will be used.`);
        return combined.slice(0, 100);
      }
      return combined;
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
      "image/tiff": [".tiff", ".tif"],
      "image/gif": [".gif"],
      "image/bmp": [".bmp"],
    },
    maxSize: 20 * 1024 * 1024,
    multiple: true,
  });

  const removeImage = (id: string) => {
    setImages((prev) => {
      const img = prev.find((i) => i.id === id);
      if (img) URL.revokeObjectURL(img.preview);
      return prev.filter((i) => i.id !== id);
    });
  };

  const moveImage = (index: number, direction: "up" | "down") => {
    setImages((prev) => {
      const newImages = [...prev];
      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= newImages.length) return prev;
      [newImages[index], newImages[targetIndex]] = [newImages[targetIndex], newImages[index]];
      return newImages;
    });
  };

  const clearAllImages = () => {
    images.forEach((img) => URL.revokeObjectURL(img.preview));
    setImages([]);
  };

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

    if (images.length === 0) {
      toast.error("Please add at least one image");
      return;
    }

    // Validate required fields
    if (!metadata.retailer || !metadata.country || !metadata.currency || !metadata.language || !metadata.validFrom || !metadata.validUntil) {
      toast.error("Please fill in all required fields");
      return;
    }

    startTransition(async () => {
      try {
        setUploadStage("Preparing images...");
        setUploadProgress(10);

        const formData = new FormData();

        // Add all images in order
        images.forEach((img) => {
          formData.append("files", img.file);
        });

        // Add metadata
        if (metadata.retailer) formData.append("retailer", metadata.retailer);
        if (metadata.country) formData.append("country", metadata.country);
        if (metadata.language) formData.append("language", metadata.language);
        if (metadata.currency) formData.append("currency", metadata.currency);
        if (metadata.validFrom) formData.append("valid_from", new Date(metadata.validFrom).toISOString());
        if (metadata.validUntil) formData.append("valid_until", new Date(metadata.validUntil).toISOString());

        setUploadStage("Uploading images...");
        setUploadProgress(30);

        const result = await uploadImagesAsLeaflet(formData);

        if (result.success && result.data) {
          setUploadProgress(100);
          setUploadStage("Complete!");
          toast.success(`Leaflet created from ${images.length} images! ID: ${result.data.leaflet_id}`);
          router.push(`/leaflets/${result.data.leaflet_id}`);
        } else {
          toast.error(result.error || "Upload failed");
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

  const totalSize = images.reduce((sum, img) => sum + img.file.size, 0);
  const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl mx-auto">
        {/* Dropzone */}
        <div
          {...getRootProps()}
          className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors"
          style={{
            borderColor: isDragActive
              ? colors.primaryBrandBlue
              : images.length > 0
              ? colors.success
              : colors.borderGray,
            backgroundColor: isDragActive
              ? colors.lightBlueTint
              : "transparent",
          }}
        >
          <input {...getInputProps()} />

          <ImageIcon className="h-12 w-12 mx-auto mb-4" style={{ color: colors.secondaryText }} />
          <p className="text-lg font-medium" style={{ color: colors.primaryText }}>
            {isDragActive
              ? "Drop your images here"
              : "Drag & drop images here"}
          </p>
          <p className="text-sm mt-1" style={{ color: colors.secondaryText }}>
            JPEG, PNG, WEBP, TIFF, GIF, BMP (max 20MB each, 100 images max)
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-4"
            onClick={(e) => e.stopPropagation()}
          >
            Or click to browse
          </Button>
        </div>

        {/* Image Preview Grid */}
        {images.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium" style={{ color: colors.primaryText }}>
                  {images.length} image{images.length !== 1 ? "s" : ""} selected
                </span>
                <span className="text-sm ml-2" style={{ color: colors.secondaryText }}>
                  ({totalSizeMB} MB total)
                </span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={clearAllImages}
                className="text-red-500 hover:text-red-600"
              >
                Clear all
              </Button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {images.map((img, index) => (
                <div
                  key={img.id}
                  className="relative group rounded-lg overflow-hidden border"
                  style={{ borderColor: colors.borderGray }}
                >
                  {/* Image Preview */}
                  <div className="aspect-[3/4] relative bg-gray-100">
                    <NextImage
                      src={img.preview}
                      alt={img.file.name}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                    {/* Page Number Badge */}
                    <div
                      className="absolute top-2 left-2 px-2 py-1 rounded text-xs font-bold text-white"
                      style={{ backgroundColor: colors.primaryBrandBlue }}
                    >
                      Page {index + 1}
                    </div>
                  </div>

                  {/* Hover Controls */}
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    {/* Move Up */}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-white hover:bg-white/20"
                      onClick={() => moveImage(index, "up")}
                      disabled={index === 0}
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>

                    {/* Move Down */}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-white hover:bg-white/20"
                      onClick={() => moveImage(index, "down")}
                      disabled={index === images.length - 1}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>

                    {/* Remove */}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-white hover:bg-red-500/80"
                      onClick={() => removeImage(img.id)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Filename */}
                  <div
                    className="p-2 text-xs truncate"
                    style={{ color: colors.secondaryText }}
                    title={img.file.name}
                  >
                    {img.file.name}
                  </div>
                </div>
              ))}
            </div>

            <p className="text-sm" style={{ color: colors.secondaryText }}>
              <GripVertical className="inline h-4 w-4 mr-1" />
              Hover over images to reorder or remove them. First image = Page 1.
            </p>
          </div>
        )}

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
          disabled={images.length === 0 || isPending}
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
              Upload {images.length} Image{images.length !== 1 ? "s" : ""} & Process
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
