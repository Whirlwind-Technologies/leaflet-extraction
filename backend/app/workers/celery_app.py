"""
Celery Worker Configuration and Tasks.

This module configures Celery and defines background tasks for
PDF processing and other async operations.

Example Usage:
    from app.workers.celery_app import celery_app
    from app.workers.tasks import process_pdf_task
    
    # Queue a PDF for processing
    result = process_pdf_task.delay(leaflet_id="LEAF_2025_001234")
"""

import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Get broker/backend URLs from environment with defaults
def _build_redis_url(db: int) -> str:
    """Build Redis URL from individual env vars, including password if set."""
    host = os.getenv('REDIS_HOST', 'localhost')
    port = os.getenv('REDIS_PORT', '6379')
    password = os.getenv('REDIS_PASSWORD', '')
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", _build_redis_url(1))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _build_redis_url(2))

# Create Celery application
celery_app = Celery(
    "leaflet_extraction",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks",
        "app.workers.intake_tasks",
        "app.workers.extraction_tasks",
        "app.workers.export_tasks",
        "app.workers.maintenance_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "4")),
    
    # Result settings
    result_expires=86400,  # 24 hours
    
    # Task routes
    task_routes={
        "app.workers.tasks.process_pdf_task": {"queue": "pdf"},
        "app.workers.tasks.process_page_task": {"queue": "pdf"},
        "app.workers.tasks.extract_products_task": {"queue": "extraction"},
        "app.workers.tasks.extract_product_images_task": {"queue": "extraction"},
        "app.workers.tasks.validate_products_task": {"queue": "validation"},
        "app.workers.tasks.export_products_task": {"queue": "default"},
        "app.workers.tasks.cleanup_exports_task": {"queue": "default"},
        "app.workers.tasks.send_contact_emails_task": {"queue": "default"},
    },
    
    # Default queue
    task_default_queue="default",
    
    # Retry settings
    task_annotations={
        "*": {
            "rate_limit": "10/s",
            "max_retries": 3,
            "default_retry_delay": 60,
        }
    },
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-old-files": {
        "task": "app.workers.tasks.cleanup_old_files_task",
        "schedule": 86400.0,  # Daily
    },
    "update-processing-stats": {
        "task": "app.workers.tasks.update_stats_task",
        "schedule": 3600.0,  # Hourly
    },
    # Budget monitoring tasks
    "monitor-budgets": {
        "task": "monitor_budgets",
        "schedule": 900.0,  # Every 15 minutes
    },
    "aggregate-usage-data": {
        "task": "aggregate_usage_data",
        "schedule": 3600.0,  # Hourly
    },
    # Notification cleanup task
    "cleanup-notifications": {
        "task": "cleanup_notifications",
        "schedule": 86400.0,  # Daily
    },
    # Spending counter reset (monthly, daily, hourly)
    "reset-spending-counters": {
        "task": "reset_spending_counters",
        "schedule": 3600.0,  # Hourly
    },
    # Export file and job cleanup
    "cleanup-exports": {
        "task": "app.workers.tasks.cleanup_exports_task",
        "schedule": 3600.0,  # Every hour
    },
}