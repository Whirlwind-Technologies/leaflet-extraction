# AI-Powered Leaflet Data Extraction Platform

A zero-configuration SaaS solution that automatically extracts structured product data from multi-page promotional PDF leaflets using advanced vision-language models (VLMs).

## 🚀 Features

- **Template-Independent AI**: Understands visual layout, spatial relationships, and promotional context
- **95%+ Accuracy**: With minimal human review
- **Multi-Language Support**: Handles Balkans/Adriatic region languages and currencies
- **Zero Configuration**: No setup time for new retailers
- **Scalable Architecture**: Serves both internal BI needs and B2B clients
- **Real-time Progress**: WebSocket-based extraction progress updates
- **Smart Validation**: Auto-approval for high-confidence extractions
- **Card-First Extraction**: Detects product card regions first, annotates with numbered boxes, then VLM matches products to regions for accurate bounding boxes
- **Auto-refresh URLs**: S3 presigned URLs automatically refresh when expired
- **Performant Leaflet Detail**: Paginated products, lazy-loaded thumbnails, concurrent presigned URL generation, and skeleton loading states
- **Optimized Review Navigation**: LRU cache with sliding window prefetch, keyboard shortcuts, background review queue, and crossfade transitions
- **Multi-Format Export**: CSV, Excel, and JSON export from any product list with sync/async paths and S3-backed download URLs
- **Webhook Integration**: Event-driven notifications with SSRF protection, delivery logs, and retry policies
- **Organization Management**: Invitations, role-based access, platform provider quotas, and admin overrides
- **Cost Tracking**: Numeric-precision cost columns, per-provider breakdowns, date-range queries, and budget alerts

## 🌍 Supported Regions

Pre-configured for Balkans/Adriatic markets with auto-populated settings:

| Country | Currency | Language |
|---------|----------|----------|
| Slovenia | EUR | Slovenian |
| Croatia | EUR | Croatian |
| Serbia | RSD | Serbian |
| Bosnia & Herzegovina | BAM | Bosnian |
| Montenegro | EUR | Serbian |
| North Macedonia | MKD | Macedonian |
| Albania | ALL | Albanian |
| Kosovo | EUR | Albanian |
| Bulgaria | BGN | Bulgarian |
| Romania | RON | Romanian |
| Greece | EUR | Greek |
| Italy | EUR | Italian |
| Austria | EUR | German |
| Hungary | HUF | Hungarian |

## 📋 What It Extracts

| Field | Description |
|-------|-------------|
| Brand | Product brand name |
| Product Code | SKU, item number, reference code |
| Product Name | Full product description |
| Quantity | Numeric quantity |
| Units | Unit of measurement (g, kg, ml, L, pieces, pack) |
| Regular Price | Product price (always populated; original price if discount exists) |
| Discounted Price | Sale/promotional price (only when discount badge is present) |
| Discount Percentage | Calculated or displayed discount |
| Currency | Currency symbol/code |
| Product ID | Barcode/EAN if visible |
| Page Number | Page location in leaflet |
| Bounding Box | Coordinates of product in page |
| Product Images | Extracted product images (Base64 or URL) |

## 🛠 Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0
- **Cache/Queue**: Redis 7+ / Celery
- **AI**: Anthropic Claude Sonnet 4 (primary), multi-provider support
- **OCR**: PaddleOCR 3.x for text detection and product region identification
- **Image Processing**: OpenCV, Pillow for visual boundary detection
- **Storage**: AWS S3

### Frontend
- **Framework**: Next.js 16 + React 19 + TypeScript
- **Styling**: Tailwind CSS 4
- **Components**: Radix UI / shadcn/ui

### DevOps
- **Containerization**: Docker & Docker Compose
- **Monitoring**: Flower (Celery), Health checks

## 📁 Project Structure

