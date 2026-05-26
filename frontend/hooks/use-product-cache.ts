"use client";

import { useCallback, useRef } from "react";
import { batchGetProducts, getProduct } from "@/lib/actions/products";
import type { Product } from "@/lib/types";

const MAX_CACHE_SIZE = 30;
const PREFETCH_WINDOW = 3;

/**
 * LRU product cache with sliding-window prefetch.
 *
 * Products are cached in a Map (insertion order = LRU order).
 * When the cache exceeds MAX_CACHE_SIZE, the oldest entries are evicted.
 * On navigation to index N, the next PREFETCH_WINDOW products are
 * batch-fetched in the background.
 */
export function useProductCache() {
  const cache = useRef<Map<string, Product>>(new Map());
  const inflight = useRef<Set<string>>(new Set());

  /** Move key to most-recent position and enforce max size. */
  const touch = useCallback((id: string, product: Product) => {
    const map = cache.current;
    map.delete(id); // remove old position
    map.set(id, product); // insert at end (most recent)

    // Evict oldest entries if over limit
    while (map.size > MAX_CACHE_SIZE) {
      const firstKey = map.keys().next().value;
      if (firstKey !== undefined) map.delete(firstKey);
    }
  }, []);

  /** Synchronous cache lookup. Returns null on miss. */
  const getFromCache = useCallback((id: string): Product | null => {
    const product = cache.current.get(id);
    if (product) {
      touch(id, product); // refresh LRU position
      return product;
    }
    return null;
  }, [touch]);

  /** Seed the cache with a product (e.g. the initial product from SSR). */
  const seed = useCallback((product: Product) => {
    touch(product.id, product);
  }, [touch]);

  /** Remove a product from the cache (e.g. after editing). */
  const invalidate = useCallback((id: string) => {
    cache.current.delete(id);
  }, []);

  /**
   * Batch prefetch products by ID.
   * Skips IDs that are already cached or in-flight.
   */
  const prefetch = useCallback(async (ids: string[]) => {
    const needed = ids.filter(
      (id) => !cache.current.has(id) && !inflight.current.has(id)
    );
    if (needed.length === 0) return;

    // Mark as in-flight to prevent duplicate fetches
    needed.forEach((id) => inflight.current.add(id));

    try {
      const products = await batchGetProducts(needed);
      for (const p of products) {
        touch(p.id, p);
        inflight.current.delete(p.id);
      }
    } catch {
      // Clear in-flight on error so retry is possible
      needed.forEach((id) => inflight.current.delete(id));
    }
  }, [touch]);

  /**
   * Sliding-window warmup: prefetch the next PREFETCH_WINDOW products
   * around the given index in the product ID list.
   */
  const warmup = useCallback(
    (currentIndex: number, allIds: string[]) => {
      const start = currentIndex + 1;
      const end = Math.min(start + PREFETCH_WINDOW, allIds.length);
      const window = allIds.slice(start, end);
      if (window.length > 0) {
        // Fire and forget — don't block navigation
        prefetch(window);
      }
    },
    [prefetch]
  );

  /**
   * Get a product, checking cache first, then falling back to single fetch.
   * Always warms up the sliding window after retrieval.
   */
  const getProductCached = useCallback(
    async (
      id: string,
      currentIndex: number,
      allIds: string[]
    ): Promise<Product | null> => {
      // 1. Check cache
      const cached = getFromCache(id);
      if (cached) {
        // Warm up in background
        warmup(currentIndex, allIds);
        return cached;
      }

      // 2. Cache miss — single fetch as fallback
      const product = await getProduct(id);
      if (product) {
        touch(product.id, product);
        // Warm up in background
        warmup(currentIndex, allIds);
      }
      return product;
    },
    [getFromCache, touch, warmup]
  );

  return {
    getFromCache,
    getProductCached,
    seed,
    invalidate,
    prefetch,
    warmup,
  };
}
