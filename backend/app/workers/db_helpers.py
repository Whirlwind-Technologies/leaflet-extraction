"""
Database and async helper utilities for Celery tasks.

Provides synchronous database session management, an async-to-sync bridge,
VLM usage recording, extraction data cleanup, leaflet status updates,
platform quota consumption, and organization provider checks.

These helpers are shared across multiple task modules (intake, extraction,
export, maintenance) and are intentionally kept in a single module to
avoid circular imports between task files.
"""

import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, delete, func as sa_func, select, text, update
from sqlalchemy.orm import Session

from app.models.analytics import CostTracking
from app.models.organization_usage import OrganizationVLMUsage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database engine singleton for connection pooling
# ---------------------------------------------------------------------------

_db_engine = None
_db_session_factory = None


def get_sync_db_session():
    """
    Get a synchronous database session for Celery tasks.

    Uses a singleton engine with connection pooling for efficiency.
    """
    global _db_engine, _db_session_factory

    if _db_engine is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings

        _db_engine = create_engine(
            settings.database_url_sync,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        _db_session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_db_engine
        )

    return _db_session_factory()


def run_async(coro):
    """Run an async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# VLM usage recording
# ---------------------------------------------------------------------------

def _record_vlm_usage(
    db: Session,
    organization_id: UUID,
    provider_info: dict,
    input_tokens: int,
    output_tokens: int,
    total_cost: float,
    page_count: int = 0,
    product_count: int = 0,
    average_confidence: Optional[float] = None,
):
    """
    Record VLM usage to OrganizationVLMUsage table for usage reports.

    Args:
        db: Database session
        organization_id: Organization UUID
        provider_info: Provider info dict with type, provider_id, etc.
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        total_cost: Total cost in USD
        page_count: Number of pages processed
        product_count: Number of products extracted
        average_confidence: Average extraction confidence
    """
    if not organization_id:
        logger.warning("Cannot record VLM usage: no organization_id")
        return

    # Get provider ID (could be organization or platform provider)
    provider_id = provider_info.get('provider_id')
    if not provider_id:
        logger.warning("Cannot record VLM usage: no provider_id in provider_info")
        return

    try:
        provider_uuid = UUID(provider_id)
    except (ValueError, TypeError):
        logger.warning(f"Invalid provider_id format: {provider_id}")
        return

    usage_date = date.today()
    current_hour = datetime.now(timezone.utc).hour

    # Try to find existing record for today
    existing = db.execute(
        select(OrganizationVLMUsage).where(
            OrganizationVLMUsage.organization_id == organization_id,
            OrganizationVLMUsage.platform_provider_id == provider_uuid,
            OrganizationVLMUsage.usage_date == usage_date,
            OrganizationVLMUsage.usage_hour == current_hour,
        )
    ).scalar_one_or_none()

    if existing:
        # Update existing record
        existing.request_count += 1
        existing.input_tokens += input_tokens
        existing.output_tokens += output_tokens
        existing.total_cost = (existing.total_cost or 0) + total_cost
        existing.leaflet_count = (existing.leaflet_count or 0) + 1
        existing.page_count = (existing.page_count or 0) + page_count
        existing.product_count = (existing.product_count or 0) + product_count
        if average_confidence is not None:
            # Update rolling average
            old_avg = existing.average_confidence or 0
            old_count = existing.leaflet_count - 1
            existing.average_confidence = (old_avg * old_count + average_confidence) / existing.leaflet_count
    else:
        # Create new record
        new_usage = OrganizationVLMUsage(
            organization_id=organization_id,
            platform_provider_id=provider_uuid,
            usage_date=usage_date,
            usage_hour=current_hour,
            request_count=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            leaflet_count=1,
            page_count=page_count,
            product_count=product_count,
            average_confidence=average_confidence,
        )
        db.add(new_usage)

    db.commit()
    logger.debug(
        f"Recorded VLM usage: org={organization_id}, provider={provider_id}, "
        f"tokens={input_tokens + output_tokens}, cost=${total_cost:.4f}"
    )


# ---------------------------------------------------------------------------
# Extraction data cleanup
# ---------------------------------------------------------------------------

def _cleanup_extraction_data_sync(db: Session, leaflet, progress=None) -> dict:
    """
    Synchronous cleanup of extraction data for a leaflet.

    This function removes all existing products and their images before
    re-extraction to prevent duplicate records.

    Args:
        db: Synchronous database session
        leaflet: The leaflet model instance
        progress: Optional progress publisher for status updates

    Returns:
        Dict with cleanup statistics
    """
    from app.models.product import Product, ProductReview
    from app.models.leaflet import LeafletPage
    from app.utils.storage import get_storage_backend

    stats = {
        "products_deleted": 0,
        "reviews_deleted": 0,
        "storage_files_deleted": 0,
    }

    # Delete any CostTracking rows for this leaflet to avoid stale analytics
    # Must happen before the early return when no products exist
    db.execute(delete(CostTracking).where(CostTracking.leaflet_id == leaflet.id))
    db.commit()  # Commit CostTracking delete so it takes effect on all paths

    # Get all products for this leaflet
    products_result = db.execute(
        select(Product).where(Product.leaflet_id == leaflet.id)
    )
    products = products_result.scalars().all()

    if not products:
        return stats

    # Collect image paths to delete from storage
    image_paths_to_delete = []
    for product in products:
        if product.image_path:
            image_paths_to_delete.append(product.image_path)
        if product.image_url and "leaflets/" in str(product.image_url):
            try:
                if "/" in product.image_url:
                    path_parts = product.image_url.split("leaflets/")
                    if len(path_parts) > 1:
                        path = "leaflets/" + path_parts[1].split("?")[0]
                        image_paths_to_delete.append(path)
            except Exception as e:
                logger.warning(f"Could not extract image path from URL: {e}")

    # Delete product reviews first (due to foreign key)
    for product in products:
        reviews_result = db.execute(
            select(ProductReview).where(ProductReview.product_id == product.id)
        )
        reviews = reviews_result.scalars().all()
        for review in reviews:
            db.delete(review)
            stats["reviews_deleted"] += 1

    # Delete products
    for product in products:
        db.delete(product)
        stats["products_deleted"] += 1

    # Commit database deletions
    db.commit()

    # Delete product images from storage
    storage = get_storage_backend()
    for image_path in image_paths_to_delete:
        try:
            if run_async(storage.file_exists(image_path)):
                run_async(storage.delete_file(image_path))
                stats["storage_files_deleted"] += 1
        except Exception as e:
            logger.warning(f"Failed to delete image {image_path}: {e}")

    # Also delete the entire products folder for this leaflet
    products_folder = f"leaflets/{leaflet.leaflet_id}/products/"
    try:
        deleted_count = run_async(storage.delete_folder(products_folder))
        if deleted_count > 0:
            stats["storage_files_deleted"] += deleted_count
    except Exception as e:
        logger.warning(f"Failed to delete products folder: {e}")

    # Reset leaflet extraction-related counters
    leaflet.auto_approved_count = 0
    leaflet.review_required_count = 0
    leaflet.overall_confidence = None
    leaflet.api_tokens_used = 0
    leaflet.processing_cost = None

    # Reset processing metadata extraction fields (keep PDF processing data)
    if leaflet.processing_metadata:
        keys_to_remove = [
            "extraction_completed_at",
            "total_products_extracted",
            "auto_approved_count",
            "review_required_count",
            "input_tokens",
            "output_tokens",
            "merged_products",
            "duplicates_removed",
            "parallel_extraction",
        ]
        for key in keys_to_remove:
            leaflet.processing_metadata.pop(key, None)

    # Reset page product counts
    pages_result = db.execute(
        select(LeafletPage).where(LeafletPage.leaflet_id == leaflet.id)
    )
    pages = pages_result.scalars().all()
    for page in pages:
        page.products_count = 0

    db.commit()

    return stats


# ---------------------------------------------------------------------------
# Leaflet status helpers
# ---------------------------------------------------------------------------

def _update_leaflet_status(
    db: Session,
    leaflet_id: str,
    status: str,
    message: Optional[str] = None,
    current_step: Optional[str] = None,
):
    """Helper to update leaflet status."""
    from app.models.leaflet import Leaflet, LeafletStatus

    try:
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet:
            leaflet.status = LeafletStatus(status)
            if message:
                leaflet.status_message = message
            if current_step:
                leaflet.current_step = current_step
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update leaflet status: {e}")
        db.rollback()


# ---------------------------------------------------------------------------
# Platform quota management
# ---------------------------------------------------------------------------

def _try_consume_platform_quota(
    db: Session,
    organization_id,
) -> tuple:
    """
    Atomically try to consume one platform provider quota slot.

    Uses an atomic UPDATE with a WHERE guard so that the counter is only
    incremented when the organization still has quota remaining.  This
    prevents race conditions when multiple extraction tasks start
    simultaneously for the same organization.

    Args:
        db: Synchronous database session (Celery context).
        organization_id: UUID of the organization to check.

    Returns:
        Tuple of (success, limit, used) where:
            success -- True if a slot was consumed, False if limit reached.
            limit   -- The configured platform_leaflet_limit.
            used    -- The (possibly updated) platform_leaflets_used count.
    """
    try:
        result = db.execute(
            text("""
                UPDATE organizations
                SET platform_leaflets_used = platform_leaflets_used + 1,
                    updated_at = NOW()
                WHERE id = :org_id
                  AND (platform_leaflet_limit = 0
                       OR platform_leaflets_used < platform_leaflet_limit)
                RETURNING platform_leaflets_used, platform_leaflet_limit
            """),
            {"org_id": str(organization_id)},
        )
        row = result.fetchone()
        db.commit()

        if row is not None:
            # Slot consumed successfully
            return True, row[1], row[0]

        # Limit exceeded -- fetch current values for error reporting
        org_result = db.execute(
            text("""
                SELECT platform_leaflet_limit, platform_leaflets_used
                FROM organizations WHERE id = :org_id
            """),
            {"org_id": str(organization_id)},
        )
        org_row = org_result.fetchone()
        if org_row:
            return False, org_row[0], org_row[1]

        # Organization not found (should never happen at this point).
        # Fail closed: deny the request rather than silently allowing it.
        logger.critical(
            f"Organization {organization_id} not found during quota check "
            f"— data integrity issue"
        )
        return False, 10, 10

    except Exception as e:
        logger.error(
            f"Failed to check platform quota for org {organization_id}: {e}. "
            f"Failing closed — denying request as a precaution."
        )
        db.rollback()
        return False, 10, 10


def _check_org_has_own_provider(db: Session, organization_id) -> bool:
    """
    Check whether the organization has at least one active VLM provider.

    Args:
        db: Synchronous database session.
        organization_id: UUID of the organization.

    Returns:
        True if the organization has its own active VLM provider configured.
    """
    from app.models.vlm_provider import VLMProvider

    result = db.execute(
        select(VLMProvider).where(
            VLMProvider.organization_id == organization_id,
            VLMProvider.is_active.is_(True),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
