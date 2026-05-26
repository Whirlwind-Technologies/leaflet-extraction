"use server";

import { cookies } from "next/headers";
import { ActionResult, PaginatedResponse } from "@/lib/types";
import { z } from "zod";

// ===== TYPE DEFINITIONS =====

export type PlatformVLMProviderType = "anthropic" | "openai" | "google" | "azure_openai" | "aws_bedrock" | "custom";

export interface PlatformProvider {
  id: string;
  name: string;
  provider_type: PlatformVLMProviderType;
  provider_display_name: string;
  model_name: string;
  max_tokens: number;
  temperature: number;
  priority: number;
  is_active: boolean;
  is_default: boolean;
  monthly_budget?: number;
  total_spent: number;
  current_month_spent: number;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  last_used_at: string | null;
  masked_api_key: string;
  api_endpoint?: string;
  created_at: string;
  updated_at?: string;
}

export interface UsageReport {
  id: string;
  organization_id: string;
  organization_name: string;
  platform_provider_id: string;
  platform_provider_name: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  average_response_time: number;
  success_rate: number;
  created_at: string;
}

export interface BudgetAlert {
  id: string;
  organization_id?: string;
  organization_name?: string;
  provider_id?: string;
  provider_name?: string;
  alert_type: "budget_threshold" | "provider_failure" | "cost_anomaly";
  threshold_percentage: number;
  current_usage: number;
  budget_limit?: number;
  is_active: boolean;
  notification_channels: string[];
  email_recipients?: string[];
  webhook_url?: string;
  slack_webhook?: string;
  cooldown_minutes: number;
  last_triggered_at?: string;
  trigger_count: number;
  created_at: string;
  updated_at: string;
  created_by?: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  user_id?: string;
  username?: string;
  organization_id?: string;
  organization_name?: string;
  event_type: "vlm_request" | "provider_change" | "budget_alert" | "admin_action" | "system_event";
  resource_type: string;
  resource_id?: string;
  action: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  cost?: number;
  success: boolean;
  error_message?: string;
}

export interface SystemNotification {
  id: string;
  title: string;
  message: string;
  notification_type: "info" | "warning" | "error" | "success";
  severity: "low" | "medium" | "high" | "critical";
  target_type: "all_users" | "organization" | "user" | "role";
  target_id?: string;
  is_read: boolean;
  created_at: string;
  expires_at?: string;
}

// ===== VALIDATION SCHEMAS =====

const CreateProviderSchema = z.object({
  name: z.string().min(1, "Name is required").max(255),
  provider_type: z.enum(["anthropic", "openai", "google", "azure_openai", "aws_bedrock", "custom"]),
  model_name: z.string().min(1, "Model name is required"),
  api_key: z.string().min(1, "API key is required"),
  priority: z.number().min(1).max(999),
  monthly_budget: z.number().positive().optional().nullable(),
  api_endpoint: z.string().url().optional().nullable(),
  region: z.string().optional().nullable(),
  metadata: z.record(z.string(), z.unknown()).optional().nullable(),
});

// For updates, we need a schema that allows optional fields without the min(1) constraints
const UpdateProviderSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1, "Name is required").max(255).optional(),
  provider_type: z.enum(["anthropic", "openai", "google", "azure_openai", "aws_bedrock", "custom"]).optional(),
  model_name: z.string().min(1, "Model name is required").optional(),
  api_key: z.string().min(1, "API key is required").optional(),
  priority: z.number().min(1).max(999).optional(),
  monthly_budget: z.number().positive().optional().nullable(),
  api_endpoint: z.string().url().optional().nullable(),
  region: z.string().optional().nullable(),
  metadata: z.record(z.string(), z.unknown()).optional().nullable(),
});

const UsageFiltersSchema = z.object({
  organization_id: z.string().uuid().optional(),
  provider_id: z.string().uuid().optional(),
  start_date: z.string().optional(),  // Accept any date string format
  end_date: z.string().optional(),    // Accept any date string format
  skip: z.number().min(0).optional(),
  limit: z.number().min(1).max(1000).optional(),
});

