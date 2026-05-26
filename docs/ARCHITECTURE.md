# Architecture

This document describes the system architecture of the AI-Powered Leaflet Data Extraction Platform — how components are structured, how data flows through the system, and how the platform is deployed.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Architecture](#2-component-architecture)
   - [Frontend](#21-frontend)
   - [Backend API](#22-backend-api)
   - [Celery Workers](#23-celery-workers)
   - [Intake Subsystem](#24-intake-subsystem)
   - [Extraction Pipeline](#25-extraction-pipeline)
   - [Data Stores](#26-data-stores)
3. [Data Flow](#3-data-flow)
   - [Leaflet Upload & Extraction](#31-leaflet-upload--extraction)
   - [Product Review](#32-product-review)
   - [Export](#33-export)
   - [Webhook Delivery](#34-webhook-delivery)
4. [API Layer](#4-api-layer)
5. [Authentication & Security](#5-authentication--security)
6. [Organization & Multi-Tenancy](#6-organization--multi-tenancy)
7. [Real-Time Communication](#7-real-time-communication)
8. [Storage](#8-storage)
9. [AI / VLM Integration](#9-ai--vlm-integration)
10. [Cost Tracking](#10-cost-tracking)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Monitoring & Health](#12-monitoring--health)
13. [Database Schema Overview](#13-database-schema-overview)
14. [Key Design Decisions](#14-key-design-decisions)

---

## 1. System Overview

The platform is a SaaS application that ingests promotional PDF leaflets, extracts structured product data from each page using a multi-stage AI pipeline, and exposes the results through a web UI and a REST API.

```
Browser / B2B API client
        │
        ├─── HTTPS ──► Next.js frontend  (port 3000)
        │
        └─── HTTPS / WSS ──► FastAPI backend  (port 8000)
                                    │
                    ┌───────────────┼────────────────┐
                    ▼               ▼                ▼
               PostgreSQL        Redis 7+         AWS S3
               (primary DB)    (cache + queue)  (file storage)
                                    │
                                    ▼
                           Celery workers
                                    │
                    ┌───────────────┼────────────────┐
                    ▼               ▼                ▼
              PaddleOCR       Claude VLM        Export jobs
             card detection   extraction       (CSV/Excel/JSON)
```

**Key design principles:**

- **Zero configuration for new retailers** — the AI pipeline is template-independent; it understands visual layout and spatial context without per-retailer setup.
- **Async-first processing** — PDF extraction and large exports are always handled by Celery workers; the API returns immediately and clients track progress via WebSocket or polling.
- **Multi-tenancy via organizations** — all data is scoped to an organization. Users belong to organizations and inherit their VLM provider and quota settings.

---

## 2. Component Architecture

### 2.1 Frontend

**Technology:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI / shadcn/ui

The frontend uses the Next.js App Router. All data fetching uses React Server Components where possible; interactive review and upload flows use Client Components.

```
frontend/
├── app/                    # App Router pages and layouts
├── components/
│   ├── ui/                 # shadcn/ui primitives
│   ├── dashboard/          # Leaflet list, stats, analytics
│   ├── review/             # Product review interface
│   └── export/             # Export dialogs and status
├── hooks/
│   ├── useProductCache     # LRU cache with sliding-window prefetch
│   ├── useReviewQueue      # Background review submission queue
│   └── useProgressWS       # WebSocket extraction progress
└── lib/
    ├── actions/            # Next.js Server Actions
    ├── types/              # Shared TypeScript types
    └── utils/              # API client, formatters
```

**Performance features:**

- **LRU product cache** — caches products client-side with a sliding window that prefetches 3 products ahead of the current review position.
- **Background review queue** — review submissions are queued optimistically; the reviewer navigates immediately without waiting for the API response.
- **Lazy-loaded thumbnails** — leaflet page thumbnails load on demand using Intersection Observer.
- **Concurrent presigned URL generation** — product image URLs are fetched in parallel and auto-refreshed when expired.
- **Skeleton loading states** — all async data surfaces show skeleton placeholders to eliminate layout shift.

### 2.2 Backend API

**Technology:** FastAPI, Python 3.10+, SQLAlchemy 2.0, Pydantic v2, Alembic

The API is organized under `/api/v1/` and follows REST conventions. WebSocket connections are handled by FastAPI's native WebSocket support.

```
backend/app/
├── api/v1/
│   ├── leaflets.py         # Upload (PDF, ZIP, images, bulk, presigned), list, detail, reprocess
│   ├── products.py         # Review, batch fetch, export, image refresh
│   ├── retailers.py        # Retailer CRUD
│   ├── categories.py       # Product category listing
│   ├── webhooks.py         # Webhook management and delivery logs
│   ├── product_export.py   # Export: create, preview, status, download
│   ├── organizations.py    # Org settings, invitations, quota
│   ├── vlm_providers.py    # Provider config, usage, cost queries
│   └── admin.py            # Platform admin: org overrides, health
├── core/
│   ├── intake/             # File ingestion: pdf_processor, zip_processor, image_processor
│   ├── extraction/         # VLM orchestration, prompt building, reconciliation
│   ├── validation/         # Product field validation rules and priority scoring
│   ├── categories/         # Category loader (product_categories.csv)
│   ├── review/             # Review queue routing and priority assignment
│   ├── image_processing/   # (see §2.5)
│   ├── progress.py         # WebSocket progress publisher (Redis pub/sub)
│   └── websocket.py        # WebSocket connection manager
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic request/response schemas
├── services/
│   ├── export_service.py         # CSV/Excel/JSON generation
│   ├── webhook_service.py        # Webhook delivery and retry
│   ├── email_service.py          # SMTP email sending (Jinja2 templates)
│   ├── analytics_service.py      # Dashboard metrics queries
│   ├── leaflet_service.py        # Leaflet business logic
│   ├── budget_monitoring_service.py  # VLM budget threshold alerts
│   ├── notification_service.py   # System notification management
│   ├── platform_vlm_service.py   # Platform-level VLM provider management
│   └── vlm_audit_service.py      # VLM call audit logging
├── utils/                  # Storage, cache, security, URL validation, export storage
└── workers/                # Celery app config and task definitions
```

### 2.3 Celery Workers

**Technology:** Celery, Redis (broker + result backend)

Two worker processes run alongside the API:

- **`celery_worker`** — consumes four queues: `default`, `pdf`, `extraction`, `validation`. Concurrency 2 in development.
- **`celery_beat`** — scheduler that fires periodic maintenance tasks on a configured cadence.

**On-demand tasks** (triggered by API calls or chained from other tasks):

| Task | Queue | Trigger | Notes |
|------|-------|---------|-------|
| `process_pdf_task` | `pdf` | Upload API | PDF → page images (300 DPI). Chains `extract_products_task` on success |
| `process_zip_task` | `pdf` | Upload API | ZIP of images → page images. Chains `extract_products_task` on success |
| `process_single_page_task` | `pdf` | Manual reprocess | Reprocesses a single page |
| `extract_products_task` | `extraction` | Chained from intake tasks | Full VLM extraction: quota check → cleanup → OCR → card detection → VLM → reconciliation → sanitization → bbox finalization → validation → DB write. Auto-chains `extract_product_images_task` |
| `extract_product_images_task` | `extraction` | Chained from extraction | Crops product images from page images using bounding boxes; stores as base64 (< 100 KB) or S3 file |
| `export_products_task` | `default` | Export API (≥ 1,000 products) | Writes CSV/Excel/JSON to S3; updates `ExportJob` with presigned download URL |
| `cleanup_old_files_task` | `default` | Manual / scheduled | Deletes S3 files for old leaflets |
| `update_stats_task` | `default` | Manual / scheduled | Recomputes and caches processing statistics |

**Periodic tasks** (fired by `celery_beat`):

| Task | Cadence | Purpose |
|------|---------|---------|
| `cleanup_exports_task` | Hourly | Deletes export files older than 24 h; purges `ExportJob` records older than 7 days |
| `aggregate_usage_data_task` | Daily | Aggregates VLM audit logs into `OrganizationVLMUsage` for reporting |
| `monitor_budgets_task` | Periodic | Checks per-provider monthly budget thresholds and triggers alerts |
| `cleanup_audit_logs_task` | Periodic | Purges `VLMProviderAuditLog` records older than 90 days |
| `cleanup_notifications_task` | Periodic | Removes expired or old system notifications |
| `reset_spending_counters_task` | Hourly | Resets stale `current_month_spent`, `current_day_spent`, `current_hour_requests` counters on VLM provider rows using staleness-guarded SQL `UPDATE` to avoid races with `record_usage()` |

Workers share the same codebase as the API. Redis acts as both the Celery broker (DB 1) and result backend (DB 2). Flower (port 5555) provides a web UI for task monitoring.

### 2.4 Intake Subsystem

Before extraction can begin, uploaded files must be converted to page images. This is handled by `core/intake/`:

| File | Input | Output |
|------|-------|--------|
| `pdf_processor.py` | PDF file bytes | PNG page images at 300 DPI + thumbnails |
| `zip_processor.py` | ZIP of images | Images sorted by natural filename order, standardized |
| `image_processor.py` | Single image file | Standardized image (used by the multi-image upload endpoint) |

The intake task (`process_pdf_task` or `process_zip_task`) checks whether a VLM provider is configured before chaining to extraction. If no provider is available, the leaflet is set to `validating` status and waits for a manual trigger.

### 2.5 Extraction Pipeline

The extraction pipeline runs inside `extract_products_task` and processes all pages of a leaflet. Pages are downloaded from S3 first, then processed in sequence (OCR) and partially in parallel (VLM).

```
All page images downloaded from S3
        │
        ▼
PaddleOCR pre-run (sequential, max_workers=1)
  └── Detects text regions on all pages before VLM starts
  └── Sequential to avoid PaddlePaddle "Interface already registered" errors
        │  (text region bounding boxes, cached per leaflet)
        ▼
Per-page card-first pipeline (VLM calls run concurrently, max 2):
  │
  ├── card_detector.py
  │     └── Projects OCR regions onto 3×4 grid (projection profiles)
  │     └── Falls back to 3×5 grid if card count is ambiguous
  │
  ├── card_annotator.py
  │     └── Draws numbered bounding boxes on the page image
  │
  └── VLM (Claude Sonnet 4 / configured provider)
        └── Receives annotated image + structured prompt
        └── Maps products to numbered card regions
        └── Extracts all product fields
        │
        ▼
Cross-page Reconciliation
  └── Merges split products that span multiple pages
  └── Removes duplicates
        │
        ▼
Sanitization  (sanitize_products())
  └── Filters out category headers / section titles misidentified as products
  └── Fixes misplaced prices, computes missing regular_price
        │
        ▼
Bounding Box Finalization
  └── Products with card-detected bbox: kept as-is
  └── Products without bbox: grid-position fallback assigned, flagged bbox_fallback
        │
        ▼
Validation  (ProductValidator)
  └── Field-level rules and confidence scoring
  └── Sets review_status: AUTO_APPROVED or PENDING
  └── Assigns review_priority score
        │
        ▼
Product records written to PostgreSQL (batched, 25 per commit)
        │
        ▼
[auto-chain] extract_product_images_task
  └── Crops product regions from page images using bounding boxes
  └── Scores image quality (QualityScorer, min 0.70)
  └── < 100 KB → stored as base64 on product record
  └── ≥ 100 KB → uploaded to S3, presigned URL stored
```

**Key files:**

| File | Responsibility |
|------|---------------|
| `card_detector.py` | Detects product card regions using projection profile analysis (3×4 primary, 3×5 fallback) |
| `card_annotator.py` | Renders numbered bounding boxes onto page images for VLM input |
| `paddle_ocr_detector.py` | Wraps PaddleOCR for text region detection; singleton instance to avoid re-initialization cost |
| `ocr_bbox_detector.py` | OCR-based bounding box detection fallback |
| `visual_boundary_detector.py` | OpenCV-based visual edge detection for boundary refinement |
| `bbox_refiner.py` | Post-processing refinement of detected bounding boxes |
| `extractor.py` | Crops product images from page images given a bounding box |
| `quality.py` | Scores extracted image quality (sharpness, contrast, size) |
| `encoder.py` | Handles base64 encoding for small product images |
| `storage.py` | Image-specific storage helpers |

### 2.6 Data Stores

| Store | Technology | Purpose |
|-------|-----------|---------|
| Primary database | PostgreSQL 15+ | All application data: leaflets, products, orgs, webhooks, export jobs, VLM usage |
| Cache / queue | Redis 7+ | Celery broker (DB 1), result backend (DB 2); API-level caching (DB 0) |
| File storage | AWS S3 | PDF uploads, extracted product images, async export files |

S3 presigned URLs are used for all file access. URLs auto-refresh when expired (handled by `POST /api/v1/products/{id}/refresh-image-url`). A `local` storage mode is available for development (set `STORAGE_MODE=local`).

---

## 3. Data Flow

### 3.1 Leaflet Upload & Extraction

```
1.  Client           POST /api/v1/leaflets/upload (multipart PDF)
2.  Backend          Validates file, creates Leaflet record (status: pending)
                     Uploads PDF to S3
                     Enqueues process_leaflet task → Redis
                     Returns leaflet_id immediately (202 Accepted)

3.  Celery worker    Picks up task
                     Converts PDF pages to images
                     For each page:
                       a. PaddleOCR → text regions
                       b. card_detector → card regions
                       c. card_annotator → annotated image
                       d. VLM → raw product data
                       e. Reconciliation → validated products
                       f. Writes products to PostgreSQL
                       g. Uploads product images to S3
                     Updates Leaflet status: processing → completed | failed

4.  WebSocket        Backend publishes progress events per page
    (client)         Client receives: { page, total, status, products_found }
                     On PLATFORM_LIMIT_REACHED: shows provider-setup CTA

5.  Auto-approval    Products above confidence threshold → approved automatically
                     Products below threshold → queued for human review
```

### 3.2 Product Review

```
1.  Client           GET /api/v1/leaflets/{id}/products?page=N (paginated)
                     Frontend LRU cache prefetches 3 products ahead

2.  Review action    Client queues action locally (optimistic UI)
                     Background queue sends: POST /api/v1/products/{id}/review
                     { action: "approve" | "reject" | "edit", fields?: {...} }

3.  Backend          Updates product status and fields
                     Triggers product.reviewed webhook event

4.  Batch fetch      POST /api/v1/products/batch [id, id, ...]
                     Powers the prefetch cache for the review interface
```

**Keyboard shortcuts in review UI:** `A` approve, `R` reject, `S` save edits, `Alt+←/→` navigate.

### 3.3 Export

```
Sync path  (< 1,000 products):
  POST /api/v1/products/export
      → Backend streams file directly as StreamingResponse
      → Client receives file download immediately

Async path (≥ 1,000 products):
  POST /api/v1/products/export
      → Backend creates ExportJob record (status: pending)
      → Enqueues export_products Celery task
      → Returns { export_job_id }

  Celery worker:
      → Queries products with applied filters
      → Writes CSV / Excel / JSON to S3
      → Updates ExportJob (status: completed, download_url: presigned S3 URL)

  Client polls:
      GET /api/v1/products/export/{id}/status
      → When completed: GET /api/v1/products/export/{id}/download
```

Export modes: `all`, `filtered`, `selected`, `review_queue`. Preview row count before export with `POST /api/v1/products/export/preview`.

### 3.4 Webhook Delivery

```
Platform event occurs (e.g. leaflet.completed)
      │
      ▼
Backend publishes event internally
      │
      ▼
For each active webhook subscribed to this event type:
  Celery enqueues deliver_webhook task
      │
      ▼
Worker:
  1. Validates webhook URL against SSRF blocklist (private/internal IPs blocked)
  2. Builds payload with HMAC-SHA256 signature header
  3. HTTP POST to endpoint (timeout: configured per webhook, 5–120s)
  4. Records delivery log (request headers/body, response status/headers/body)
     — sensitive headers redacted from log
  5. On failure: retries up to configured retry_count with backoff
```

---

## 4. API Layer

All endpoints are under `/api/v1/`. Full interactive documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc) when the server is running.

**Endpoint groups:**

| Group | Prefix | Key operations |
|-------|--------|---------------|
| Leaflets | `/api/v1/leaflets` | Upload, list, detail, products list |
| Products | `/api/v1/products` | Review, batch fetch, export, image refresh |
| Retailers | `/api/v1/retailers` | CRUD |
| Categories | `/api/v1/categories` | List (352 categories from CSV) |
| Export | `/api/v1/products/export` | Create, preview, status, download |
| Webhooks | `/api/v1/webhooks` | CRUD, test delivery, delivery history |
| Organizations | `/api/v1/organizations` | Settings, invitations, platform quota |
| VLM Providers | `/api/v1/vlm-providers` | Provider config, cost queries |
| Admin | `/api/v1/admin` | Org overrides, system health |

**Versioning:** The current version is `v1`. All breaking changes will be introduced under a new version prefix.

**Pagination:** List endpoints accept `page` and `page_size` query parameters. Responses include `total`, `page`, `page_size`, and `items`.

---

## 5. Authentication & Security

### Authentication methods

| Method | Use case | Header |
|--------|---------|--------|
| JWT (Bearer) | Web UI users | `Authorization: Bearer <token>` |
| API Key | B2B clients, programmatic access | `X-API-Key: <key>` |

JWT tokens use HS256. Access tokens expire after 30 minutes; refresh tokens after 7 days. API keys are Fernet-encrypted at rest.

### Security controls

| Control | Implementation |
|---------|---------------|
| Password hashing | bcrypt |
| Secret storage | Fernet symmetric encryption (VLM API keys, webhook secrets) |
| SSRF prevention | Webhook URLs validated against private/internal IP blocklists before delivery |
| SQL injection | SQLAlchemy ORM parameterized queries throughout |
| Input validation | Pydantic v2 on all request bodies and query parameters |
| CORS | Configured allowlist of specific origins |
| Rate limiting | Configurable per-endpoint |
| Sensitive data in logs | Webhook delivery logs redact sensitive headers |
| Webhook authenticity | HMAC-SHA256 signature on every delivery (`X-Signature` header) |

---

## 6. Organization & Multi-Tenancy

All data is scoped to an **organization**. Every authenticated user belongs to exactly one organization.

### Roles

| Role | Permissions |
|------|------------|
| Owner | Full access including org deletion |
| Admin | Manage members, invitations, provider settings |
| Member | Upload, review, export; cannot manage org settings |

### Invitations

Admins and owners invite users by email. Invitations generate a secure token with a configurable expiration window. Status flow: `pending` → `accepted` | `expired` | `revoked`. Resend is rate-limited via `resend_count` tracking.

### Platform Provider Quota

Organizations using the platform's shared VLM provider receive a default limit of **10 free leaflet extractions**. After the limit is reached, the organization must configure their own VLM provider key.

- Quota enforcement happens at extraction time, not at upload time.
- Admins can override limits per organization via `PATCH /api/v1/admin/organizations/{org_id}` (set to `0` for unlimited).
- When the limit is hit, a `PLATFORM_LIMIT_REACHED` WebSocket event is sent to the client with a CTA to configure a provider.

---

## 7. Real-Time Communication

WebSocket connections are used for extraction progress updates. The client connects to a per-leaflet WebSocket endpoint after upload.

**Event types published during extraction:**

| Event | Payload |
|-------|---------|
| `page_started` | `{ page, total }` |
| `page_completed` | `{ page, total, products_found }` |
| `extraction_completed` | `{ leaflet_id, total_products }` |
| `extraction_failed` | `{ leaflet_id, error }` |
| `PLATFORM_LIMIT_REACHED` | `{ message, cta_url }` |

The frontend `useProgressWS` hook manages connection lifecycle, reconnect on drop, and event dispatching to UI state.

---

## 8. Storage

### S3 structure

```
s3://{S3_BUCKET_NAME}/
├── leaflets/
│   └── {org_id}/{leaflet_id}/
│       ├── original.pdf
│       └── pages/
│           └── page_{n}.jpg
├── products/
│   └── {org_id}/{leaflet_id}/{product_id}/
│       └── image.jpg
└── exports/
    └── {org_id}/{export_job_id}/
        └── export.{csv|xlsx|json}
```

All S3 objects are accessed via presigned URLs with a configurable expiry. The backend's `storage` utility abstracts S3 and local-disk backends behind a common interface, selected by the `STORAGE_MODE` environment variable.

### Local storage mode

Set `STORAGE_MODE=local` in development to write files to the local filesystem instead of S3. The same presigned-URL abstraction applies; URLs are generated as local HTTP paths served by the backend.

---

## 9. AI / VLM Integration

### Multi-provider architecture

The platform supports multiple VLM providers through a unified `multi_provider_client.py` interface. The provider is configured per organization in VLM provider settings.

| Provider | Default model | Notes |
|----------|-------------|-------|
| Anthropic | Claude Sonnet 4 | Primary provider |
| Others | Configurable | Fallback support |

### Extraction prompt design

The VLM receives two inputs per page:

1. **Annotated page image** — the original page with numbered bounding boxes drawn over each detected product card region.
2. **Structured prompt** — instructs the VLM to match products to the numbered regions and extract all required fields.

This "card-first" approach (detect regions → annotate → extract) produces more accurate bounding boxes than asking the VLM to locate products from scratch.

### Auto-approval

Products with a VLM confidence score above the configured threshold (`AUTO_APPROVAL_THRESHOLD`, default `0.90`) and a validation pass are eligible for auto-approval. Auto-approval is controlled by the `feature_auto_approval` config flag; when disabled (the current default), all products are set to `PENDING` regardless of confidence score.

---

## 10. Cost Tracking

All VLM usage is recorded in the database by `multi_provider_client.py` via `record_usage()` at call time.

- Cost columns use `Numeric(10,4)` precision (migrated from `Float`) to eliminate floating-point drift across many transactions.
- `GET /api/v1/vlm-providers/usage/costs` supports period presets (`last_7_days`, `this_month`, `last_month`, `this_year`, `all_time`) and custom date ranges with `day` / `week` / `month` granularity.
- Response includes per-provider cost, token counts (input + output), and percentage of total spend.
- Configurable monthly budget limits per provider with alerts when approaching thresholds.

---

## 11. Deployment Architecture

### Development (Docker Compose)

```
postgres        PostgreSQL 18.3-alpine      localhost:5432
redis           Redis 7-alpine              localhost:6379
backend         FastAPI + Uvicorn           localhost:8000
celery_worker   Celery worker (concurrency 2)   (internal) — queues: default, pdf, extraction, validation
celery_beat     Celery Beat scheduler       (internal, no ports)
flower          Celery Flower UI            localhost:5555
frontend        Next.js dev server          localhost:3000
```

All services share a single Docker bridge network (`leaflet_network`). The backend, `celery_worker`, `celery_beat`, and `flower` all build from the same `backend/Dockerfile`; the frontend has its own image. `postgres` and `redis` use healthchecks; the backend waits on both before starting.

### Production (`docker-compose.prod.yml`)

The production compose file adds:

- Production-grade Uvicorn worker count
- `NEXT_PUBLIC_*` build args baked into the Next.js image at build time
- Environment variable injection from `.env` or secrets manager

**Important:** `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` are embedded into the Next.js bundle at build time. Changing these values requires a full frontend rebuild:

```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Post-deployment steps

After first deploy (or after schema changes):

```bash
# Apply database migrations
docker compose exec backend alembic upgrade head

# Seed product categories (first deploy only)
docker compose exec backend python scripts/seed_categories.py

# Create superuser (first deploy only)
docker compose exec backend python scripts/create_superuser.py
```

---

## 12. Monitoring & Health

### Health endpoints

| Endpoint | Auth required | Description |
|----------|-------------|-------------|
| `GET /health` | No | Basic liveness check |
| `GET /api/v1/admin/system/health` | Yes (admin) | Full component health with latency |

The detailed health check reports status and latency for PostgreSQL, Redis, S3, and Celery workers.

### Celery monitoring

Flower is available at `http://localhost:5555` in development. It shows:

- Active, reserved, and failed tasks
- Per-worker task throughput
- Task retry history
- Queue depths

### Application metrics

The analytics dashboard (`/analytics`) queries the same underlying database views as the products and review pages, ensuring consistency. It auto-refreshes every 60 seconds and supports date-range presets and a custom calendar picker.

---

## 13. Database Schema Overview

Core tables and their relationships:

```
organizations
    │
    ├── users (many, via memberships)
    ├── invitations
    ├── platform_quota
    └── vlm_provider_configs
            │
            └── vlm_usage_records

leaflets (scoped to org)
    │
    └── products (many)
            │
            └── export_job_products (join)

export_jobs (scoped to org)
    └── export_job_products (join to products)

webhooks (scoped to org)
    └── webhook_deliveries

retailers
    └── leaflets (many)
```

All migrations are managed by Alembic. Migration files live in `backend/alembic/versions/`. To generate a new migration after model changes:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe your change"
docker compose exec backend alembic upgrade head
```

---

## 14. Key Design Decisions

**Card-first extraction over direct VLM prompting**
Asking the VLM to locate and extract products simultaneously produces inconsistent bounding boxes. The card-first approach separates detection (PaddleOCR + OpenCV) from extraction (VLM), giving the VLM pre-numbered regions to map products to. This improves bounding box accuracy significantly.

**Async extraction with WebSocket progress**
PDF processing can take 30–120 seconds for multi-page leaflets. Returning a task ID immediately and streaming progress events over WebSocket provides a better UX than long-polling or extended HTTP timeouts.

**Sync/async export split at 1,000 rows**
Exports under 1,000 products complete fast enough to stream synchronously. Larger exports run as Celery tasks to avoid holding HTTP connections open, with S3-backed download URLs polled by the client.

**Organization-scoped VLM provider config**
Different organizations may have different AI budget constraints or data residency requirements. Storing VLM provider keys per organization (Fernet-encrypted) allows each org to bring their own key while the platform provides a shared provider with a quota for evaluation.

**`Numeric(10,4)` for cost columns**
Floating-point (`Float`) columns accumulate rounding errors over thousands of VLM calls. Using `Numeric(10,4)` (fixed decimal precision) ensures that per-call costs sum correctly in aggregate queries and budget alert calculations.

**Atomic platform quota enforcement**
The platform VLM quota check uses a single atomic SQL `UPDATE … WHERE platform_leaflets_used < platform_leaflet_limit RETURNING …` rather than a read-then-write pattern. This prevents race conditions when multiple extraction tasks start simultaneously for the same organization — only one will increment the counter; the rest see the limit already reached. Re-extraction of an already-processed leaflet skips the quota check (tracked via `used_platform_provider` on the leaflet row).

**Soft delete for webhooks**
Deleting a webhook marks it inactive and preserves all delivery history. This is important for audit trails — integrators may need to review past delivery logs even after an endpoint has been removed.