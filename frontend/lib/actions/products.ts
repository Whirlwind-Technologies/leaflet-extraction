"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import type {
  Product,
  ActionResult,
  AuthResponse,
  ProductNavigationContext,
  ProductExportRequest,
  ExportPreviewResponse,
  ExportStatusResponse,
  ExportJobResponse,
} from "@/lib/types";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Refresh the access token using the refresh token.
 * Returns the new access token or null if refresh failed.
 */
async function tryRefreshToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      // Refresh token expired - clear cookies
      cookieStore.delete("access_token");
      cookieStore.delete("refresh_token");
      return null;
    }

    const data: AuthResponse = await response.json();

    // Update cookies with new tokens
    cookieStore.set("access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8, // 8 hours
      path: "/",
    });

    if (data.refresh_token) {
      cookieStore.set("refresh_token", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30, // 30 days
        path: "/",
      });
    }

    return data.access_token;
  } catch {
    return null;
  }
}

async function getAuthHeaders(): Promise<{ Authorization: string }> {
  const cookieStore = await cookies();
  let token = cookieStore.get("access_token")?.value;

  if (!token) {
    // Try to refresh the token
    token = await tryRefreshToken() ?? undefined;
    if (!token) {
      throw new Error("Not authenticated");
    }
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Make an authenticated API request with automatic token refresh on 401.
 */
async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const authHeaders = await getAuthHeaders();

  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers,
    },
  });

  // If 401, try to refresh token and retry once
  if (response.status === 401) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      return fetch(url, {
        ...options,
        headers: {
          Authorization: `Bearer ${newToken}`,
          ...options.headers,
        },
      });
    }
  }

  return response;
}

export interface ReviewData {
  action: "approved" | "rejected" | "corrected" | "needs_correction";
  corrections?: Record<string, unknown>;
  notes?: string;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  time_spent_seconds?: number;
}

export interface ProductStats {
  total: number;
  approved: number;
  auto_approved: number;
  pending: number;
  rejected: number;
  needs_correction: number;
}

export async function getProductStats(params?: {
  leafletId?: string;
}): Promise<ProductStats> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.leafletId) searchParams.set("leaflet_id", params.leafletId);

    const url = `${API_BASE_URL}/api/v1/products/stats?${searchParams.toString()}`;

    const response = await fetchWithAuth(url, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      console.error(`Failed to fetch product stats: ${response.status}`);
      return {
        total: 0,
        approved: 0,
        auto_approved: 0,
        pending: 0,
        rejected: 0,
        needs_correction: 0,
      };
    }

    return response.json();
  } catch (error) {
    console.error("Failed to fetch product stats:", error);
    return {
      total: 0,
      approved: 0,
      auto_approved: 0,
      pending: 0,
      rejected: 0,
      needs_correction: 0,
    };
  }
}

export async function getProducts(params?: {
  leafletId?: string;
  pageNumber?: number;
  reviewStatus?: string;
  category?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: string;
}): Promise<{ products: Product[]; total: number }> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.leafletId) searchParams.set("leaflet_id", params.leafletId);
    if (params?.pageNumber != null) searchParams.set("page_number", params.pageNumber.toString());
    if (params?.reviewStatus) searchParams.set("review_status", params.reviewStatus);
    if (params?.category) searchParams.set("category", params.category);
    if (params?.page != null) searchParams.set("page", params.page.toString());
    if (params?.pageSize != null) searchParams.set("page_size", params.pageSize.toString());
    if (params?.sortBy) searchParams.set("sort_by", params.sortBy);
    if (params?.sortOrder) searchParams.set("sort_order", params.sortOrder);

    const url = `${API_BASE_URL}/api/v1/products?${searchParams.toString()}`;

    const response = await fetchWithAuth(url, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error");
      console.error(`Failed to fetch products: ${response.status} - ${errorText}`);
      return { products: [], total: 0 };
    }
    
    const data = await response.json();

    return {
      products: data.items || [],
      total: data.total || 0,
    };
  } catch (error) {
    console.error("Failed to fetch products:", error);
    return { products: [], total: 0 };
  }
}