```
leaflet-extraction-platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # API endpoints (leaflets, products, export, webhooks, admin)
│   │   ├── core/
│   │   │   ├── extraction/   # VLM extraction, prompt building, reconciliation
│   │   │   ├── validation/   # Product validation rules
│   │   │   ├── categories/   # Category loader and management
│   │   │   ├── review/       # Review queue routing and priority assignment
│   │   │   └── image_processing/
│   │   │       ├── card_detector.py           # Card region detection (3x4 projection profiles, 3x5 grid fallback)
│   │   │       ├── card_annotator.py          # Draws numbered region boxes for VLM
│   │   │       ├── paddle_ocr_detector.py     # PaddleOCR text detection
│   │   │       ├── visual_boundary_detector.py # OpenCV visual detection
│   │   │       ├── extractor.py               # Bounding box image extraction
│   │   │       └── quality.py                 # Image quality scoring
│   │   ├── models/           # SQLAlchemy models (leaflet, product, webhook, export_job, org)
│   │   ├── schemas/          # Pydantic schemas (product_export, platform_quota, vlm_usage)
│   │   ├── services/         # Business services (export, webhook, email, analytics)
│   │   ├── utils/            # Utilities (storage, cache, security, url_validation)
│   │   └── workers/          # Celery workers and task definitions
│   ├── alembic/              # Database migrations
│   ├── scripts/              # Seed scripts (categories, superuser)
│   └── requirements.txt
├── frontend/
│   ├── app/                  # Next.js App Router pages
│   ├── components/           # React components (UI, dashboard, review, export)
│   ├── hooks/                # Custom hooks (product cache, review queue, progress WS)
│   ├── lib/                  # Actions, utilities, types
│   └── public/
├── product_categories.csv    # 352 product categories with descriptions
├── docker-compose.yml
├── docker-compose.prod.yml
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Whirlwind-Technologies/leaflet-extraction-platform.git
   cd leaflet-extraction-platform
   ```

2. **Copy environment files**
   ```bash
   cp .env.example .env
   ```
   At minimum, set these values before starting:

   | Variable | What to set |
   |----------|-------------|
   | `SECRET_KEY` | Run `openssl rand -hex 32` and paste the output |
   | `POSTGRES_PASSWORD` | Any strong password |
   | `REDIS_PASSWORD` | Any strong password (or remove from `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` if not using auth) |
   | `STORAGE_MODE` | Set to `local` to skip S3 entirely in development |
   | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET_NAME` | Only required if `STORAGE_MODE=s3` |

   > **Tip:** For a quick local test, set `STORAGE_MODE=local` — no AWS account needed.
   

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
    # Apply schema migrations
   docker-compose exec backend alembic upgrade head

   # Seed the 352 product categories (first run only)
   docker-compose exec backend python scripts/seed_categories.py

   # Create the first superuser account (first run only)
   docker-compose exec backend python scripts/create_superuser.py
   # You will be prompted to enter an email, full name, and password.
   # Password must be at least 8 characters and contain uppercase, lowercase, and a digit.
   ```

5. **Verify everything is running**
   ```bash
   # Check all containers are healthy
   docker-compose ps

   # Check backend health
   curl http://localhost:8000/health
   ```

   Expected output from `/health`:
   ```json
   {
     "status": "healthy",
     "database": "connected",
     "redis": "connected"
   }
   ```

   Then open:
   - **Frontend**: http://localhost:3000
   - **API docs**: http://localhost:8000/docs
   - **Celery monitor**: http://localhost:5555

### Local Development (Without Docker)

1. **Start dependencies** (PostgreSQL and Redis must be running first)
   ```bash
   # macOS with Homebrew
   brew services start postgresql@15
   brew services start redis

   # Ubuntu/Debian
   sudo systemctl start postgresql redis
   ```

2. **Backend setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

   # Run migrations and seed
   alembic upgrade head
   python scripts/seed_categories.py
   python scripts/create_superuser.py

   # Start API server
   uvicorn app.main:app --reload
   ```

3. **Celery worker** (new terminal, same venv)
   ```bash
   cd backend
   source venv/bin/activate
   celery -A app.workers.celery_app worker --loglevel=info
   ```

4. **Frontend setup** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_USER` | PostgreSQL user | `leaflet_user` |
| `POSTGRES_PASSWORD` | PostgreSQL password | - |
| `POSTGRES_DB` | PostgreSQL database | `leaflet_extraction` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `SECRET_KEY` | JWT secret key | - |
| `STORAGE_MODE` | Storage backend (`s3` or `local`) | `s3` |
| `AWS_ACCESS_KEY_ID` | AWS S3 access key | - |
| `AWS_SECRET_ACCESS_KEY` | AWS S3 secret key | - |
| `AWS_REGION` | AWS region | `us-east-1` |
| `S3_BUCKET_NAME` | S3 bucket for file storage | `leaflet-extraction-storage` |

See `.env.example` for complete list.

## 📚 API Documentation