const BudgetAlertSchema = z.object({
  platform_provider_id: z.string().uuid(),
  organization_id: z.string().uuid().optional().nullable(),
  alert_type: z.enum(["warning", "critical", "exhausted", "rate_limit"]),
  threshold_percentage: z.number().min(1).max(100),
  period: z.enum(["daily", "monthly", "hourly"]).optional().default("monthly"),
  is_active: z.boolean().optional().default(true),
  // Notification settings
  notify_super_admins: z.boolean().optional().default(true),
  notify_org_admins: z.boolean().optional().default(false),
  email_recipients: z.array(z.string()).optional().default([]),
  webhook_url: z.string().url().optional().nullable(),
  slack_webhook_url: z.string().url().optional().nullable(),
  // Rate limiting
  cooldown_minutes: z.number().min(1).optional().default(60),
  max_triggers_per_day: z.number().min(1).optional().default(10),
  custom_message: z.string().optional().nullable(),
});

const AuditFiltersSchema = z.object({
  user_id: z.string().uuid().optional(),
  organization_id: z.string().uuid().optional(),
  event_type: z.enum(["vlm_request", "provider_change", "budget_alert", "admin_action", "system_event"]).optional(),
  start_date: z.string().datetime().optional(),
  end_date: z.string().datetime().optional(),
  search: z.string().optional(),
  skip: z.number().min(0).optional(),
  limit: z.number().min(1).max(1000).optional(),
});

// ===== HELPER FUNCTIONS =====

const API_BASE_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ActionResult<T>> {
  try {
    const authHeaders = await getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...options.headers,
      },
      ...options,
    });

    // Handle 204 No Content responses (e.g., DELETE operations)
    if (response.status === 204) {
      return {
        success: true,
        data: undefined as T,
      };
    }

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.detail || `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    return {
      success: true,
      data,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Network error occurred",
    };
  }
}

// ===== WORKING ADMIN ACTIONS (Using existing backend endpoints) =====

export async function getSystemStats(): Promise<ActionResult<SystemStats>> {
  return apiRequest<SystemStats>("/api/v1/admin/stats");
}

export async function getUsers(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  organization_id?: string;
}): Promise<ActionResult<UserResponse[]>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", String(params.page));
  if (params?.page_size) searchParams.append("page_size", String(params.page_size));
  if (params?.search) searchParams.append("search", params.search);
  if (params?.is_active !== undefined) searchParams.append("is_active", String(params.is_active));
  if (params?.is_superuser !== undefined) searchParams.append("is_superuser", String(params.is_superuser));
  if (params?.organization_id) searchParams.append("organization_id", params.organization_id);

  const queryString = searchParams.toString();
  const endpoint = `/api/v1/admin/users${queryString ? `?${queryString}` : ""}`;

  return apiRequest<UserResponse[]>(endpoint);
}

export async function getAllOrganizations(): Promise<ActionResult<OrganizationInfo[]>> {
  return apiRequest<OrganizationInfo[]>("/api/v1/admin/users/organizations");
}

export async function getUser(userId: string): Promise<ActionResult<UserResponse>> {
  return apiRequest<UserResponse>(`/api/v1/admin/users/${userId}`);
}

export async function createUser(data: UserCreate): Promise<ActionResult<UserResponse>> {
  return apiRequest<UserResponse>("/api/v1/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(userId: string, data: UserUpdate): Promise<ActionResult<UserResponse>> {
  return apiRequest<UserResponse>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteUser(userId: string): Promise<ActionResult<void>> {
  return apiRequest<void>(`/api/v1/admin/users/${userId}`, {
    method: "DELETE",
  });
}

export async function toggleUserActive(userId: string): Promise<ActionResult<{ message: string; is_active: boolean }>> {
  return apiRequest<{ message: string; is_active: boolean }>(`/api/v1/admin/users/${userId}/toggle-active`, {
    method: "POST",
  });
}

export async function resetUserPassword(userId: string, newPassword: string): Promise<ActionResult<{ message: string }>> {
  return apiRequest<{ message: string }>(`/api/v1/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export async function approveUser(userId: string): Promise<ActionResult<{
  message: string;
  user_id: string;
  is_active: boolean;
  is_verified: boolean;
}>> {
  return apiRequest(`/api/v1/admin/users/${userId}/approve`, {
    method: "POST",
  });
}

