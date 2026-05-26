"""
Workers Package.

This package contains Celery workers and background tasks.

Components:
    - celery_app: Celery application configuration
    - tasks: Re-export shim (preserves ``from app.workers.tasks import ...``)
    - db_helpers: Synchronous DB sessions and helper functions for tasks
    - ocr_helpers: PaddleOCR Redis-backed caching
    - intake_tasks: PDF / ZIP processing tasks
    - extraction_tasks: VLM extraction + image cropping tasks
    - export_tasks: Product export + export cleanup tasks
    - maintenance_tasks: Cleanup, stats, budget, notification tasks
"""

from app.workers.celery_app import celery_app
from app.workers.intake_tasks import (
    process_pdf_task,
    process_single_page_task,
    process_zip_task,
)
from app.workers.extraction_tasks import (
    extract_products_task,
    extract_product_images_task,
)
from app.workers.export_tasks import (
    export_products_task,
    cleanup_exports_task,
)
from app.workers.maintenance_tasks import (
    cleanup_old_files_task,
    update_stats_task,
    aggregate_usage_data_task,
    monitor_budgets_task,
    cleanup_audit_logs_task,
    cleanup_notifications_task,
    reset_spending_counters_task,
    send_contact_emails_task,
)

__all__ = [
    "celery_app",
    "process_pdf_task",
    "process_single_page_task",
    "process_zip_task",
    "extract_products_task",
    "extract_product_images_task",
    "export_products_task",
    "cleanup_exports_task",
    "cleanup_old_files_task",
    "update_stats_task",
    "aggregate_usage_data_task",
    "monitor_budgets_task",
    "cleanup_audit_logs_task",
    "cleanup_notifications_task",
    "reset_spending_counters_task",
    "send_contact_emails_task",
]
