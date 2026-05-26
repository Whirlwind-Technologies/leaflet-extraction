"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import type {
  ActionResult,
  Retailer,
  RetailerCreate,
  RetailerUpdate,
} from "@/lib/types";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Get all retailers for the current organization.
 */
export async function getRetailers(params?: {
  search?: string;
  is_active?: boolean;
}): Promise<Retailer[]> {
  const authHeaders = await getAuthHeaders();
  const searchParams = new URLSearchParams();

  if (params?.search) searchParams.set("search", params.search);
  if (params?.is_active !== undefined) {
    searchParams.set("is_active", params.is_active.toString());
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/retailers?${searchParams.toString()}`,
    {
      headers: {
        ...authHeaders,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    console.error("Failed to fetch retailers:", response.status);
    return [];
  }

  return response.json();
}

/**
 * Get a single retailer by ID.
 */
export async function getRetailer(id: string): Promise<Retailer | null> {
  try {
    const authHeaders = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/retailers/${id}`, {
      headers: {
        ...authHeaders,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch (error) {
    console.error("Get retailer error:", error);
    return null;
  }
}

/**
 * Create a new retailer.
 */
export async function createRetailer(
  data: RetailerCreate
): Promise<ActionResult<Retailer>> {
  try {
    const authHeaders = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/retailers`, {
      method: "POST",
      headers: {
        ...authHeaders,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || errorData.message || "Failed to create retailer",
      };
    }

    const retailer: Retailer = await response.json();
    revalidatePath("/retailers");
    revalidatePath("/upload");

    return {
      success: true,
      data: retailer,
    };
  } catch (error) {
    console.error("Create retailer error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

/**
 * Update an existing retailer.
 */
export async function updateRetailer(
  id: string,
  data: RetailerUpdate
): Promise<ActionResult<Retailer>> {
  try {
    const authHeaders = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/retailers/${id}`, {
      method: "PUT",
      headers: {
        ...authHeaders,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || errorData.message || "Failed to update retailer",
      };
    }

    const retailer: Retailer = await response.json();
    revalidatePath("/retailers");
    revalidatePath("/upload");

    return {
      success: true,
      data: retailer,
    };
  } catch (error) {
    console.error("Update retailer error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}

/**
 * Delete a retailer (soft delete by default).
 */
export async function deleteRetailer(
  id: string,
  hardDelete: boolean = false
): Promise<ActionResult> {
  try {
    const authHeaders = await getAuthHeaders();

    const url = new URL(`${API_BASE_URL}/api/v1/retailers/${id}`);
    if (hardDelete) {
      url.searchParams.set("hard_delete", "true");
    }

    const response = await fetch(url.toString(), {
      method: "DELETE",
      headers: authHeaders,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || errorData.message || "Failed to delete retailer",
      };
    }

    revalidatePath("/retailers");
    revalidatePath("/upload");

    return {
      success: true,
    };
  } catch (error) {
    console.error("Delete retailer error:", error);
    return {
      success: false,
      error: "An unexpected error occurred",
    };
  }
}
