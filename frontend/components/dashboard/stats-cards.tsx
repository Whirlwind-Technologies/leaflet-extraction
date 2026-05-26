import Image from "next/image";
import { FileText, CheckCircle, Package, Clock } from "lucide-react";
import type { Leaflet, Product } from "@/lib/types";
import { brandColors as colors } from "@/lib/brand-colors";

interface StatsCardsProps {
  leaflets: Leaflet[];
  productCount?: number;
  products?: Product[];
}

export function StatsCards({ leaflets, productCount = 0, products = [] }: StatsCardsProps) {
  const total = leaflets.length;
  const processing = leaflets.filter(
    (l) => l.status === "processing" || l.status === "extracting"
  ).length;
  const completed = leaflets.filter((l) => l.status === "completed").length;

  // Product stats
  const pendingReview = products.filter(
    p => p.review_status === "pending" || p.review_status === "needs_correction"
  ).length;

  const stats = [
    {
      label: "Total Leaflets",
      value: total,
      icon: FileText,
      iconColor: colors.primaryText,
      bgColor: colors.offWhiteBg,
    },
    {
      label: "Processing",
      value: processing,
      icon: () => <Image src="/processing.svg" alt="Processing" width={20} height={20} className="h-5 w-5" />,
      iconColor: colors.primaryBrandBlue,
      bgColor: colors.lightBlueTint,
    },
    {
      label: "Completed",
      value: completed,
      icon: CheckCircle,
      iconColor: colors.success,
      bgColor: colors.successBg,
    },
    {
      label: "Products Extracted",
      value: productCount,
      icon: Package,
      iconColor: colors.primaryText,
      bgColor: colors.offWhiteBg,
    },
    {
      label: "Pending Review",
      value: pendingReview,
      icon: Clock,
      iconColor: colors.warning,
      bgColor: colors.warningBg,
      highlight: pendingReview > 0,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-white rounded-lg p-6 border transition-all"
          style={{
            borderColor: stat.highlight ? colors.warningBorder : colors.borderGray,
          }}
        >
          <div className="flex flex-col gap-3">
            <div
              className="w-11 h-11 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: stat.bgColor }}
            >
              <stat.icon
                className="h-5 w-5"
                style={{ color: stat.iconColor }}
                strokeWidth={1.5}
              />
            </div>
            <div>
              <p className="text-2xl font-semibold mb-1" style={{ color: colors.deepNavy }}>
                {stat.value}
              </p>
              <p className="text-xs font-normal" style={{ color: colors.secondaryText }}>
                {stat.label}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