export async function rejectUser(userId: string, rejectionReason?: string): Promise<ActionResult<{
  message: string;
  user_id: string;
  rejection_reason: string;
}>> {
  return apiRequest(`/api/v1/admin/users/${userId}/reject`, {
    method: "POST",
    body: JSON.stringify({
      rejection_reason: rejectionReason || null,
    }),
  });
}

export async function getPendingUsersCount(): Promise<ActionResult<{ count: number }>> {
  const result = await apiRequest<UserResponse[]>("/api/v1/admin/users?is_active=false&page_size=1");
  if (result.success && result.data) {
    // We need the full count, fetch with is_active=false
    const countResult = await apiRequest<UserResponse[]>("/api/v1/admin/users?is_active=false&page_size=100");
    return {
      success: true,
      data: { count: countResult.data?.length ?? 0 },
    };
  }
  return { success: false, error: result.error };
}

export async function getOrganizations(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
}): Promise<ActionResult<PaginatedResponse<{
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
  member_count?: number;
  total_leaflets?: number;
  total_cost?: number;
}>>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", String(params.page));
  if (params?.page_size) searchParams.append("page_size", String(params.page_size));
  if (params?.search) searchParams.append("search", params.search);
  if (params?.status) searchParams.append("status", params.status);

  const queryString = searchParams.toString();
  // The organizations list endpoint is under /admin/users/organizations
  const endpoint = `/api/v1/admin/users/organizations${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PaginatedResponse<{
    id: string;
    name: string;
    slug: string;
    status: string;
    created_at: string;
    member_count?: number;
    total_leaflets?: number;
    total_cost?: number;
  }>>(endpoint);
}

export interface OrganizationInfo {
  id: string;
  name: string;
  slug: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  last_login?: string;
  created_at: string;
  organizations: OrganizationInfo[];
  leaflet_count: number;
  product_count: number;
  total_cost: number;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_verified?: boolean;
}

export interface UserUpdate {
  email?: string;
  password?: string;
  full_name?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_verified?: boolean;
}

export interface SystemStats {
  total_users: number;
  active_users: number;
  total_leaflets: number;
  total_products: number;
  total_cost: number;
  leaflets_today: number;
  leaflets_this_week: number;
  leaflets_this_month: number;
  avg_products_per_leaflet: number;
  processing_success_rate: number;
}

// ===== REGISTRATION ACTIONS =====

export interface Registration {
  id: string;
  name: string;
  slug: string;
  status: string;
  business_email: string;
  business_phone: string | null;
  requested_by: {
    id: string;
    email: string;
    full_name: string;
  } | null;
  created_at: string;
  approved_at: string | null;
  rejection_reason: string | null;
}

export async function getRegistrations(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<ActionResult<PaginatedResponse<Registration>>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.append("page", String(params.page));
  if (params?.page_size) searchParams.append("page_size", String(params.page_size));
  if (params?.status) searchParams.append("status", params.status);

  const queryString = searchParams.toString();
  const endpoint = `/api/v1/admin/registrations/${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PaginatedResponse<Registration>>(endpoint);
}

export async function approveRegistration(registrationId: string): Promise<ActionResult<{
  success: boolean;
  message: string;
  organization_id: string;
  status: string;
}>> {
  return apiRequest(`/api/v1/admin/registrations/${registrationId}/approve`, {
    method: "POST",
  });
}

export async function rejectRegistration(registrationId: string, rejectionReason?: string): Promise<ActionResult<{
  success: boolean;
  message: string;
  organization_id: string;
  status: string;
}>> {
  return apiRequest(`/api/v1/admin/registrations/${registrationId}/reject`, {
    method: "POST",
    body: JSON.stringify({ rejection_reason: rejectionReason || null }),
  });
}

