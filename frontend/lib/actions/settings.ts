"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

export interface ActionResult<T = void> {
  success: boolean;
  data?: T;
  error?: string;
}

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

// ============== VLM STATUS ==============

export interface PlatformFallbackInfo {
  provider_name: string;
  provider_type: string;
  model_name: string;
  is_healthy: boolean;
  is_available: boolean;
  last_used?: string | null;
  usage_cost_current_month?: number | null;
}

export interface VlmStatus {
  has_active_provider: boolean;
  has_fallback: boolean;
  can_extract: boolean;
  default_provider: string | null;
  provider_count: number;
  active_count: number;
  message: string;
  platform_fallback?: PlatformFallbackInfo | null;
}

export async function getVlmStatus(): Promise<VlmStatus> {
  try {
    const headers = await getAuthHeaders();
    // Add cache-busting timestamp to prevent any caching
    const timestamp = Date.now();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/vlm-providers/status?_t=${timestamp}`,
      {
        headers,
        cache: "no-store",
        next: { revalidate: 0 },
      }
    );
    
    if (!response.ok) {
      console.error("VLM status request failed:", response.status, response.statusText);
      return {
        has_active_provider: false,
        has_fallback: false,
        can_extract: false,
        default_provider: null,
        provider_count: 0,
        active_count: 0,
        message: "Unable to check provider status",
      };
    }
    
    const data = await response.json();
    console.log("VLM status response:", data);
    return data;
  } catch (error) {
    console.error("Failed to fetch VLM status:", error);
    return {
      has_active_provider: false,
      has_fallback: false,
      can_extract: false,
      default_provider: null,
      provider_count: 0,
      active_count: 0,
      message: "Unable to check provider status",
    };
  }
}

// ============== ERROR EXTRACTION HELPER ==============

interface FastApiValidationError {
  msg: string;
  loc?: (string | number)[];
  type?: string;
}

/**
 * Extracts a human-readable error message from various backend error response formats.
 *
 * Handles:
 * - FastAPI 422 validation errors: { detail: [{ msg, loc, type }] }
 * - Custom app errors (400, 409, 500): { error: { code, message, details } }
 * - Simple string detail: { detail: "some message" }
 * - Plain message field: { message: "some message" }
 */
function extractErrorMessage(
  status: number,
  errorData: Record<string, unknown>,
  fallbackMessage: string
): string {
  // FastAPI validation errors (422): detail is an array
  if (status === 422 && Array.isArray(errorData.detail)) {
    const details = errorData.detail as FastApiValidationError[];
    const fieldErrors = details
      .map((e) => {
        const field = e.loc?.slice(-1)[0] ?? "unknown";
        return `${field}: ${e.msg}`;
      })
      .join(", ");
    return fieldErrors || "Validation error";
  }

  // Custom app errors: { error: { message: "..." } }
  const appError = errorData.error;
  if (
    appError &&
    typeof appError === "object" &&
    !Array.isArray(appError) &&
    "message" in (appError as Record<string, unknown>)
  ) {
    const msg = (appError as Record<string, unknown>).message;
    if (typeof msg === "string" && msg.length > 0) {
      return msg;
    }
  }

  // Simple string detail
  if (typeof errorData.detail === "string" && errorData.detail.length > 0) {
    return errorData.detail;
  }

  // Plain message field
  if (typeof errorData.message === "string" && errorData.message.length > 0) {
    return errorData.message;
  }

  return `${fallbackMessage} (${status})`;
}

// ============== VLM PROVIDERS ==============

export interface VlmProvider {
  id: string;
  provider_type: string;
  name: string;
  provider_display_name: string;
  model_name: string;
  max_tokens: number;
  temperature: number;
  api_endpoint?: string | null;
  is_default: boolean;
  is_active: boolean;
  monthly_budget: number | null;
  total_spent: number;
  current_month_spent: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  last_used_at: string | null;
  masked_api_key: string;
  created_at: string;
}

export interface CreateVlmProviderData {
  provider_type: string;
  name: string;
  api_key: string;
  model_name: string;
  api_endpoint?: string;
  monthly_budget?: number;
  config?: Record<string, unknown>;
}

export async function getVlmProviders(): Promise<VlmProvider[]> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/`, {
      headers,
      cache: "no-store",
    });
    
    if (!response.ok) {
      return [];
    }
    
    const data = await response.json();
    return data.items || data || [];
  } catch (error) {
    console.error("Failed to fetch VLM providers:", error);
    return [];
  }
}

