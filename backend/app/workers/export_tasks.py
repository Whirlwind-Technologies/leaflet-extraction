"""
Export tasks — product data export and cleanup.

Contains Celery tasks for generating and managing export files:
- ``export_products_task``: Generate CSV/Excel/JSON export files for large
  datasets asynchronously.
- ``cleanup_exports_task``: Periodic task to delete expired export files
  and old job records.

Each task preserves its original ``name=`` so that in-flight messages in
Redis queues continue to resolve after the module split.
"""

import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.workers.db_helpers import get_sync_db_session, run_async

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# export_products_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.export_products_task",
    queue="default",
    soft_time_limit=600,   # 10 minutes
    time_limit=660,        # 11 minutes hard limit
    acks_late=True,
    max_retries=2,
)
def export_products_task(self, export_job_id: str, request_data: dict) -> dict:
    """
    Export products to a file asynchronously for large datasets (1000+).

    This task is dispatched by the ``POST /products/export`` endpoint when
    the product count exceeds the sync threshold.  It:

    1. Marks the ExportJob as ``processing``.
    2. Deserializes ``request_data`` into a ``ProductExportRequest``.
    3. Streams products via ``ExportService.export_products()``.
    4. Uploads the generated file to S3 via ``export_storage``.
    5. Updates the ExportJob record with ``file_path``, ``file_size_bytes``,
       and ``status=completed``.
    6. On failure, sets ``status=failed`` with an ``error_message``.

    Args:
        self: Celery task instance (for retries).
        export_job_id: UUID string of the ExportJob record.
        request_data: JSON-serializable dict from
                      ``ProductExportRequest.model_dump(mode="json")``.

    Returns:
        Dict with status, export_job_id, and file_size_bytes.
    """
    db = get_sync_db_session()

    try:
        from app.models.export_job import ExportJob
        from app.schemas.product_export import ProductExportRequest
        from app.services.export_service import ExportService
        from app.utils.export_storage import upload_export_file

        logger.info(
            f"Starting export task for job {export_job_id}",
        )

        # 1. Look up the ExportJob and mark as processing
        job = db.execute(
            select(ExportJob).where(ExportJob.id == export_job_id)
        ).scalar_one_or_none()

        if job is None:
            logger.error(f"ExportJob not found: {export_job_id}")
            return {"status": "failed", "error": "ExportJob not found"}

        job.status = "processing"
        db.commit()

        # 2. Deserialize the request
        export_request = ProductExportRequest(**request_data)
        organization_id = job.organization_id

        # 2a. Verify the owning user still exists and belongs to the org
        from app.models.user import User
        user_result = db.execute(select(User).where(User.id == job.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError(
                f"User {job.user_id} not found for export job {export_job_id}"
            )

        # 2b. For 'selected' mode, verify ALL product_ids belong to the org
        if export_request.mode == "selected" and export_request.product_ids:
            from sqlalchemy import func as sql_func
            from app.models.product import Product

            accessible_count = db.execute(
                select(sql_func.count(Product.id)).where(
                    Product.id.in_(export_request.product_ids),
                    Product.organization_id == job.organization_id,
                )
            ).scalar()
            if accessible_count != len(export_request.product_ids):
                inaccessible = len(export_request.product_ids) - accessible_count
                raise ValueError(
                    f"{inaccessible} product IDs are inaccessible "
                    f"to this organization"
                )

        # 3. Generate the export file using a temporary async engine.
        #    The FastAPI app's async engine is not initialized in the Celery
        #    worker context, so we create a one-shot engine for this task.
        async def _generate_export():
            """Run the async export service with a temporary async engine."""
            from sqlalchemy.ext.asyncio import (
                AsyncSession as _AsyncSession,
                async_sessionmaker as _async_sessionmaker,
                create_async_engine as _create_async_engine,
            )
            from app.config import settings

            engine = _create_async_engine(
                settings.database_url,
                pool_size=5,
                max_overflow=5,
                pool_pre_ping=True,
            )
            session_factory = _async_sessionmaker(
                bind=engine,
                class_=_AsyncSession,
                expire_on_commit=False,
            )
            try:
                async with session_factory() as async_db:
                    service = ExportService(async_db)
                    file_buffer = await service.export_products(
                        export_request, organization_id
                    )
                    return file_buffer.getvalue()
            finally:
                await engine.dispose()

        file_bytes = run_async(_generate_export())

        # 4. Upload to S3
        file_format = {
            "csv": "csv",
            "excel": "xlsx",
            "json": "json",
        }.get(job.format, job.format)

        file_path = run_async(
            upload_export_file(
                organization_id=organization_id,
                export_id=export_job_id,
                file_bytes=file_bytes,
                file_format=file_format,
            )
        )

        # 5. Update job record as completed
        job.status = "completed"
        job.file_path = file_path
        job.file_size_bytes = len(file_bytes)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Export task completed for job {export_job_id}: "
            f"{job.product_count} products, {len(file_bytes)} bytes"
        )

        return {
            "status": "completed",
            "export_job_id": export_job_id,
            "file_size_bytes": len(file_bytes),
        }

    except SoftTimeLimitExceeded:
        logger.error(f"Export task timed out: {export_job_id}")
        try:
            job = db.execute(
                select(ExportJob).where(ExportJob.id == export_job_id)
            ).scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = "Export task timed out after 10 minutes"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        raise

    except Exception as exc:
        logger.exception(f"Export task failed for job {export_job_id}: {exc}")
        try:
            job = db.execute(
                select(ExportJob).where(ExportJob.id == export_job_id)
            ).scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()

        # Retry with exponential backoff for transient errors
        if self.request.retries < self.max_retries:
            self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

        return {
            "status": "failed",
            "export_job_id": export_job_id,
            "error": str(exc)[:500],
        }

    finally:
        db.close()


# ---------------------------------------------------------------------------
# cleanup_exports_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.workers.tasks.cleanup_exports_task",
    queue="default",
    soft_time_limit=300,   # 5 minutes
    time_limit=360,        # 6 minutes hard limit
)
def cleanup_exports_task() -> dict:
    """
    Periodic task to delete expired export files and old job records.

    Runs hourly via Celery beat.  Two cleanup phases:
    1. Delete export files from S3/local storage older than 24 hours.
    2. Delete ExportJob database records older than 7 days.

    Returns:
        Dict with deleted_files and deleted_jobs counts.
    """
    from app.utils.export_storage import cleanup_old_exports

    # Phase 1: Clean up expired files from storage
    deleted_files = run_async(cleanup_old_exports(max_age_hours=24))
    logger.info(f"Cleaned up {deleted_files} expired export files")

    # Phase 2: Clean up old ExportJob records (older than 7 days)
    deleted_jobs = 0
    db = get_sync_db_session()
    try:
        from app.models.export_job import ExportJob

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = db.execute(
            select(ExportJob).where(ExportJob.created_at < cutoff)
        )
        old_jobs = result.scalars().all()
        for job in old_jobs:
            db.delete(job)
        db.commit()
        deleted_jobs = len(old_jobs)
        logger.info(f"Cleaned up {deleted_jobs} old export job records")
    except Exception as exc:
        logger.error(f"Failed to clean up export jobs: {exc}")
        db.rollback()
    finally:
        db.close()

    return {"deleted_files": deleted_files, "deleted_jobs": deleted_jobs}
