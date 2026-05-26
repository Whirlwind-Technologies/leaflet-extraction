// ===== CORE TYPE DEFINITIONS =====

export type PlatformVLMProviderType = "anthropic" | "openai" | "google" | "azure_openai" | "aws_bedrock";

export type NotificationType = "info" | "warning" | "error" | "success";
export type NotificationSeverity = "low" | "medium" | "high" | "critical";
export type NotificationTargetType = "all_users" | "organization" | "user" | "role";

export type AlertType = "budget_threshold" | "provider_failure" | "cost_anomaly";
export type EventType = "vlm_request" | "provider_change" | "budget_alert" | "admin_action" | "system_event";
export type BackupType = "manual" | "scheduled" | "pre_deletion";
export type BackupStatus = "pending" | "completed" | "failed";

// ===== PLATFORM PROVIDER TYPES =====

export interface PlatformProvider {
  id: string;
  name: string;
  provider_type: PlatformVLMProviderType;
  model_name: string;
  priority: number;
  is_active: boolean;
  is_healthy: boolean;
  last_health_check: string | null;
  monthly_budget?: number;
  daily_budget?: number;
  hourly_rate_limit?: number;
  current_monthly_usage: number;
  current_daily_usage: number;
  current_hourly_usage: number;
  api_endpoint?: string;
  region?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
  last_used_at?: string;
  total_requests: number;
  total_cost: number;
  average_response_time?: number;
  success_rate?: number;
  metadata?: Record<string, unknown>;
}

export interface ProviderHealthStatus {
  id: string;
  name: string;
  provider_type: PlatformVLMProviderType;
  is_healthy: boolean;
  last_health_check: string;
  response_time?: number;
  error_message?: string;
  uptime_percentage: number;
  requests_last_24h: number;
  avg_response_time_24h: number;
}

export interface ProviderTestResult {
  provider_id: string;
  provider_name: string;
  success: boolean;
  response_time?: number;
  error_message?: string;
  test_timestamp: string;
}

// ===== USAGE REPORTING TYPES =====

export interface UsageReport {
  id: string;
  organization_id: string;
  organization_name: string;
  platform_provider_id: string;
  platform_provider_name: string;
  provider_type: PlatformVLMProviderType;
  model_name: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  average_response_time: number;
  success_rate: number;
  error_count: number;
  created_at: string;
}

export interface UsageAnalytics {
  total_requests: number;
  total_cost: number;
  organization_count: number;
  active_providers: number;
  avg_cost_per_request: number;
  avg_response_time: number;
  success_rate: number;
  trends_data: UsageTrendData[];
  cost_breakdown: CostBreakdownData[];
  top_organizations: TopOrganizationData[];
  provider_performance: ProviderPerformanceData[];
}

export interface UsageTrendData {
  date: string;
  requests: number;
  cost: number;
  response_time: number;
  success_rate: number;
}

export interface CostBreakdownData {
  provider_id: string;
  provider_name: string;
  provider_type: PlatformVLMProviderType;
  cost: number;
  percentage: number;
  requests: number;
  avg_cost_per_request: number;
}

export interface TopOrganizationData {
  organization_id: string;
  organization_name: string;
  total_cost: number;
  total_requests: number;
  avg_cost_per_request: number;
  growth_percentage: number;
}

export interface ProviderPerformanceData {
  provider_id: string;
  provider_name: string;
  provider_type: PlatformVLMProviderType;
  requests: number;
  avg_response_time: number;
  success_rate: number;
  cost_per_request: number;
  uptime_percentage: number;
}

// ===== BUDGET ALERT TYPES =====