export async function createVlmProvider(
  data: CreateVlmProviderData
): Promise<ActionResult<VlmProvider>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/`, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to create provider"),
      };
    }

    const provider = await response.json();
    revalidatePath("/settings");
    revalidatePath("/dashboard");
    revalidatePath("/upload");
    return { success: true, data: provider };
  } catch (error) {
    console.error("Failed to create VLM provider:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function updateVlmProvider(
  providerId: string,
  data: Partial<CreateVlmProviderData>
): Promise<ActionResult<VlmProvider>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/${providerId}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to update provider"),
      };
    }

    const provider = await response.json();
    revalidatePath("/settings");
    revalidatePath("/dashboard");
    revalidatePath("/upload");
    return { success: true, data: provider };
  } catch (error) {
    console.error("Failed to update VLM provider:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function deleteVlmProvider(providerId: string): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/${providerId}`, {
      method: "DELETE",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to delete provider"),
      };
    }

    revalidatePath("/settings");
    revalidatePath("/dashboard");
    revalidatePath("/upload");
    return { success: true };
  } catch (error) {
    console.error("Failed to delete VLM provider:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function setDefaultVlmProvider(providerId: string): Promise<ActionResult> {
  // Uses PUT method to match backend endpoint
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/${providerId}/default`, {
      method: "PUT",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to set default"),
      };
    }

    revalidatePath("/settings");
    revalidatePath("/dashboard");
    revalidatePath("/upload");
    return { success: true };
  } catch (error) {
    console.error("Failed to set default provider:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function testVlmProvider(
  providerId: string
): Promise<ActionResult<{ success: boolean; message: string }>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/${providerId}/test`, {
      method: "POST",
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to test provider"),
      };
    }

    const data = await response.json();
    return { success: data.success, data };
  } catch (error) {
    console.error("Failed to test provider:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

// ============== API KEYS ==============

export interface ApiKey {
  id: string;
  name: string;
  description?: string;
  key_prefix: string;
  scopes: string[];
  rate_limit: number;
  daily_limit: number | null;
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  total_requests: number;
  requests_today: number;
  created_at: string;
}

export interface CreateApiKeyData {
  name: string;
  description?: string;
  scopes: string[];
  rate_limit?: number;
  daily_limit?: number;
  expires_in_days?: number;
}

export async function getApiKeys(): Promise<ApiKey[]> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/api-keys/`, {
      headers,
      cache: "no-store",
    });
    
    if (!response.ok) {
      return [];
    }
    
    const data = await response.json();
    return data.items || data || [];
  } catch (error) {
    console.error("Failed to fetch API keys:", error);
    return [];
  }
}

export async function createApiKey(
  data: CreateApiKeyData
): Promise<ActionResult<{ api_key: ApiKey; plain_key: string }>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/api-keys/`, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to create API key"),
      };
    }
    
    const result = await response.json();
    
    // Transform backend response to match frontend expected format
    // Backend returns: { id, name, key, key_prefix, scopes, rate_limit, expires_at, message }
    // Frontend expects: { api_key: ApiKey, plain_key: string }
    const apiKey: ApiKey = {
      id: result.id,
      name: result.name,
      description: result.description || undefined,
      key_prefix: result.key_prefix,
      scopes: result.scopes,
      rate_limit: result.rate_limit,
      daily_limit: result.daily_limit || null,
      is_active: true, // Newly created keys are always active
      expires_at: result.expires_at,
      last_used_at: null,
      total_requests: 0,
      requests_today: 0,
      created_at: new Date().toISOString(),
    };
    
    revalidatePath("/settings");
    return { 
      success: true, 
      data: {
        api_key: apiKey,
        plain_key: result.key, // The backend returns the plain key as 'key'
      }
    };
  } catch (error) {
    console.error("Failed to create API key:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function revokeApiKey(keyId: string): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/api-keys/${keyId}`, {
      method: "DELETE",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to revoke API key"),
      };
    }

    revalidatePath("/settings");
    return { success: true };
  } catch (error) {
    console.error("Failed to revoke API key:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function regenerateApiKey(
  keyId: string
): Promise<ActionResult<{ plain_key: string }>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/api-keys/${keyId}/regenerate`, {
      method: "POST",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to regenerate API key"),
      };
    }

    const result = await response.json();
    revalidatePath("/settings");
    return { success: true, data: result };
  } catch (error) {
    console.error("Failed to regenerate API key:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

// ============== WEBHOOKS ==============

export interface Webhook {
  id: string;
  name: string;
  description?: string;
  url: string;
  events: string[];
  is_active: boolean;
  last_triggered_at: string | null;
  last_error: string | null;
  failure_count: number;
  total_deliveries: number;
  total_failures: number;
  created_at: string;
}

export interface WebhookDelivery {
  id: string;
  event_type: string;
  status_code: number | null;
  success: boolean;
  response_time_ms: number | null;
  error_message: string | null;
  created_at: string;
}

export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
  page: number;
  pages: number;
}

export interface CreateWebhookData {
  name: string;
  description?: string;
  url: string;
  events: string[];
}

export async function getWebhooks(): Promise<Webhook[]> {
  const headers = await getAuthHeaders();
  // Always include inactive webhooks so toggled-off ones remain visible
  const response = await fetch(
    `${API_BASE_URL}/api/v1/webhooks/?include_inactive=true`,
    {
      headers,
      cache: "no-store",
    }
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = extractErrorMessage(
      response.status,
      errorData,
      "Failed to fetch webhooks"
    );
    throw new Error(msg);
  }

  const data = await response.json();
  return Array.isArray(data) ? data : data.items || [];
}

export async function createWebhook(
  data: CreateWebhookData
): Promise<ActionResult<{ webhook: Webhook; secret: string }>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/webhooks/`, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(
          response.status,
          errorData,
          "Failed to create webhook"
        ),
      };
    }

    // Backend returns { webhook: WebhookResponse, secret: string }
    const result = await response.json();
    revalidatePath("/settings");
    return {
      success: true,
      data: {
        webhook: result.webhook,
        secret: result.secret,
      },
    };
  } catch (error) {
    console.error("Failed to create webhook:", error);
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function updateWebhook(
  webhookId: string,
  data: Partial<CreateWebhookData> & { is_active?: boolean }
): Promise<ActionResult<Webhook>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/webhooks/${webhookId}`,
      {
        method: "PATCH",
        headers,
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(
          response.status,
          errorData,
          "Failed to update webhook"
        ),
      };
    }

    const webhook = await response.json();
    revalidatePath("/settings");
    return { success: true, data: webhook };
  } catch (error) {
    console.error("Failed to update webhook:", error);
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function deleteWebhook(webhookId: string): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/webhooks/${webhookId}`, {
      method: "DELETE",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to delete webhook"),
      };
    }

    revalidatePath("/settings");
    return { success: true };
  } catch (error) {
    console.error("Failed to delete webhook:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function testWebhook(
  webhookId: string
): Promise<ActionResult<{ success: boolean; message: string }>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/webhooks/${webhookId}/test`,
      {
        method: "POST",
        headers,
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(
          response.status,
          errorData,
          "Failed to test webhook"
        ),
      };
    }

    // Backend returns { success, status_code, response_time_ms, error }
    const data = await response.json();
    const message = data.success
      ? `Test webhook delivered successfully (${data.status_code}, ${data.response_time_ms}ms)`
      : `Test failed: ${data.error || "Unknown error"}`;
    return {
      success: data.success,
      data: { success: data.success, message },
    };
  } catch (error) {
    console.error("Failed to test webhook:", error);
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function getWebhookDeliveries(
  webhookId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<WebhookDeliveryListResponse> {
  const empty: WebhookDeliveryListResponse = {
    deliveries: [],
    total: 0,
    page: 1,
    pages: 1,
  };
  try {
    const headers = await getAuthHeaders();
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    const response = await fetch(
      `${API_BASE_URL}/api/v1/webhooks/${webhookId}/deliveries?${params.toString()}`,
      { headers, cache: "no-store" }
    );

    if (!response.ok) {
      return empty;
    }

    // Backend returns { deliveries: [...], total, page, pages }
    const data = await response.json();
    return {
      deliveries: data.deliveries ?? [],
      total: data.total ?? 0,
      page: data.page ?? 1,
      pages: data.pages ?? 1,
    };
  } catch (error) {
    console.error("Failed to fetch webhook deliveries:", error);
    return empty;
  }
}

// ============== ACCOUNT ==============

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  company?: string;
  is_active: boolean;
  is_verified: boolean;
  is_superuser?: boolean;
  created_at: string;
  last_login?: string | null;
  login_count?: number;
}

export async function getUserProfile(): Promise<UserProfile | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
      headers,
      cache: "no-store",
    });
    
    if (!response.ok) {
      return null;
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch user profile:", error);
    return null;
  }
}

export interface UserStats {
  total_leaflets: number;
  total_products: number;
  completed_leaflets: number;
  pending_reviews: number;
}

export async function getUserStats(): Promise<UserStats> {
  const empty: UserStats = {
    total_leaflets: 0,
    total_products: 0,
    completed_leaflets: 0,
    pending_reviews: 0,
  };
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/stats`, {
      headers,
      cache: "no-store",
    });
    if (!response.ok) return empty;
    return response.json();
  } catch (error) {
    console.error("Failed to fetch user stats:", error);
    return empty;
  }
}

