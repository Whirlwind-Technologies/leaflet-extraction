"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import type {
  ActionResult,
  AuthResponse,
  ConfirmUploadResponse,
  Leaflet,
  LeafletPage,
  LeafletProcessingStatus,
  LeafletUploadResponse,
  PaginatedResponse,
  PrepareUploadResponse,
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
      cookieStore.delete("access_token");
      cookieStore.delete("refresh_token");
      return null;
    }

    const data: AuthResponse = await response.json();

    cookieStore.set("access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 8,
      path: "/",
    });

    if (data.refresh_token) {
      cookieStore.set("refresh_token", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 30,
        path: "/",
      });
    }

    return data.access_token;
  } catch {
    return null;
  }
}

async function getAuthHeaders(): Promise<HeadersInit> {
  const cookieStore = await cookies();
  let token = cookieStore.get("access_token")?.value;

  if (!token) {
    token = await tryRefreshToken() ?? undefined;
  }

  return token ? { Authorization: `Bearer ${token}` } : {};
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

export async function uploadLeaflet(
  formData: FormData
): Promise<ActionResult<LeafletUploadResponse>> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      // Extract error message from various possible response formats
      const errorMessage =
        errorData.error?.details?.[0]?.message ||  // ValidationException format
        errorData.error?.message ||                 // APIException format
        errorData.detail ||                         // FastAPI default format
        "Upload failed";
      return {
        success: false,
        error: errorMessage,
      };
    }

    const data: LeafletUploadResponse = await response.json();
    revalidatePath("/dashboard");
    revalidatePath("/leaflets");

    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Upload error:", error);
    return {
      success: false,
      error: "An unexpected error occurred during upload",
    };
  }
}

/**
 * Prepare for direct upload to S3.
 * Returns a presigned URL for direct file upload.
 */
export async function prepareUpload(
  formData: FormData
): Promise<ActionResult<PrepareUploadResponse>> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/prepare-upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage =
        errorData.error?.details?.[0]?.message ||
        errorData.error?.message ||
        errorData.detail ||
        "Failed to prepare upload";
      return {
        success: false,
        error: errorMessage,
      };
    }

    const data: PrepareUploadResponse = await response.json();
    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Prepare upload error:", error);
    return {
      success: false,
      error: "An unexpected error occurred while preparing upload",
    };
  }
}

/**
 * Confirm that direct upload is complete and start processing.
 */
