# Leaflet Extraction Platform -- API Endpoint Reference

> **Base URL:** `{domain}/api/v1`
>
> **Generated:** 2026-02-24 | **API Version:** v1

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Leaflets](#2-leaflets)
3. [Products](#3-products)
4. [Product Export](#4-product-export)
5. [Leaflet Export (Legacy)](#5-leaflet-export-legacy)
6. [Webhooks](#6-webhooks)
7. [API Keys](#7-api-keys)
8. [VLM Providers](#8-vlm-providers)
9. [Analytics](#9-analytics)
10. [Retailers](#10-retailers)
11. [Categories](#11-categories)
12. [Organizations](#12-organizations)
13. [Notifications](#13-notifications)
14. [Business Registration](#14-business-registration)
15. [Invitations](#15-invitations)
16. [Contact](#16-contact)
17. [WebSocket](#17-websocket)
18. [Error Handling](#18-error-handling)
19. [Webhook Events](#19-webhook-events)
20. [Rate Limiting](#20-rate-limiting)

---

## Authentication Types

| Label | Header | Description |
|-------|--------|-------------|
| **jwt** | `Authorization: Bearer <token>` | Web application users (JWT access token) |
| **api_key** | `X-API-Key: <key>` | B2B integrations (Fernet-encrypted API key) |
| **both** | Either of the above | Accepts JWT or API key |
| **public** | None | No authentication required |

---

## 1. Authentication

Base path: `/api/v1/auth`

### POST /auth/register

Register a new personal user account. Account requires admin approval before login.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Rate Limited** | Yes |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Jane Doe"
}
```

**Response:**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": false,
  "is_verified": false,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Examples:**

```bash
# curl
curl -X POST {domain}/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!","full_name":"Jane Doe"}'
```

```python
# Python (requests)
import requests

response = requests.post(
    f"{domain}/api/v1/auth/register",
    json={
        "email": "user@example.com",
        "password": "SecurePass123!",
        "full_name": "Jane Doe",
    },
)
data = response.json()
```

```javascript
// JavaScript (fetch)
const response = await fetch(`${domain}/api/v1/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    email: "user@example.com",
    password: "SecurePass123!",
    full_name: "Jane Doe",
  }),
});
const data = await response.json();
```

---

### POST /auth/register/business

Register a new business account with organization. Requires admin approval.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Rate Limited** | Yes |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "email": "admin@company.com",
  "password": "SecurePass123!",
  "full_name": "Jane Doe",
  "company_name": "Acme Corp",
  "company_size": "10-50"
}
```

---

### POST /auth/login

Authenticate and receive access + refresh tokens.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Rate Limited** | Yes |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

**Examples:**

```bash
# curl
curl -X POST {domain}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'
```

```python
# Python
response = requests.post(
    f"{domain}/api/v1/auth/login",
    json={"email": "user@example.com", "password": "SecurePass123!"},
)
tokens = response.json()
access_token = tokens["access_token"]
```

```javascript
// JavaScript
const response = await fetch(`${domain}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "user@example.com", password: "SecurePass123!" }),
});
const { access_token, refresh_token } = await response.json();
```

---

### POST /auth/refresh

Refresh an expired access token using the refresh token.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Rate Limited** | Yes |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

---

### GET /auth/me

Get the currently authenticated user's profile.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Response:**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Examples:**

```bash
curl {domain}/api/v1/auth/me \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

```python
response = requests.get(
    f"{domain}/api/v1/auth/me",
    headers={"Authorization": f"Bearer {access_token}"},
)
```

```javascript
const response = await fetch(`${domain}/api/v1/auth/me`, {
  headers: { Authorization: `Bearer ${accessToken}` },
});
```

---

### POST /auth/logout

Invalidate the current session.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /auth/change-password

Change the authenticated user's password.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "current_password": "OldPass123!",
  "new_password": "NewSecure456!"
}
```

---

### POST /auth/password-reset

Request a password reset email.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `202 Accepted` |

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

---

### POST /auth/password-reset/confirm

Complete password reset with token from email.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "token": "reset-token-from-email",
  "new_password": "NewSecure456!"
}
```

---

### POST /auth/forgot-password

Alias for `/auth/password-reset`.

---

### POST /auth/reset-password

Alias for `/auth/password-reset/confirm`.

---

## 2. Leaflets

Base path: `/api/v1/leaflets`

All leaflet endpoints accept **both** JWT and API key authentication.

### POST /leaflets/upload

Upload a PDF leaflet for extraction.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Rate Limited** | Yes (10/60s upload limit) |
| **Status** | `201 Created` |
| **Content-Type** | `multipart/form-data` |

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | PDF file (max 100MB) |
| `retailer_name` | string | No | Retailer name for context |
| `country` | string | No | Country code (e.g., SI, HR) |
| `currency` | string | No | Currency code (e.g., EUR) |
| `auto_extract` | boolean | No | Start extraction immediately (default: true) |

**Response:**

```json
{
  "id": "uuid",
  "leaflet_id": "LEAF_2025_000123",
  "status": "uploaded",
  "filename": "promo-leaflet.pdf",
  "page_count": null,
  "retailer_name": "Mercator",
  "country": "SI",
  "currency": "EUR",
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Examples:**

```bash
# curl
curl -X POST {domain}/api/v1/leaflets/upload \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@leaflet.pdf" \
  -F "retailer_name=Mercator" \
  -F "country=SI"
```

```python
# Python
with open("leaflet.pdf", "rb") as f:
    response = requests.post(
        f"{domain}/api/v1/leaflets/upload",
        headers={"Authorization": f"Bearer {access_token}"},
        files={"file": ("leaflet.pdf", f, "application/pdf")},
        data={"retailer_name": "Mercator", "country": "SI"},
    )
```

```javascript
// JavaScript
const formData = new FormData();
formData.append("file", pdfFile);
formData.append("retailer_name", "Mercator");

const response = await fetch(`${domain}/api/v1/leaflets/upload`, {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: formData,
});
```

---

### POST /leaflets/upload/images

Upload pre-rendered page images instead of a PDF.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `201 Created` |
| **Content-Type** | `multipart/form-data` |

---

### POST /leaflets/upload/bulk

Upload multiple PDF leaflets in a single request.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `201 Created` |
| **Content-Type** | `multipart/form-data` |

---

### GET /leaflets

List leaflets with pagination and filtering.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number (min: 1) |
| `page_size` | int | 50 | Items per page (1-200) |
| `status` | string | null | Filter by status |
| `retailer_name` | string | null | Filter by retailer |
| `search` | string | null | Search filename or ID |
| `sort_by` | string | created_at | Sort field |
| `sort_order` | string | desc | Sort direction (asc/desc) |

**Response:**

```json
{
  "items": [
    {
      "id": "uuid",
      "leaflet_id": "LEAF_2025_000123",
      "status": "completed",
      "filename": "promo.pdf",
      "page_count": 12,
      "product_count": 48,
      "auto_approved_count": 38,
      "review_required_count": 10,
      "retailer_name": "Mercator",
      "created_at": "2026-01-15T10:30:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

**Examples:**

```bash
curl "{domain}/api/v1/leaflets?page=1&page_size=20&status=completed" \
  -H "X-API-Key: ${API_KEY}"
```

```python
response = requests.get(
    f"{domain}/api/v1/leaflets",
    headers={"X-API-Key": api_key},
    params={"page": 1, "page_size": 20, "status": "completed"},
)
```

```javascript
const params = new URLSearchParams({ page: "1", page_size: "20", status: "completed" });
const response = await fetch(`${domain}/api/v1/leaflets?${params}`, {
  headers: { "X-API-Key": apiKey },
});
```

---

### GET /leaflets/{leaflet_id}

Get detailed information about a specific leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaflet_id` | UUID | Leaflet UUID |

**Response:** Full leaflet object including page details, progress, and extraction stats.

---

### PUT /leaflets/{leaflet_id}

Update leaflet metadata (retailer, country, currency).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### DELETE /leaflets/{leaflet_id}

Delete a leaflet and all associated data.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `204 No Content` |

---

### GET /leaflets/{leaflet_id}/status

Get the current processing status and progress of a leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Response:**

```json
{
  "id": "uuid",
  "status": "extracting",
  "progress": 0.45,
  "current_step": "Extracting page 5 of 12",
  "auto_approved_count": 20,
  "review_required_count": 5
}
```

---

### GET /leaflets/{leaflet_id}/pages

Get page images and thumbnails for a leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /leaflets/{leaflet_id}/extract

Start or restart product extraction for a leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /leaflets/{leaflet_id}/extract-images

Start product image extraction (cropping) for a leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /leaflets/{leaflet_id}/reprocess

Reprocess a leaflet from scratch (PDF -> extraction).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### DELETE /leaflets/{leaflet_id}/extraction

Delete all extracted products for a leaflet while keeping the PDF and pages. Allows re-extraction.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### GET /leaflets/{leaflet_id}/diagnostic

Get diagnostic information about a leaflet extraction.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

## 3. Products

Base path: `/api/v1/products`

All product endpoints accept **both** JWT and API key authentication.

### GET /products

List products with filtering, search, and pagination.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Items per page (1-200) |
| `leaflet_id` | UUID | null | Filter by leaflet |
| `review_status` | string | null | Filter: auto_approved, pending, approved, rejected |
| `search` | string | null | Search product name, brand, code |
| `brand` | string | null | Filter by brand |
| `category_id` | UUID | null | Filter by category |
| `min_price` | float | null | Minimum regular price |
| `max_price` | float | null | Maximum regular price |
| `has_discount` | boolean | null | Filter products with/without discount |
| `sort_by` | string | created_at | Sort field |
| `sort_order` | string | desc | Sort direction |

**Response:**

```json
{
  "items": [
    {
      "id": "uuid",
      "leaflet_id": "uuid",
      "product_name": "Alpsko Mleko 1L",
      "brand": "Ljubljanske mlekarne",
      "product_code": "LM-001",
      "regular_price": 1.29,
      "discounted_price": 0.99,
      "discount_percentage": 23.26,
      "currency": "EUR",
      "review_status": "auto_approved",
      "confidence": 0.95,
      "page_number": 3
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

**Examples:**

```bash
curl "{domain}/api/v1/products?leaflet_id=${LEAFLET_ID}&review_status=pending&page_size=20" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

```python
response = requests.get(
    f"{domain}/api/v1/products",
    headers={"Authorization": f"Bearer {access_token}"},
    params={"leaflet_id": leaflet_id, "review_status": "pending"},
)
products = response.json()["items"]
```

```javascript
const params = new URLSearchParams({ leaflet_id: leafletId, review_status: "pending" });
const response = await fetch(`${domain}/api/v1/products?${params}`, {
  headers: { Authorization: `Bearer ${accessToken}` },
});
```

---

### GET /products/stats

Get aggregate product statistics for the current organization.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Response:**

```json
{
  "total_products": 1500,
  "auto_approved": 1100,
  "pending_review": 250,
  "approved": 120,
  "rejected": 30,
  "avg_confidence": 0.92
}
```

---

### GET /products/review-queue

Get products queued for human review, sorted by review priority.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Query Parameters:** Same as GET /products, plus:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_confidence` | float | null | Minimum confidence score |
| `max_confidence` | float | null | Maximum confidence score |
| `has_validation_errors` | boolean | null | Products with validation issues |

---

### GET /products/categories

Get distinct category values used across products.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /products/batch

Fetch multiple products by ID in a single request (max 20).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "product_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

---

### GET /products/{product_id}

Get full details for a single product including image data and field confidence scores.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Response:**

```json
{
  "id": "uuid",
  "leaflet_id": "uuid",
  "page_number": 3,
  "brand": "Ljubljanske mlekarne",
  "product_code": "LM-001",
  "product_name": "Alpsko Mleko 1L",
  "quantity": "1",
  "units": "L",
  "size": "1L",
  "regular_price": 1.29,
  "discounted_price": 0.99,
  "discount_percentage": 23.26,
  "currency": "EUR",
  "product_id": "3831234567890",
  "promotional_info": "25% off this week",
  "confidence": 0.95,
  "field_confidence": {
    "product_name": 0.98,
    "regular_price": 0.95,
    "discount_percentage": 0.96
  },
  "review_status": "auto_approved",
  "validation_passed": true,
  "validation_errors": [],
  "bounding_box": {"x": 100, "y": 200, "width": 300, "height": 400},
  "image_url": "https://s3.example.com/product.jpg?...",
  "created_at": "2026-01-15T10:30:00Z"
}
```

---

### PUT /products/{product_id}

Update product data (during review).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Request Body:** Partial product update -- only include fields to change.

```json
{
  "product_name": "Corrected Product Name",
  "regular_price": 1.49,
  "discounted_price": 1.09
}
```

---

### POST /products/{product_id}/review

Submit a review decision for a product.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "status": "approved",
  "notes": "Verified price against original"
}
```

**Allowed statuses:** `approved`, `rejected`

---

### POST /products/batch-review

Submit review decisions for multiple products at once (max 100).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "reviews": [
    {"product_id": "uuid-1", "status": "approved"},
    {"product_id": "uuid-2", "status": "rejected", "notes": "Wrong price"}
  ]
}
```

---

### POST /products/{product_id}/refresh-image-url

Refresh an expired presigned image URL for a product.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /products/{product_id}/re-extract-image

Re-extract the product image from the page using updated bounding box.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### GET /products/{product_id}/reviews

Get the review history for a product.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

## 4. Product Export

Base path: `/api/v1/products/export`

Cross-leaflet product export system with sync/async support.

### POST /products/export/preview

Preview an export -- returns product count and estimated file size without generating the file.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "format": "csv",
  "mode": "filtered",
  "filters": {
    "review_status": "approved",
    "has_discount": true
  }
}
```

**Response:**

```json
{
  "product_count": 850,
  "leaflet_count": 15,
  "estimated_file_size": 245000
}
```

---

### POST /products/export

Create an export. For <1000 products, returns a streaming file immediately. For >=1000 products, creates an async job.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` (sync) or `202 Accepted` (async) |

**Request Body:**

```json
{
  "format": "csv",
  "mode": "filtered",
  "filters": {
    "review_status": "approved"
  },
  "include_images": false
}
```

**Modes:** `all`, `filtered`, `selected`, `review_queue`

**Formats:** `csv`, `excel`, `json`

**Sync Response (< 1000 products):** Returns file as StreamingResponse.

**Async Response (>= 1000 products):**

```json
{
  "export_id": "uuid",
  "status": "pending",
  "product_count": 2500,
  "message": "Export job created. Poll status endpoint for progress."
}
```

---

### GET /products/export/{export_id}/status

Check the status of an async export job.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Response:**

```json
{
  "export_id": "uuid",
  "status": "completed",
  "progress": 1.0,
  "product_count": 2500,
  "file_size": 524288,
  "created_at": "2026-01-15T10:30:00Z",
  "completed_at": "2026-01-15T10:31:15Z",
  "expires_at": "2026-01-16T10:31:15Z"
}
```

**Statuses:** `pending`, `processing`, `completed`, `failed`

---

### GET /products/export/{export_id}/download

Download a completed export file. Returns a presigned URL (1 hour expiry).

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Response:**

```json
{
  "download_url": "https://s3.example.com/exports/...",
  "filename": "products-export-20260115.csv",
  "file_size": 524288,
  "expires_at": "2026-01-15T11:31:15Z"
}
```

---

## 5. Leaflet Export (Legacy)

Base path: `/api/v1/export`

Single-leaflet export. For cross-leaflet exports, use the Product Export endpoints above.

### GET /export/{leaflet_id}

Export all products from a single leaflet.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | json | Export format: csv, excel, json |
| `image_storage` | string | url | Image handling: base64, url, both |

---

### GET /export/{leaflet_id}/json

Export a leaflet's products as JSON.

---

### GET /export/{leaflet_id}/csv

Export a leaflet's products as CSV.

---

## 6. Webhooks

Base path: `/api/v1/webhooks`

Configure webhook endpoints to receive real-time event notifications.

### POST /webhooks

Create a new webhook endpoint.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "url": "https://yourapp.example.com/webhooks/leaflet",
  "events": ["leaflet.processing.completed", "product.approved"],
  "description": "Production webhook",
  "is_active": true
}
```

**Response:**

```json
{
  "id": "uuid",
  "url": "https://yourapp.example.com/webhooks/leaflet",
  "events": ["leaflet.processing.completed", "product.approved"],
  "description": "Production webhook",
  "is_active": true,
  "secret": "whsec_...",
  "failure_count": 0,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**Examples:**

```bash
curl -X POST {domain}/api/v1/webhooks \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://yourapp.example.com/webhooks/leaflet",
    "events": ["leaflet.processing.completed"],
    "description": "Production webhook"
  }'
```

```python
response = requests.post(
    f"{domain}/api/v1/webhooks",
    headers={"Authorization": f"Bearer {access_token}"},
    json={
        "url": "https://yourapp.example.com/webhooks/leaflet",
        "events": ["leaflet.processing.completed"],
    },
)
webhook = response.json()
```

---

### GET /webhooks

List all configured webhooks.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /webhooks/events

List all available webhook event types. No authentication required.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

---

### GET /webhooks/{webhook_id}

Get details for a specific webhook.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /webhooks/{webhook_id}/secret

Retrieve the webhook signing secret. Use this to verify payload signatures.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PATCH /webhooks/{webhook_id}

Partially update a webhook configuration.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PUT /webhooks/{webhook_id}

Fully replace a webhook configuration.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### DELETE /webhooks/{webhook_id}

Delete a webhook (soft delete).

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `204 No Content` |

---

### POST /webhooks/{webhook_id}/test

Send a test webhook delivery.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /webhooks/{webhook_id}/regenerate-secret

Generate a new signing secret for a webhook.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /webhooks/{webhook_id}/deliveries

Get delivery history for a webhook with pagination.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page |
| `status` | string | null | Filter: success, failed |

---

### GET /webhooks/stats/summary

Get aggregate statistics across all webhooks.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

## 7. API Keys

Base path: `/api/v1/api-keys`

Manage API keys for programmatic access (B2B integrations).

### POST /api-keys

Create a new API key. The key value is only returned once at creation time.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "name": "Production Integration",
  "expires_at": "2027-01-15T00:00:00Z"
}
```

**Response:**

```json
{
  "id": "uuid",
  "name": "Production Integration",
  "key": "lxk_abc123def456...",
  "prefix": "lxk_abc1",
  "created_at": "2026-01-15T10:30:00Z",
  "expires_at": "2027-01-15T00:00:00Z"
}
```

> **Important:** The `key` field is only returned at creation time. Store it securely.

---

### GET /api-keys

List all API keys for the authenticated user.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /api-keys/{key_id}

Get details for a specific API key (excludes the key value).

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /api-keys/{key_id}/stats

Get usage statistics for an API key.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PATCH /api-keys/{key_id}

Update an API key's name or expiry.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### DELETE /api-keys/{key_id}

Revoke an API key.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `204 No Content` |

---

### POST /api-keys/{key_id}/regenerate

Regenerate the API key value. Invalidates the previous key.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /api-keys/test

Test an API key's validity. Authenticates via the `X-API-Key` header.

| Property | Value |
|----------|-------|
| **Auth** | api_key |
| **Status** | `200 OK` |

---

## 8. VLM Providers

Base path: `/api/v1/vlm-providers`

Configure VLM (Vision-Language Model) providers for product extraction.

### GET /vlm-providers/types

Get a list of supported VLM provider types and their available models.

| Property | Value |
|----------|-------|
| **Auth** | public (requires DB) |
| **Status** | `200 OK` |

**Response:**

```json
[
  {
    "provider_type": "anthropic",
    "display_name": "Anthropic Claude",
    "models": [
      {"model_id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"}
    ]
  }
]
```

---

### POST /vlm-providers

Add a new VLM provider with your own API key.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "name": "My Claude Provider",
  "provider_type": "anthropic",
  "model_name": "claude-sonnet-4-20250514",
  "api_key": "sk-ant-...",
  "monthly_budget": 100.00,
  "is_active": true
}
```

---

### GET /vlm-providers

List all VLM providers for the authenticated user.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /vlm-providers/default

Get the default VLM provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /vlm-providers/status

Get an overview of all provider statuses.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /vlm-providers/usage/stats

Get aggregated VLM usage statistics.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /vlm-providers/usage/costs

Get detailed cost breakdown by provider and time period.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | current_month | Time period: current_month, last_month, last_30_days, last_90_days, custom |
| `start_date` | string | null | Start date (YYYY-MM-DD) for custom period |
| `end_date` | string | null | End date (YYYY-MM-DD) for custom period |
| `group_by` | string | daily | Grouping: daily, weekly, monthly |

---

### GET /vlm-providers/{provider_id}

Get details for a specific provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /vlm-providers/{provider_id}/stats

Get usage stats for a specific provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PATCH /vlm-providers/{provider_id}

Update a VLM provider configuration.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PUT /vlm-providers/{provider_id}/default

Set a provider as the default.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### DELETE /vlm-providers/{provider_id}

Delete a VLM provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `204 No Content` |

---

### POST /vlm-providers/{provider_id}/test

Test connectivity to a VLM provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /vlm-providers/{provider_id}/reset-monthly

Reset the monthly usage counters for a provider.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

## 9. Analytics

Base path: `/api/v1/analytics`

### GET /analytics/summary

Get a summary of extraction analytics for a date range.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | string | null | Start date (YYYY-MM-DD) |
| `end_date` | string | null | End date (YYYY-MM-DD) |

---

### GET /analytics/dashboard

Get dashboard metrics.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/costs

Get cost analytics.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/quality

Get extraction quality metrics (accuracy, confidence distribution).

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/usage

Get usage analytics.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/trends/leaflets

Get leaflet processing trends over time.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/trends/products

Get product extraction trends over time.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/trends/costs

Get cost trends over time.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/exports

Get export analytics.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /analytics/top-retailers

Get top retailers by volume or cost.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

## 10. Retailers

Base path: `/api/v1/retailers`

### GET /retailers

List all retailers.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /retailers

Create a new retailer.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "name": "Mercator",
  "country": "SI",
  "currency": "EUR"
}
```

---

### GET /retailers/{retailer_id}

Get retailer details.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PUT /retailers/{retailer_id}

Update a retailer.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### DELETE /retailers/{retailer_id}

Delete a retailer.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `204 No Content` |

---

## 11. Categories

Base path: `/api/v1/categories`

Product categories used for classification. Write operations require superuser.

### GET /categories

List all product categories.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Items per page |
| `search` | string | null | Search by name |
| `parent_id` | UUID | null | Filter by parent category |

---

### GET /categories/{category_id}

Get a specific category.

| Property | Value |
|----------|-------|
| **Auth** | both |
| **Status** | `200 OK` |

---

### POST /categories

Create a new category (superuser only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (superuser) |
| **Status** | `201 Created` |

---

### PATCH /categories/{category_id}

Update a category (superuser only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (superuser) |
| **Status** | `200 OK` |

---

### DELETE /categories/{category_id}

Delete a category (superuser only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (superuser) |
| **Status** | `204 No Content` |

---

### POST /categories/reload

Reload categories from the seed CSV (superuser only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (superuser) |
| **Status** | `200 OK` |

---

## 12. Organizations

Base path: `/api/v1/organizations`

### GET /organizations

List organizations the authenticated user belongs to.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /organizations/current/platform-quota

Get the current organization's platform AI provider usage quota.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Response:**

```json
{
  "platform_leaflet_limit": 10,
  "platform_leaflets_used": 3,
  "remaining": 7,
  "is_unlimited": false
}
```

---

### GET /organizations/{org_id}

Get details for a specific organization.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PUT /organizations/{org_id}

Update organization details (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### POST /organizations/{org_id}/switch

Switch the active organization context.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /organizations/{org_id}/deletion-request

Request deletion of an organization (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### GET /organizations/{org_id}/members

List members of an organization.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /organizations/{org_id}/members

Add a member to the organization (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `201 Created` |

---

### PUT /organizations/{org_id}/members/{user_id}

Update a member's role (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### DELETE /organizations/{org_id}/members/{user_id}

Remove a member from the organization (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### GET /organizations/{org_id}/invitations

List pending invitations for an organization (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### POST /organizations/{org_id}/invitations

Send an invitation to join the organization (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "email": "newmember@example.com",
  "role": "member"
}
```

---

### DELETE /organizations/{org_id}/invitations/{invitation_id}

Revoke a pending invitation (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

### POST /organizations/{org_id}/invitations/{invitation_id}/resend

Resend an invitation email (admin/owner only).

| Property | Value |
|----------|-------|
| **Auth** | jwt (org admin/owner) |
| **Status** | `200 OK` |

---

## 13. Notifications

Base path: `/api/v1/notifications`

### GET /notifications

List notifications for the authenticated user.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page |

---

### GET /notifications/unread-count

Get the count of unread notifications.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

**Response:**

```json
{
  "unread_count": 5
}
```

---

### POST /notifications/mark-all-read

Mark all notifications as read.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /notifications/preferences

Get notification preferences.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### PUT /notifications/preferences

Update notification preferences.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### GET /notifications/types

Get available notification types.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /notifications/{notification_id}/read

Mark a specific notification as read.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

### POST /notifications/{notification_id}/dismiss

Dismiss a notification.

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

## 14. Business Registration

Base path: `/api/v1/registrations`

Public endpoints for business registration workflow.

### POST /registrations

Register a new business organization. Creates org + user, pending admin approval.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `201 Created` |

**Request Body:**

```json
{
  "organization_name": "Acme Corp",
  "user_email": "admin@acme.com",
  "user_password": "SecurePass123!",
  "user_full_name": "Jane Doe",
  "business_name": "Acme Corporation d.o.o.",
  "business_email": "info@acme.com",
  "business_phone": "+386 1 234 5678",
  "business_address": "Ljubljana, Slovenia",
  "tax_id": "SI12345678"
}
```

**Response:**

```json
{
  "registration_id": "uuid",
  "status": "pending_approval",
  "message": "Registration submitted successfully...",
  "organization_name": "Acme Corp",
  "created_at": "2026-01-15T10:30:00Z"
}
```

---

### GET /registrations/{registration_id}/status

Check the status of a business registration.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

**Response:**

```json
{
  "registration_id": "uuid",
  "organization_name": "Acme Corp",
  "status": "pending_approval",
  "submitted_at": "2026-01-15T10:30:00Z",
  "approved_at": null,
  "rejection_reason": null
}
```

---

### POST /registrations/invitations/accept

Accept an organization invitation using a token (legacy path -- prefer `/invitations/{token}/accept`).

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

---

## 15. Invitations

Base path: `/api/v1/invitations`

Public endpoints for accepting organization invitations.

### GET /invitations/{token}

Get invitation details without accepting it.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

**Response:**

```json
{
  "email": "newmember@example.com",
  "organization_name": "Acme Corp",
  "organization_type": "business",
  "role": "member",
  "expires_at": "2026-01-22T10:30:00Z",
  "user_exists": false
}
```

---

### POST /invitations/{token}/accept

Accept an invitation and join the organization. Creates a new user account if one does not exist.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Status** | `200 OK` |

**Request Body (new user):**

```json
{
  "full_name": "New Member",
  "password": "SecurePass123!"
}
```

**Request Body (existing user):** Empty body is acceptable.

**Response:**

```json
{
  "organization_id": "uuid",
  "organization_name": "Acme Corp",
  "role": "member",
  "message": "Successfully joined Acme Corp!",
  "is_new_user": true
}
```

---

## 16. Contact

Base path: `/api/v1/contact`

### POST /contact

Submit a contact form message. Public endpoint with multi-layer spam protection.

| Property | Value |
|----------|-------|
| **Auth** | public |
| **Rate Limited** | Yes (per-email, per-IP, global) |
| **Status** | `200 OK` |

**Request Body:**

```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "message": "I'd like to learn more about the platform.",
  "website": "",
  "timestamp": 1708700000.0,
  "recaptcha_token": "optional-recaptcha-token"
}
```

> **Note:** The `website` field is a honeypot. If filled, the request is silently accepted but not processed.

---

## 17. WebSocket

Base path: `/api/v1/ws`

WebSocket connections for real-time updates. Authentication is provided via the `token` query parameter.

### WS /ws/progress/{leaflet_id}

Subscribe to real-time extraction progress for a specific leaflet.

| Property | Value |
|----------|-------|
| **Auth** | jwt (via `?token=<jwt>` query param) |
| **Protocol** | WebSocket |

**Connection URL:**

```
wss://{domain}/api/v1/ws/progress/{leaflet_id}?token={access_token}
```

**Message Format:**

All WebSocket messages follow this structure:

```json
{
  "type": "extraction_progress",
  "leaflet_id": "uuid",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": {
    "page_number": 5,
    "total_pages": 12,
    "products_found": 8,
    "progress": 0.42
  }
}
```

**Message Types:**

| Type | Description |
|------|-------------|
| `extraction_progress` | Page-by-page extraction update |
| `extraction_complete` | Extraction finished with summary |
| `extraction_error` | Error during extraction |
| `validation_complete` | Validation results available |
| `image_extraction_progress` | Product image cropping progress |
| `status_change` | Leaflet status transition |

**Example (JavaScript):**

```javascript
const ws = new WebSocket(
  `wss://${domain}/api/v1/ws/progress/${leafletId}?token=${accessToken}`
);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  switch (message.type) {
    case "extraction_progress":
      console.log(`Page ${message.data.page_number}/${message.data.total_pages}`);
      break;
    case "extraction_complete":
      console.log(`Done! ${message.data.total_products} products extracted`);
      break;
    case "extraction_error":
      console.error(`Error: ${message.data.error_message}`);
      break;
  }
};
```

---

### WS /ws/progress

Subscribe to progress updates for all leaflets (multi-leaflet stream).

| Property | Value |
|----------|-------|
| **Auth** | jwt (via `?token=<jwt>` query param) |
| **Protocol** | WebSocket |

---

### WS /ws/notifications/{user_id}

Subscribe to real-time notifications.

| Property | Value |
|----------|-------|
| **Auth** | jwt (via `?token=<jwt>` query param) |
| **Protocol** | WebSocket |

---

### GET /ws/progress/{leaflet_id}/latest

Get the latest progress snapshot (HTTP fallback for WebSocket).

| Property | Value |
|----------|-------|
| **Auth** | jwt |
| **Status** | `200 OK` |

---

## 18. Error Handling

All API errors follow a consistent structure:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "errors": [
      {
        "field": "regular_price",
        "message": "Price must be positive"
      }
    ]
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Input validation failed |
| `NOT_FOUND` | 404 | Resource does not exist |
| `AUTHENTICATION_ERROR` | 401 | Missing or invalid authentication |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `DUPLICATE_ERROR` | 409 | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `PROCESSING_ERROR` | 500 | Internal processing failure |
| `STORAGE_ERROR` | 500 | File storage operation failed |
| `EXTERNAL_API_ERROR` | 502 | External VLM provider failure |
| `CONFIGURATION_ERROR` | 500 | System misconfiguration |
| `PLATFORM_LIMIT_REACHED` | 403 | Organization platform AI quota exhausted |

### Handling Errors

```python
# Python
response = requests.get(f"{domain}/api/v1/leaflets/{leaflet_id}", headers=headers)

if response.status_code == 404:
    error = response.json()["detail"]
    print(f"Error: {error['message']}")  # "Leaflet not found"
elif response.status_code == 401:
    # Token expired -- refresh and retry
    pass
elif response.status_code == 429:
    # Rate limited -- wait and retry
    retry_after = response.headers.get("Retry-After", "60")
    time.sleep(int(retry_after))
```

```javascript
// JavaScript
try {
  const response = await fetch(`${domain}/api/v1/leaflets/${leafletId}`, { headers });

  if (!response.ok) {
    const { detail } = await response.json();
    switch (detail.code) {
      case "NOT_FOUND":
        console.error(`Not found: ${detail.message}`);
        break;
      case "RATE_LIMIT_EXCEEDED":
        await new Promise((r) => setTimeout(r, 60000));
        break;
      default:
        console.error(`API Error: ${detail.code} - ${detail.message}`);
    }
  }
} catch (error) {
  console.error("Network error:", error);
}
```

---

## 19. Webhook Events

When configured, the platform sends HTTP POST requests to your webhook URL for the following events. Each delivery includes:

- **Header `X-Webhook-Signature`:** HMAC-SHA256 signature (`sha256=<hex>`) computed using the webhook secret.
- **Header `Content-Type`:** `application/json`

### Event Types

| Event | Trigger |
|-------|---------|
| `leaflet.uploaded` | A new leaflet has been uploaded |
| `leaflet.processing.started` | PDF processing has begun |
| `leaflet.processing.completed` | All extraction stages finished successfully |
| `leaflet.processing.failed` | Processing failed with an error |
| `leaflet.review.required` | Products need human review |
| `leaflet.review.completed` | All product reviews are done |
| `leaflet.export.ready` | An export file is available for download |
| `product.updated` | A product's data was modified |
| `product.approved` | A product was approved during review |
| `product.rejected` | A product was rejected during review |

### Example Payloads

**leaflet.processing.completed**

```json
{
  "event": "leaflet.processing.completed",
  "timestamp": "2026-01-15T10:35:00Z",
  "data": {
    "leaflet_id": "uuid",
    "leaflet_code": "LEAF_2025_000123",
    "status": "completed",
    "total_products": 48,
    "auto_approved": 38,
    "review_required": 10,
    "processing_time_seconds": 185,
    "processing_cost": 0.2450
  }
}
```

**product.approved**

```json
{
  "event": "product.approved",
  "timestamp": "2026-01-15T11:00:00Z",
  "data": {
    "product_id": "uuid",
    "leaflet_id": "uuid",
    "product_name": "Alpsko Mleko 1L",
    "review_status": "approved",
    "reviewed_by": "user-uuid"
  }
}
```

### Verifying Webhook Signatures

```python
# Python
import hashlib
import hmac

def verify_webhook_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your handler:
signature = request.headers["X-Webhook-Signature"]
is_valid = verify_webhook_signature(request.body, signature, webhook_secret)
```

```javascript
// JavaScript (Node.js)
const crypto = require("crypto");

function verifySignature(payload, signature, secret) {
  const expected =
    "sha256=" + crypto.createHmac("sha256", secret).update(payload).digest("hex");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}
```

---

## 20. Rate Limiting

The API applies rate limits to prevent abuse. Rate-limited endpoints return `429 Too Many Requests` when limits are exceeded.

### Default Limits

| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| `/auth/login` | Configurable | Per-IP |
| `/auth/register` | Configurable | Per-IP |
| `/auth/refresh` | Configurable | Per-IP |
| `/leaflets/upload` | 10 requests | 60 seconds |
| `/contact` | Per-email + Per-IP + Global | 1 hour |
| General API | Configurable | Per-user |

### Rate Limit Headers

When rate limited, the response includes:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

### Best Practices

1. **Implement exponential backoff** when receiving 429 responses.
2. **Cache responses** where possible to reduce API calls.
3. **Use webhooks** for event-driven architectures instead of polling.
4. **Use batch endpoints** (e.g., `POST /products/batch`) to reduce request count.

---

## Pagination

All list endpoints return paginated results:

```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

**Standard parameters:**

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `page` | int | 1 | >= 1 | Page number |
| `page_size` | int | 50 | 1-200 | Items per page |
| `sort_by` | string | varies | - | Sort field |
| `sort_order` | string | desc | asc/desc | Sort direction |

---

## Interactive Documentation

The full interactive API documentation with request/response schemas is available at:

```
{domain}/docs
```

This Swagger UI allows you to test endpoints directly from the browser with JWT authentication.