export interface BudgetAlert {
  id: string;
  organization_id?: string;
  organization_name?: string;
  provider_id?: string;
  provider_name?: string;
  alert_type: AlertType;
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

export interface AlertHistory {
  id: string;
  budget_alert_id: string;
  alert_type: AlertType;
  triggered_at: string;
  threshold_percentage: number;
  actual_usage: number;
  budget_limit?: number;
  organization_name?: string;
  provider_name?: string;
  notification_sent: boolean;
  notification_channels: string[];
  message: string;
  resolved_at?: string;
  resolution_note?: string;
}

// ===== AUDIT LOG TYPES =====

export interface AuditLog {
  id: string;
  timestamp: string;
  user_id?: string;
  username?: string;
  organization_id?: string;
  organization_name?: string;
  session_id?: string;
  event_type: EventType;
  resource_type: string;
  resource_id?: string;
  action: string;
  details?: Record<string, unknown>;
  ip_address?: string;
  user_agent?: string;
  request_id?: string;
  cost?: number;
  tokens_used?: number;
  response_time?: number;
  success: boolean;
  error_code?: string;
  error_message?: string;
  compliance_tags?: string[];
}

export interface ComplianceReport {
  report_id: string;
  generated_at: string;
  period_start: string;
  period_end: string;
  organization_filter?: string;
  total_events: number;
  security_events: number;
  access_events: number;
  data_events: number;
  error_events: number;
  download_url: string;
  expires_at: string;
}

// ===== NOTIFICATION TYPES =====

export interface SystemNotification {
  id: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  severity: NotificationSeverity;
  target_type: NotificationTargetType;
  target_id?: string;
  metadata?: Record<string, unknown>;
  is_read: boolean;
  read_at?: string;
  created_at: string;
  expires_at?: string;
  action_url?: string;
  action_label?: string;
}

export interface NotificationPreference {
  id: string;
  user_id: string;
  email_enabled: boolean;
  push_enabled: boolean;
  notification_types: NotificationType[];
  severity_threshold: NotificationSeverity;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  created_at: string;
  updated_at: string;
}

// ===== BACKUP TYPES =====

export interface ProviderBackup {
  id: string;
  platform_provider_id: string;
  provider_name: string;
  provider_type: PlatformVLMProviderType;
  backup_type: BackupType;
  backup_data: string; // encrypted JSON
  backup_size_bytes: number;
  checksum: string;
  status: BackupStatus;
  created_at: string;
  created_by?: string;
  created_by_name?: string;
  restored_at?: string;
  restored_by?: string;
  restored_by_name?: string;
  restore_reason?: string;
  retention_until?: string;
  metadata?: Record<string, unknown>;
}

export interface BackupRestoreRequest {
  restore_reason: string;
  preserve_current?: boolean;
  notify_users?: boolean;
}

// ===== FORM DATA TYPES =====

export interface CreateProviderData {
  name: string;
  provider_type: PlatformVLMProviderType;
  model_name: string;
  api_key: string;
  priority: number;
  monthly_budget?: number;
  daily_budget?: number;
  hourly_rate_limit?: number;
  api_endpoint?: string;
  region?: string;
  metadata?: Record<string, unknown>;
}

export interface UpdateProviderData extends Partial<CreateProviderData> {
  id: string;
}

export interface CreateBudgetAlertData {
  organization_id?: string;
  provider_id?: string;
  alert_type: AlertType;
  threshold_percentage: number;
  notification_channels: string[];
  email_recipients?: string[];
  webhook_url?: string;
  slack_webhook?: string;
  cooldown_minutes?: number;
}

export interface UpdateBudgetAlertData extends Partial<CreateBudgetAlertData> {
  id: string;
}

// ===== FILTER TYPES =====

export interface ProviderFilters {
  search?: string;
  provider_type?: PlatformVLMProviderType;
  is_active?: boolean;
  is_healthy?: boolean;
  min_priority?: number;
  max_priority?: number;
  has_budget?: boolean;
  over_budget?: boolean;
  skip?: number;
  limit?: number;
}

export interface UsageFilters {
  organization_id?: string;
  provider_id?: string;
  provider_type?: PlatformVLMProviderType;
  start_date?: string;
  end_date?: string;
  min_cost?: number;
  max_cost?: number;
  min_requests?: number;
  skip?: number;
  limit?: number;
}

export interface AuditFilters {
  user_id?: string;
  organization_id?: string;
  event_type?: EventType;
  resource_type?: string;
  action?: string;
  start_date?: string;
  end_date?: string;
  success?: boolean;
  min_cost?: number;
  search?: string;
  ip_address?: string;
  skip?: number;
  limit?: number;
}

export interface AlertFilters {
  organization_id?: string;
  provider_id?: string;
  alert_type?: AlertType;
  is_active?: boolean;
  threshold_min?: number;
  threshold_max?: number;
  recently_triggered?: boolean;
  skip?: number;
  limit?: number;
}

// ===== SYSTEM HEALTH TYPES =====

export interface SystemHealth {
  overall_status: "healthy" | "degraded" | "down";
  providers: ProviderHealthStatus[];
  budget_alerts_active: number;
  recent_errors: number;
  uptime_percentage: number;
  avg_response_time: number;
  total_requests_24h: number;
  total_cost_24h: number;
  last_updated: string;
}

// ===== DASHBOARD STATISTICS =====

export interface AdminDashboardStats {
  total_providers: number;
  active_providers: number;
  healthy_providers: number;
  total_organizations: number;
  active_budget_alerts: number;
  recent_audit_events: number;
  total_cost_today: number;
  total_requests_today: number;
  avg_response_time_24h: number;
  success_rate_24h: number;
  top_cost_organizations: TopOrganizationData[];
  recent_notifications: SystemNotification[];
  provider_health_summary: ProviderHealthStatus[];
}

// ===== EXPORT TYPES =====

export interface ExportRequest {
  format: "csv" | "excel" | "json";
  filters: Record<string, unknown>;
  include_metadata?: boolean;
  date_format?: "iso" | "human";
}

export interface ExportResponse {
  download_url: string;
  expires_at: string;
  file_size_bytes: number;
  record_count: number;
}

// ===== UI COMPONENT PROPS =====

export interface ProviderRowProps {
  provider: PlatformProvider;
  onEdit: (provider: PlatformProvider) => void;
  onDelete: (id: string) => void;
  onTest: (id: string) => void;
  onToggleActive: (id: string, active: boolean) => void;
  isSelected: boolean;
  onSelect: (id: string, selected: boolean) => void;
}

export interface UsageChartProps {
  data: UsageTrendData[];
  period: "daily" | "weekly" | "monthly";
  metric: "requests" | "cost" | "response_time";
  className?: string;
}

export interface NotificationItemProps {
  notification: SystemNotification;
  onMarkRead: (id: string) => void;
  onAction?: (notification: SystemNotification) => void;
  compact?: boolean;
}

export interface BudgetAlertCardProps {
  alert: BudgetAlert;
  onEdit: (alert: BudgetAlert) => void;
  onDelete: (id: string) => void;
  onToggleActive: (id: string, active: boolean) => void;
  usage?: number;
  showHistory?: boolean;
}

// ===== CONFIGURATION TYPES =====

export interface ProviderConfig {
  provider_type: PlatformVLMProviderType;
  display_name: string;
  icon: string;
  models: string[];
  requires_endpoint: boolean;
  supports_regions: boolean;
  regions?: string[];
  default_model: string;
  pricing_per_1k_tokens?: {
    input: number;
    output: number;
  };
}

export const PROVIDER_CONFIGS: Record<PlatformVLMProviderType, ProviderConfig> = {
  anthropic: {
    provider_type: "anthropic",
    display_name: "Anthropic Claude",
    icon: "claude",
    models: ["claude-sonnet-4.5-20250929", "claude-opus-4.5-20251101", "claude-haiku-4-20250107"],
    requires_endpoint: false,
    supports_regions: false,
    default_model: "claude-sonnet-4.5-20250929",
    pricing_per_1k_tokens: { input: 3.0, output: 15.0 },
  },
  openai: {
    provider_type: "openai",
    display_name: "OpenAI GPT",
    icon: "openai",
    models: ["gpt-4o-latest-20250326", "gpt-4o", "gpt-4-turbo"],
    requires_endpoint: false,
    supports_regions: false,
    default_model: "gpt-4o-latest-20250326",
    pricing_per_1k_tokens: { input: 5.0, output: 15.0 },
  },
  google: {
    provider_type: "google",
    display_name: "Google Gemini",
    icon: "google",
    models: ["gemini-2.5-pro", "gemini-2.0-flash-exp", "gemini-1.5-pro"],
    requires_endpoint: false,
    supports_regions: true,
    regions: ["us-central1", "us-east1", "europe-west1", "asia-southeast1"],
    default_model: "gemini-2.5-pro",
    pricing_per_1k_tokens: { input: 2.5, output: 10.0 },
  },
  azure_openai: {
    provider_type: "azure_openai",
    display_name: "Azure OpenAI",
    icon: "azure",
    models: ["gpt-4o", "gpt-4-turbo", "gpt-35-turbo"],
    requires_endpoint: true,
    supports_regions: true,
    regions: ["eastus", "westus2", "northcentralus", "swedencentral", "francecentral"],
    default_model: "gpt-4o",
  },
  aws_bedrock: {
    provider_type: "aws_bedrock",
    display_name: "AWS Bedrock",
    icon: "aws",
    models: ["anthropic.claude-3-5-sonnet-20241022-v2:0", "anthropic.claude-3-opus-20240229-v1:0"],
    requires_endpoint: false,
    supports_regions: true,
    regions: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    default_model: "anthropic.claude-3-5-sonnet-20241022-v2:0",
  },
};

// ===== UTILITY TYPES =====

export type TableSortDirection = "asc" | "desc";

export interface TableSort {
  field: string;
  direction: TableSortDirection;
}

export interface PaginationState {
  page: number;
  limit: number;
  total: number;
}

export interface LoadingState {
  isLoading: boolean;
  loadingText?: string;
  progress?: number;
}

export interface ErrorState {
  hasError: boolean;
  errorMessage?: string;
  errorCode?: string;
}