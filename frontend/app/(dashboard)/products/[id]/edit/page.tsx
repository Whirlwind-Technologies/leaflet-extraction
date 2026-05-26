import { Suspense } from "react";
import { notFound, redirect } from "next/navigation";
import { cookies } from "next/headers";
import { ProductEditorNav } from "@/components/review/product-editor-nav";
import type { PageImageInfo } from "@/components/review/product-editor-nav";
import { getProduct, getProductSiblings } from "@/lib/actions/products";
import { getLeafletPages } from "@/lib/actions/leaflets";

interface ProductEditPageProps {
  params: Promise<{
    id: string;
  }>;
  searchParams: Promise<{
    leaflet_id?: string;
    status?: string;
    page_number?: string;
  }>;
}

export default async function ProductEditPage({ params, searchParams }: ProductEditPageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;

  return (
    <div className="h-[calc(100vh-4rem)]">
      <Suspense fallback={<ProductEditorSkeleton />}>
        <ProductEditorWrapper
          productId={id}
          leafletIdParam={resolvedSearchParams.leaflet_id}
          statusParam={resolvedSearchParams.status}
          pageNumberParam={resolvedSearchParams.page_number}
        />
      </Suspense>
    </div>
  );
}

async function ProductEditorWrapper({
  productId,
  leafletIdParam,
  statusParam,
  pageNumberParam,
}: {
  productId: string;
  leafletIdParam?: string;
  statusParam?: string;
  pageNumberParam?: string;
}) {
  // Check if user is authenticated
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    redirect("/login");
  }

  const product = await getProduct(productId);

  if (!product) {
    // Could be auth error or not found - check token again
    const currentToken = cookieStore.get("access_token")?.value;
    if (!currentToken) {
      redirect("/login");
    }
    notFound();
  }

  // Get all page images for this leaflet (cached in the wrapper for client-side navigation)
  const pages = await getLeafletPages(product.leaflet_id);
  const allPages: Record<number, PageImageInfo> = {};
  for (const page of pages) {
    allPages[page.page_number] = {
      imageUrl: page.image_url || null,
      width: page.width || 2304,
      height: page.height || 3508,
    };
  }

  // Compute sibling navigation if we have context
  const leafletId = leafletIdParam || product.leaflet_id;
  const parsedPageNumber = pageNumberParam ? parseInt(pageNumberParam, 10) : undefined;
  const pageNumber = parsedPageNumber !== undefined && !isNaN(parsedPageNumber) ? parsedPageNumber : undefined;
  const navigation = await getProductSiblings({
    currentProductId: productId,
    leafletId,
    reviewStatus: statusParam,
    pageNumber,
  });

  return (
    <ProductEditorNav
      initialProduct={product}
      allPages={allPages}
      navigation={navigation ?? undefined}
    />
  );
}

function ProductEditorSkeleton() {
  return (
    <div className="flex h-full">
      <div className="flex-1 bg-muted animate-pulse" />
      <div className="w-96 border-l p-4 space-y-4">
        <div className="h-8 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
      </div>
    </div>
  );
}