Once running, access the interactive API documentation at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/leaflets/upload` | Upload a new PDF leaflet |
| GET | `/api/v1/leaflets/` | List all leaflets |
| GET | `/api/v1/leaflets/{id}` | Get leaflet details |
| GET | `/api/v1/leaflets/{id}/products` | Get extracted products (paginated) |
| GET | `/api/v1/products/stats` | Get product statistics by status |
| POST | `/api/v1/products/batch` | Batch fetch products by IDs |
| POST | `/api/v1/products/{id}/review` | Submit product review |
| POST | `/api/v1/products/batch-review` | Batch review multiple products |
| POST | `/api/v1/products/{id}/refresh-image-url` | Refresh expired S3 URL |
| POST | `/api/v1/products/export` | Create product export (CSV/Excel/JSON) |
| POST | `/api/v1/products/export/preview` | Preview export row count |
| GET | `/api/v1/products/export/{id}/status` | Check async export job status |
| GET | `/api/v1/products/export/{id}/download` | Download completed export |
| GET | `/api/v1/retailers/` | List all retailers |
| POST | `/api/v1/retailers/` | Create retailer |
| GET | `/api/v1/categories/` | List product categories |
| GET | `/api/v1/export/{leaflet_id}` | Export single leaflet data |
| POST | `/api/v1/webhooks` | Create webhook |
| GET | `/api/v1/webhooks` | List webhooks |
| POST | `/api/v1/webhooks/{id}/test` | Send test webhook event |
| GET | `/api/v1/webhooks/{id}/deliveries` | View delivery history |
| DELETE | `/api/v1/webhooks/{id}` | Delete webhook (soft delete) |
| GET | `/api/v1/organizations/current/platform-quota` | Get platform AI quota |
| POST | `/api/v1/organizations/current/invitations` | Invite user to organization |
| POST | `/api/v1/organizations/current/invitations/{id}/resend` | Resend invitation email |
| GET | `/api/v1/vlm-providers/usage/costs` | Query VLM cost breakdown by date range |
| PATCH | `/api/v1/admin/organizations/{org_id}` | Update org platform settings |
| GET | `/api/v1/admin/system/health` | System health check |

## 📦 Product Review Navigation

The review interface is optimized for high-throughput product review with minimal latency:

- **LRU Product Cache**: Products are cached client-side with a sliding window that prefetches 3 products ahead of the current position.
- **Background Review Queue**: Review submissions (approve, reject, edit) are queued optimistically and sent to the API without blocking navigation. The reviewer can move to the next product immediately.
- **Keyboard Shortcuts**: `A` to approve, `R` to reject, `S` to save edits, `Alt+Left/Right` arrows to navigate between products.
- **Crossfade Transitions**: Smooth visual transitions between products to reduce review fatigue.
- **Batch Fetch Endpoint**: `POST /api/v1/products/batch` fetches multiple products in a single request, powering the prefetch cache.

## 📤 Product Export

Products can be exported from the All Products list, the Review Queue, or any filtered view:

| Feature | Details |
|---------|---------|
| **Formats** | CSV, Excel (.xlsx), JSON |
| **Export Modes** | `all` (every product), `filtered` (current filters), `selected` (checked rows), `review_queue` (pending review) |
| **Sync Path** | Exports under 1,000 products return an immediate file download via `StreamingResponse` |
| **Async Path** | Exports of 1,000+ products are dispatched to a Celery task; the client polls `GET /export/{id}/status` until complete |
| **Storage** | Async export files are stored in S3 with presigned download URLs |
| **Preview** | `POST /api/v1/products/export/preview` returns the row count before committing to the export |

## 🔔 Webhook System

Event-driven notifications for integrating with external systems:

- **Event Types**: 10 events covering `leaflet.*` (uploaded, processing, completed, failed), `product.*` (extracted, reviewed, updated), and `export.*` (started, completed) lifecycle stages.
- **Test Delivery**: `POST /api/v1/webhooks/{id}/test` sends a synthetic event and returns the HTTP response status, letting you verify connectivity before going live.
- **Delivery Logs**: `GET /api/v1/webhooks/{id}/deliveries` returns paginated delivery history with request/response bodies and headers (sensitive headers are redacted).
- **Retry Policy**: Configurable retry count (0-10) and timeout (5-120s) per webhook.
- **SSRF Prevention**: Webhook URLs are validated against private and internal IP ranges before delivery.
- **Security**: Webhook secrets are Fernet-encrypted at rest; each delivery includes an HMAC signature header.
- **Soft Delete**: Deleting a webhook marks it inactive and preserves delivery history for audit.

## 🏢 Organizations and Quotas

### Platform Provider Quota

Organizations using the platform's shared AI provider receive a default limit of **10 free leaflet extractions**. After the limit is reached, the organization must configure their own VLM provider to continue extracting.

- Enforcement happens at extraction time (not upload), so PDFs can be uploaded before configuring a provider.
- Admins can override the limit per organization via `PATCH /api/v1/admin/organizations/{org_id}` (set to `0` for unlimited).
- Quota status is available at `GET /api/v1/organizations/current/platform-quota`.
- When the limit is hit, a `PLATFORM_LIMIT_REACHED` WebSocket message is published with a CTA directing users to the provider settings page.

### Organization Invitations

- Admins and owners can invite users by email via `POST /api/v1/organizations/current/invitations`.
- Invitations generate a secure token with a configurable expiration window.
- Resend capability with cooldown tracking (`resend_count` on the invitation model).
- Invitation status flow: `pending` -> `accepted` | `expired` | `revoked`.

## 💰 VLM Cost Tracking

All cost columns use `Numeric(10,4)` precision (migrated from `Float`) to eliminate rounding drift over many transactions.

- **Single source of truth**: Cost is calculated and recorded in `multi_provider_client.py` via `record_usage()`.
- **Date-range queries**: `GET /api/v1/vlm-providers/usage/costs` supports period presets (`last_7_days`, `this_month`, `last_month`, `this_year`, `all_time`) and custom date ranges with day/week/month granularity.
- **Per-provider breakdown**: Response includes cost, token counts, and percentage-of-total for each provider.
- **Budget alerts**: Configurable per-provider monthly budget limits with alerts when approaching thresholds.

## 📊 Analytics

The analytics dashboard provides accurate, real-time metrics:

- All metrics use the same underlying queries as the products and review pages, ensuring consistency.
- Date range picker with presets (Last 7 days, Last 30 days, This month) and a custom calendar selector.
- Auto-refresh every 60 seconds with a manual refresh button and "Last updated" indicator.

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_pdf_processor.py
```