export async function getReviewQueue(params?: {
  leafletId?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ products: Product[]; total: number }> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.leafletId) searchParams.set("leaflet_id", params.leafletId);
    if (params?.page != null) searchParams.set("page", params.page.toString());
    if (params?.pageSize != null) searchParams.set("page_size", params.pageSize.toString());

    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/review-queue?${searchParams.toString()}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
      }
    );
    
    if (!response.ok) {
      return { products: [], total: 0 };
    }
    
    const data = await response.json();
    return {
      products: data.items || [],
      total: data.total || 0,
    };
  } catch (error) {
    console.error("Failed to fetch review queue:", error);
    return { products: [], total: 0 };
  }
}

export async function getProduct(productId: string): Promise<Product | null> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}`,
      {
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error");
      console.error(`Failed to fetch product ${productId}: ${response.status} - ${errorText}`);
      return null;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    // Handle "Not authenticated" error from getAuthHeaders
    if (error instanceof Error && error.message === "Not authenticated") {
      console.error("User not authenticated, redirect to login");
      return null;
    }
    console.error("Failed to fetch product:", error);
    return null;
  }
}

export async function reviewProduct(
  productId: string,
  reviewData: ReviewData
): Promise<ActionResult> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}/review`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(reviewData),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to submit review",
      };
    }

    // Revalidate all pages that might show this product
    revalidatePath("/leaflets", "layout");
    revalidatePath("/products", "layout");
    revalidatePath("/review", "layout");
    revalidatePath("/dashboard", "layout");

    return { success: true };
  } catch (error) {
    console.error("Failed to review product:", error);
    return {
      success: false,
      error: "An error occurred while submitting review",
    };
  }
}

export async function batchReviewProducts(
  productIds: string[],
  action: "approved" | "rejected",
  notes?: string
): Promise<ActionResult<{ processed: number; succeeded: number; failed: number }>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/batch-review`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          product_ids: productIds,
          action,
          notes,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to batch review",
      };
    }

    const data = await response.json();

    // Revalidate all pages that might show these products
    revalidatePath("/leaflets", "layout");
    revalidatePath("/products", "layout");
    revalidatePath("/review", "layout");
    revalidatePath("/dashboard", "layout");

    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Failed to batch review:", error);
    return {
      success: false,
      error: "An error occurred during batch review",
    };
  }
}

export async function updateProduct(
  productId: string,
  updates: Partial<Product>,
  options?: { skipReviewHistory?: boolean }
): Promise<ActionResult> {
  try {
    const body = {
      ...updates,
      ...(options?.skipReviewHistory && { skip_review_history: true }),
    };

    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to update product",
      };
    }

    // Revalidate all pages that might show this product
    revalidatePath("/leaflets", "layout");
    revalidatePath("/products", "layout");
    revalidatePath("/review", "layout");
    revalidatePath("/dashboard", "layout");

    return { success: true };
  } catch (error) {
    console.error("Failed to update product:", error);
    return {
      success: false,
      error: "An error occurred while updating product",
    };
  }
}

export async function triggerExtraction(leafletId: string): Promise<ActionResult> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/leaflets/${leafletId}/extract`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to trigger extraction",
      };
    }
    
    return { success: true };
  } catch (error) {
    console.error("Failed to trigger extraction:", error);
    return {
      success: false,
      error: "An error occurred while triggering extraction",
    };
  }
}

export interface ReExtractImageResult {
  image_url: string | null;
  image_base64: string | null;
  image_width: number | null;
  image_height: number | null;
  image_quality_score: number | null;
}

