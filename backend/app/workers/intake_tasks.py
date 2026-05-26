"""
Intake tasks — PDF and ZIP file processing.

Contains Celery tasks that handle the initial ingestion of leaflet files:
- ``process_pdf_task``: Convert PDF pages to images and store.
- ``process_zip_task``: Extract images from a ZIP archive.
- ``process_single_page_task``: Reprocess a single page from a PDF.

Each task preserves its original ``name=`` so that in-flight messages in
Redis queues continue to resolve after the module split.
"""

import logging
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.workers.db_helpers import (
    get_sync_db_session,
    run_async,
    _update_leaflet_status,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# process_pdf_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_pdf_task",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    soft_time_limit=1800,  # 30 minutes - large PDFs (40MB+) need time on modest hardware
    time_limit=2100,       # 35 minutes hard limit
)
def process_pdf_task(self, leaflet_id: str) -> dict:
    """
    Process a PDF leaflet: convert to images and store.

    This task:
    1. Retrieves the PDF from storage
    2. Converts each page to a high-resolution image
    3. Generates thumbnails
    4. Updates the database with page information

    Args:
        leaflet_id: The leaflet ID to process

    Returns:
        Dict with processing results
    """
    logger.info(f"Starting PDF processing for leaflet: {leaflet_id}")
    db = None

    try:
        db = get_sync_db_session()
        logger.info(f"Database session created for leaflet: {leaflet_id}")

        from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus
        from app.core.intake.pdf_processor import get_pdf_processor
        from app.utils.storage import get_storage_backend

        # Get leaflet from database
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise ValueError(f"Leaflet not found: {leaflet_id}")

        logger.info(f"Found leaflet: {leaflet_id}, source_path: {leaflet.source_path}")

        # Update status to processing
        leaflet.status = LeafletStatus.PROCESSING
        leaflet.current_step = "pdf_conversion"
        leaflet.processing_started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Updated status to PROCESSING for leaflet: {leaflet_id}")

        # Publish progress update for real-time WebSocket tracking
        from app.core.progress import get_progress_publisher
        progress = get_progress_publisher()
        progress.publish_status(leaflet_id, "processing", "Starting PDF conversion...")

        # Get PDF content from storage
        logger.info(f"Downloading PDF from storage: {leaflet.source_path}")
        storage = get_storage_backend()
        pdf_content = run_async(storage.download_file(leaflet.source_path))
        logger.info(f"Downloaded PDF: {len(pdf_content)} bytes")

        # Process PDF
        logger.info(f"Starting PDF conversion for leaflet: {leaflet_id}")
        processor = get_pdf_processor()
        processing_result = run_async(
            processor.process_pdf(
                pdf_content=pdf_content,
                leaflet_id=leaflet_id,
                save_source=False,  # Already saved during upload
            )
        )

        if not processing_result.success:
            logger.error(f"PDF processing failed: {processing_result.error_message}")
            leaflet.status = LeafletStatus.FAILED
            leaflet.status_message = processing_result.error_message
            db.commit()
            raise ValueError(processing_result.error_message)

        logger.info(f"PDF conversion complete: {processing_result.page_count} pages")

        # Update leaflet with results
        leaflet.page_count = processing_result.page_count
        leaflet.pdf_type = processing_result.pdf_type
        leaflet.progress = 0.3  # 30% complete after PDF conversion
        leaflet.current_step = "pages_created"

        # Create page records
        total_pages = processing_result.page_count
        for i, page_result in enumerate(processing_result.pages):
            page = LeafletPage(
                leaflet_id=leaflet.id,
                page_number=page_result.page_number,
                image_path=page_result.image_path,
                thumbnail_path=page_result.thumbnail_path,
                image_url=page_result.image_url,
                width=page_result.width,
                height=page_result.height,
                file_size=page_result.file_size,
                format=page_result.format,
                is_processed=False,  # Will be True after VLM extraction
            )
            db.add(page)

            # Publish per-page progress (5% to 30% range for PDF processing)
            progress.publish_progress(
                leaflet_id=leaflet_id,
                progress=0.05 + (0.25 * (i + 1) / total_pages),
                message=f"Processed page {i + 1}/{total_pages}",
            )

        # Update metadata
        leaflet.processing_metadata = {
            **leaflet.processing_metadata,
            "pdf_metadata": processing_result.metadata,
            "pdf_conversion_completed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Check if user has a VLM provider configured before queueing extraction
        from app.models.vlm_provider import VLMProvider
        from sqlalchemy import func
        from app.models.platform_vlm_provider import PlatformVLMProvider

        # Count active organization-level providers (check by organization_id)
        provider_count_result = db.execute(
            select(func.count(VLMProvider.id)).where(
                VLMProvider.organization_id == leaflet.organization_id,
                VLMProvider.is_active == True
            )
        )
        has_org_provider = (provider_count_result.scalar() or 0) > 0

        # Count active platform-level providers as fallback
        platform_count_result = db.execute(
            select(func.count(PlatformVLMProvider.id)).where(
                PlatformVLMProvider.is_active == True
            )
        )
        has_platform_provider = (platform_count_result.scalar() or 0) > 0

        logger.info(
            f"VLM provider check: org_provider={has_org_provider}, platform_provider={has_platform_provider}, "
            f"org_id={leaflet.organization_id}"
        )

        if not has_org_provider and not has_platform_provider:
            # No VLM provider available - mark as awaiting configuration
            logger.warning(
                f"No VLM provider configured for user {leaflet.user_id}. "
                f"Leaflet {leaflet_id} will wait for manual extraction trigger."
            )
            leaflet.status = LeafletStatus.VALIDATING  # Ready but waiting for extraction
            leaflet.current_step = "awaiting_vlm_configuration"
            leaflet.status_message = (
                "PDF processed successfully. Configure an AI provider in Settings "
                "to extract products, then use 'Extract Products' button."
            )
            db.commit()

            return {
                "success": True,
                "leaflet_id": leaflet_id,
                "page_count": processing_result.page_count,
                "pdf_type": processing_result.pdf_type,
                "extraction_queued": False,
                "message": "No VLM provider configured. Manual extraction trigger required.",
            }

        # Mark as ready for extraction
        leaflet.status = LeafletStatus.EXTRACTING
        leaflet.current_step = "starting_extraction"

        db.commit()

        logger.info(
            f"PDF processing completed for {leaflet_id}: "
            f"{processing_result.page_count} pages. Chaining extraction task..."
        )

        # Chain the extraction task
        from app.workers.tasks import extract_products_task
        extract_products_task.apply_async(
            args=[leaflet_id],
            queue="extraction",
            countdown=2,  # Small delay to ensure DB commit is visible
        )

        return {
            "success": True,
            "leaflet_id": leaflet_id,
            "page_count": processing_result.page_count,
            "pdf_type": processing_result.pdf_type,
            "extraction_queued": True,
        }

    except SoftTimeLimitExceeded:
        logger.error(f"PDF processing timed out for {leaflet_id}")
        if db:
            _update_leaflet_status(db, leaflet_id, "failed", "Processing timed out")
        raise

    except Exception as e:
        logger.error(f"PDF processing failed for {leaflet_id}: {e}", exc_info=True)
        if db:
            _update_leaflet_status(db, leaflet_id, "failed", str(e))
        raise

    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# process_zip_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_zip_task",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    soft_time_limit=1800,  # 30 minutes
    time_limit=2100,       # 35 minutes hard limit
)
def process_zip_task(self, leaflet_id: str) -> dict:
    """
    Process a ZIP file containing leaflet page images.

    This task:
    1. Retrieves the ZIP from storage
    2. Extracts and validates images
    3. Sorts images by natural filename order
    4. Processes each image (standardize, thumbnail)
    5. Updates the database with page information
    6. Chains to extract_products_task

    Args:
        leaflet_id: The leaflet ID to process

    Returns:
        Dict with processing results
    """
    logger.info(f"Starting ZIP processing for leaflet: {leaflet_id}")
    db = None

    try:
        db = get_sync_db_session()
        logger.info(f"Database session created for leaflet: {leaflet_id}")

        from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus, LeafletSourceType
        from app.core.intake.zip_processor import get_zip_processor
        from app.utils.storage import get_storage_backend

        # Get leaflet from database
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise ValueError(f"Leaflet not found: {leaflet_id}")

        logger.info(f"Found leaflet: {leaflet_id}, source_path: {leaflet.source_path}")

        # Update status to processing
        leaflet.status = LeafletStatus.PROCESSING
        leaflet.current_step = "zip_extraction"
        leaflet.processing_started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Updated status to PROCESSING for leaflet: {leaflet_id}")

        # Get ZIP content from storage
        logger.info(f"Downloading ZIP from storage: {leaflet.source_path}")
        storage = get_storage_backend()
        zip_content = run_async(storage.download_file(leaflet.source_path))
        logger.info(f"Downloaded ZIP: {len(zip_content)} bytes")

        # Process ZIP
        logger.info(f"Starting ZIP processing for leaflet: {leaflet_id}")
        processor = get_zip_processor()
        processing_result = run_async(
            processor.process_zip(
                zip_content=zip_content,
                leaflet_id=leaflet_id,
                save_source=False,  # Already saved during upload
            )
        )

        if not processing_result.success:
            logger.error(f"ZIP processing failed: {processing_result.error_message}")
            leaflet.status = LeafletStatus.FAILED
            leaflet.status_message = processing_result.error_message
            db.commit()
            raise ValueError(processing_result.error_message)

        logger.info(f"ZIP extraction complete: {processing_result.page_count} pages")

        # Update leaflet with results
        leaflet.page_count = processing_result.page_count
        leaflet.source_type = LeafletSourceType.IMAGES
        leaflet.progress = 0.3  # 30% complete after image processing
        leaflet.current_step = "pages_created"

        # Create page records
        for page_result in processing_result.pages:
            page = LeafletPage(
                leaflet_id=leaflet.id,
                page_number=page_result.page_number,
                image_path=page_result.image_path,
                thumbnail_path=page_result.thumbnail_path,
                image_url=page_result.image_url,
                width=page_result.width,
                height=page_result.height,
                file_size=page_result.file_size,
                format=page_result.format,
                is_processed=False,  # Will be True after VLM extraction
            )
            db.add(page)

        # Update metadata
        leaflet.processing_metadata = {
            **leaflet.processing_metadata,
            "zip_processing_completed_at": datetime.now(timezone.utc).isoformat(),
            "skipped_files": processing_result.skipped_files,
            "failed_images": processing_result.failed_images,
        }

        # Check if user has a VLM provider configured before queueing extraction
        from app.models.vlm_provider import VLMProvider
        from sqlalchemy import func
        from app.models.platform_vlm_provider import PlatformVLMProvider

        # Count active organization-level providers
        provider_count_result = db.execute(
            select(func.count(VLMProvider.id)).where(
                VLMProvider.organization_id == leaflet.organization_id,
                VLMProvider.is_active == True
            )
        )
        has_org_provider = (provider_count_result.scalar() or 0) > 0

        # Count active platform-level providers as fallback
        platform_count_result = db.execute(
            select(func.count(PlatformVLMProvider.id)).where(
                PlatformVLMProvider.is_active == True
            )
        )
        has_platform_provider = (platform_count_result.scalar() or 0) > 0

        logger.info(
            f"VLM provider check: org_provider={has_org_provider}, platform_provider={has_platform_provider}, "
            f"org_id={leaflet.organization_id}"
        )

        if not has_org_provider and not has_platform_provider:
            # No VLM provider available - mark as awaiting configuration
            logger.warning(
                f"No VLM provider configured for user {leaflet.user_id}. "
                f"Leaflet {leaflet_id} will wait for manual extraction trigger."
            )
            leaflet.status = LeafletStatus.VALIDATING
            leaflet.current_step = "awaiting_vlm_configuration"
            leaflet.status_message = (
                "Images processed successfully. Configure an AI provider in Settings "
                "to extract products, then use 'Extract Products' button."
            )
            db.commit()

            return {
                "success": True,
                "leaflet_id": leaflet_id,
                "page_count": processing_result.page_count,
                "source_type": "images",
                "extraction_queued": False,
                "message": "No VLM provider configured. Manual extraction trigger required.",
            }

        # Mark as ready for extraction
        leaflet.status = LeafletStatus.EXTRACTING
        leaflet.current_step = "starting_extraction"

        db.commit()

        logger.info(
            f"ZIP processing completed for {leaflet_id}: "
            f"{processing_result.page_count} pages. Chaining extraction task..."
        )

        # Chain the extraction task
        from app.workers.tasks import extract_products_task
        extract_products_task.apply_async(
            args=[leaflet_id],
            queue="extraction",
            countdown=2,  # Small delay to ensure DB commit is visible
        )

        return {
            "success": True,
            "leaflet_id": leaflet_id,
            "page_count": processing_result.page_count,
            "source_type": "images",
            "extraction_queued": True,
        }

    except SoftTimeLimitExceeded:
        logger.error(f"ZIP processing timed out for {leaflet_id}")
        if db:
            _update_leaflet_status(db, leaflet_id, "failed", "Processing timed out")
        raise

    except Exception as e:
        logger.error(f"ZIP processing failed for {leaflet_id}: {e}", exc_info=True)
        if db:
            _update_leaflet_status(db, leaflet_id, "failed", str(e))
        raise

    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# process_single_page_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_single_page_task",
    max_retries=2,
)
def process_single_page_task(
    self,
    leaflet_id: str,
    page_number: int,
) -> dict:
    """
    Process a single page from a PDF.

    Useful for reprocessing individual pages or parallel processing.

    Args:
        leaflet_id: The leaflet ID
        page_number: Page number to process (1-indexed)

    Returns:
        Dict with page processing results
    """
    logger.info(f"Processing page {page_number} for leaflet: {leaflet_id}")
    db = get_sync_db_session()

    try:
        from app.models.leaflet import Leaflet, LeafletPage
        from app.core.intake.pdf_processor import get_pdf_processor
        from app.utils.storage import get_storage_backend

        # Get leaflet
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise ValueError(f"Leaflet not found: {leaflet_id}")

        # Get PDF content
        storage = get_storage_backend()
        pdf_content = run_async(storage.download_file(leaflet.source_path))

        # Process single page
        processor = get_pdf_processor()
        image = run_async(processor.extract_page(pdf_content, page_number))

        if image is None:
            raise ValueError(f"Could not extract page {page_number}")

        # Process the page image
        page_result = run_async(
            processor._process_page(image, leaflet_id, page_number)
        )

        # Update or create page record
        result = db.execute(
            select(LeafletPage).where(
                LeafletPage.leaflet_id == leaflet.id,
                LeafletPage.page_number == page_number,
            )
        )
        page = result.scalar_one_or_none()

        if page:
            page.image_path = page_result.image_path
            page.thumbnail_path = page_result.thumbnail_path
            page.image_url = page_result.image_url
            page.width = page_result.width
            page.height = page_result.height
            page.file_size = page_result.file_size
        else:
            page = LeafletPage(
                leaflet_id=leaflet.id,
                page_number=page_number,
                image_path=page_result.image_path,
                thumbnail_path=page_result.thumbnail_path,
                image_url=page_result.image_url,
                width=page_result.width,
                height=page_result.height,
                file_size=page_result.file_size,
                format=page_result.format,
            )
            db.add(page)

        db.commit()

        return {
            "success": True,
            "leaflet_id": leaflet_id,
            "page_number": page_number,
            "image_path": page_result.image_path,
        }

    except Exception as e:
        logger.error(f"Page processing failed: {e}")
        raise

    finally:
        db.close()
