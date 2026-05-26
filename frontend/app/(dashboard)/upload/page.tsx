import { FileUploader } from "@/components/upload/file-uploader";
import { BulkFileUploader } from "@/components/upload/bulk-file-uploader";
import { ImageUploader } from "@/components/upload/image-uploader";


import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VlmStatusBanner } from "@/components/dashboard/vlm-status-banner";
import { FileText, Search, Zap, Lightbulb, Image } from "lucide-react";
import { brandColors as colors } from "@/lib/brand-colors";

export default function UploadPage() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-10">
        <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
          Upload Leaflets
        </h1>
        <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
          Upload PDF, ZIP, or image files for AI-powered product data extraction
        </p>
      </div>

      {/* VLM Status Banner - important reminder on upload page */}
      <div className="mb-8">
        <VlmStatusBanner />
      </div>

      <div className="bg-white rounded-lg border p-8" style={{ borderColor: colors.borderGray }}>
        <Tabs defaultValue="single" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-8">
            <TabsTrigger value="single">PDF / ZIP Upload</TabsTrigger>
            <TabsTrigger value="images">Image Upload</TabsTrigger>
            <TabsTrigger value="bulk">Bulk Upload</TabsTrigger>
          </TabsList>
          <TabsContent value="single">
            <FileUploader />
          </TabsContent>
          <TabsContent value="images">
            <ImageUploader />
          </TabsContent>
          <TabsContent value="bulk">
            <BulkFileUploader />
          </TabsContent>
        </Tabs>
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-4 gap-6">
        <InfoCard
          icon={FileText}
          title="PDF / ZIP Upload"
          description="PDF files or ZIP archives with page images (up to 100MB)"
        />
        <InfoCard
          icon={Image}
          title="Image Upload"
          description="Drag & drop multiple images directly (JPG, PNG, WEBP, etc.)"
        />
        <InfoCard
          icon={Search}
          title="What We Extract"
          description="Brand, product name, prices, discounts, quantities, and more"
        />
        <InfoCard
          icon={Zap}
          title="Processing Time"
          description="Most leaflets are processed in 2-5 minutes"
        />
      </div>

      <div
        className="mt-8 rounded-lg p-6 border"
        style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray }}
      >
        <div className="flex items-start gap-4">
          <div
            className="w-10 h-10 bg-white rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ borderColor: colors.borderGray }}
          >
            <Lightbulb className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-medium mb-2" style={{ color: colors.primaryText }}>
              Upload Tips
            </h3>
            <ul className="text-sm font-light space-y-1" style={{ color: colors.secondaryText }}>
              <li>• <strong>PDF/ZIP:</strong> Upload a PDF leaflet or ZIP archive containing page images</li>
              <li>• <strong>Images:</strong> Drag & drop multiple images directly - reorder before uploading</li>
              <li>• <strong>Bulk:</strong> Upload up to 20 PDF files at once with shared metadata</li>
              <li>• Processing starts automatically after upload</li>
              <li>• Track progress on the dashboard or review queue</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number; style?: React.CSSProperties }>;
  title: string;
  description: string;
}) {
  return (
    <div
      className="rounded-lg p-6 border"
      style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray }}
    >
      <div
        className="w-10 h-10 bg-white rounded-lg flex items-center justify-center mb-4"
      >
        <Icon className="h-5 w-5" style={{ color: colors.primaryText }} strokeWidth={1.5} />
      </div>
      <h3 className="text-base font-medium mb-2" style={{ color: colors.primaryText }}>
        {title}
      </h3>
      <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
        {description}
      </p>
    </div>
  );
}
