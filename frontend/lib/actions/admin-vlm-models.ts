"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

export interface ActionResult<T = void> {
  success: boolean;
  data?: T;
  error?: string;
}

// ===== TYPE DEFINITIONS =====

export interface VlmModel {
  id: string;
  provider_type: string;
  model_id: string;
  display_name: string;
  description?: string;
  max_tokens: number;
  context_window?: number;
  temperature_default: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  supports_vision: boolean;
  supports_tools: boolean;
  is_default: boolean;
  is_active: boolean;
  is_deprecated: boolean;
  deprecation_date?: string;
  replacement_model_id?: string;
  release_date?: string;
  capabilities?: Record<string, unknown>;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface VlmModelCreate {
  provider_type: string;
  model_id: string;
  display_name: string;
  description?: string;
  max_tokens?: number;
  context_window?: number;
  temperature_default?: number;
  input_cost_per_1m?: number;
  output_cost_per_1m?: number;
  supports_vision?: boolean;
  supports_tools?: boolean;
  is_default?: boolean;
  is_active?: boolean;
  sort_order?: number;
}

export interface VlmModelUpdate {
  display_name?: string;
  description?: string;
  max_tokens?: number;
  context_window?: number;
  temperature_default?: number;
  input_cost_per_1m?: number;
  output_cost_per_1m?: number;
  supports_vision?: boolean;
  supports_tools?: boolean;
  is_default?: boolean;
  is_active?: boolean;
  is_deprecated?: boolean;
  deprecation_date?: string;
  replacement_model_id?: string;
  sort_order?: number;
}

export interface VlmModelListResponse {
  items: VlmModel[];
  total: number;
}

// ===== HELPER FUNCTIONS =====

async function getAuthHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    throw new Error("Not authenticated");
  }

  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

// ===== API FUNCTIONS =====

export async function getVlmModels(params?: {
  provider_type?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<VlmModelListResponse>> {
  try {
    const headers = await getAuthHeaders();

    const queryParams = new URLSearchParams();
    if (params?.provider_type) queryParams.set("provider_type", params.provider_type);
    if (params?.is_active !== undefined) queryParams.set("is_active", String(params.is_active));
    if (params?.page) queryParams.set("page", String(params.page));
    if (params?.page_size) queryParams.set("page_size", String(params.page_size));

    const url = `${API_BASE_URL}/api/v1/admin/vlm-models/?${queryParams.toString()}`;

    const response = await fetch(url, {
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to load VLM models" };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Failed to fetch VLM models:", error);
    return { success: false, error: "An error occurred while loading models" };
  }
}

export async function getVlmModel(id: string): Promise<ActionResult<VlmModel>> {
  try {
    const headers = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/admin/vlm-models/${id}`, {
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to load VLM model" };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Failed to fetch VLM model:", error);
    return { success: false, error: "An error occurred while loading model" };
  }
}

export async function createVlmModel(
  modelData: VlmModelCreate
): Promise<ActionResult<VlmModel>> {
  try {
    const headers = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/admin/vlm-models/`, {
      method: "POST",
      headers,
      body: JSON.stringify(modelData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to create VLM model" };
    }

    const data = await response.json();

    revalidatePath("/admin/vlm-models");
    revalidatePath("/settings");

    return { success: true, data };
  } catch (error) {
    console.error("Failed to create VLM model:", error);
    return { success: false, error: "An error occurred while creating model" };
  }
}

export async function updateVlmModel(
  id: string,
  modelData: VlmModelUpdate
): Promise<ActionResult<VlmModel>> {
  try {
    const headers = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/admin/vlm-models/${id}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify(modelData),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to update VLM model" };
    }

    const data = await response.json();

    revalidatePath("/admin/vlm-models");
    revalidatePath("/settings");

    return { success: true, data };
  } catch (error) {
    console.error("Failed to update VLM model:", error);
    return { success: false, error: "An error occurred while updating model" };
  }
}

export async function deleteVlmModel(id: string): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/admin/vlm-models/${id}`, {
      method: "DELETE",
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to delete VLM model" };
    }

    revalidatePath("/admin/vlm-models");
    revalidatePath("/settings");

    return { success: true };
  } catch (error) {
    console.error("Failed to delete VLM model:", error);
    return { success: false, error: "An error occurred while deleting model" };
  }
}

export async function setDefaultVlmModel(id: string): Promise<ActionResult<VlmModel>> {
  try {
    const headers = await getAuthHeaders();

    const response = await fetch(`${API_BASE_URL}/api/v1/admin/vlm-models/${id}/set-default`, {
      method: "POST",
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to set default model" };
    }

    const data = await response.json();

    revalidatePath("/admin/vlm-models");
    revalidatePath("/settings");

    return { success: true, data };
  } catch (error) {
    console.error("Failed to set default VLM model:", error);
    return { success: false, error: "An error occurred while setting default model" };
  }
}

export async function deprecateVlmModel(
  id: string,
  replacementModelId?: string
): Promise<ActionResult<VlmModel>> {
  try {
    const headers = await getAuthHeaders();

    const queryParams = new URLSearchParams();
    if (replacementModelId) {
      queryParams.set("replacement_model_id", replacementModelId);
    }

    const url = `${API_BASE_URL}/api/v1/admin/vlm-models/${id}/deprecate?${queryParams.toString()}`;

    const response = await fetch(url, {
      method: "POST",
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to deprecate model" };
    }

    const data = await response.json();

    revalidatePath("/admin/vlm-models");
    revalidatePath("/settings");

    return { success: true, data };
  } catch (error) {
    console.error("Failed to deprecate VLM model:", error);
    return { success: false, error: "An error occurred while deprecating model" };
  }
}
