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
    "Content-Type": "application/json",
  };
}

// ============== ANALYTICS SUMMARY (Source of Truth) ==============

/**
 * Mirrors the backend AnalyticsSummary schema from GET /api/v1/analytics/summary.
 * Every number here is computed live from the same queries as the product list
 * and leaflet list pages, guaranteeing consistency.
 */
export interface AnalyticsSummary {
  // Product counts by review status (matches GET /api/v1/products/stats)
  total_products: number;
  auto_approved: number;
  approved: number;
  pending: number;
  rejected: number;
  needs_correction: number;

  // Derived product metrics
  total_approved: number;        // auto_approved + approved
  total_awaiting_review: number; // pending + needs_correction
  auto_approval_rate: number;    // percentage 0-100
  avg_confidence: number;        // 0-100 scale
  validation_pass_rate: number;  // percentage 0-100
  high_priority_count: number;   // products with review_priority >= 70

  // Leaflet counts
  total_leaflets: number;
  leaflets_completed: number;
  leaflets_processing: number;
  leaflets_failed: number;
  leaflets_by_status: Record<string, number>;

  // Period info
  start_date: string | null;
  end_date: string | null;
}

/**
 * Fetch live analytics summary from the dedicated endpoint.
 * This is the ONLY data source the Analytics page should use for metrics.
 */
export async function getAnalyticsSummary(params?: {
  startDate?: string;
  endDate?: string;
}): Promise<AnalyticsSummary | null> {
  try {
    const headers = await getAuthHeaders();
    const searchParams = new URLSearchParams();
    if (params?.startDate) searchParams.set("start_date", params.startDate);
    if (params?.endDate) searchParams.set("end_date", params.endDate);

    const qs = searchParams.toString();
    const url = `${API_BASE_URL}/api/v1/analytics/summary${qs ? `?${qs}` : ""}`;

    const response = await fetch(url, { headers, cache: "no-store" });

    if (!response.ok) {
      console.error(`Failed to fetch analytics summary: ${response.status}`);
      return null;
    }

    return response.json();
  } catch (error) {
    console.error("Failed to fetch analytics summary:", error);
    return null;
  }
}

// ============== DASHBOARD STATS ==============

export interface DashboardStats {
  leaflets: {
    total: number;
    period_total: number;
    completed: number;
    failed: number;
    processing: number;
  };
  products: {
    total: number;
    period_total: number;
    auto_approved: number;
    reviewed: number;
    pending: number;
  };
  costs: {
    total_cost: number;
    period_cost: number;
    total_tokens: number;
    period_tokens: number;
  };
  quality: {
    auto_approval_rate: number;
    avg_confidence: number;
    validation_pass_rate: number;
    extraction_success_rate: number;
  };
}

export async function getDashboardStats(days: number = 30): Promise<DashboardStats | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/analytics/dashboard?days=${days}`,
      { headers, cache: "no-store" }
    );
    
    if (!response.ok) {
      return null;
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch dashboard stats:", error);
    return null;
  }
}

// ============== COST BREAKDOWN ==============

export interface CostBreakdown {
  period_cost: number;
  period_input_tokens: number;
  period_output_tokens: number;
  daily_costs: Array<{
    date: string;
    cost: number;
    input_tokens: number;
    output_tokens: number;
  }>;
  by_provider: Array<{
    provider_type: string;
    provider_name: string;
    cost: number;
    percentage: number;
  }>;
  by_model: Array<{
    model_name: string;
    cost: number;
    percentage: number;
  }>;
}

export async function getCostBreakdown(days: number = 30): Promise<CostBreakdown | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/analytics/costs?days=${days}`,
      { headers, cache: "no-store" }
    );
    
    if (!response.ok) {
      return null;
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch cost breakdown:", error);
    return null;
  }
}

// ============== QUALITY METRICS ==============

export interface QualityMetrics {
  extraction_success_rate: number;
  auto_approval_rate: number;
  validation_pass_rate: number;
  avg_confidence: number;
  error_rate: number;
  correction_rate: number;
  field_accuracy: Record<string, number>;
  common_errors: Array<{
    error_type: string;
    count: number;
    percentage: number;
  }>;
  improvement_suggestions: string[];
}

export async function getQualityMetrics(days: number = 30): Promise<QualityMetrics | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/analytics/quality?days=${days}`,
      { headers, cache: "no-store" }
    );
    
    if (!response.ok) {
      return null;
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch quality metrics:", error);
    return null;
  }
}

// ============== USAGE TRENDS ==============

export interface UsageTrends {
  total_leaflets: number;
  total_products: number;
  total_cost: number;
  trends: Array<{
    date: string;
    leaflets: number;
    products: number;
    cost: number;
  }>;
}

export async function getUsageTrends(days: number = 30): Promise<UsageTrends | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/analytics/trends?days=${days}`,
      { headers, cache: "no-store" }
    );
    
    if (!response.ok) {
      return null;
    }
    
    return response.json();
  } catch (error) {
    console.error("Failed to fetch usage trends:", error);
    return null;
  }
}

// ============== EXPORT ANALYTICS ==============

export async function exportAnalytics(
  format: "json" | "csv" = "json",
  days: number = 30
): Promise<Blob | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(
      `${API_BASE_URL}/api/v1/analytics/export?format=${format}&days=${days}`,
      { headers }
    );
    
    if (!response.ok) {
      return null;
    }
    
    return response.blob();
  } catch (error) {
    console.error("Failed to export analytics:", error);
    return null;
  }
}