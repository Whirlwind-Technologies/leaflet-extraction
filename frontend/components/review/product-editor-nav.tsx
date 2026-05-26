"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { ProductEditor } from "./product-editor";
import { useProductCache } from "@/hooks/use-product-cache";
import { useReviewQueue } from "@/hooks/use-review-queue";
import type { Product, ProductNavigationContext } from "@/lib/types";

export interface PageImageInfo {
  imageUrl: string | null;
  width: number;
  height: number;
}

interface ProductEditorNavProps {
  initialProduct: Product;
  allPages: Record<number, PageImageInfo>;
  navigation?: ProductNavigationContext;
}

export function ProductEditorNav({
  initialProduct,
  allPages,
  navigation,
}: ProductEditorNavProps) {
  const [currentProduct, setCurrentProduct] = useState<Product>(initialProduct);
  const [currentIndex, setCurrentIndex] = useState(navigation?.currentIndex ?? 0);
  const [isLoadingNav, setIsLoadingNav] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [reviewedInSession, setReviewedInSession] = useState(0);

  const productIds = useMemo(() => navigation?.productIds ?? [], [navigation?.productIds]);
  const totalCount = productIds.length;

  const prevProductId = currentIndex > 0 ? productIds[currentIndex - 1] : null;
  const nextProductId = currentIndex < totalCount - 1 ? productIds[currentIndex + 1] : null;

  const pageInfo = allPages[currentProduct.page_number];

  // Cache & review queue
  const cache = useProductCache();
  const reviewQueue = useReviewQueue();

  // Seed initial product into cache
  const seeded = useRef(false);
  useEffect(() => {
    if (!seeded.current) {
      cache.seed(initialProduct);
      // Warmup next products
      if (navigation) {
        cache.warmup(navigation.currentIndex, productIds);
      }
      seeded.current = true;
    }
  }, [initialProduct, cache, navigation, productIds]);

  // Build the navigation context for the current position
  const currentNav: ProductNavigationContext | undefined =
    navigation && totalCount > 1
      ? {
          ...navigation,
          prevProductId,
          nextProductId,
          currentIndex,
          totalCount,
        }
      : undefined;

  const handleNavigate = useCallback(
    async (targetProductId: string) => {
      const targetIndex = productIds.indexOf(targetProductId);
      if (targetIndex === -1) return;

      // Start crossfade transition
      setIsTransitioning(true);

      // Brief fade-out (50ms)
      await new Promise((r) => setTimeout(r, 50));

      // Try cache first, then fall back to single fetch
      let product: Product | null = null;
      const cached = cache.getFromCache(targetProductId);

      if (cached) {
        product = cached;
      } else {
        setIsLoadingNav(true);
        product = await cache.getProductCached(
          targetProductId,
          targetIndex,
          productIds
        );
        setIsLoadingNav(false);
      }

      if (product) {
        setCurrentProduct(product);
        setCurrentIndex(targetIndex);
        cache.seed(product); // ensure cache is touched

        // Warmup next products in background
        cache.warmup(targetIndex, productIds);

        // Update URL without full navigation for bookmarkability
        const url = `/products/${targetProductId}/edit?${navigation?.contextQueryString ?? ""}`;
        window.history.replaceState(null, "", url);
      }

      // Fade-in (100ms)
      await new Promise((r) => setTimeout(r, 30));
      setIsTransitioning(false);
    },
    [productIds, navigation?.contextQueryString, cache]
  );

  // Handle review submission (enqueue for background processing)
  const handleReviewSubmit = useCallback(
    (productId: string, reviewData: import("@/lib/actions/products").ReviewData) => {
      reviewQueue.enqueue(productId, reviewData, {
        onSuccess: () => cache.invalidate(productId), // invalidate only after confirmed
      });
      setReviewedInSession((prev) => prev + 1);
    },
    [reviewQueue, cache]
  );

  return (
    <div className="h-full relative">
      {/* Subtle loading indicator for cache misses only */}
      {isLoadingNav && (
        <div className="absolute top-0 left-0 right-0 z-50 h-0.5 bg-primary/20">
          <div className="h-full bg-primary animate-pulse" style={{ width: "60%" }} />
        </div>
      )}

      {/* Crossfade wrapper */}
      <div
        className="h-full transition-opacity duration-150 ease-in-out"
        style={{ opacity: isTransitioning ? 0 : 1 }}
      >
        <ProductEditor
          product={currentProduct}
          pageImageUrl={pageInfo?.imageUrl ?? null}
          pageWidth={pageInfo?.width ?? 2304}
          pageHeight={pageInfo?.height ?? 3508}
          navigation={currentNav}
          onNavigate={totalCount > 1 ? handleNavigate : undefined}
          onReviewSubmit={totalCount > 1 ? handleReviewSubmit : undefined}
          isLoadingNav={isLoadingNav}
          reviewedInSession={reviewedInSession}
        />
      </div>
    </div>
  );
}