export async function reExtractProductImage(
  productId: string
): Promise<ActionResult<ReExtractImageResult>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}/re-extract-image`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to re-extract image",
      };
    }
    
    const responseData = await response.json();
    return { 
      success: true,
      data: {
        image_url: responseData.data?.image_url || null,
        image_base64: responseData.data?.image_base64 || null,
        image_width: responseData.data?.image_width || null,
        image_height: responseData.data?.image_height || null,
        image_quality_score: responseData.data?.image_quality_score || null,
      }
    };
  } catch (error) {
    console.error("Failed to re-extract image:", error);
    return {
      success: false,
      error: "An error occurred while re-extracting image",
    };
  }
}

export interface ProductReview {
  id: string;
  product_id: string;
  reviewer_id: string | null;
  action: string;
  previous_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  changed_fields: string[];
  notes: string | null;
  time_spent_seconds: number | null;
  created_at: string;
}

export async function getProductReviews(
  productId: string
): Promise<ProductReview[]> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}/reviews`,
      {
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
      }
    );
    
    if (!response.ok) {
      return [];
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch product reviews:", error);
    return [];
  }
}

export interface ExtractionClearResult {
  products_deleted: number;
  reviews_deleted: number;
  storage_files_deleted: number;
}

export async function clearExtractionData(
  leafletId: string
): Promise<ActionResult<ExtractionClearResult>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/leaflets/${leafletId}/extraction`,
      {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to clear extraction data",
      };
    }
    
    const data = await response.json();
    return {
      success: true,
      data: data.data,
    };
  } catch (error) {
    console.error("Failed to clear extraction data:", error);
    return {
      success: false,
      error: "An error occurred while clearing extraction data",
    };
  }
}

/**
 * Refresh the presigned URL for a product image.
 * 
 * This is useful when the presigned URL has expired.
 */
export async function refreshProductImageUrl(
  productId: string
): Promise<ActionResult<{ image_url: string; expires_in: number }>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}/refresh-image-url`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to refresh image URL",
      };
    }
    
    const data = await response.json();
    return {
      success: true,
      data: {
        image_url: data.image_url,
        expires_in: data.expires_in,
      },
    };
  } catch (error) {
    console.error("Failed to refresh image URL:", error);
    return {
      success: false,
      error: "An error occurred while refreshing image URL",
    };
  }
}

/**
 * Batch fetch multiple products by ID in a single request.
 * Used by the product cache to prefetch nearby products.
 */
export async function batchGetProducts(
  productIds: string[]
): Promise<Product[]> {
  if (productIds.length === 0) return [];

  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/batch`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ product_ids: productIds.slice(0, 20) }),
        cache: "no-store",
      }
    );

    if (!response.ok) {
      console.error(`Failed to batch fetch products: ${response.status}`);
      return [];
    }

    const data = await response.json();
    return data.products || [];
  } catch (error) {
    console.error("Failed to batch fetch products:", error);
    return [];
  }
}

/**
 * Review a product without triggering revalidatePath.
 * Used by the optimistic review queue to avoid UI disruption during review sessions.
 */
export async function reviewProductOptimistic(
  productId: string,
  reviewData: ReviewData
): Promise<ActionResult> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}/review`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(reviewData),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to submit review",
      };
    }

    // No revalidatePath — caller handles revalidation at session end
    return { success: true };
  } catch (error) {
    console.error("Failed to review product (optimistic):", error);
    return {
      success: false,
      error: "An error occurred while submitting review",
    };
  }
}

/**
 * Update a product without triggering revalidatePath.
 * Used during review sessions to avoid UI disruption.
 */
export async function updateProductOptimistic(
  productId: string,
  updates: Partial<Product>,
  options?: { skipReviewHistory?: boolean }
): Promise<ActionResult> {
  try {
    const body = {
      ...updates,
      ...(options?.skipReviewHistory && { skip_review_history: true }),
    };

    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/${productId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to update product",
      };
    }

    // No revalidatePath — caller handles revalidation at session end
    return { success: true };
  } catch (error) {
    console.error("Failed to update product (optimistic):", error);
    return {
      success: false,
      error: "An error occurred while updating product",
    };
  }
}

/**
 * Trigger revalidation of all product-related paths.
 * Called once when exiting a review session to sync UI.
 */
export async function revalidateProductPaths(): Promise<void> {
  revalidatePath("/leaflets", "layout");
  revalidatePath("/products", "layout");
  revalidatePath("/review", "layout");
  revalidatePath("/dashboard", "layout");
}

