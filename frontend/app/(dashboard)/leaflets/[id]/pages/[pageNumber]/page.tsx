import { notFound } from "next/navigation";
import { getLeaflet, getLeafletPages } from "@/lib/actions/leaflets";
import { getProducts } from "@/lib/actions/products";
import { PageViewer } from "@/components/leaflet/page-viewer";

interface PageViewerPageProps {
  params: Promise<{ id: string; pageNumber: string }>;
}

export default async function PageViewerPage({ params }: PageViewerPageProps) {
  const { id, pageNumber } = await params;
  const pageNum = parseInt(pageNumber, 10);

  if (isNaN(pageNum)) {
    notFound();
  }

  const [leaflet, pages] = await Promise.all([
    getLeaflet(id),
    getLeafletPages(id),
  ]);

  if (!leaflet) {
    notFound();
  }

  const currentPage = pages.find((p) => p.page_number === pageNum);
  if (!currentPage) {
    notFound();
  }

  // Only fetch products for the current page (not all 500+ across the leaflet)
  const productsData = await getProducts({
    leafletId: id,
    pageNumber: pageNum,
    pageSize: 100,
  });
  const products = productsData.products || [];

  return (
    <PageViewer
      leaflet={leaflet}
      page={currentPage}
      pages={pages}
      products={products}
    />
  );
}
