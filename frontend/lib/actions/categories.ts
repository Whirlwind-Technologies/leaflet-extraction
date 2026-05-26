"use server";

import { cookies } from "next/headers";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function getAuthHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    throw new Error("Not authenticated");
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

export interface SystemCategory {
  id: string;
  name: string;
  description?: string;
  is_fallback: boolean;
  is_active: boolean;
  sort_order: number;
}

export interface SystemCategoriesResponse {
  categories: SystemCategory[];
  total: number;
  returned: number;
  has_more: boolean;
}

/**
 * Get system-defined product categories from the database.
 */
export async function getSystemCategories(params?: {
  search?: string;
  includeInactive?: boolean;
  fallbackOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<SystemCategoriesResponse> {
  try {
    const authHeaders = await getAuthHeaders();

    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set("search", params.search);
    if (params?.includeInactive) searchParams.set("include_inactive", "true");
    if (params?.fallbackOnly) searchParams.set("fallback_only", "true");
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.offset) searchParams.set("offset", params.offset.toString());

    const url = `${API_BASE_URL}/api/v1/categories?${searchParams.toString()}`;

    const response = await fetch(url, {
      headers: {
        ...authHeaders,
        "Content-Type": "application/json",
      },
      next: {
        revalidate: 300, // Cache for 5 minutes
      },
    });

    if (!response.ok) {
      console.error(`Failed to fetch system categories: ${response.status}`);
      return {
        categories: [],
        total: 0,
        returned: 0,
        has_more: false,
      };
    }

    return response.json();
  } catch (error) {
    console.error("Failed to fetch system categories:", error);
    return {
      categories: [],
      total: 0,
      returned: 0,
      has_more: false,
    };
  }
}

/**
 * Get all system categories (for dropdown).
 *
 * This fetches all categories at once for client-side filtering.
 */
export async function getAllSystemCategories(): Promise<SystemCategory[]> {
  try {
    const response = await getSystemCategories({
      limit: 500, // Get all categories
    });
    return response.categories;
  } catch (error) {
    console.error("Failed to fetch all system categories:", error);
    return [];
  }
}

/**
 * Search system categories by name or description.
 */
export async function searchSystemCategories(
  query: string,
  limit: number = 50
): Promise<SystemCategory[]> {
  try {
    const response = await getSystemCategories({
      search: query,
      limit,
    });
    return response.categories;
  } catch (error) {
    console.error("Failed to search categories:", error);
    return [];
  }
}