export async function suspendRegistration(registrationId: string): Promise<ActionResult<{
  success: boolean;
  message: string;
  organization_id: string;
  status: string;
  deactivated_users: number;
}>> {
  return apiRequest(`/api/v1/admin/registrations/${registrationId}/suspend`, {
    method: "POST",
  });
}

export async function deleteRegistration(registrationId: string): Promise<ActionResult<{
  success: boolean;
  message: string;
  organization_name: string;
  deleted_leaflets: number;
  deleted_products: number;
  deleted_users: number;
}>> {
  return apiRequest(`/api/v1/admin/registrations/${registrationId}`, {
    method: "DELETE",
  });
}

// ===== ORGANIZATION QUOTA MANAGEMENT ACTIONS =====

export interface OrganizationWithQuota {
  id: string;
  name: string;
  slug: string;
  status: string;
  platform_leaflet_limit: number;
  platform_leaflets_used: number;
  created_at: string;
}

export interface OrganizationPlatformSettingsResponse {
  id: string;
  name: string;
  platform_leaflet_limit: number;
  platform_leaflets_used: number;
  message: string;
}

export interface PaginatedOrganizationList {
  items: OrganizationWithQuota[];
  total: number;
  page: number;
  page_size: number;
}

export async function getOrganizationsWithQuota(
  page: number = 1,
  pageSize: number = 100
): Promise<ActionResult<PaginatedOrganizationList>> {
  return apiRequest<PaginatedOrganizationList>(
    `/api/v1/admin/organizations/?page=${page}&page_size=${pageSize}`
  );
}

