"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LeafletPage, Product } from "@/lib/types";

interface LeafletPagesProps {
  pages: LeafletPage[];
  products?: Product[];
  leafletId?: string;
}

/**
 * Convert internal MinIO URLs to browser-accessible URLs
 * Docker internal: http://minio:9000/... -> http://localhost:9000/...
 */
function getAccessibleUrl(url: string | null | undefined): string | null {
  if (!url) return null;

  return url
    .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
}

/**
 * Count products by status for a page
 */
function getStatusCounts(products: Product[]): {
  approved: number;
  pending: number;
  rejected: number;
} {
  const counts = { approved: 0, pending: 0, rejected: 0 };

  products.forEach((p) => {
    if (p.review_status === "approved" || p.review_status === "auto_approved") {
      counts.approved++;
    } else if (p.review_status === "pending") {
      counts.pending++;
    } else if (p.review_status === "rejected") {
      counts.rejected++;
    }
  });

  return counts;
}

function PageThumbnail({ page }: { page: LeafletPage }) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const thumbnailUrl = getAccessibleUrl(page.thumbnail_url);

  if (!thumbnailUrl || imageError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-muted">
        <ImageIcon className="h-8 w-8 text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      {/* Skeleton placeholder shown until image loads */}
      {!imageLoaded && (
        <div className="absolute inset-0 bg-muted animate-pulse" />
      )}
      <Image
        src={thumbnailUrl}
        alt={`Page ${page.page_number}`}
        fill
        loading="lazy"
        className={cn(
          "object-cover transition-opacity duration-300",
          imageLoaded ? "opacity-100" : "opacity-0"
        )}
        unoptimized
        onLoad={() => setImageLoaded(true)}
        onError={() => setImageError(true)}
      />
    </>
  );
}

interface StatusIndicatorProps {
  counts: { approved: number; pending: number; rejected: number };
}

function StatusIndicator({ counts }: StatusIndicatorProps) {
  const total = counts.approved + counts.pending + counts.rejected;
  if (total === 0) return null;

  return (
    <div className="absolute bottom-2 left-2 right-2 flex gap-1">
      {counts.approved > 0 && (
        <div
          className="h-1.5 rounded-full bg-green-500"
          style={{ flex: counts.approved }}
          title={`${counts.approved} approved`}
        />
      )}
      {counts.pending > 0 && (
        <div
          className="h-1.5 rounded-full bg-yellow-500"
          style={{ flex: counts.pending }}
          title={`${counts.pending} pending`}
        />
      )}
      {counts.rejected > 0 && (
        <div
          className="h-1.5 rounded-full bg-red-500"
          style={{ flex: counts.rejected }}
          title={`${counts.rejected} rejected`}
        />
      )}
    </div>
  );
}

export function LeafletPages({ pages, products = [], leafletId }: LeafletPagesProps) {
  // Group products by page number
  const productsByPage = useMemo(() => {
    const byPage: Record<number, Product[]> = {};
    products.forEach((p) => {
      if (!byPage[p.page_number]) {
        byPage[p.page_number] = [];
      }
      byPage[p.page_number].push(p);
    });
    return byPage;
  }, [products]);

  // Get leaflet ID from first page if not provided
  const effectiveLeafletId = leafletId || (pages.length > 0 ? pages[0].leaflet_id : "");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pages ({pages.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {pages.map((page) => {
            const pageProducts = productsByPage[page.page_number] || [];
            const statusCounts = getStatusCounts(pageProducts);

            return (
              <Link
                key={page.id}
                href={`/leaflets/${effectiveLeafletId}/pages/${page.page_number}`}
              >
                <div className="aspect-[3/4] bg-muted rounded-lg overflow-hidden relative group cursor-pointer transition-all hover:ring-2 hover:ring-primary hover:ring-offset-2">
                  <PageThumbnail page={page} />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="text-white text-sm font-medium">
                      Page {page.page_number}
                    </span>
                  </div>
                  {page.products_count > 0 && (
                    <div className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded-full">
                      {page.products_count}
                    </div>
                  )}
                  <StatusIndicator counts={statusCounts} />
                </div>
              </Link>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
