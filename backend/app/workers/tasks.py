"""
Celery Tasks — re-export shim.

All task implementations live in focused submodules under ``app/workers/``.
This module re-exports every public name so that existing callers
(``from app.workers.tasks import process_pdf_task``) and Celery's
autodiscovery continue to work without changes.

Submodules:
    db_helpers          — sync DB sessions, run_async, status helpers
    ocr_helpers         — PaddleOCR Redis cache and pre-run
    intake_tasks        — PDF / ZIP processing
    extraction_tasks    — VLM extraction + image cropping
    export_tasks        — product export + export cleanup
    maintenance_tasks   — cleanup, stats, budgets, notifications, email
"""

# ---- DB & async helpers ----
from app.workers.db_helpers import (  # noqa: F401
    get_sync_db_session,
    run_async,
    _record_vlm_usage,
    _cleanup_extraction_data_sync,
    _update_leaflet_status,
    _try_consume_platform_quota,
    _check_org_has_own_provider,
)

# ---- OCR helpers ----
from app.workers.ocr_helpers import (  # noqa: F401
    get_cached_ocr_results,
    clear_ocr_cache,
    _prerun_ocr_on_pages,
    _check_paddle_ocr_available,
    _get_sync_redis,
    _serialize_regions,
    _deserialize_regions,
    _ocr_cache_key,
    OCR_CACHE_TTL_SECONDS,
)

# ---- Intake tasks (PDF / ZIP) ----
from app.workers.intake_tasks import (  # noqa: F401
    process_pdf_task,
    process_zip_task,
    process_single_page_task,
)

# ---- Extraction tasks (VLM + images) ----
from app.workers.extraction_tasks import (  # noqa: F401
    extract_products_task,
    extract_product_images_task,
)

# ---- Export tasks ----
from app.workers.export_tasks import (  # noqa: F401
    export_products_task,
    cleanup_exports_task,
)

# ---- Maintenance tasks ----
from app.workers.maintenance_tasks import (  # noqa: F401
    cleanup_old_files_task,
    update_stats_task,
    aggregate_usage_data_task,
    monitor_budgets_task,
    cleanup_audit_logs_task,
    cleanup_notifications_task,
    reset_spending_counters_task,
    send_contact_emails_task,
)