// ---------------------------------------------------------------------------
// Product Export Actions
// ---------------------------------------------------------------------------

/**
 * Preview an export to see how many products will be included.
 * Does NOT generate the file -- just returns counts and estimated size.
 */
export async function exportProductsPreview(
  request: ProductExportRequest
): Promise<ActionResult<ExportPreviewResponse>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/export/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to preview export",
      };
    }

    const data: ExportPreviewResponse = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Failed to preview export:", error);
    return {
      success: false,
      error: "An error occurred while previewing export",
    };
  }
}

/**
 * Trigger a product export.
 *
 * - For small exports (< 1000 products) the backend responds synchronously
 *   with status 200 and a downloadable file. We return `{ async: false }` and
 *   the caller should construct a download URL client-side.
 * - For large exports (>= 1000 products) the backend responds with status 202
 *   and a job payload. We return `{ async: true, exportId }` so the caller
 *   can poll for completion.
 */
export async function exportProducts(
  request: ProductExportRequest
): Promise<ActionResult<{ downloadUrl?: string; exportId?: string; async: boolean }>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }
    );

    if (response.status === 202) {
      // Async job created
      const data: ExportJobResponse = await response.json();
      return {
        success: true,
        data: { exportId: data.export_id, async: true },
      };
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to export products",
      };
    }

    // Synchronous export -- the response body is the file itself.
    // We cannot stream the file through a server action, so we return
    // a flag and the caller will trigger the download client-side by
    // opening the API URL directly.
    return {
      success: true,
      data: { async: false },
    };
  } catch (error) {
    console.error("Failed to export products:", error);
    return {
      success: false,
      error: "An error occurred while exporting products",
    };
  }
}

/**
 * Check the status of an asynchronous export job.
 */
export async function getExportStatus(
  exportId: string
): Promise<ActionResult<ExportStatusResponse>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/products/export/${exportId}/status`,
      {
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error: error.detail || "Failed to fetch export status",
      };
    }

    const data: ExportStatusResponse = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Failed to get export status:", error);
    return {
      success: false,
      error: "An error occurred while checking export status",
    };
  }
}

export async function getProductSiblings(params: {
  currentProductId: string;
  leafletId: string;
  reviewStatus?: string;
  pageNumber?: number;
}): Promise<ProductNavigationContext | null> {
  try {
    // Fetch products matching the context filters (capped at 100 by the server).
    // Use page_number asc so that for leaflets with >100 products the first
    // pages (most likely to be navigated) are included in the sibling list.
    const { products } = await getProducts({
      leafletId: params.leafletId,
      reviewStatus: params.reviewStatus,
      pageNumber: params.pageNumber,
      pageSize: 100,
      sortBy: "page_number",
      sortOrder: "asc",
    });

    if (products.length === 0) return null;

    // Sort by page_number asc, then bounding_box.y asc
    const sorted = [...products].sort((a, b) => {
      const pageDiff = a.page_number - b.page_number;
      if (pageDiff !== 0) return pageDiff;
      return (a.bounding_box?.y ?? 0) - (b.bounding_box?.y ?? 0);
    });

    const currentIndex = sorted.findIndex(p => p.id === params.currentProductId);
    if (currentIndex === -1) return null;

    // Build context query string for preserving navigation context
    const contextParams = new URLSearchParams();
    contextParams.set("leaflet_id", params.leafletId);
    if (params.reviewStatus) contextParams.set("status", params.reviewStatus);
    if (params.pageNumber != null) contextParams.set("page_number", params.pageNumber.toString());

    return {
      prevProductId: currentIndex > 0 ? sorted[currentIndex - 1].id : null,
      nextProductId: currentIndex < sorted.length - 1 ? sorted[currentIndex + 1].id : null,
      currentIndex,
      totalCount: sorted.length,
      contextQueryString: contextParams.toString(),
      productIds: sorted.map(p => p.id),
    };
  } catch (error) {
    console.error("Failed to get product siblings:", error);
    return null;
  }
}