import { Suspense } from "react";
import { notFound } from "next/navigation";
import { getLeaflet, getLeafletPages } from "@/lib/actions/leaflets";
import { getProducts } from "@/lib/actions/products";
import { LeafletDetail } from "@/components/leaflet/leaflet-detail";
import { LeafletPages } from "@/components/leaflet/leaflet-pages";
import { LeafletProducts } from "@/components/leaflet/leaflet-products";
import { LeafletDetailSkeleton } from "@/components/dashboard/skeletons";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface LeafletPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}

export default async function LeafletPage({ params, searchParams }: LeafletPageProps) {
  const { id } = await params;
  const { tab } = await searchParams;

  return (
    <Suspense fallback={<LeafletDetailSkeleton />}>
      <LeafletContent id={id} defaultTab={tab} />
    </Suspense>
  );
}

// Renamed from LeafletDetailWrapper to avoid Next.js 16/Turbopack performance measurement issue
// The error "cannot have a negative time stamp" occurs when React DevTools tries to measure
// async Server Components with certain naming patterns
async function LeafletContent({ id, defaultTab }: { id: string; defaultTab?: string }) {
  const leaflet = await getLeaflet(id);

  if (!leaflet) {
    notFound();
  }

  // Use the product count from the leaflet detail response (cheap COUNT query)
  // instead of loading all products just to count them.
  const productCount = leaflet.products_count ?? 0;
  const hasProducts = productCount > 0;

  // Fetch pages and a small initial page of products concurrently.
  // Products are paginated server-side (default 50) -- the LeafletProducts
  // component will fetch additional pages client-side as the user navigates.
  const [pages, productsData] = await Promise.all([
    getLeafletPages(id),
    hasProducts
      ? getProducts({ leafletId: id, pageSize: 50, page: 1, sortBy: "page_number", sortOrder: "asc" })
      : Promise.resolve({ products: [], total: 0 }),
  ]);

  const products = productsData.products || [];

  // Default to products tab if there are products, otherwise pages
  const activeTab = defaultTab || (hasProducts ? "products" : "pages");

  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-10">
      <LeafletDetail leaflet={leaflet} productCount={productCount} />

      {(pages.length > 0 || hasProducts) && (
        <Tabs defaultValue={activeTab} className="w-full">
          <TabsList>
            <TabsTrigger value="products" className="gap-2">
              Products
              {hasProducts && (
                <span className="ml-1 px-2 py-0.5 text-xs bg-[#5B8DBE]/10 text-[#5B8DBE] rounded-full">
                  {productCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="pages" className="gap-2">
              Pages
              {pages.length > 0 && (
                <span className="ml-1 px-2 py-0.5 text-xs bg-[#F9FAFB] text-[#6B7280] rounded-full">
                  {pages.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="products" className="mt-8">
            <LeafletProducts
              products={products}
              leafletId={id}
              pages={pages}
              totalProducts={productsData.total || productCount}
            />
          </TabsContent>

          <TabsContent value="pages" className="mt-8">
            <LeafletPages pages={pages} leafletId={id} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