## 🚀 Production Deployment

Use `docker-compose.prod.yml` for production deployments:

```bash
# Build and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Run database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Seed product categories
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_categories.py
```

### Important: Next.js Build Args

Next.js embeds `NEXT_PUBLIC_*` variables at **build time**. Update `docker-compose.prod.yml` with your domain:

```yaml
frontend:
  build:
    args:
      - NEXT_PUBLIC_API_URL=https://leafxtract.com
      - NEXT_PUBLIC_WS_URL=wss://leafxtract.com
```

If you change these values, rebuild with `--no-cache`:
```bash
docker compose -f docker-compose.prod.yml build --no-cache frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

## 📈 Monitoring

### Health Endpoints

- **Basic**: `GET /health` - Quick health check
- **Detailed**: `GET /api/v1/admin/system/health` - Full system status (requires auth)

### Basic Health Response
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

### Detailed Health Response
```json
{
  "overall_status": "healthy",
  "components": [
    {"name": "PostgreSQL Database", "status": "healthy", "latency_ms": 5},
    {"name": "Redis Cache", "status": "healthy", "latency_ms": 2},
    {"name": "S3 Storage", "status": "healthy", "latency_ms": 150},
    {"name": "Celery Workers", "status": "healthy", "details": {"active_workers": 4}}
  ]
}
```

### Celery Monitoring
- **Flower UI**: http://localhost:5555
- Monitor task execution, failures, and queue depths

## 🔐 Security

- JWT-based authentication (HS256, 30min access / 7-day refresh tokens)
- API key authentication for B2B clients (Fernet-encrypted, `X-API-Key` header)
- Fernet encryption for all stored secrets (VLM API keys, webhook secrets)
- SSRF prevention on webhook delivery URLs (blocks private/internal IP ranges)
- Rate limiting (configurable per-endpoint)
- Input validation with Pydantic on all endpoints
- SQL injection prevention via SQLAlchemy ORM
- CORS configured for specific allowed origins
- Password hashing with bcrypt
- Sensitive header redaction in webhook delivery logs

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For support, email support@wwindtech.com or create an issue.