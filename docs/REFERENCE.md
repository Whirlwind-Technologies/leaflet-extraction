# API Reference

Base URL: `http://localhost:8000/api/v1` (development) · `https://www.leafxtract.com/api/v1` (production)

Interactive docs: [Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc)

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Common Conventions](#2-common-conventions)
3. [Error Responses](#3-error-responses)
4. [Leaflets](#4-leaflets)
5. [Products](#5-products)
6. [Export](#6-export)
7. [Webhooks](#7-webhooks)
8. [Organizations](#8-organizations)
9. [Retailers](#9-retailers)
10. [VLM Providers](#10-vlm-providers)
11. [API Keys](#11-api-keys)
12. [Users](#12-users)
13. [WebSocket](#13-websocket)
14. [Health](#14-health)

---

## 1. Authentication

All endpoints (except registration, login, and `/health`) require one of:

| Method | Header | Notes |
|--------|--------|-------|
| JWT Bearer | `Authorization: Bearer <access_token>` | Obtain from `POST /auth/login` |
| API Key | `X-API-Key: <key>` | Manage via `POST /users/me/api-keys` |

### POST /auth/register

Register a new individual user account.

**Request body**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Jane Smith"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string | Yes | Must be unique |
| `password` | string | Yes | Min 8 characters |
| `full_name` | string | No | Display name |

**Response `201`**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "is_active": true,
  "created_at": "2025-06-01T12:00:00Z"
}
```

**Errors:** `422` invalid fields · `409` email already registered

---

### POST /auth/login

Exchange credentials for JWT tokens.

**Request body** (`application/x-www-form-urlencoded`)
```
username=user@example.com&password=SecurePassword123!
```

**Response `200`**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Token lifetimes: access = 30 min · refresh = 7 days

**Errors:** `401` invalid credentials · `403` account inactive

---

### POST /auth/refresh

Exchange a refresh token for a new access token.

**Request body**
```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

**Response `200`** — same shape as `/auth/login`

**Errors:** `401` token invalid or expired

---

### POST /auth/logout

Invalidate the current session. Requires `Authorization` header.

**Response `200`**
```json
{ "message": "Successfully logged out" }
```

---

### POST /auth/forgot-password

Request a password-reset email.

**Request body**
```json
{ "email": "user@example.com" }
```

**Response `200`** — always returns success to prevent email enumeration.

---

### POST /auth/reset-password

Complete a password reset.

**Request body**
```json
{
  "token": "<reset_token_from_email>",
  "new_password": "NewSecurePassword123!"
}
```

**Response `200`**
```json
{ "message": "Password reset successfully" }
```

**Errors:** `400` token invalid or expired

---

## 2. Common Conventions

### Pagination

All list endpoints accept these query parameters:

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `page` | integer | `1` | 1-indexed |
| `page_size` | integer | `20` | Max `100` |
| `sort_by` | string | `created_at` | Field name |
| `sort_order` | string | `desc` | `asc` or `desc` |

**Paginated response envelope**
```json
{
  "items": [...],
  "total": 284,
  "page": 1,
  "page_size": 20,
  "pages": 15,
  "has_next": true,
  "has_prev": false
}
```

### IDs

Resources have two IDs:

- **`id`** — UUID (e.g. `3fa85f64-5717-4562-b3fc-2c963f66afa6`). Use for programmatic references.
- **`leaflet_id`** — Human-readable string (e.g. `LEAF_2025_A3F2B1`). Accepted wherever a leaflet ID is required (path params accept either format).

### Dates

All timestamps are ISO 8601 UTC strings: `2025-06-01T12:00:00Z`. Date inputs accept both `YYYY-MM-DD` and full ISO 8601 (JavaScript's `.toISOString()` `Z` suffix is handled server-side).

### Bounding Box

```json
{ "x": 42, "y": 118, "width": 280, "height": 350 }
```

Coordinates are pixels relative to the top-left corner of the page image.

---

## 3. Error Responses

All errors follow this envelope:

```json
{
  "detail": "Human-readable message"
}
```

Validation errors return an array of field-level details:

```json
{
  "detail": [
    { "field": "file", "message": "File must be a PDF or ZIP archive" },
    { "field": "currency", "message": "Currency code must be 3 characters (ISO 4217)" }
  ]
}
```

| HTTP status | Meaning |
|-------------|---------|
| `400` | Bad request — request is malformed |
| `401` | Unauthenticated — missing or invalid token |
| `403` | Forbidden — authenticated but not authorized |
| `404` | Not found |
| `409` | Conflict — duplicate resource |
| `422` | Validation error — Pydantic schema failure |
| `429` | Rate limited |
| `500` | Internal server error |

---

## 4. Leaflets

### POST /leaflets/upload

Upload a PDF or ZIP leaflet for processing.

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | Yes | PDF (max configured `max_file_size`) or ZIP of page images (max 200 MB) |
| `retailer` | string | No | Retailer name (max 255 chars) |
| `country` | string | No | ISO 3166-1 alpha-2 (e.g. `SI`, `HR`) |
| `language` | string | No | ISO 639-1 (e.g. `sl`, `hr`) |
| `currency` | string | No | ISO 4217 (e.g. `EUR`, `RSD`) |
| `valid_from` | string | No | ISO 8601 date — leaflet validity start |
| `valid_until` | string | No | ISO 8601 date — leaflet validity end |
| `auto_process` | boolean | No | Default `true`. Set `false` to upload without queuing extraction |

**Response `201`**
```json
{
  "leaflet_id": "LEAF_2025_A3F2B1",
  "message": "Leaflet uploaded and processing started.",
  "status": "processing",
  "is_existing": false
}
```

When `is_existing: true`, the file hash matched a previous upload. The existing `leaflet_id` is returned so the client can navigate to it.

**Errors:** `422` invalid file type / magic bytes / size · `413` file too large

---

### POST /leaflets/upload/images

Upload multiple image files as a single multi-page leaflet. Each image becomes one page in order of upload.

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `files` | file[] | Yes | 1–100 images. JPEG, PNG, WEBP, TIFF, GIF, BMP. Max 20 MB each, 200 MB total |
| `retailer` | string | No | |
| `country` | string | No | |
| `language` | string | No | |
| `currency` | string | No | |
| `auto_process` | boolean | No | Default `true` |

**Response `201`** — same shape as `/leaflets/upload`

---

### POST /leaflets/upload/bulk

Upload up to 20 PDF files in a single request. Each file is processed independently; partial success is allowed.

**Content-Type:** `multipart/form-data`

| Field | Type | Notes |
|-------|------|-------|
| `files` | file[] | Max 20 PDFs |
| `retailer`, `country`, `language`, `currency` | string | Applied to all files |
| `valid_from`, `valid_until` | string | Applied to all files |
| `auto_process` | boolean | Default `true` |

**Response `201`**
```json
{
  "message": "Processed 3 files: 3 successful, 0 failed",
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "filename": "aldi-week12.pdf",
      "success": true,
      "leaflet_id": "LEAF_2025_A3F2B1",
      "status": "processing",
      "is_existing": false,
      "error": null
    }
  ]
}
```

---

### POST /leaflets/prepare-upload

Get a presigned S3 URL for direct browser-to-S3 upload. Use this for large files to avoid routing through the backend.

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `filename` | string | Yes | Must end in `.pdf` or `.zip` |
| `file_size` | integer | Yes | Bytes |
| `retailer`, `country`, `language`, `currency` | string | No | |
| `valid_from`, `valid_until` | string | No | |

**Response `200`**
```json
{
  "leaflet_id": "LEAF_2025_C9D4E2",
  "upload_url": "https://s3.amazonaws.com/...",
  "upload_fields": { "key": "...", "AWSAccessKeyId": "..." },
  "upload_method": "POST",
  "storage_path": "leaflets/LEAF_2025_C9D4E2/source/original.pdf",
  "expires_in": 3600
}
```

After uploading to `upload_url`, call `POST /leaflets/confirm-upload/{leaflet_id}` to finalize.

---

### POST /leaflets/confirm-upload/{leaflet_id}

Confirm that direct S3 upload completed and optionally start processing.

**Content-Type:** `multipart/form-data`

| Field | Type | Notes |
|-------|------|-------|
| `auto_process` | boolean | Default `true` |

**Response `200`**
```json
{
  "leaflet_id": "LEAF_2025_C9D4E2",
  "status": "processing",
  "message": "Upload confirmed and processing started."
}
```

**Errors:** `404` leaflet not found · `422` file not found in storage (upload failed)

---

### GET /leaflets/

List all leaflets for the current organization.

**Query parameters**

| Parameter | Type | Notes |
|-----------|------|-------|
| `page`, `page_size`, `sort_by`, `sort_order` | | See [Pagination](#pagination) |
| `status` | string | `pending` · `processing` · `extracting` · `reviewing` · `completed` · `failed` |
| `retailer` | string | Case-insensitive partial match |
| `country` | string | Exact match (uppercase) |
| `search` | string | Partial match on filename |

**Response `200`** — paginated envelope, items are `LeafletResponse`:
```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "leaflet_id": "LEAF_2025_A3F2B1",
      "filename": "aldi-week12.pdf",
      "file_size": 4823040,
      "page_count": 16,
      "status": "completed",
      "status_message": null,
      "progress": 1.0,
      "current_step": "completed",
      "retailer": "ALDI",
      "country": "SI",
      "language": "sl",
      "currency": "EUR",
      "overall_confidence": 0.94,
      "products_count": 142,
      "auto_approved_count": 128,
      "review_required_count": 14,
      "valid_from": "2025-03-10T00:00:00Z",
      "valid_until": "2025-03-16T00:00:00Z",
      "processing_started_at": "2025-03-09T08:12:00Z",
      "processing_completed_at": "2025-03-09T08:14:32Z",
      "created_at": "2025-03-09T08:11:45Z",
      "updated_at": "2025-03-09T08:14:32Z"
    }
  ],
  "total": 84,
  "page": 1,
  "page_size": 20,
  "pages": 5,
  "has_next": true,
  "has_prev": false
}
```

---

### GET /leaflets/{leaflet_id}

Get full details for a single leaflet, including all pages with presigned image URLs.

**Path parameter:** `leaflet_id` — UUID or human-readable ID

**Response `200`** — `LeafletDetail` (extends `LeafletResponse`):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "leaflet_id": "LEAF_2025_A3F2B1",
  "filename": "aldi-week12.pdf",
  "file_size": 4823040,
  "page_count": 16,
  "status": "completed",
  "progress": 1.0,
  "retailer": "ALDI",
  "country": "SI",
  "language": "sl",
  "currency": "EUR",
  "overall_confidence": 0.94,
  "products_count": 142,
  "auto_approved_count": 128,
  "review_required_count": 14,
  "processing_metadata": { "model": "claude-sonnet-4-20250514", "pages_failed": [] },
  "api_tokens_used": 184320,
  "processing_cost": 0.3214,
  "pages": [
    {
      "id": "c9b2a1f0-3344-4abc-8def-aabbccdd1122",
      "page_number": 1,
      "image_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
      "thumbnail_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
      "width": 2480,
      "height": 3508,
      "products_count": 9,
      "is_processed": true,
      "extraction_confidence": 0.96,
      "created_at": "2025-03-09T08:12:05Z",
      "updated_at": "2025-03-09T08:13:10Z"
    }
  ],
  "valid_from": "2025-03-10T00:00:00Z",
  "valid_until": "2025-03-16T00:00:00Z",
  "processing_started_at": "2025-03-09T08:12:00Z",
  "processing_completed_at": "2025-03-09T08:14:32Z",
  "created_at": "2025-03-09T08:11:45Z",
  "updated_at": "2025-03-09T08:14:32Z"
}
```

Page image URLs are presigned and valid for 1 hour.

**Errors:** `404` leaflet not found

---

### GET /leaflets/{leaflet_id}/status

Lightweight polling endpoint for extraction progress.

**Response `200`**
```json
{
  "leaflet_id": "LEAF_2025_A3F2B1",
  "status": "processing",
  "progress": 0.5625,
  "current_step": "extracting_page_9",
  "message": "Processing page 9 of 16",
  "pages_processed": 9,
  "products_found": 74,
  "timestamp": "2025-03-09T08:13:05Z"
}
```

`progress` is `0.0`–`1.0`. For real-time updates prefer the [WebSocket endpoint](#13-websocket).

---

### GET /leaflets/{leaflet_id}/pages

List all pages for a leaflet with presigned image and thumbnail URLs.

**Response `200`** — array of page objects (same shape as the `pages` array in `GET /leaflets/{id}`)

---

### PUT /leaflets/{leaflet_id}

Update leaflet metadata. Only provided fields are updated.

**Request body**
```json
{
  "retailer": "LIDL",
  "country": "HR",
  "language": "hr",
  "currency": "EUR",
  "valid_from": "2025-04-01",
  "valid_until": "2025-04-07"
}
```

All fields optional. `country` is stored uppercase; `currency` must be 3 characters.

**Response `200`** — updated `LeafletResponse`

**Errors:** `404` not found

---

### DELETE /leaflets/{leaflet_id}

Permanently delete a leaflet and all associated data: products, page images, product images, and the source PDF from S3.

**Response `204`** — no body

**Errors:** `404` not found

---

### POST /leaflets/{leaflet_id}/reprocess

Re-queue a leaflet for full reprocessing (PDF conversion + extraction).

**Response `200`**
```json
{
  "success": true,
  "message": "Leaflet queued for processing",
  "data": { "leaflet_id": "LEAF_2025_A3F2B1" }
}
```

**Errors:** `404` not found · `409` leaflet already processing

---

### POST /leaflets/{leaflet_id}/extract

Trigger VLM product extraction for a leaflet that has completed PDF conversion (status `extracting` or `validating`).

**Response `200`**
```json
{
  "success": true,
  "message": "Product extraction queued",
  "data": {
    "leaflet_id": "LEAF_2025_A3F2B1",
    "task_id": "d5c3a2b1-abcd-4321-efgh-000011112222"
  }
}
```

**Errors:** `404` not found · `422` wrong status · `422` no pages found

---

### POST /leaflets/{leaflet_id}/extract-images

Extract product images from page images using existing bounding boxes. Useful after extraction completes if image extraction was skipped.

**Query parameters**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `force` | boolean | `false` | Clear existing images and re-extract all |

**Response `200`**
```json
{
  "success": true,
  "message": "Product image extraction queued",
  "data": {
    "leaflet_id": "LEAF_2025_A3F2B1",
    "task_id": "e6d4b3c2-dcba-1234-hgfe-333322221111",
    "force": false
  }
}
```

**Errors:** `404` not found · `422` still processing or no products found

---

### DELETE /leaflets/{leaflet_id}/extraction

Remove all extracted products and images while keeping the source PDF and page images. Resets the leaflet to `validating` status so extraction can be re-triggered.

**Response `200`**
```json
{
  "success": true,
  "message": "Extraction data cleared successfully",
  "data": {
    "leaflet_id": "LEAF_2025_A3F2B1",
    "products_deleted": 142,
    "reviews_deleted": 28,
    "storage_files_deleted": 142
  }
}
```

**Errors:** `404` not found · `422` leaflet is currently processing

---

## 5. Products

### GET /products/

List products with filtering and pagination.

**Query parameters**

| Parameter | Type | Notes |
|-----------|------|-------|
| `page`, `page_size`, `sort_by`, `sort_order` | | See [Pagination](#pagination) |
| `leaflet_id` | UUID | Filter by parent leaflet |
| `page_number` | integer | Filter by page within leaflet |
| `review_status` | string | `pending` · `auto_approved` · `approved` · `rejected` · `needs_correction` |
| `brand` | string | Case-insensitive partial match |
| `category` | string | Exact category name |
| `min_confidence` | float | `0.0`–`1.0` |
| `validation_passed` | boolean | |
| `search` | string | Case-insensitive match on `product_name` |

**Response `200`** — paginated, items are `ProductListResponse`:
```json
{
  "items": [
    {
      "id": "b1c2d3e4-1234-5678-abcd-ef0123456789",
      "leaflet_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "page_number": 3,
      "brand": "Coca-Cola",
      "product_code": "5449000054227",
      "product_name": "Coca-Cola Zero Sugar 2L",
      "quantity": 2.0,
      "units": "L",
      "regular_price": 2.49,
      "discounted_price": 1.79,
      "discount_percentage": 28.1,
      "currency": "EUR",
      "product_id": "5449000054227",
      "category": "Soft Drinks",
      "suggested_category": "Soft Drinks",
      "bounding_box": { "x": 42, "y": 118, "width": 280, "height": 350 },
      "image_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
      "thumbnail_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
      "image_width": 280,
      "image_height": 350,
      "image_quality_score": 0.92,
      "confidence": 0.97,
      "field_confidence": {
        "brand": 0.99,
        "product_name": 0.98,
        "regular_price": 0.96,
        "discounted_price": 0.97,
        "discount_percentage": 0.95
      },
      "uncertainty_flags": [],
      "review_status": "auto_approved",
      "review_priority": 0,
      "reviewed_by": null,
      "reviewed_at": null,
      "validation_passed": true,
      "validation_errors": [],
      "is_corrected": false,
      "is_split_product": false,
      "created_at": "2025-03-09T08:13:22Z",
      "updated_at": "2025-03-09T08:13:22Z"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "pages": 8,
  "has_next": true,
  "has_prev": false
}
```

---

### GET /products/stats

Aggregate counts by `review_status` for the current organization.

**Query parameters**

| Parameter | Type | Notes |
|-----------|------|-------|
| `leaflet_id` | UUID | Scope to a single leaflet |

**Response `200`**
```json
{
  "total": 142,
  "pending": 0,
  "auto_approved": 128,
  "approved": 9,
  "rejected": 3,
  "needs_correction": 2
}
```

---

### GET /products/review-queue

Products requiring human review, ordered by priority (highest first).

**Query parameters**

| Parameter | Type | Notes |
|-----------|------|-------|
| `page`, `page_size` | | See [Pagination](#pagination) |
| `leaflet_id` | UUID | Scope to a single leaflet |

**Response `200`** — paginated `ProductListResponse` items, same schema as `/products/`

---

### POST /products/batch

Fetch up to 20 products by ID in a single request. Powers the review UI's LRU prefetch cache.

**Request body**
```json
{
  "product_ids": [
    "b1c2d3e4-1234-5678-abcd-ef0123456789",
    "c2d3e4f5-2345-6789-bcde-f01234567890"
  ]
}
```

`product_ids`: 1–20 UUIDs.

**Response `200`**
```json
{
  "products": [
    { /* full ProductResponse */ },
    { /* full ProductResponse */ }
  ],
  "found": 2,
  "not_found": []
}
```

**Errors:** `422` more than 20 IDs

---

### GET /products/{product_id}

Get a single product by UUID.

**Response `200`** — full `ProductResponse` (same fields as list items plus `promotional_info`, `review_notes`, `validation_errors`)

**Errors:** `404` not found

---

### PUT /products/{product_id}

Update product data fields. All fields optional; only provided fields are updated.

**Request body**
```json
{
  "brand": "Coca-Cola",
  "product_name": "Coca-Cola Zero Sugar 2L",
  "regular_price": 2.49,
  "discounted_price": 1.79,
  "discount_percentage": 28.1,
  "currency": "EUR",
  "quantity": 2.0,
  "units": "L",
  "product_code": "5449000054227",
  "product_id": "5449000054227",
  "category": "Soft Drinks",
  "bounding_box": { "x": 42, "y": 118, "width": 280, "height": 350 }
}
```

**Response `200`** — updated `ProductResponse`

**Errors:** `404` not found · `422` validation failure

---

### POST /products/{product_id}/review

Submit a review decision for a product.

**Request body**
```json
{
  "action": "corrected",
  "corrections": {
    "regular_price": 2.49,
    "discounted_price": 1.79
  },
  "notes": "Price was misread from promotional banner",
  "bounding_box": null,
  "time_spent_seconds": 14
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `action` | string | Yes | `approved` · `rejected` · `corrected` · `needs_correction` |
| `corrections` | object | No | Required when `action` is `corrected`. Keys are product field names |
| `notes` | string | No | Reviewer notes |
| `bounding_box` | object | No | Corrected bounding box |
| `time_spent_seconds` | integer | No | Time taken to review (≥ 0) |

**Response `200`** — updated `ProductResponse`

**Errors:** `404` not found · `422` invalid action

---

### POST /products/batch-review

Apply the same review action to multiple products at once. Supported actions: `approved`, `rejected`.

**Request body**
```json
{
  "product_ids": [
    "b1c2d3e4-1234-5678-abcd-ef0123456789",
    "c2d3e4f5-2345-6789-bcde-f01234567890"
  ],
  "action": "approved",
  "notes": "Spot-checked and confirmed"
}
```

`product_ids`: 1–100 UUIDs.

**Response `200`**
```json
{
  "processed": 2,
  "succeeded": 2,
  "failed": 0,
  "errors": []
}
```

If some products fail, `errors` contains `[{ "product_id": "...", "error": "..." }]` entries.

---

### GET /products/{product_id}/review-history

Paginated review history for a product.

**Response `200`** — paginated, items are `ProductReviewResponse`:
```json
{
  "items": [
    {
      "id": "d4e5f6a7-3456-7890-cdef-012345678901",
      "product_id": "b1c2d3e4-1234-5678-abcd-ef0123456789",
      "reviewer_id": "a1b2c3d4-0000-1111-2222-333344445555",
      "action": "corrected",
      "previous_data": { "regular_price": 2.99 },
      "new_data": { "regular_price": 2.49 },
      "changed_fields": ["regular_price"],
      "notes": "Price was misread from promotional banner",
      "time_spent_seconds": 14,
      "created_at": "2025-03-09T10:22:14Z",
      "updated_at": "2025-03-09T10:22:14Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "has_next": false,
  "has_prev": false
}
```

---

### POST /products/{product_id}/refresh-image-url

Generate a fresh presigned S3 URL for a product's image. Use when the current URL has expired (URLs are valid for 1 hour).

**Response `200`**
```json
{
  "image_url": "https://s3.amazonaws.com/...?X-Amz-Expires=3600&...",
  "expires_in": 3600
}
```

**Errors:** `404` not found · `422` product has no file-stored image (base64 products do not need URL refresh)

---

### POST /products/{product_id}/re-extract-image

Re-run image extraction for a single product using its stored bounding box.

**Response `200`**
```json
{
  "success": true,
  "message": "Image re-extracted successfully",
  "data": {
    "image_url": "https://s3.amazonaws.com/...",
    "image_quality_score": 0.91
  }
}
```

**Errors:** `404` product or page or leaflet not found · `422` extraction failed

---

## 6. Export

The export system has two paths depending on the number of matching products:

- **Sync** (< 1,000 products): file streamed directly in the response
- **Async** (≥ 1,000 products): job created, poll for status, then download

### POST /products/export/preview

Count products and estimate file size before committing to an export. Use to populate a confirmation dialog.

**Request body** — same as `POST /products/export` (see below)

**Response `200`**
```json
{
  "product_count": 3842,
  "leaflet_count": 27,
  "estimated_file_size": "3.8 MB"
}
```

Estimates: CSV ~0.5 KB/product, CSV+URLs ~0.6 KB, Excel ~0.7 KB, JSON ~1.0 KB, JSON+base64 ~50 KB per product.

---

### POST /products/export

Export products to CSV, Excel, or JSON.

**Request body**
```json
{
  "format": "csv",
  "image_storage": "url",
  "mode": "filtered",
  "filters": {
    "review_status": ["approved", "auto_approved"],
    "leaflet_id": "LEAF_2025_A3F2B1",
    "brand": "Coca-Cola",
    "min_confidence": 0.85,
    "search": null,
    "category": null,
    "page_number": null,
    "validation_passed": null,
    "sort_by": "created_at",
    "sort_order": "desc"
  },
  "product_ids": null
}
```

| Field | Type | Options | Notes |
|-------|------|---------|-------|
| `format` | string | `csv` · `excel` · `json` | Required |
| `image_storage` | string | `url` · `base64` · `none` | Default `url` |
| `mode` | string | `all` · `filtered` · `selected` · `review_queue` | Required |
| `filters` | object | | Required when `mode` is `filtered` |
| `product_ids` | UUID[] | | Required when `mode` is `selected`. Max 500 |

**`filters` fields**

| Field | Type | Notes |
|-------|------|-------|
| `search` | string | Case-insensitive match on `product_name` |
| `review_status` | string[] | One or more of `pending` · `auto_approved` · `approved` · `rejected` · `needs_correction` |
| `leaflet_id` | string | UUID or human-readable ID |
| `category` | string | Exact match |
| `brand` | string | Case-insensitive |
| `min_confidence` | float | `0.0`–`1.0` |
| `page_number` | integer | |
| `validation_passed` | boolean | |
| `sort_by`, `sort_order` | string | |

**Sync response `200`** — binary file stream

```
Content-Type: text/csv
Content-Disposition: attachment; filename="leafxtract-products-2025-03-09.csv"
```

**Async response `202`**
```json
{
  "export_id": "f7a8b9c0-4567-8901-defg-123456789012",
  "status": "pending",
  "product_count": 3842,
  "message": "Export job created for 3842 products. Poll the status endpoint for progress."
}
```

**Errors:** `422` invalid request · `429` more than 5 concurrent pending exports

---

### GET /products/export/{export_id}/status

Check the status of an async export job.

**Response `200`**
```json
{
  "export_id": "f7a8b9c0-4567-8901-defg-123456789012",
  "status": "completed",
  "format": "csv",
  "mode": "filtered",
  "product_count": 3842,
  "created_at": "2025-03-09T09:00:00Z",
  "completed_at": "2025-03-09T09:00:47Z",
  "expires_at": "2025-03-10T09:00:00Z",
  "error_message": null
}
```

`status` values: `pending` · `processing` · `completed` · `failed`

Download links expire 24 hours after job creation.

---

### GET /products/export/{export_id}/download

Download a completed async export file. Redirects to a presigned S3 URL.

**Response `302`** — redirect to presigned download URL

**Errors:** `404` job not found · `422` job not yet completed · `410` download link expired

---

## 7. Webhooks

Webhooks deliver event notifications as `HTTP POST` requests to your endpoint. Each delivery includes an `X-LeafXtract-Signature` header containing an `HMAC-SHA256` signature computed with the webhook secret.

**Available event types**

| Event | Fired when |
|-------|-----------|
| `leaflet.uploaded` | A new leaflet is uploaded |
| `leaflet.processing` | Processing starts |
| `leaflet.completed` | All pages extracted successfully |
| `leaflet.failed` | Processing fails |
| `product.extracted` | Products extracted from a page |
| `product.reviewed` | A product review is submitted |
| `product.updated` | A product's data is updated |
| `export.started` | An async export job is created |
| `export.completed` | An export job finishes |
| `export.failed` | An export job fails |

### POST /webhooks

Create a new webhook.

**Request body**
```json
{
  "url": "https://your-service.example.com/webhook",
  "events": ["leaflet.completed", "product.reviewed"],
  "secret": "your-signing-secret-min-16-chars",
  "description": "Production notification endpoint",
  "retry_count": 3,
  "timeout_seconds": 30,
  "is_active": true
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `url` | string | Yes | HTTPS endpoint. Must not resolve to private/internal IPs (SSRF protection) |
| `events` | string[] | Yes | At least one event type from the table above |
| `secret` | string | No | Used for HMAC signing. Stored Fernet-encrypted. Min 16 chars |
| `description` | string | No | |
| `retry_count` | integer | No | `0`–`10`. Default `3` |
| `timeout_seconds` | integer | No | `5`–`120`. Default `30` |
| `is_active` | boolean | No | Default `true` |

**Response `201`**
```json
{
  "id": "a1b2c3d4-1111-2222-3333-444455556666",
  "url": "https://your-service.example.com/webhook",
  "events": ["leaflet.completed", "product.reviewed"],
  "description": "Production notification endpoint",
  "retry_count": 3,
  "timeout_seconds": 30,
  "is_active": true,
  "created_at": "2025-03-09T08:00:00Z",
  "updated_at": "2025-03-09T08:00:00Z"
}
```

Note: `secret` is not returned after creation. Use `GET /webhooks/{id}/secret` to retrieve it.

**Errors:** `422` invalid URL or SSRF-blocked address · `422` invalid event type

---

### GET /webhooks

List all webhooks for the current organization.

**Response `200`** — array of webhook objects (same shape as create response)

---

### GET /webhooks/events

List all available event type strings.

**Response `200`**
```json
{
  "events": [
    { "type": "leaflet.uploaded", "description": "A new leaflet is uploaded" },
    { "type": "leaflet.completed", "description": "Extraction completed successfully" }
  ]
}
```

---

### GET /webhooks/{webhook_id}

Get details for a single webhook.

**Response `200`** — webhook object

**Errors:** `404` not found

---

### GET /webhooks/{webhook_id}/secret

Retrieve the plaintext webhook secret. The secret is decrypted from Fernet storage on the fly.

**Response `200`**
```json
{ "secret": "your-signing-secret-min-16-chars" }
```

---

### PATCH /webhooks/{webhook_id}

Update webhook configuration. All fields optional.

**Request body** — subset of create body fields

**Response `200`** — updated webhook object

---

### DELETE /webhooks/{webhook_id}

Soft-delete the webhook. Delivery history is preserved for audit purposes.

**Response `204`** — no body

---

### POST /webhooks/{webhook_id}/test

Send a synthetic test event to the webhook endpoint and return the delivery result synchronously.

**Request body** (optional)
```json
{ "event_type": "leaflet.completed" }
```

**Response `200`**
```json
{
  "success": true,
  "status_code": 200,
  "response_body": "OK",
  "latency_ms": 142,
  "error": null
}
```

**Errors:** `404` not found · `422` webhook inactive

---

### GET /webhooks/{webhook_id}/deliveries

Paginated delivery history. Includes request/response payloads with sensitive headers redacted.

**Query parameters:** `page`, `page_size`

**Response `200`** — paginated, items are delivery records:
```json
{
  "items": [
    {
      "id": "d1e2f3a4-5678-9012-bcde-f01234567890",
      "webhook_id": "a1b2c3d4-1111-2222-3333-444455556666",
      "event_type": "leaflet.completed",
      "request_url": "https://your-service.example.com/webhook",
      "request_headers": { "Content-Type": "application/json", "X-LeafXtract-Signature": "[REDACTED]" },
      "request_body": "{ ... }",
      "response_status_code": 200,
      "response_headers": { "Content-Type": "text/plain" },
      "response_body": "OK",
      "duration_ms": 142,
      "attempt_number": 1,
      "succeeded": true,
      "error_message": null,
      "created_at": "2025-03-09T08:14:35Z"
    }
  ],
  "total": 48,
  "page": 1,
  "page_size": 20,
  "pages": 3,
  "has_next": true,
  "has_prev": false
}
```

---

### POST /webhooks/{webhook_id}/regenerate-secret

Generate and store a new signing secret, replacing the old one.

**Response `200`**
```json
{ "secret": "new-randomly-generated-secret-value" }
```

---

## 8. Organizations

### GET /organizations/

List organizations the current user belongs to.

**Response `200`** — array of organization objects:
```json
[
  {
    "id": "org-uuid",
    "name": "Whirlwind Technologies",
    "slug": "whirlwind-technologies",
    "role": "admin",
    "is_active": true,
    "created_at": "2025-01-15T10:00:00Z"
  }
]
```

---

### GET /organizations/current

Get the current organization's full details.

**Response `200`**
```json
{
  "id": "org-uuid",
  "name": "Whirlwind Technologies",
  "slug": "whirlwind-technologies",
  "email": "admin@wwindtech.com",
  "is_active": true,
  "settings": {},
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-06-01T08:00:00Z"
}
```

---

### PUT /organizations/current

Update organization settings. Admin or Owner role required.

**Request body**
```json
{
  "name": "Whirlwind Technologies LLC",
  "email": "billing@wwindtech.com"
}
```

**Response `200`** — updated organization object

---

### GET /organizations/current/platform-quota

Get the current organization's platform-shared VLM quota status.

**Response `200`**
```json
{
  "quota_limit": 10,
  "quota_used": 7,
  "quota_remaining": 3,
  "is_unlimited": false,
  "has_own_provider": false,
  "limit_reached": false
}
```

When `limit_reached` is `true`, extraction will be blocked until the org configures its own VLM provider. Set `quota_limit` to `0` via the admin endpoint for unlimited access.

---

### GET /organizations/current/members

List organization members.

**Query parameters:** `page`, `page_size`

**Response `200`** — paginated list of members:
```json
{
  "items": [
    {
      "id": "user-uuid",
      "email": "jane@example.com",
      "full_name": "Jane Smith",
      "role": "admin",
      "is_active": true,
      "joined_at": "2025-02-01T09:00:00Z"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "has_next": false,
  "has_prev": false
}
```

---

### POST /organizations/current/invitations

Invite a user to the organization by email. Admin or Owner role required.

**Request body**
```json
{
  "email": "newuser@example.com",
  "role": "member"
}
```

`role`: `member` · `admin` (Owner can invite any role; Admin can only invite members)

**Response `201`**
```json
{
  "id": "inv-uuid",
  "email": "newuser@example.com",
  "role": "member",
  "status": "pending",
  "expires_at": "2025-03-16T08:00:00Z",
  "created_at": "2025-03-09T08:00:00Z"
}
```

---

### POST /organizations/current/invitations/{invitation_id}/resend

Resend the invitation email. Subject to a resend cooldown tracked by `resend_count`.

**Response `200`**
```json
{ "message": "Invitation resent successfully" }
```

**Errors:** `404` not found · `422` invitation not in pending status · `429` resend too soon

---

### DELETE /organizations/current/invitations/{invitation_id}

Revoke a pending invitation.

**Response `204`** — no body

---

## 9. Retailers

### GET /retailers/

List all retailers for the current organization.

**Query parameters:** `page`, `page_size`, `search`

**Response `200`** — paginated list:
```json
{
  "items": [
    {
      "id": "ret-uuid",
      "name": "ALDI",
      "country": "SI",
      "website": "https://www.aldi.si",
      "leaflet_count": 42,
      "created_at": "2025-01-20T10:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "has_next": false,
  "has_prev": false
}
```

---

### POST /retailers/

Create a retailer.

**Request body**
```json
{
  "name": "LIDL",
  "country": "HR",
  "website": "https://www.lidl.hr",
  "default_language": "hr",
  "default_currency": "EUR"
}
```

**Response `201`** — created retailer object

**Errors:** `409` retailer name already exists in this org

---

### GET /retailers/{retailer_id}

Get retailer details.

**Response `200`** — retailer object

**Errors:** `404` not found

---

### PUT /retailers/{retailer_id}

Update retailer. All fields optional.

**Response `200`** — updated retailer object

---

### DELETE /retailers/{retailer_id}

Delete a retailer. Fails if the retailer has associated leaflets.

**Response `204`** — no body

**Errors:** `409` retailer has associated leaflets

---

## 10. VLM Providers

### GET /vlm-providers/types

List all supported provider types with their required configuration fields.

**Response `200`**
```json
{
  "providers": [
    {
      "type": "anthropic",
      "display_name": "Anthropic Claude",
      "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
      "required_fields": ["api_key"],
      "optional_fields": ["model", "max_tokens"]
    }
  ]
}
```

---

### POST /vlm-providers/

Create a VLM provider configuration for the current organization.

**Request body**
```json
{
  "provider_type": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-sonnet-4-20250514",
  "display_name": "Anthropic Production",
  "monthly_budget_limit": 100.00,
  "is_default": true
}
```

**Response `201`** — provider object (API key is not returned after creation)

**Errors:** `422` invalid provider type · `422` invalid API key (tested on creation)

---

### GET /vlm-providers/

List VLM provider configurations for the current organization.

**Response `200`** — array of provider objects

---

### GET /vlm-providers/default

Get the active default provider for the current organization.

**Response `200`** — provider object, or `404` if no provider configured

---

### GET /vlm-providers/status

Check connectivity and quota for the active VLM provider.

**Response `200`**
```json
{
  "provider_type": "anthropic",
  "status": "healthy",
  "model": "claude-sonnet-4-20250514",
  "monthly_budget_limit": 100.00,
  "monthly_spend": 34.72,
  "budget_remaining": 65.28,
  "budget_percentage_used": 34.7
}
```

---

### GET /vlm-providers/usage/costs

Query VLM cost breakdown with date range filtering and per-provider breakdown.

**Query parameters**

| Parameter | Type | Notes |
|-----------|------|-------|
| `period` | string | `last_7_days` · `this_month` · `last_month` · `this_year` · `all_time` |
| `start_date` | string | ISO 8601 date (used with `period=custom`) |
| `end_date` | string | ISO 8601 date |
| `granularity` | string | `day` · `week` · `month` |

**Response `200`**
```json
{
  "period": "this_month",
  "start_date": "2025-03-01",
  "end_date": "2025-03-31",
  "total_cost": 34.72,
  "total_input_tokens": 18420000,
  "total_output_tokens": 3280000,
  "providers": [
    {
      "provider_type": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "cost": 34.72,
      "input_tokens": 18420000,
      "output_tokens": 3280000,
      "percentage_of_total": 100.0
    }
  ],
  "timeline": [
    { "date": "2025-03-01", "cost": 3.14, "requests": 12 },
    { "date": "2025-03-02", "cost": 4.22, "requests": 16 }
  ]
}
```

All cost values use `Numeric(10,4)` precision in the database; returned as decimals.

---

### GET /vlm-providers/{provider_id}

Get a single provider configuration.

**Response `200`** — provider object

**Errors:** `404` not found

---

### PATCH /vlm-providers/{provider_id}

Update provider configuration. All fields optional.

**Request body**
```json
{
  "model": "claude-opus-4-20250514",
  "monthly_budget_limit": 200.00
}
```

**Response `200`** — updated provider object

---

### PUT /vlm-providers/{provider_id}/set-default

Set a provider as the organization's default.

**Response `200`** — updated provider object

---

### DELETE /vlm-providers/{provider_id}

Delete a provider configuration.

**Response `204`** — no body

**Errors:** `422` cannot delete the only active provider

---

### POST /vlm-providers/{provider_id}/test

Send a minimal test request to the provider to verify credentials and connectivity.

**Response `200`**
```json
{
  "success": true,
  "provider_type": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "latency_ms": 824,
  "error": null
}
```

---

## 11. API Keys

API keys allow B2B clients and scripts to authenticate without a user session.

### POST /users/me/api-keys

Create a new API key for the current user.

**Request body**
```json
{
  "name": "CI Pipeline Key",
  "description": "Used by GitHub Actions for automated uploads",
  "expires_at": "2026-01-01T00:00:00Z",
  "rate_limit_per_minute": 60
}
```

**Response `201`**
```json
{
  "id": "key-uuid",
  "name": "CI Pipeline Key",
  "key": "lxt_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "prefix": "lxt_live_xxxx",
  "expires_at": "2026-01-01T00:00:00Z",
  "created_at": "2025-03-09T08:00:00Z"
}
```

**Important:** The `key` value is only returned once at creation. Store it securely.

---

### GET /users/me/api-keys

List API keys for the current user. The full key value is never returned in list responses.

**Response `200`** — array of key objects (without `key` field)

---

### DELETE /users/me/api-keys/{key_id}

Revoke an API key immediately.

**Response `204`** — no body

---

## 12. Users

### GET /users/me

Get the current authenticated user's profile.

**Response `200`**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "full_name": "Jane Smith",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-06-01T08:00:00Z"
}
```

---

### PUT /users/me

Update the current user's profile.

**Request body**
```json
{
  "full_name": "Jane A. Smith",
  "email": "jane.new@example.com"
}
```

**Response `200`** — updated user object

---

### POST /auth/change-password

Change the current user's password.

**Request body**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

**Response `200`**
```json
{ "message": "Password changed successfully" }
```

**Errors:** `401` incorrect current password

---

## 13. WebSocket

Connect to receive real-time extraction progress events.

### WS /ws/leaflets/{leaflet_id}/progress

```
ws://localhost:8000/ws/leaflets/LEAF_2025_A3F2B1/progress?token=<access_token>
```

Pass the JWT access token as a `token` query parameter.

**Messages received** — JSON objects:

```json
{ "event": "page_started", "page": 3, "total": 16 }
```

```json
{
  "event": "page_completed",
  "page": 3,
  "total": 16,
  "products_found": 9,
  "progress": 0.1875
}
```

```json
{
  "event": "extraction_completed",
  "leaflet_id": "LEAF_2025_A3F2B1",
  "total_products": 142,
  "auto_approved": 128,
  "review_required": 14
}
```

```json
{
  "event": "extraction_failed",
  "leaflet_id": "LEAF_2025_A3F2B1",
  "error": "VLM provider rate limit exceeded"
}
```

```json
{
  "event": "PLATFORM_LIMIT_REACHED",
  "message": "Your organization has used all 10 free extractions.",
  "cta_url": "/settings/providers"
}
```

The connection closes automatically when the leaflet reaches `completed` or `failed` status.

---

## 14. Health

### GET /health

Basic liveness check. No authentication required.

**Response `200`**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "database": "connected",
  "redis": "connected",
  "timestamp": 1741514400.0
}
```

---

### GET /api/v1/admin/system/health

Detailed component health with latency measurements. Requires authentication and admin role.

**Response `200`**
```json
{
  "overall_status": "healthy",
  "components": [
    { "name": "PostgreSQL Database", "status": "healthy", "latency_ms": 5 },
    { "name": "Redis Cache",         "status": "healthy", "latency_ms": 2 },
    { "name": "S3 Storage",          "status": "healthy", "latency_ms": 148 },
    {
      "name": "Celery Workers",
      "status": "healthy",
      "details": { "active_workers": 4, "queued_tasks": 2 }
    }
  ]
}
```

`overall_status` is `healthy` only if all components report healthy. Any degraded component sets it to `degraded`; any down component sets it to `unhealthy`.