"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Download,
  FileJson,
  FileSpreadsheet,
  Loader2,
  ChevronDown,
  ImageIcon,
  Image as ImageLucide,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ExportMenuProps {
  leafletId: string;
  productCount: number;
  disabled?: boolean;
}

type ImageStorageOption = "url" | "base64" | "none";

export function ExportMenu({ leafletId, productCount, disabled }: ExportMenuProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<string | null>(null);

  const handleExport = async (format: "json" | "csv", imageStorage: ImageStorageOption = "url") => {
    if (productCount === 0) {
      toast.error("No products to export");
      return;
    }

    setIsExporting(true);
    setExportFormat(format);

    try {
      const params = new URLSearchParams({
        format,
        image_storage: imageStorage,
        include_product_codes: "true",
      });

      const response = await fetch(
        `/api/export/${leafletId}?${params.toString()}`,
        {
          method: "GET",
          credentials: "include",
        }
      );

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      if (format === "csv") {
        // Download CSV file
        const blob = await response.blob();
        const contentDisposition = response.headers.get("Content-Disposition");
        let filename = `${leafletId}_export.csv`;
        
        if (contentDisposition) {
          // Match filename with or without quotes
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
        
        toast.success(`CSV exported successfully!`);
      } else {
        // JSON - either download or copy
        const data = await response.json();
        
        // Download JSON file
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${leafletId}_export.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        toast.success(`JSON exported: ${data.total_products} products`);
      }
    } catch (error) {
      console.error("Export error:", error);
      toast.error("Export failed. Please try again.");
    } finally {
      setIsExporting(false);
      setExportFormat(null);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={disabled || isExporting || productCount === 0}>
          {isExporting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Exporting {exportFormat?.toUpperCase()}...
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export
              <ChevronDown className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Export Format</DropdownMenuLabel>
        <DropdownMenuSeparator />
        
        {/* JSON Export */}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <FileJson className="mr-2 h-4 w-4" />
            Export as JSON
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Image Options
            </DropdownMenuLabel>
            <DropdownMenuItem onClick={() => handleExport("json", "url")}>
              <ImageIcon className="mr-2 h-4 w-4" />
              With Image URLs
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("json", "base64")}>
              <ImageLucide className="mr-2 h-4 w-4" />
              With Base64 Images
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("json", "none")}>
              <FileJson className="mr-2 h-4 w-4" />
              Data Only (No Images)
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        
        {/* CSV Export */}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Export as CSV
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Image Options
            </DropdownMenuLabel>
            <DropdownMenuItem onClick={() => handleExport("csv", "url")}>
              <ImageIcon className="mr-2 h-4 w-4" />
              With Image URLs
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("csv", "none")}>
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Data Only (No Images)
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        
        <DropdownMenuSeparator />
        
        {/* Quick exports */}
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Quick Export
        </DropdownMenuLabel>
        <DropdownMenuItem onClick={() => handleExport("json", "url")}>
          <FileJson className="mr-2 h-4 w-4" />
          JSON (Default)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleExport("csv", "url")}>
          <FileSpreadsheet className="mr-2 h-4 w-4" />
          CSV (Default)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}