export async function updateOrganizationLimit(
  orgId: string,
  platformLeafletLimit: number
): Promise<ActionResult<OrganizationPlatformSettingsResponse>> {
  return apiRequest<OrganizationPlatformSettingsResponse>(
    `/api/v1/admin/organizations/${orgId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ platform_leaflet_limit: platformLeafletLimit }),
    }
  );
}

// ===== PLATFORM PROVIDER ACTIONS =====

export async function getPlatformProviders(
  filters?: {
    search?: string;
    provider_type?: PlatformVLMProviderType;
    is_active?: boolean;
    skip?: number;
    limit?: number;
  }
): Promise<ActionResult<PlatformProvider[]>> {
  const params = new URLSearchParams();

  if (filters?.search) params.append("search", filters.search);
  if (filters?.provider_type) params.append("provider_type", filters.provider_type);
  if (filters?.is_active !== undefined) params.append("is_active", String(filters.is_active));
  if (filters?.skip) params.append("skip", String(filters.skip));
  if (filters?.limit) params.append("limit", String(filters.limit));

  const queryString = params.toString();
  const endpoint = `/api/v1/admin/platform-providers${queryString ? `?${queryString}` : ""}`;

  // Backend returns { providers: [], total: 0, skip: 0, limit: 100 }
  const result = await apiRequest<{ providers: PlatformProvider[]; total: number; skip: number; limit: number }>(endpoint);

  if (result.success && result.data) {
    return {
      success: true,
      data: result.data.providers,
    };
  }

  return {
    success: result.success,
    error: result.error,
    data: [],
  };
}

export async function createPlatformProvider(
  data: Record<string, unknown>
): Promise<ActionResult<PlatformProvider>> {
  // Filter out null and undefined values for optional fields before validation
  const cleanedData: Record<string, unknown> = {};
  const optionalFields = ['monthly_budget', 'api_endpoint', 'region', 'metadata'];

  for (const [key, value] of Object.entries(data)) {
    // Keep required fields even if empty (validation will catch them)
    // Only filter out null/undefined for optional fields
    if (optionalFields.includes(key)) {
      if (value !== null && value !== undefined) {
        cleanedData[key] = value;
      }
    } else {
      cleanedData[key] = value;
    }
  }

  const validation = CreateProviderSchema.safeParse(cleanedData);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  return apiRequest<PlatformProvider>("/api/v1/admin/platform-providers", {
    method: "POST",
    body: JSON.stringify(validation.data),
  });
}

export async function updatePlatformProvider(
  data: Record<string, unknown>
): Promise<ActionResult<PlatformProvider>> {
  // Filter out empty strings, null, and undefined values before validation
  // This allows partial updates without triggering min(1) validators on empty fields
  const cleanedData: Record<string, unknown> = { id: data.id };

  for (const [key, value] of Object.entries(data)) {
    if (key === 'id') continue;
    // Keep the value only if it's not empty string, null, or undefined
    if (value !== '' && value !== null && value !== undefined) {
      cleanedData[key] = value;
    }
  }

  const validation = UpdateProviderSchema.safeParse(cleanedData);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  const { id, ...updateData } = validation.data;

  return apiRequest<PlatformProvider>(`/api/v1/admin/platform-providers/${id}`, {
    method: "PUT",
    body: JSON.stringify(updateData),
  });
}

export async function deletePlatformProvider(id: string): Promise<ActionResult<void>> {
  return apiRequest<void>(`/api/v1/admin/platform-providers/${id}`, {
    method: "DELETE",
  });
}

export async function testPlatformProvider(id: string): Promise<ActionResult<{
  success: boolean;
  response_time_ms: number;
  error_message?: string;
}>> {
  return apiRequest(`/api/v1/admin/platform-providers/${id}/test`, {
    method: "POST",
  });
}

export async function bulkTestProviders(ids: string[]): Promise<ActionResult<Array<{
  provider_id: string;
  success: boolean;
  response_time_ms?: number;
  error_message?: string;
}>>> {
  return apiRequest("/api/v1/admin/platform-providers/bulk-test", {
    method: "POST",
    body: JSON.stringify({ provider_ids: ids }),
  });
}

// ===== USAGE REPORT ACTIONS =====

export async function getUsageReports(
  filters: z.infer<typeof UsageFiltersSchema> = {}
): Promise<ActionResult<PaginatedResponse<UsageReport>>> {
  const validation = UsageFiltersSchema.safeParse(filters);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  const params = new URLSearchParams();
  Object.entries(validation.data).forEach(([key, value]) => {
    if (value !== undefined) {
      params.append(key, String(value));
    }
  });

  const queryString = params.toString();
  const endpoint = `/api/v1/admin/usage-reports${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PaginatedResponse<UsageReport>>(endpoint);
}

export async function getUsageAnalytics(filters: {
  organization_id?: string;
  provider_id?: string;
  start_date?: string;
  end_date?: string;
}): Promise<ActionResult<{
  total_requests: number;
  total_cost: number;
  organization_count: number;
  avg_cost_per_request: number;
  trends_data: Array<{ date: string; requests: number; cost: number }>;
  cost_breakdown: Array<{ provider: string; cost: number; percentage: number }>;
}>> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.append(key, value);
    }
  });

  const queryString = params.toString();
  const endpoint = `/api/v1/admin/usage-reports/analytics${queryString ? `?${queryString}` : ""}`;

  return apiRequest(endpoint);
}

export async function getUsageReportFilterOptions(): Promise<ActionResult<{
  organizations: Array<{ id: string; name: string }>;
  providers: Array<{ id: string; name: string; provider_type: string }>;
}>> {
  return apiRequest("/api/v1/admin/usage-reports/filter-options");
}

export async function exportUsageReport(filters: z.infer<typeof UsageFiltersSchema>, format: "csv" | "excel" | "json"): Promise<ActionResult<{
  download_url: string;
  expires_at: string;
}>> {
  const validation = UsageFiltersSchema.safeParse(filters);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  return apiRequest("/api/v1/admin/usage-reports/export", {
    method: "POST",
    body: JSON.stringify({ ...validation.data, format }),
  });
}

// ===== BUDGET ALERT ACTIONS =====

export async function getBudgetAlerts(): Promise<ActionResult<PaginatedResponse<BudgetAlert>>> {
  return apiRequest<PaginatedResponse<BudgetAlert>>("/api/v1/admin/budget-alerts");
}

export async function createBudgetAlert(
  data: z.infer<typeof BudgetAlertSchema>
): Promise<ActionResult<BudgetAlert>> {
  const validation = BudgetAlertSchema.safeParse(data);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  return apiRequest<BudgetAlert>("/api/v1/admin/budget-alerts", {
    method: "POST",
    body: JSON.stringify(validation.data),
  });
}

