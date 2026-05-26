"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  reviewProductOptimistic,
  revalidateProductPaths,
} from "@/lib/actions/products";
import type { ReviewData } from "@/lib/actions/products";
import { toast } from "sonner";

interface ReviewQueueItem {
  productId: string;
  reviewData: ReviewData;
  retries: number;
  onSuccess?: () => void;
}

const MAX_RETRIES = 2;

/**
 * Background review queue that processes reviews sequentially
 * without blocking navigation. Failed reviews are retried up to
 * MAX_RETRIES times, then surfaced via a toast.
 *
 * On unmount (leaving the review session), pending reviews are
 * flushed and revalidation is triggered.
 */
export function useReviewQueue() {
  const queue = useRef<ReviewQueueItem[]>([]);
  const processing = useRef(false);
  const reviewedCount = useRef(0);
  const mountedRef = useRef(true);

  // Use a ref for the enqueue function so processQueue can call it
  // without a circular dependency between useCallback hooks.
  const enqueueRef = useRef<(productId: string, reviewData: ReviewData) => void>(
    () => {}
  );

  const processQueue = useCallback(async () => {
    if (processing.current) return;
    processing.current = true;

    while (queue.current.length > 0) {
      const item = queue.current[0];

      const result = await reviewProductOptimistic(
        item.productId,
        item.reviewData
      );

      if (result.success) {
        queue.current.shift(); // Remove processed item
        reviewedCount.current += 1;
        item.onSuccess?.();
      } else {
        item.retries += 1;
        if (item.retries > MAX_RETRIES) {
          queue.current.shift(); // Give up on this item
          if (mountedRef.current) {
            const failedItem = item; // capture for closure
            toast.error(
              `Failed to submit review for product after ${MAX_RETRIES + 1} attempts`,
              {
                description: result.error,
                action: {
                  label: "Retry",
                  onClick: () =>
                    enqueueRef.current(failedItem.productId, failedItem.reviewData),
                },
                duration: 10000,
              }
            );
          }
        } else {
          // Wait before retrying
          await new Promise((r) => setTimeout(r, 1000 * item.retries));
        }
      }
    }

    processing.current = false;
  }, []);

  const enqueue = useCallback(
    (
      productId: string,
      reviewData: ReviewData,
      options?: { onSuccess?: () => void }
    ) => {
      queue.current.push({
        productId,
        reviewData,
        retries: 0,
        onSuccess: options?.onSuccess,
      });
      processQueue();
    },
    [processQueue]
  );

  // Keep the ref in sync with the latest enqueue callback
  useEffect(() => {
    enqueueRef.current = enqueue;
  }, [enqueue]);

  /** Flush remaining queue items and revalidate paths on session end. */
  const flush = useCallback(async () => {
    // Wait for current processing to finish
    while (processing.current) {
      await new Promise((r) => setTimeout(r, 100));
    }
    // Process any remaining items
    if (queue.current.length > 0) {
      await processQueue();
    }
    // Revalidate once at the end (only if still mounted or just unmounted)
    if (reviewedCount.current > 0) {
      try {
        await revalidateProductPaths();
      } catch (error) {
        console.error("Failed to revalidate paths on session end:", error);
      }
    }
  }, [processQueue]);

  const getReviewedCount = useCallback(() => reviewedCount.current, []);
  const getPendingCount = useCallback(() => queue.current.length, []);

  // Flush on unmount (leaving review session)
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Fire-and-forget flush + revalidation
      flush();
    };
  }, [flush]);

  return {
    enqueue,
    flush,
    getReviewedCount,
    getPendingCount,
  };
}
