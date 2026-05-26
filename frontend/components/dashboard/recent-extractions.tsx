"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle,
  Clock,
  AlertTriangle,
  Zap,
  Package,
} from "lucide-react";
import type { Product } from "@/lib/types";
import { brandColors as colors } from "@/lib/brand-colors";

interface RecentExtractionsProps {
  products: Product[];
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "auto_approved":
      return <Zap className="h-4 w-4" style={{ color: colors.primaryBrandBlue }} strokeWidth={2} />;
    case "approved":
      return <CheckCircle className="h-4 w-4" style={{ color: colors.success }} strokeWidth={2} />;
    case "pending":
      return <Clock className="h-4 w-4" style={{ color: colors.warning }} strokeWidth={2} />;
    case "needs_correction":
      return <AlertTriangle className="h-4 w-4" style={{ color: colors.warning }} strokeWidth={2} />;
    default:
      return <Clock className="h-4 w-4" style={{ color: colors.secondaryText }} strokeWidth={2} />;
  }
}

export function RecentExtractions({ products }: RecentExtractionsProps) {
  if (products.length === 0) {
    return (
      <div
        className="bg-white rounded-lg border overflow-hidden"
        style={{ borderColor: colors.borderGray }}
      >
        <div className="p-6 border-b" style={{ borderColor: colors.borderGray }}>
          <h3 className="text-lg font-light" style={{ color: colors.primaryText }}>
            Recent Extractions
          </h3>
        </div>
        <div className="p-8 text-center">
          <div
            className="w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: colors.offWhiteBg }}
          >
            <Package className="h-6 w-6" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
          </div>
          <p className="text-sm font-light mb-1" style={{ color: colors.primaryText }}>
            No products extracted yet
          </p>
          <p className="text-xs font-light" style={{ color: colors.secondaryText }}>
            Upload a leaflet to get started
          </p>
        </div>
      </div>
    );
  }

  // Calculate quick stats
  const pendingCount = products.filter(
    p => p.review_status === "pending" || p.review_status === "needs_correction"
  ).length;

  return (
    <div
      className="bg-white rounded-lg border overflow-hidden"
      style={{ borderColor: colors.borderGray }}
    >
      <div className="p-6 border-b" style={{ borderColor: colors.borderGray }}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-light" style={{ color: colors.primaryText }}>
            Recent Extractions
          </h3>
          {pendingCount > 0 && (
            <span
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-light"
              style={{ backgroundColor: colors.warningBg, color: colors.warningText }}
            >
              {pendingCount} pending
            </span>
          )}
        </div>
      </div>
      <div className="p-4 space-y-1">
        {products.slice(0, 8).map((product) => (
          <Link
            key={product.id}
            href={`/products/${product.id}`}
            className="flex items-center gap-3 p-3 rounded-lg transition-colors"
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <StatusIcon status={product.review_status} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-light truncate" style={{ color: colors.primaryText }}>
                {product.product_name}
              </p>
              <p className="text-xs font-light" style={{ color: colors.secondaryText }}>
                {product.brand && `${product.brand} • `}
                {product.discounted_price !== null && (
                  <span className="font-light" style={{ color: colors.primaryText }}>
                    {product.currency || "€"} {product.discounted_price.toFixed(2)}
                  </span>
                )}
                {product.discounted_price === null && product.regular_price !== null && (
                  <span className="font-light" style={{ color: colors.primaryText }}>
                    {product.currency || "€"} {product.regular_price.toFixed(2)}
                  </span>
                )}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs font-light" style={{ color: colors.secondaryText }}>
                {product.confidence ? `${Math.round(product.confidence * 100)}%` : "—"}
              </p>
            </div>
          </Link>
        ))}

        {products.length > 8 && (
          <div className="pt-2 text-center">
            <Link
              href="/review"
              className="inline-flex items-center gap-2 text-sm font-light transition-opacity hover:opacity-80"
              style={{ color: colors.primaryBrandBlue }}
            >
              View all {products.length} products
              <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
            </Link>
          </div>
        )}

        {pendingCount > 0 && (
          <div className="pt-3 border-t" style={{ borderColor: colors.borderGray }}>
            <Link
              href="/review"
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
              style={{ backgroundColor: colors.primaryBrandBlue }}
            >
              Review {pendingCount} Pending
              <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
