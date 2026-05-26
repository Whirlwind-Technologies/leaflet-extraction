export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  default_organization_id?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

export interface Leaflet {
  id: string;
  leaflet_id: string;
  user_id: string;
  filename: string;
  file_size: number;
  file_hash: string;
  mime_type: string;
  page_count: number | null;
  pdf_type: string | null;
  status: LeafletStatus;
  progress: number;
  current_step: string | null;
  status_message: string | null;
  retailer: string | null;
  country: string | null;
  language: string | null;
  currency: string | null;
  valid_from: string | null;
  valid_until: string | null;
  source_path: string;
  created_at: string;
  updated_at: string;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  /** Total product count (from COUNT query, available on detail endpoint). */
  products_count?: number;
  overall_confidence?: number | null;
  auto_approved_count?: number;
  review_required_count?: number;
}

export type LeafletStatus =
  | "pending"
  | "uploading"
  | "processing"
  | "extracting"
  | "validating"
  | "reviewing"
  | "completed"
  | "failed"
  | "cancelled";

export interface LeafletPage {
  id: string;
  leaflet_id: string;
  page_number: number;
  image_path: string;
  thumbnail_path: string;
  image_url: string | null;
  thumbnail_url: string | null;
  width: number;
  height: number;
  file_size: number;
  format: string;
  is_processed: boolean;
  products_count: number;
  created_at: string;
}

export interface ProductImage {
  storage_type: string;
  data: string | null;
  url: string | null;
  path: string | null;  // Storage path for URL refresh
  format: string;
  dimensions: { width: number; height: number };
  size_bytes: number | null;
  quality_score: number | null;
}

export interface Product {
  id: string;
  leaflet_id: string;
  page_number: number;
  brand: string | null;
  product_code: string | null;
  product_name: string;
  quantity: number | null;
  units: string | null;
  size: string | null;
  regular_price: number | null;
  discounted_price: number | null;
  discount_percentage: number | null;
  currency: string | null;
  product_id: string | null;
  promotional_info: string | null;
  suggested_category: string | null;
  category: string | null;
  category_confidence: number | null;
  category_alternatives: CategoryAlternative[] | null;
  bounding_box: BoundingBox;
  image: ProductImage | null;
  image_storage_type: string | null;
  image_base64: string | null;
  image_url: string | null;
  image_path: string | null;  // Storage path for URL refresh
  thumbnail_url: string | null;
  image_width: number | null;
  image_height: number | null;
  image_size_bytes: number | null;
  image_quality_score: number | null;
  confidence: number | null;
  field_confidence: FieldConfidence | null;
  uncertainty_flags: string[];
  review_status: ReviewStatus;
  review_priority: number;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  validation_passed: boolean;
  validation_errors: ValidationError[];
  is_corrected: boolean;
  is_split_product: boolean;
  created_at: string;
  updated_at: string;
}

export interface FieldConfidence {
  brand: number | null;
  product_code: number | null;
  product_name: number | null;
  quantity: number | null;
  units: number | null;
  regular_price: number | null;
  discounted_price: number | null;
  discount_percentage: number | null;
  currency: number | null;
  product_id: number | null;
  suggested_category: number | null;
}

export interface CategoryAlternative {
  category: string;
  confidence: number;
}

export interface ValidationError {
  field: string;
  error_type: string;
  message: string;
  severity: string;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type ReviewStatus =
  | "pending"
  | "auto_approved"
  | "approved"
  | "rejected"
  | "corrected"
  | "needs_correction";

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface LeafletUploadResponse {
  leaflet_id: string;
  message: string;
  status: LeafletStatus;
  is_existing?: boolean;
}

export interface PrepareUploadResponse {
  leaflet_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  upload_method: string;
  storage_path: string;
  expires_in: number;
}

export interface ConfirmUploadResponse {
  leaflet_id: string;
  status: LeafletStatus;
  message: string;
}

export interface LeafletProcessingStatus {
  leaflet_id: string;
  status: LeafletStatus;
  progress: number;
  current_step: string | null;
  message: string | null;
  pages_processed: number;
  products_found: number;
  timestamp: string;
}

export interface ActionResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface UploadMetadata {
  retailer?: string;
  country?: string;
  language?: string;
  currency?: string;
}

// Retailer Registry Types
export interface Retailer {
  id: string;
  organization_id: string;
  name: string;
  country: string | null;
  currency: string | null;
  language: string | null;
  logo_url: string | null;
  external_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RetailerCreate {
  name: string;
  country?: string;
  currency?: string;
  language?: string;
  logo_url?: string;
  external_id?: string;
}

export interface RetailerUpdate {
  name?: string;
  country?: string;
  currency?: string;
  language?: string;
  logo_url?: string;
  external_id?: string;
  is_active?: boolean;
}

export interface ProductNavigationContext {
  prevProductId: string | null;
  nextProductId: string | null;
  currentIndex: number;
  totalCount: number;
  contextQueryString: string;
  productIds: string[];
}

// ---------------------------------------------------------------------------
// Product Export Types
// ---------------------------------------------------------------------------

export type ExportFormat = "csv" | "excel" | "json";

export type ExportImageStorage = "url" | "base64" | "none";

export type ExportMode = "all" | "filtered" | "selected" | "review_queue";

export type ExportJobStatus = "pending" | "processing" | "completed" | "failed";

export interface ProductExportFilters {
  search?: string;
  review_status?: string[];
  leaflet_id?: string;
  category?: string;
  brand?: string;
  min_confidence?: number;
  page_number?: number;
  validation_passed?: boolean;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface ReviewQueueExportFilters {
  leaflet_id?: string;
}

export interface ProductExportRequest {
  format: ExportFormat;
  image_storage: ExportImageStorage;
  mode: ExportMode;
  filters?: ProductExportFilters;
  product_ids?: string[];
  review_queue_filters?: ReviewQueueExportFilters;
}

export interface ExportPreviewResponse {
  product_count: number;
  leaflet_count: number;
  estimated_file_size: string;
}

export interface ExportJobResponse {
  export_id: string;
  status: ExportJobStatus;
  product_count: number;
  message: string;
}

export interface ExportStatusResponse {
  export_id: string;
  status: ExportJobStatus;
  product_count: number;
  file_size?: string;
  download_url?: string;
  format: ExportFormat;
  created_at: string;
  completed_at?: string;
  error_message?: string;
}