export async function updateUserProfile(
  data: { full_name?: string; company?: string }
): Promise<ActionResult<UserProfile>> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
      method: "PUT",
      headers,
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to update profile"),
      };
    }

    const profile = await response.json();
    revalidatePath("/settings");
    return { success: true, data: profile };
  } catch (error) {
    console.error("Failed to update profile:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/password`, {
      method: "PUT",
      headers,
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to change password"),
      };
    }

    return { success: true };
  } catch (error) {
    console.error("Failed to change password:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

export async function deleteAccount(): Promise<ActionResult> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
      method: "DELETE",
      headers,
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: extractErrorMessage(response.status, errorData, "Failed to delete account"),
      };
    }

    return { success: true };
  } catch (error) {
    console.error("Failed to delete account:", error);
    const message = error instanceof Error ? error.message : "An unexpected error occurred";
    return { success: false, error: message };
  }
}

// ============== PROVIDER TYPES ==============

export interface VlmModelInfo {
  model_id: string;
  display_name: string;
  description?: string;
  max_tokens: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  is_default: boolean;
  is_deprecated: boolean;
  replacement_model_id?: string;
  supports_vision?: boolean;
}

export interface ProviderTypeInfo {
  type: string;
  display_name: string;
  default_model: string;
  default_max_tokens: number;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  requires_endpoint: boolean;
  models: VlmModelInfo[];
}

