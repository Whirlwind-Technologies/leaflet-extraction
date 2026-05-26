"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  Clock,
  FileText,
  Loader2,
  XCircle,
  Package,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { Leaflet, LeafletStatus } from "@/lib/types";
import { brandColors as colors } from "@/lib/brand-colors";

interface LeafletListProps {
  leaflets: Leaflet[];
  total: number;
}

const statusConfig: Record<
  LeafletStatus,
  { icon: typeof Clock; color: string; bg: string; label: string }
> = {
  pending: { icon: Clock, color: colors.warning, bg: colors.warningBg, label: "Pending" },
  uploading: { icon: Loader2, color: colors.primaryBrandBlue, bg: colors.lightBlueTint, label: "Uploading" },
  processing: { icon: Loader2, color: colors.primaryBrandBlue, bg: colors.lightBlueTint, label: "Processing" },
  extracting: { icon: Loader2, color: colors.primaryBrandBlue, bg: colors.lightBlueTint, label: "Extracting" },
  validating: { icon: AlertTriangle, color: colors.warning, bg: colors.warningBg, label: "Ready" },
  reviewing: { icon: Clock, color: colors.primaryBrandBlue, bg: colors.lightBlueTint, label: "Reviewing" },
  completed: { icon: CheckCircle, color: colors.success, bg: colors.successBg, label: "Completed" },
  failed: { icon: XCircle, color: colors.error, bg: colors.errorBg, label: "Failed" },
  cancelled: { icon: XCircle, color: colors.secondaryText, bg: colors.offWhiteBg, label: "Cancelled" },
};

export function LeafletList({ leaflets, total }: LeafletListProps) {
  if (leaflets.length === 0) {
    return (
      <div
        className="bg-white rounded-lg p-12 border"
        style={{ borderColor: colors.borderGray }}
      >
        <div className="flex flex-col items-center justify-center">
          <div
            className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
            style={{ backgroundColor: colors.offWhiteBg }}
          >
            <FileText className="h-6 w-6" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
          </div>
          <p className="text-sm font-medium mb-1" style={{ color: colors.primaryText }}>
            No leaflets yet
          </p>
          <p className="text-xs mb-4" style={{ color: colors.secondaryText }}>
            Upload your first leaflet to get started
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
            style={{ backgroundColor: colors.primaryBrandBlue }}
          >
            Upload Leaflet
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className="bg-white rounded-lg border overflow-hidden"
      style={{ borderColor: colors.borderGray }}
    >
      <div className="p-6 border-b" style={{ borderColor: colors.borderGray }}>
        <h3 className="text-lg font-semibold" style={{ color: colors.primaryText }}>
          Recent Leaflets ({total})
        </h3>
      </div>
      <div>
        {leaflets.map((leaflet) => {
          const config = statusConfig[leaflet.status] || statusConfig.pending;
          const StatusIcon = config.icon;
          const isAnimated =
            leaflet.status === "processing" ||
            leaflet.status === "extracting" ||
            leaflet.status === "uploading";
          const isReady = leaflet.status === "validating";
          const isCompleted = leaflet.status === "completed" || leaflet.status === "reviewing";

          return (
            <Link
              key={leaflet.id}
              href={isCompleted ? `/leaflets/${leaflet.leaflet_id}?tab=products` : `/leaflets/${leaflet.leaflet_id}`}
              className="flex items-center gap-4 p-5 transition-colors group border-b last:border-0"
              style={{ borderColor: colors.borderGray }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <div
                className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: config.bg }}
              >
                <StatusIcon
                  className={`h-5 w-5 ${isAnimated ? "animate-spin" : ""}`}
                  style={{ color: config.color }}
                  strokeWidth={1.5}
                />
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate mb-1" style={{ color: colors.primaryText }}>
                  {leaflet.filename}
                </p>
                <div className="flex items-center gap-2 text-xs" style={{ color: colors.secondaryText }}>
                  <span>{leaflet.retailer || "Unknown retailer"}</span>
                  <span>•</span>
                  <span>{leaflet.page_count || 0} pages</span>
                  {isReady && (
                    <>
                      <span>•</span>
                      <span className="inline-flex items-center gap-1" style={{ color: colors.warning }}>
                        <AlertTriangle className="h-3 w-3" strokeWidth={1.5} />
                        Needs AI Provider
                      </span>
                    </>
                  )}
                  {isCompleted && (
                    <>
                      <span>•</span>
                      <span className="inline-flex items-center gap-1" style={{ color: colors.primaryBrandBlue }}>
                        <Package className="h-3 w-3" strokeWidth={1.5} />
                        View Products
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div className="text-right hidden sm:block">
                <span
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium"
                  style={{ backgroundColor: config.bg, color: config.color }}
                >
                  {config.label}
                </span>
                <p className="text-xs mt-1" style={{ color: colors.secondaryText }}>
                  {formatDate(leaflet.created_at)}
                </p>
              </div>

              <ChevronRight
                className="h-5 w-5 flex-shrink-0 transition-colors"
                style={{ color: colors.secondaryText }}
                strokeWidth={1.5}
              />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
