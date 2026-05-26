import { Suspense } from "react";
import { ReviewQueue } from "@/components/review/review-queue";
import { getReviewQueue } from "@/lib/actions/products";
import { ReviewQueueSkeleton } from "@/components/dashboard/skeletons";

interface ReviewPageProps {
  searchParams: Promise<{
    leaflet_id?: string;
    page?: string;
    page_size?: string;
    status?: string;
  }>;
}

export default async function ReviewPage({ searchParams }: ReviewPageProps) {
  const params = await searchParams;
  const page = parseInt(params.page || "1", 10);
  const pageSize = parseInt(params.page_size || "20", 10);

  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight text-foreground">
            Review <span className="font-normal">Queue</span>
          </h1>
          <p className="text-sm font-light text-muted-foreground">
            Review and approve extracted product data
          </p>
        </div>
      </div>

      <Suspense fallback={<ReviewQueueSkeleton />}>
        <ReviewQueueWrapper
          leafletId={params.leaflet_id}
          page={page}
          pageSize={pageSize}
          statusFilter={params.status}
        />
      </Suspense>
    </div>
  );
}

async function ReviewQueueWrapper({
  leafletId,
  page,
  pageSize,
  statusFilter,
}: {
  leafletId?: string;
  page: number;
  pageSize: number;
  statusFilter?: string;
}) {
  const { products, total } = await getReviewQueue({
    leafletId,
    page,
    pageSize,
  });

  // Apply client-side filters (should be done server-side in production)
  let filteredProducts = products;
  if (statusFilter) {
    filteredProducts = filteredProducts.filter(p => p.review_status === statusFilter);
  }

  return (
    <ReviewQueue
      products={filteredProducts}
      leafletId={leafletId}
      totalCount={total}
      currentPage={page}
      pageSize={pageSize}
    />
  );
}