export async function getProviderTypes(): Promise<ProviderTypeInfo[]> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/v1/vlm-providers/types`, {
      headers,
      cache: "no-store",
    });

    if (!response.ok) {
      console.error("Provider types request failed:", response.status);
      return [];
    }

    return await response.json();
  } catch (error) {
    console.error("Failed to fetch provider types:", error);
    return [];
  }
}

// ============== USAGE STATS ==============

export interface UsageStats {
  total_leaflets: number;
  total_products: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  this_month_leaflets: number;
  this_month_cost: number;
  average_tokens_per_page: number;
  provider_breakdown: Array<{
    name: string;
    provider_type: string;
    total_requests: number;
    total_tokens: number;
    total_spent: number;
    current_month_spent: number;
  }>;
}

export async function getUsageStats(): Promise<UsageStats | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/vlm-providers/usage/stats`,
      {
        headers,
        cache: "no-store",
      }
    );
    
    if (!response.ok) {
      console.error("Usage stats request failed:", response.status);
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch usage stats:", error);
    return null;
  }
}

// ============== USAGE COSTS (DATE RANGE) ==============

export type CostPeriod =
  | "last_7_days"
  | "last_30_days"
  | "this_month"
  | "last_month"
  | "this_year"
  | "all_time"
  | "custom";

export type CostGroupBy = "day" | "week" | "month";

export interface CostPeriodInfo {
  start_date: string;
  end_date: string;
  period_type: CostPeriod;
  label: string;
}

export interface CostSummary {
  total_cost: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  leaflets_processed: number;
  pages_processed: number;
  products_extracted: number;
  avg_cost_per_leaflet: number;
  avg_cost_per_request: number;
}

export interface CostByProvider {
  provider_id: string | null;
  provider_name: string;
  provider_type: string;
  cost: number;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  tokens: number;
  percentage_of_total: number;
}

export interface CostBreakdownPoint {
  date: string;
  cost: number;
  requests: number;
  tokens: number;
  leaflets: number;
}

export interface VLMCostResponse {
  period: CostPeriodInfo;
  summary: CostSummary;
  by_provider: CostByProvider[];
  daily_breakdown: CostBreakdownPoint[];
}

export async function getUsageCosts(
  period: CostPeriod = "this_month",
  groupBy: CostGroupBy = "day",
  startDate?: string,
  endDate?: string
): Promise<VLMCostResponse | null> {
  try {
    const headers = await getAuthHeaders();
    const params = new URLSearchParams({ period, group_by: groupBy });
    if (period === "custom" && startDate) params.set("start_date", startDate);
    if (period === "custom" && endDate) params.set("end_date", endDate);

    const response = await fetch(
      `${API_BASE_URL}/api/v1/vlm-providers/usage/costs?${params.toString()}`,
      { headers, cache: "no-store" }
    );

    if (!response.ok) {
      console.error("Usage costs request failed:", response.status);
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error("Failed to fetch usage costs:", error);
    return null;
  }
}

// ============== PLATFORM QUOTA ==============

export interface PlatformQuota {
  limit: number;
  used: number;
  remaining: number | null;
  has_own_provider: boolean;
  is_unlimited: boolean;
}

export async function getPlatformQuota(): Promise<PlatformQuota | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/organizations/current/platform-quota`,
      { headers, cache: "no-store" }
    );
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error("Failed to fetch platform quota:", error);
    return null;
  }
}