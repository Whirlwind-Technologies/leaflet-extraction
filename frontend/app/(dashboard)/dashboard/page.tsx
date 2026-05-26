import { Suspense } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { getLeaflets } from "@/lib/actions/leaflets";
import { getProducts, getReviewQueue } from "@/lib/actions/products";



import { LeafletList } from "@/components/dashboard/leaflet-list";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentExtractions } from "@/components/dashboard/recent-extractions";
import { VlmStatusBanner } from "@/components/dashboard/vlm-status-banner";
import { PendingUsersBanner } from "@/components/dashboard/pending-users-banner";
import { LeafletListSkeleton, StatsCardsSkeleton, RecentExtractionsSkeleton } from "@/components/dashboard/skeletons";
import { brandColors as colors } from "@/lib/brand-colors";

export default async function DashboardPage() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 mb-10">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
            Dashboard
          </h1>
          <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
            Manage your leaflet extractions and monitor progress
          </p>
        </div>
        <Link
          href="/upload"
          className="inline-flex items-center gap-2 whitespace-nowrap px-4 py-2 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
          style={{ backgroundColor: colors.deepBlue }}
        >
          <Plus className="h-5 w-5" strokeWidth={1.5} />
          Upload Leaflet
        </Link>
      </div>

      {/* VLM Status Banner - shows warning if no provider configured */}
      <div className="mb-6">
        <VlmStatusBanner />
      </div>

      {/* Pending Users Banner - visible to superusers only */}
      <Suspense fallback={null}>
        <div className="mb-6">
          <PendingUsersBanner />
        </div>
      </Suspense>

      <Suspense fallback={<StatsCardsSkeleton />}>
        <StatsCardsWrapper />
      </Suspense>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
        <div className="lg:col-span-2">
          <Suspense fallback={<LeafletListSkeleton />}>
            <LeafletListWrapper />
          </Suspense>
        </div>

        <div>
          <Suspense fallback={<RecentExtractionsSkeleton />}>
            <RecentExtractionsWrapper />
          </Suspense>
        </div>
      </div>
    </div>
  );
}

async function StatsCardsWrapper() {
  const [leafletsData, productsData] = await Promise.all([
    getLeaflets({ page_size: 100 }),
    // Fetch max allowed for stats calculation (100 is backend limit)
    // Note: For accurate stats with many products, consider adding a dedicated stats endpoint
    getProducts({ pageSize: 100 }),
  ]);

  return (
    <StatsCards
      leaflets={leafletsData.items}
      productCount={productsData.total}
      products={productsData.products}
    />
  );
}

async function LeafletListWrapper() {
  const data = await getLeaflets({ page: 1, page_size: 10 });
  return <LeafletList leaflets={data.items} total={data.total} />;
}

async function RecentExtractionsWrapper() {
  const { products } = await getReviewQueue({ pageSize: 10 });
  return <RecentExtractions products={products} />;
}