export async function confirmUpload(
  leafletId: string,
  autoProcess: boolean = true
): Promise<ActionResult<ConfirmUploadResponse>> {
  try {
    const formData = new FormData();
    formData.append("auto_process", autoProcess.toString());

    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/leaflets/confirm-upload/${leafletId}`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage =
        errorData.error?.details?.[0]?.message ||
        errorData.error?.message ||
        errorData.detail ||
        "Failed to confirm upload";
      return {
        success: false,
        error: errorMessage,
      };
    }

    const data: ConfirmUploadResponse = await response.json();
    revalidatePath("/dashboard");
    revalidatePath("/leaflets");

    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Confirm upload error:", error);
    return {
      success: false,
      error: "An unexpected error occurred while confirming upload",
    };
  }
}

export async function getLeaflets(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}): Promise<PaginatedResponse<Leaflet>> {
  const searchParams = new URLSearchParams();

  if (params?.page) searchParams.set("page", params.page.toString());
  if (params?.page_size) searchParams.set("page_size", params.page_size.toString());
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("search", params.search);

  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/leaflets?${searchParams.toString()}`,
    {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error("Failed to fetch leaflets");
  }

  return response.json();
}

export async function getLeaflet(id: string): Promise<Leaflet | null> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/${id}`, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

export async function getLeafletStatus(
  id: string
): Promise<LeafletProcessingStatus | null> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/${id}/status`, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

export async function getLeafletPages(id: string): Promise<LeafletPage[]> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/${id}/pages`, {
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    return response.json();
  } catch {
    return [];
  }
}

export async function reprocessLeaflet(id: string): Promise<ActionResult> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/leaflets/${id}/reprocess`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Reprocess failed",
      };
    }

    revalidatePath(`/leaflets/${id}`);
    revalidatePath("/dashboard");

    return {
      success: true,
    };
  } catch (error) {
    console.error("Reprocess error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

export async function deleteLeaflet(id: string): Promise<ActionResult> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/${id}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Delete failed",
      };
    }

    revalidatePath("/dashboard");
    revalidatePath("/leaflets");

    return {
      success: true,
    };
  } catch (error) {
    console.error("Delete error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

export async function updateLeaflet(
  id: string,
  data: {
    retailer?: string;
    country?: string;
    language?: string;
    currency?: string;
  }
): Promise<ActionResult<Leaflet>> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Update failed",
      };
    }

    const leaflet: Leaflet = await response.json();
    revalidatePath(`/leaflets/${id}`);

    return {
      success: true,
      data: leaflet,
    };
  } catch (error) {
    console.error("Update error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}


export interface BulkUploadResult {
  filename: string;
  success: boolean;
  leaflet_id: string | null;
  error: string | null;
  status: string | null;
}

export interface BulkUploadResponse {
  message: string;
  total: number;
  successful: number;
  failed: number;
  results: BulkUploadResult[];
}

export async function bulkUploadLeaflets(
  formData: FormData
): Promise<ActionResult<BulkUploadResponse>> {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/leaflets/upload/bulk`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Bulk upload failed",
      };
    }

    const data: BulkUploadResponse = await response.json();
    revalidatePath("/dashboard");
    revalidatePath("/leaflets");

    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Bulk upload error:", error);
    return {
      success: false,
      error: "An unexpected error occurred during bulk upload",
    };
  }
}


export type ImageStorageOption = "url" | "base64" | "none" | "both";

export async function exportLeaflet(
  leafletId: string,
  format: "json" | "csv",
  imageStorage: ImageStorageOption = "url"
): Promise<Response> {
  const params = new URLSearchParams({
    format,
    image_storage: imageStorage,
    include_product_codes: "true",
  });

  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/export/${leafletId}?${params.toString()}`,
    {
      method: "GET",
      cache: "no-store",
    }
  );

  return response;
}


export async function exportLeafletJson(
  leafletId: string,
  imageStorage: ImageStorageOption = "url"
): Promise<ActionResult<unknown>> {
  try {
    const response = await exportLeaflet(leafletId, "json", imageStorage);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Export failed",
      };
    }

    const data = await response.json();
    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Export error:", error);
    return {
      success: false,
      error: "An unexpected error occurred during export",
    };
  }
}

/**
 * Trigger product image extraction for a leaflet.
 * 
 * This extracts product images from page images using bounding boxes.
 * The leaflet must have products already extracted.
 * 
 * @param leafletId - The leaflet ID to process
 * @param force - If true, re-extracts all images even if they exist
 */
/**
 * Upload multiple images as a leaflet.
 *
 * Each image becomes a page in the leaflet, ordered by upload sequence.
 * Supported formats: JPEG, PNG, WEBP, TIFF, GIF, BMP
 */
export async function uploadImagesAsLeaflet(
  formData: FormData
): Promise<ActionResult<LeafletUploadResponse>> {
  try {
    const response = await fetchWithAuth(
      `${API_BASE_URL}/api/v1/leaflets/upload/images`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage =
        errorData.error?.details?.[0]?.message ||
        errorData.error?.message ||
        errorData.detail ||
        "Image upload failed";
      return {
        success: false,
        error: errorMessage,
      };
    }

    const data: LeafletUploadResponse = await response.json();
    revalidatePath("/dashboard");
    revalidatePath("/leaflets");

    return {
      success: true,
      data,
    };
  } catch (error) {
    console.error("Image upload error:", error);
    return {
      success: false,
      error: "An unexpected error occurred during image upload",
    };
  }
}

export async function extractProductImages(
  leafletId: string,
  force: boolean = false
): Promise<ActionResult<{ task_id: string; force: boolean }>> {
  try {
    const url = new URL(`${API_BASE_URL}/api/v1/leaflets/${leafletId}/extract-images`);
    if (force) {
      url.searchParams.set("force", "true");
    }

    const response = await fetchWithAuth(url.toString(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || "Failed to start image extraction",
      };
    }

    const data = await response.json();
    revalidatePath(`/leaflets/${leafletId}`);
    
    return {
      success: true,
      data: data.data,
    };
  } catch (error) {
    console.error("Image extraction error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}