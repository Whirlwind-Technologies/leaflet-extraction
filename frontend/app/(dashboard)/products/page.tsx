import { Suspense } from "react";
import { getProducts, getProductStats } from "@/lib/actions/products";
import { getLeaflets } from "@/lib/actions/leaflets";
import { AllProductsList } from "@/components/products/all-products-list";
import { ProductsPageSkeleton } from "@/components/dashboard/skeletons";
import { Package, CheckCircle, Clock, XCircle } from "lucide-react";
import { brandColors as colors } from "@/lib/brand-colors";

interface ProductsPageProps {
  searchParams: Promise<{
    leaflet_id?: string;
    status?: string;
    category?: string;
    page?: string;
    page_size?: string;
    search?: string;
  }>;
}

export default async function ProductsPage({ searchParams }: ProductsPageProps) {
  const params = await searchParams;

  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
            All <span className="font-normal">Products</span>
          </h1>
          <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
            Browse and manage all extracted product data
          </p>
        </div>
      </div>

      <Suspense fallback={<ProductsPageSkeleton />}>
        <ProductsWrapper params={params} />
      </Suspense>
    </div>
  );
}

async function ProductsWrapper({
  params
}: {
  params: {
    leaflet_id?: string;
    status?: string;
    category?: string;
    page?: string;
    page_size?: string;
    search?: string;
  }
}) {
  const page = parseInt(params.page || "1", 10);
  const pageSize = parseInt(params.page_size || "24", 10);

  // Fetch products, leaflets, and stats in parallel
  const [productsData, leafletsData, statsData] = await Promise.all([
    getProducts({
      leafletId: params.leaflet_id,
      reviewStatus: params.status,
      category: params.category,
      page,
      pageSize,
      sortBy: "page_number",
      sortOrder: "asc",
    }),
    getLeaflets({ page_size: 100 }),
    getProductStats({ leafletId: params.leaflet_id }),
  ]);

  const products = productsData.products || [];
  const totalProducts = productsData.total || 0;
  const leaflets = leafletsData.items || [];

  // Debug info
  const completedLeaflets = leaflets.filter(l => l.status === "completed");
  const hasCompletedLeaflets = completedLeaflets.length > 0;

  // Use stats from API (accurate counts across all pages)
  const stats = {
    total: statsData.total,
    approved: statsData.approved + statsData.auto_approved, // Combine approved and auto_approved
    pending: statsData.pending + statsData.needs_correction, // Combine pending and needs_correction
    rejected: statsData.rejected,
  };

  return (
    <>
      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div
          className="bg-white rounded-lg p-6 border shadow-sm hover:shadow-md transition-shadow duration-200"
          style={{ borderColor: colors.borderGray }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: colors.lightBlueTint }}
            >
              <Package className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={2} />
            </div>
          </div>
          <p className="text-2xl font-bold mb-1" style={{ color: colors.deepNavy }}>
            {stats.total}
          </p>
          <p className="text-xs font-medium" style={{ color: colors.secondaryText }}>
            Total Products
          </p>
        </div>

        <div
          className="bg-white rounded-lg p-6 border shadow-sm hover:shadow-md transition-shadow duration-200"
          style={{ borderColor: colors.successBorder }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: colors.successBg }}
            >
              <CheckCircle className="h-5 w-5" style={{ color: colors.success }} strokeWidth={2} />
            </div>
          </div>
          <p className="text-2xl font-bold mb-1" style={{ color: colors.success }}>
            {stats.approved}
          </p>
          <p className="text-xs font-medium" style={{ color: colors.successText }}>
            Approved
          </p>
        </div>

        <div
          className="bg-white rounded-lg p-6 border shadow-sm hover:shadow-md transition-shadow duration-200"
          style={{ borderColor: colors.warningBorder }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: colors.warningBg }}
            >
              <Clock className="h-5 w-5" style={{ color: colors.warning }} strokeWidth={2} />
            </div>
          </div>
          <p className="text-2xl font-bold mb-1" style={{ color: colors.warning }}>
            {stats.pending}
          </p>
          <p className="text-xs font-medium" style={{ color: colors.warningText }}>
            Pending Review
          </p>
        </div>

        <div
          className="bg-white rounded-lg p-6 border shadow-sm hover:shadow-md transition-shadow duration-200"
          style={{ borderColor: colors.errorBorder }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: colors.errorBg }}
            >
              <XCircle className="h-5 w-5" style={{ color: colors.error }} strokeWidth={2} />
            </div>
          </div>
          <p className="text-2xl font-bold mb-1" style={{ color: colors.error }}>
            {stats.rejected}
          </p>
          <p className="text-xs font-medium" style={{ color: colors.errorText }}>
            Rejected
          </p>
        </div>
      </div>

      {/* Products List */}
      <AllProductsList
        products={products}
        totalCount={totalProducts}
        currentPage={page}
        pageSize={pageSize}
        leaflets={leaflets}
        currentLeafletId={params.leaflet_id}
        currentStatus={params.status}
        currentCategory={params.category}
        hasCompletedLeaflets={hasCompletedLeaflets}
      />
    </>
  );
}