export async function updateBudgetAlert(
  id: string,
  data: Partial<z.infer<typeof BudgetAlertSchema>>
): Promise<ActionResult<BudgetAlert>> {
  return apiRequest<BudgetAlert>(`/api/v1/admin/budget-alerts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteBudgetAlert(id: string): Promise<ActionResult<void>> {
  return apiRequest<void>(`/api/v1/admin/budget-alerts/${id}`, {
    method: "DELETE",
  });
}

// ===== AUDIT LOG ACTIONS =====

export async function getAuditLogs(
  filters: z.infer<typeof AuditFiltersSchema> = {}
): Promise<ActionResult<PaginatedResponse<AuditLog>>> {
  const validation = AuditFiltersSchema.safeParse(filters);

  if (!validation.success) {
    return {
      success: false,
      error: validation.error.issues.map(e => e.message).join(", "),
    };
  }

  const params = new URLSearchParams();
  Object.entries(validation.data).forEach(([key, value]) => {
    if (value !== undefined) {
      params.append(key, String(value));
    }
  });

  const queryString = params.toString();
  const endpoint = `/api/v1/admin/audit-logs${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PaginatedResponse<AuditLog>>(endpoint);
}

export async function exportComplianceReport(filters: {
  start_date: string;
  end_date: string;
  format: "csv" | "json";
  organization_id?: string;
}): Promise<ActionResult<{
  download_url: string;
  expires_at: string;
}>> {
  return apiRequest("/api/v1/admin/audit-logs/compliance-export", {
    method: "POST",
    body: JSON.stringify(filters),
  });
}

// ===== NOTIFICATION ACTIONS =====

export async function getNotifications(): Promise<ActionResult<SystemNotification[]>> {
  return apiRequest<SystemNotification[]>("/api/v1/notifications");
}

export async function markNotificationRead(id: string): Promise<ActionResult<void>> {
  return apiRequest<void>(`/api/v1/notifications/${id}/read`, {
    method: "POST",
  });
}

export async function markAllNotificationsRead(): Promise<ActionResult<void>> {
  return apiRequest<void>("/api/v1/notifications/mark-all-read", {
    method: "POST",
  });
}

// ===== BACKUP ACTIONS =====

export async function getProviderBackups(params?: {
  search?: string;
  provider_id?: string;
  backup_type?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  limit?: number;
}): Promise<ActionResult<PaginatedResponse<{
  id: string;
  provider_name: string;
  backup_type: "manual" | "scheduled" | "pre_deletion";
  backup_size_bytes: number;
  status: "pending" | "completed" | "failed";
  created_at: string;
  created_by_name?: string;
}>>> {
  const filteredParams = params ? Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ) : {};

  const queryString = new URLSearchParams(
    Object.entries(filteredParams).map(([key, value]) => [key, String(value)])
  ).toString();

  const endpoint = `/api/v1/admin/provider-backups${queryString ? `?${queryString}` : ""}`;

  return apiRequest<PaginatedResponse<{
    id: string;
    provider_name: string;
    backup_type: "manual" | "scheduled" | "pre_deletion";
    backup_size_bytes: number;
    status: "pending" | "completed" | "failed";
    created_at: string;
    created_by_name?: string;
  }>>(endpoint);
}

export async function restoreProviderBackup(backupId: string, restoreReason: string): Promise<ActionResult<{
  restored_provider_id: string;
  message: string;
}>> {
  return apiRequest(`/api/v1/admin/provider-backups/${backupId}/restore`, {
    method: "POST",
    body: JSON.stringify({ restore_reason: restoreReason }),
  });
}

export async function createProviderBackup(data: {
  provider_id: string;
  backup_type: "manual" | "scheduled" | "pre_change";
  description?: string;
}): Promise<ActionResult<{
  backup_id: string;
  message: string;
}>> {
  return apiRequest("/api/v1/admin/provider-backups", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteProviderBackup(backupId: string): Promise<ActionResult<void>> {
  return apiRequest(`/api/v1/admin/provider-backups/${backupId}`, {
    method: "DELETE",
  });
}

export async function downloadProviderBackup(backupId: string): Promise<ActionResult<{
  download_url: string;
  expires_at: string;
  filename: string;
}>> {
  return apiRequest(`/api/v1/admin/provider-backups/${backupId}/download`);
}

// ===== DELETION REQUEST ACTIONS =====

export async function getDeletionRequests(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<{
  id: string;
  organization_id: string;
  organization_name: string;
  request_type: "user" | "organization";
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: {
    id: string;
    email: string;
    full_name: string;
  };
  admin_notes?: string;
  created_at: string;
  reviewed_at?: string;
  reviewed_by?: string;
}[]>> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.append("status", params.status);
  if (params?.page) searchParams.append("page", String(params.page));
  if (params?.page_size) searchParams.append("page_size", String(params.page_size));

  const queryString = searchParams.toString();
  const endpoint = `/api/v1/admin/deletion-requests${queryString ? `?${queryString}` : ""}`;

  return apiRequest(endpoint);
}

export async function approveDeletionRequest(
  requestId: string,
  data: {
    admin_notes?: string;
    confirmation_text: string;
  }
): Promise<ActionResult<{
  message: string;
  deleted_organization_id?: string;
}>> {
  return apiRequest(`/api/v1/admin/deletion-requests/${requestId}/approve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function rejectDeletionRequest(
  requestId: string,
  data: {
    admin_notes: string;
    reason: string;
  }
): Promise<ActionResult<{
  message: string;
}>> {
  return apiRequest(`/api/v1/admin/deletion-requests/${requestId}/reject`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ===== HEALTH & MONITORING =====

export async function getSystemHealth(): Promise<ActionResult<{
  overall_status: "healthy" | "degraded" | "down";
  providers: Array<{
    id: string;
    name: string;
    status: "healthy" | "unhealthy" | "unknown";
    last_check: string;
    response_time?: number;
  }>;
  budget_alerts: number;
  recent_errors: number;
}>> {
  return apiRequest("/api/v1/admin/health");
}

export interface ComponentHealth {
  name: string;
  status: "healthy" | "degraded" | "unhealthy";
  message: string;
  latency_ms?: number;
  details?: Record<string, unknown>;
}

export interface SystemHealthData {
  overall_status: "healthy" | "degraded" | "unhealthy";
  timestamp: string;
  components: ComponentHealth[];
  environment: string;
  version: string;
}

export async function getDetailedSystemHealth(): Promise<ActionResult<SystemHealthData>> {
  return apiRequest("/api/v1/admin/system/health");
}

// ===== NOTIFICATION CENTER ACTIONS =====

export interface AdminNotification {
  id: string;
  notification_type: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  is_dismissed: boolean;
  user_id?: string;
  organization_id?: string;
  role_requirement?: string;
  action_url?: string;
  action_text?: string;
  expires_at?: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface NotificationStats {
  total: number;
  unread: number;
  read: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

export async function getAdminNotifications(params: {
  page?: number;
  page_size?: number;
  notification_type?: string;
  severity?: string;
  is_read?: string;
}): Promise<ActionResult<{ items: AdminNotification[]; total_pages: number }>> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return apiRequest(`/api/v1/admin/notifications${queryString ? `?${queryString}` : ""}`);
}

export async function getNotificationStats(): Promise<ActionResult<NotificationStats>> {
  return apiRequest("/api/v1/admin/notifications/stats");
}

export async function createAdminNotification(data: {
  notification_type: string;
  title: string;
  message: string;
  severity: string;
  broadcast_to_all: boolean;
  role_requirement?: string;
  action_url?: string;
  expires_in_hours: number;
}): Promise<ActionResult<AdminNotification>> {
  return apiRequest("/api/v1/admin/notifications", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteAdminNotification(id: string): Promise<ActionResult<void>> {
  return apiRequest(`/api/v1/admin/notifications/${id}`, {
    method: "DELETE",
  });
}