"""
Extraction tasks — VLM product extraction and image cropping.

Contains Celery tasks that run the core extraction pipeline:
- ``extract_products_task``: Send page images to a VLM, reconcile products,
  validate, and store results.
- ``extract_product_images_task``: Crop individual product images from page
  images using bounding boxes.

Each task preserves its original ``name=`` so that in-flight messages in
Redis queues continue to resolve after the module split.
"""

import gc
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import and_, delete, select

from app.workers.celery_app import celery_app
from app.workers.db_helpers import (
    get_sync_db_session,
    run_async,
    _cleanup_extraction_data_sync,
    _update_leaflet_status,
    _try_consume_platform_quota,
)
from app.workers.ocr_helpers import clear_ocr_cache

# Analytics model for per-leaflet cost tracking
from app.models.analytics import CostTracking
from app.models.organization_usage import OrganizationVLMUsage

# Rate data for computing per-token cost breakdown
from app.models.vlm_provider import DEFAULT_MODELS, VLMProviderType
from app.models.platform_vlm_provider import PLATFORM_DEFAULT_MODELS, PlatformVLMProviderType

# Import BoundingBox at module level for fallback bbox generation
from app.core.extraction.schemas import BoundingBox

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# extract_products_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.extract_products_task",
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    soft_time_limit=1800,  # 30 minutes
    time_limit=2100,  # 35 minutes
)
def extract_products_task(self, leaflet_id: str, request_ip: Optional[str] = None) -> dict:
    """
    Extract products from a leaflet's page images using VLM.

    This task:
    1. Retrieves page images from storage
    2. Sends pages to Claude for product extraction (parallel)
    3. Performs cross-page reconciliation
    4. Validates extracted products
    5. Stores products in the database
    6. Updates leaflet status
    7. Publishes progress updates via Redis

    Args:
        leaflet_id: The leaflet ID to process
        request_ip: Client IP address from the triggering HTTP request (for audit logging)

    Returns:
        Dict with extraction results
    """
    logger.info(f"Starting product extraction for leaflet: {leaflet_id}")
    db = get_sync_db_session()

    try:
        from app.models.leaflet import Leaflet, LeafletPage, LeafletStatus
        from app.models.product import Product, ReviewStatus
        from app.core.extraction.vlm_extractor_service import VLMExtractorService
        from app.core.extraction.schemas import ExtractionContext, PageExtractionResult
        from app.core.extraction.reconciliation import ProductReconciler, sanitize_products
        from app.core.validation.validator import ProductValidator, determine_review_priority
        from app.core.progress import get_progress_publisher
        from app.utils.storage import get_storage_backend
        from app.config import settings

        # Initialize progress publisher
        progress = get_progress_publisher()

        # Get leaflet
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise ValueError(f"Leaflet not found: {leaflet_id}")

        # Initialize extractor with user's VLM provider settings
        # This will use the user's configured provider or fall back to system default
        try:
            extractor = VLMExtractorService(db, str(leaflet.user_id))
            provider_info = extractor.provider_info

            # Check if we have a valid provider or fallback
            if provider_info.get('type') == 'none':
                raise ValueError("No VLM provider available")

            logger.info(
                f"VLM Provider for extraction: {provider_info.get('provider_type', 'unknown')} / "
                f"{provider_info.get('model', 'default')} "
                f"(user_configured: {provider_info.get('is_user_configured', False)})"
            )
        except ValueError as e:
            logger.error(f"No VLM provider available: {e}")
            progress.publish_error(
                leaflet_id,
                "No AI provider configured. Please add one in Settings."
            )
            # Update status to validating (ready for manual trigger once provider is configured)
            leaflet.status = LeafletStatus.VALIDATING
            leaflet.current_step = "awaiting_vlm_configuration"
            leaflet.status_message = (
                "No AI provider configured. Please add one in Settings, then click 'Extract Products'."
            )
            db.commit()
            return {
                "success": False,
                "error": "No VLM provider configured",
                "message": "Configure an AI provider in Settings and retry extraction."
            }
        except Exception as e:
            logger.error(f"Failed to initialize VLM extractor: {e}")
            # No fallback available - all providers come from database
            logger.error("No VLM provider configured (organization or platform level)")
            progress.publish_error(leaflet_id, "No VLM provider configured")
            leaflet.status = LeafletStatus.VALIDATING
            leaflet.current_step = "awaiting_vlm_configuration"
            leaflet.status_message = (
                "No AI provider configured. Configure one in Settings or contact admin."
            )
            db.commit()
            return {"success": False, "error": "No VLM provider configured"}

        logger.info(f"Found leaflet: {leaflet_id}, status: {leaflet.status}")

        # --- Platform AI Provider Quota Check ---
        # If the extraction will use the platform shared provider (not the
        # org's own provider), enforce the per-organization leaflet limit.
        is_using_platform_provider = provider_info.get("type") == "platform"

        if is_using_platform_provider and leaflet.organization_id:
            # Skip quota check on re-extraction — quota was already consumed
            # the first time this leaflet was extracted with the platform provider.
            # Without this guard, re-extracting the same leaflet would decrement
            # the quota again, allowing users to exhaust their limit unfairly.
            if leaflet.used_platform_provider:
                logger.info(
                    f"Leaflet {leaflet_id} is a re-extraction with platform provider, "
                    f"skipping quota check (already consumed)"
                )
            else:
                logger.info(
                    f"Platform provider selected for {leaflet_id}, "
                    f"checking organization quota (org={leaflet.organization_id})"
                )
                try:
                    quota_ok, quota_limit, quota_used = _try_consume_platform_quota(
                        db, leaflet.organization_id
                    )
                except Exception as quota_err:
                    # Transient DB error — do NOT treat as quota exhaustion.
                    # Mark as a generic failure so the user can retry.
                    logger.error(
                        f"Transient error checking platform quota for "
                        f"org {leaflet.organization_id}, leaflet {leaflet_id}: {quota_err}"
                    )
                    error_message = (
                        "Temporary error while checking your extraction quota. "
                        "Please try again in a moment."
                    )
                    progress.publish_error(
                        leaflet_id,
                        error_message,
                        details={"error_code": "QUOTA_CHECK_ERROR"},
                    )
                    leaflet.status = LeafletStatus.FAILED
                    leaflet.current_step = "quota_check_error"
                    leaflet.status_message = error_message
                    db.commit()
                    return {
                        "success": False,
                        "error": "QUOTA_CHECK_ERROR",
                        "message": error_message,
                    }

                if not quota_ok:
                    # Quota exhausted -- block extraction
                    error_message = (
                        f"Your organization has used all {quota_limit} free leaflet "
                        f"extractions with the platform AI provider. Please add your "
                        f"own AI provider in Settings to continue."
                    )
                    logger.warning(
                        f"Platform quota exceeded for org {leaflet.organization_id}: "
                        f"limit={quota_limit}, used={quota_used}, leaflet={leaflet_id}"
                    )

                    # Publish WebSocket error with structured details
                    progress.publish_error(
                        leaflet_id,
                        error_message,
                        details={
                            "error_code": "PLATFORM_LIMIT_REACHED",
                            "limit": quota_limit,
                            "used": quota_used,
                            "action_url": "/settings?tab=ai-providers",
                            "action_text": "Add AI Provider",
                        },
                    )

                    # Update leaflet status to failed
                    leaflet.status = LeafletStatus.FAILED
                    leaflet.current_step = "platform_limit_reached"
                    leaflet.status_message = error_message
                    db.commit()

                    return {
                        "success": False,
                        "error": "PLATFORM_LIMIT_REACHED",
                        "message": error_message,
                        "limit": quota_limit,
                        "used": quota_used,
                    }

                # Quota consumed successfully -- mark leaflet as using platform provider
                leaflet.used_platform_provider = True
                db.commit()
                logger.info(
                    f"Platform quota consumed for org {leaflet.organization_id}: "
                    f"limit={quota_limit}, now_used={quota_used}, leaflet={leaflet_id}"
                )

        # Clean up any existing extraction data before re-extraction
        # This prevents duplicate products when re-running extraction
        logger.info(f"Cleaning up existing extraction data for {leaflet_id}")
        cleanup_stats = _cleanup_extraction_data_sync(db, leaflet, progress)
        if cleanup_stats["products_deleted"] > 0:
            logger.info(
                f"Cleaned up previous extraction: {cleanup_stats['products_deleted']} products, "
                f"{cleanup_stats['storage_files_deleted']} files deleted"
            )
            progress.publish_status(
                leaflet_id,
                status="extracting",
                message=f"Cleaned up {cleanup_stats['products_deleted']} existing products before re-extraction",
                progress=0.32,
            )

        # Update status to extracting
        leaflet.status = LeafletStatus.EXTRACTING
        leaflet.current_step = "extracting_products"
        leaflet.progress = 0.35
        db.commit()

        # Get pages
        pages_result = db.execute(
            select(LeafletPage)
            .where(LeafletPage.leaflet_id == leaflet.id)
            .order_by(LeafletPage.page_number)
        )
        pages = pages_result.scalars().all()

        if not pages:
            raise ValueError(f"No pages found for leaflet: {leaflet_id}")

        logger.info(f"Processing {len(pages)} pages for extraction")

        # Publish extraction start
        progress.publish_extraction_start(leaflet_id, len(pages))

        # Initialize validator and reconciler
        # Note: extractor was already initialized above with user's provider settings
        validator = ProductValidator(
            auto_approve_threshold=0.90,
            expected_currency=leaflet.currency,
        )
        reconciler = ProductReconciler()

        # Get storage backend for downloading page images
        storage = get_storage_backend()

        # Create extraction context
        context = ExtractionContext(
            leaflet_id=leaflet_id,
            leaflet_uuid=leaflet.id,
            retailer=leaflet.retailer,
            country=leaflet.country,
            language=leaflet.language,
            currency=leaflet.currency,
            page_count=len(pages),
            request_ip=request_ip,  # Pass client IP for audit logging
        )

        # Download all page images first
        logger.info("Downloading page images...")
        page_images = []
        page_info = []  # Store page metadata

        for page in pages:
            try:
                image_bytes = run_async(storage.download_file(page.image_path))
                page_images.append(image_bytes)
                page_info.append({
                    "page_number": page.page_number,
                    "width": page.width or 2304,
                    "height": page.height or 3508,
                    "format": page.format.lower() if page.format else "png",
                    "page_obj": page,
                })
            except Exception as e:
                logger.error(f"Failed to download page {page.page_number}: {e}")
                page_images.append(None)
                page_info.append(None)

        # Use parallel extraction for multiple pages
        # Reduce concurrency to avoid rate limiting (429 errors)
        use_parallel = len(pages) > 2
        max_concurrent = min(2, len(pages))  # Limit concurrent API calls to reduce rate limiting

        logger.info(
            f"Extracting products with card-first pipeline "
            f"(parallel={use_parallel}, max_concurrent={max_concurrent})"
        )

        # Extract products from all pages using card-first pipeline
        # Card detection + annotated regions -> VLM matches products to region numbers
        extraction_result = run_async(extractor.extract_leaflet(
            page_images=[img for img in page_images if img is not None],
            leaflet_id=leaflet_id,
            context=context,
            parallel=use_parallel,
            max_concurrent=max_concurrent,
        ))

        # Track metrics
        total_input_tokens = extraction_result.input_tokens
        total_output_tokens = extraction_result.output_tokens

        # Publish progress for each page
        for idx, page_result in enumerate(extraction_result.page_results):
            if page_info[idx]:
                progress.publish_page_complete(
                    leaflet_id=leaflet_id,
                    page_number=page_result.page_number,
                    total_pages=len(pages),
                    products_found=len(page_result.products),
                    tokens_used=page_result.input_tokens + page_result.output_tokens,
                )

        logger.info(
            f"Extracted {extraction_result.total_products} raw products from "
            f"{len(extraction_result.page_results)} pages"
        )

        # Update progress
        leaflet.progress = 0.75
        leaflet.current_step = "reconciling_products"
        db.commit()

        # Perform cross-page reconciliation
        logger.info("Performing cross-page reconciliation...")

        # Get page height for reconciliation
        page_height = page_info[0]["height"] if page_info[0] else 3508

        reconciliation = reconciler.reconcile(
            extraction_result.page_results,
            page_height=page_height,
        )

        logger.info(
            f"Reconciliation complete: {len(reconciliation.products)} products, "
            f"{reconciliation.merge_count} merged, {reconciliation.duplicate_count} duplicates removed"
        )

        # Publish reconciliation progress
        progress.publish_reconciliation(
            leaflet_id=leaflet_id,
            merged_count=reconciliation.merge_count,
            duplicate_count=reconciliation.duplicate_count,
        )

        # Post-extraction data sanitization
        # Fixes misplaced prices, computes missing regular_price, filters category headers
        pre_sanitize_count = len(reconciliation.products)
        reconciliation.products = sanitize_products(reconciliation.products)
        post_sanitize_count = len(reconciliation.products)
        if pre_sanitize_count != post_sanitize_count:
            logger.info(
                f"Sanitization filtered {pre_sanitize_count - post_sanitize_count} "
                f"non-product items (headers/categories)"
            )

        # Create page_map early - needed for OCR and validation
        page_map = {p.page_number: p for p in pages}

        # Build product-to-page mapping for efficient lookup
        product_page_map = {}
        for page_result in extraction_result.page_results:
            for prod in page_result.products:
                product_page_map[prod.product_name] = page_result.page_number

        # =====================================================
        # BOUNDING BOX FINALIZATION
        # Card-first pipeline assigns bboxes from detected regions.
        # Apply fallback bounding boxes for any products without them.
        # =====================================================
        leaflet.progress = 0.82
        leaflet.current_step = "finalizing_bounding_boxes"
        db.commit()

        try:
            logger.info("Finalizing bounding boxes from card-first extraction...")

            # Group products by page for fallback processing
            products_by_page = defaultdict(list)
            for product in reconciliation.products:
                if product.source_page:
                    pg_num = product.source_page
                else:
                    pg_num = product_page_map.get(product.product_name, 1)
                products_by_page[pg_num].append(product)

            products_with_bbox = 0
            products_without_bbox = 0

            for pg_num, pg_products in products_by_page.items():
                page_obj = page_map.get(pg_num, pages[0])
                page_width = page_obj.width or 2480
                page_height = page_obj.height or 3508

                # Infer grid layout from products that already have bounding boxes
                existing_bboxes = [p.bounding_box for p in pg_products if p.bounding_box]
                if existing_bboxes:
                    # Estimate columns from existing bbox X-positions
                    import math
                    centers_x = sorted(set(
                        int(b.x + b.width / 2) // max(1, page_width // 10)
                        for b in existing_bboxes
                    ))
                    cols = max(1, len(centers_x))
                else:
                    # No existing bboxes - estimate from product count
                    import math
                    cols = max(2, min(4, int(math.sqrt(len(pg_products) * 1.2))))

                # Count products with/without bounding boxes
                for prod in pg_products:
                    if prod.bounding_box:
                        products_with_bbox += 1
                    else:
                        products_without_bbox += 1
                        # Apply fallback bounding box using inferred column count
                        rows = max(2, (len(pg_products) + cols - 1) // cols)
                        cell_w, cell_h = page_width // cols, page_height // rows
                        i = pg_products.index(prod)
                        row, col = i // cols, i % cols
                        prod.bounding_box = BoundingBox(
                            x=col * cell_w + 20,
                            y=row * cell_h + 20,
                            width=cell_w - 40,
                            height=cell_h - 40
                        )
                        if 'bbox_fallback' not in prod.uncertainty_flags:
                            prod.uncertainty_flags.append('bbox_fallback')

            logger.info(
                f"Bounding box finalization complete: "
                f"{products_with_bbox} from card regions, {products_without_bbox} fallback"
            )
        except Exception as bbox_err:
            logger.error(f"Bounding box finalization failed: {bbox_err}", exc_info=True)
            # Ensure all products have fallback bounding boxes
            for prod in reconciliation.products:
                if prod.bounding_box is None:
                    prod.bounding_box = BoundingBox(x=50, y=50, width=400, height=400)
                    if 'bbox_fallback' not in prod.uncertainty_flags:
                        prod.uncertainty_flags.append('bbox_fallback')

        # Release remaining page images to free memory
        page_images.clear()
        gc.collect()

        # Update progress
        leaflet.progress = 0.85
        leaflet.current_step = "validating_products"
        db.commit()

        # Validate and store products
        progress.publish_validation_start(leaflet_id, len(reconciliation.products))

        total_products = 0
        auto_approved = 0
        review_required = 0

        # Batch commit size for better performance and reliability with large datasets
        BATCH_COMMIT_SIZE = 25

        for extracted_product in reconciliation.products:
            try:
                # Determine the page number for this product
                if extracted_product.source_page:
                    page_number = extracted_product.source_page
                else:
                    # Find page by looking at original extraction results
                    page_number = 1
                    for page_result in extraction_result.page_results:
                        for prod in page_result.products:
                            if prod.product_name == extracted_product.product_name:
                                page_number = page_result.page_number
                                break

                page = page_map.get(page_number, pages[0])

                # Validate product
                validation_result = validator.validate(
                    extracted_product,
                    page_width=page.width or 2304,
                    page_height=page.height or 3508,
                )

                # Check if auto-approval is enabled via config
                # Note: Auto-approval currently disabled in config (feature_auto_approval = False)
                if settings.feature_auto_approval and validation_result.auto_approve and extracted_product.confidence_score >= 0.85:
                    review_status = ReviewStatus.AUTO_APPROVED
                    auto_approved += 1
                else:
                    # All products require human review when auto-approval disabled
                    review_status = ReviewStatus.PENDING
                    review_required += 1

                # Calculate review priority
                review_priority = determine_review_priority(
                    extracted_product,
                    validation_result,
                )

                # Create product record
                product = Product(
                    leaflet_id=leaflet.id,
                    organization_id=leaflet.organization_id,
                    page_number=page_number,
                    brand=extracted_product.brand,
                    product_code=extracted_product.product_code,
                    product_name=extracted_product.product_name,
                    quantity=extracted_product.quantity,
                    units=extracted_product.units,
                    size=extracted_product.size,
                    regular_price=extracted_product.regular_price,
                    discounted_price=extracted_product.discounted_price,
                    discount_percentage=extracted_product.discount_percentage,
                    currency=extracted_product.currency or leaflet.currency,
                    product_id=extracted_product.product_id,
                    promotional_info=extracted_product.promotional_info,
                    suggested_category=extracted_product.suggested_category,
                    category=extracted_product.suggested_category,  # Default to AI suggestion
                    category_confidence=extracted_product.category_confidence,
                    category_alternatives=extracted_product.category_alternatives,
                    bbox_x=extracted_product.bounding_box.x,
                    bbox_y=extracted_product.bounding_box.y,
                    bbox_width=extracted_product.bounding_box.width,
                    bbox_height=extracted_product.bounding_box.height,
                    confidence=extracted_product.confidence_score,
                    field_confidence=extracted_product.field_confidence.model_dump() if extracted_product.field_confidence else {},
                    uncertainty_flags=extracted_product.uncertainty_flags,
                    review_status=review_status,
                    review_priority=review_priority,
                    validation_passed=validation_result.is_valid,
                    validation_errors=[e.model_dump() for e in validation_result.errors],
                    is_split_product=extracted_product.is_split_product,
                    merged_from=extracted_product.merged_from_pages if extracted_product.merged_from_pages else None,
                )
                db.add(product)
                total_products += 1

                # Log product creation with bounding box details
                logger.info(
                    f"Created product on page {page_number}: '{extracted_product.product_name[:40]}' "
                    f"bbox=({extracted_product.bounding_box.x},{extracted_product.bounding_box.y},"
                    f"{extracted_product.bounding_box.width}x{extracted_product.bounding_box.height}) "
                    f"status={review_status.value}"
                )

                # Update page product count
                page.products_count = (page.products_count or 0) + 1
                page.is_processed = True

                # Batch commit for better performance with large datasets
                if total_products % BATCH_COMMIT_SIZE == 0:
                    try:
                        db.commit()
                        logger.debug(f"Batch commit: {total_products}/{len(reconciliation.products)} products saved")
                    except Exception as commit_err:
                        logger.error(f"Batch commit failed: {commit_err}", exc_info=True)
                        db.rollback()
                        # Re-add current product since rollback cleared it
                        db.add(product)

            except Exception as e:
                logger.error(f"Failed to create product '{extracted_product.product_name[:40] if extracted_product.product_name else 'unknown'}': {e}", exc_info=True)
                # Rollback to recover from any DB session errors
                try:
                    db.rollback()
                except Exception:
                    pass
                continue

        # Final commit for remaining products
        try:
            db.commit()
        except Exception as commit_err:
            logger.error(f"Final commit failed: {commit_err}", exc_info=True)
            db.rollback()
            raise

        # Update leaflet with results
        leaflet.status = LeafletStatus.VALIDATING
        leaflet.current_step = "extraction_complete"
        leaflet.progress = 0.90
        leaflet.auto_approved_count = auto_approved
        leaflet.review_required_count = review_required
        leaflet.api_tokens_used = total_input_tokens + total_output_tokens

        # Use actual cost accumulated by the extractor (correct per-provider pricing)
        # instead of hardcoded Anthropic rates ($3/$15 per 1M tokens).
        leaflet.processing_cost = (
            Decimal(str(extractor.total_cost))
            if hasattr(extractor, 'total_cost') and extractor.total_cost is not None
            else Decimal("0")
        )

        # Update metadata
        leaflet.processing_metadata = {
            **(leaflet.processing_metadata or {}),
            "extraction_completed_at": datetime.now(timezone.utc).isoformat(),
            "total_products_extracted": total_products,
            "auto_approved_count": auto_approved,
            "review_required_count": review_required,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "merged_products": reconciliation.merge_count,
            "duplicates_removed": reconciliation.duplicate_count,
            "parallel_extraction": use_parallel,
            "extraction_method": "card_first",
        }

        # Calculate overall confidence
        if total_products > 0:
            all_products = db.execute(
                select(Product).where(Product.leaflet_id == leaflet.id)
            ).scalars().all()
            leaflet.overall_confidence = sum(
                p.confidence or 0 for p in all_products
            ) / len(all_products)

        # Set completion time and status
        # Always mark as completed regardless of review requirements
        # Human review will happen on all products anyway
        completion_time = datetime.now(timezone.utc)
        leaflet.processing_completed_at = completion_time
        leaflet.status = LeafletStatus.COMPLETED
        leaflet.progress = 1.0
        leaflet.current_step = "completed"

        db.commit()

        # Read provider info AFTER extraction since the provider may have
        # changed during extraction (e.g. fallback to a different provider).
        # Defined outside try blocks so both CostTracking and OrganizationVLMUsage
        # can access it even if one block fails.
        try:
            final_provider_info = extractor.provider_info
        except Exception:
            final_provider_info = {}

        # Record CostTracking entry for analytics endpoints.
        # Wrapped in try/except so analytics recording never fails the extraction.
        try:

            # Determine per-token rates from the provider's default model config
            is_platform = final_provider_info.get("type") == "platform"
            ptype_str = final_provider_info.get("provider_type", "")

            try:
                if is_platform:
                    ptype_enum = PlatformVLMProviderType(ptype_str)
                    rates = PLATFORM_DEFAULT_MODELS.get(ptype_enum, {})
                else:
                    ptype_enum = VLMProviderType(ptype_str)
                    rates = DEFAULT_MODELS.get(ptype_enum, {})
            except ValueError:
                rates = {}

            if not rates:
                logger.warning(f"No rate config found for provider type '{ptype_str}', using default Anthropic rates for CostTracking")

            in_rate = Decimal(str(rates.get("input_cost_per_1m", 3.0)))
            out_rate = Decimal(str(rates.get("output_cost_per_1m", 15.0)))
            input_cost = in_rate * total_input_tokens / Decimal("1000000")
            output_cost = out_rate * total_output_tokens / Decimal("1000000")

            # Delete any existing CostTracking row for this leaflet to ensure
            # idempotency on task retry (max_retries=2).
            db.execute(
                delete(CostTracking).where(CostTracking.leaflet_id == leaflet.id)
            )

            vlm_provider_id_str = final_provider_info.get("provider_id")
            cost_record = CostTracking(
                user_id=leaflet.user_id,
                leaflet_id=leaflet.id,
                vlm_provider_id=(
                    UUID(vlm_provider_id_str)
                    if vlm_provider_id_str
                    else None
                ),
                provider_type=final_provider_info.get("provider_type", "unknown"),
                model_name=final_provider_info.get("model", "unknown"),
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_input_tokens + total_output_tokens,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=leaflet.processing_cost or Decimal("0"),
                page_count=leaflet.page_count,
                product_count=total_products,
                input_price_per_1m=in_rate,
                output_price_per_1m=out_rate,
                processed_at=datetime.now(timezone.utc),
            )
            db.add(cost_record)
            db.commit()
            logger.info(
                f"CostTracking record created for {leaflet_id}: "
                f"cost=${leaflet.processing_cost}, "
                f"input_cost=${input_cost}, output_cost=${output_cost}, "
                f"tokens={total_input_tokens + total_output_tokens}"
            )
        except Exception as cost_err:
            logger.warning(
                f"Failed to create CostTracking record for {leaflet_id}: {cost_err}",
                exc_info=True,
            )
            db.rollback()

        # Record OrganizationVLMUsage for the usage reports page.
        # Uses get-or-create + add_usage() so concurrent leaflets in the
        # same org/provider/date/hour bucket aggregate correctly instead
        # of overwriting each other.
        try:
            if leaflet.organization_id:
                now_utc = datetime.now(timezone.utc)
                usage_date = now_utc.date()
                usage_hour = now_utc.hour

                # Determine platform_provider_id (only set for platform providers)
                platform_provider_id = None
                if final_provider_info.get("type") == "platform":
                    pid_str = final_provider_info.get("provider_id")
                    if pid_str:
                        platform_provider_id = UUID(pid_str)

                # Build NULL-safe provider filter because
                # PostgreSQL NULL != NULL in unique constraints.
                if platform_provider_id is not None:
                    provider_filter = (
                        OrganizationVLMUsage.platform_provider_id == platform_provider_id
                    )
                else:
                    provider_filter = OrganizationVLMUsage.platform_provider_id.is_(None)

                # Get-or-create with row lock to safely aggregate usage
                # from multiple leaflets finishing in the same hour.
                existing = db.execute(
                    select(OrganizationVLMUsage).where(
                        and_(
                            OrganizationVLMUsage.organization_id == leaflet.organization_id,
                            provider_filter,
                            OrganizationVLMUsage.usage_date == usage_date,
                            OrganizationVLMUsage.usage_hour == usage_hour,
                        )
                    ).with_for_update()
                ).scalar_one_or_none()

                if existing:
                    existing.add_usage(
                        request_count=leaflet.page_count or 1,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        cost=float(leaflet.processing_cost or 0),
                        leaflet_count=1,
                        page_count=leaflet.page_count or 0,
                        product_count=total_products,
                        confidence_score=leaflet.overall_confidence,
                    )
                else:
                    usage_record = OrganizationVLMUsage(
                        organization_id=leaflet.organization_id,
                        platform_provider_id=platform_provider_id,
                        usage_date=usage_date,
                        usage_hour=usage_hour,
                        request_count=leaflet.page_count or 1,
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        total_cost=leaflet.processing_cost or Decimal("0"),
                        leaflet_count=1,
                        page_count=leaflet.page_count or 0,
                        product_count=total_products,
                        average_confidence=leaflet.overall_confidence,
                    )
                    db.add(usage_record)

                db.commit()
                logger.info(
                    f"OrganizationVLMUsage {'updated' if existing else 'created'} "
                    f"for {leaflet_id}: org={leaflet.organization_id}, "
                    f"cost=${leaflet.processing_cost}, "
                    f"tokens={total_input_tokens + total_output_tokens}, "
                    f"products={total_products}"
                )
            else:
                logger.debug(
                    f"Skipping OrganizationVLMUsage for {leaflet_id}: "
                    f"no organization_id on leaflet"
                )
        except Exception as usage_err:
            logger.warning(
                f"Failed to record OrganizationVLMUsage for {leaflet_id}: {usage_err}",
                exc_info=True,
            )
            db.rollback()

        # Publish completion
        summary = {
            "total_products": total_products,
            "auto_approved": auto_approved,
            "review_required": review_required,
            "merged_products": reconciliation.merge_count,
            "duplicates_removed": reconciliation.duplicate_count,
            "tokens_used": total_input_tokens + total_output_tokens,
            "estimated_cost": leaflet.processing_cost,
            "final_status": leaflet.status.value,
        }
        progress.publish_complete(leaflet_id, summary)

        logger.info(
            f"Extraction completed for {leaflet_id}: "
            f"{total_products} products, {auto_approved} auto-approved, "
            f"{review_required} need review, {reconciliation.merge_count} merged"
        )

        # Auto-trigger product image extraction
        if total_products > 0:
            logger.info(f"Queueing product image extraction for {leaflet_id}")
            try:
                extract_product_images_task.apply_async(
                    args=[leaflet_id],
                    queue="extraction",
                    countdown=2,  # Small delay to ensure DB commits are visible
                )
                logger.info(f"Product image extraction queued for {leaflet_id}")
            except Exception as img_err:
                logger.warning(f"Failed to queue image extraction for {leaflet_id}: {img_err}")
                # Don't fail the whole extraction just because image extraction queueing failed

        return {
            "success": True,
            "leaflet_id": leaflet_id,
            **summary,
        }

    except SoftTimeLimitExceeded:
        logger.error(f"Extraction timed out for {leaflet_id}")
        if db:
            _update_leaflet_status(db, leaflet_id, "failed", "Extraction timed out")
        try:
            progress.publish_error(leaflet_id, "Extraction timed out")
        except Exception:
            pass
        raise

    except Exception as e:
        from app.core.extraction.multi_provider_client import InsufficientCreditsError

        error_str = str(e)
        logger.error(f"Extraction failed for {leaflet_id}: {e}", exc_info=True)

        # Check for billing/credit errors to provide better user feedback
        is_credit_error = (
            isinstance(e, InsufficientCreditsError) or
            "credit balance" in error_str.lower() or
            "insufficient" in error_str.lower() or
            "billing" in error_str.lower() or
            "quota" in error_str.lower()
        )

        if is_credit_error:
            error_message = (
                "API credits exhausted. Please add credits to your AI provider account "
                "or configure a different provider in Settings."
            )
            if db:
                _update_leaflet_status(
                    db, leaflet_id, "failed",
                    error_message,
                    current_step="credits_exhausted"
                )
            try:
                progress.publish_error(leaflet_id, error_message)
            except Exception:
                pass
        else:
            if db:
                _update_leaflet_status(db, leaflet_id, "failed", error_str)
            try:
                progress.publish_error(leaflet_id, error_str)
            except Exception:
                pass
        raise

    finally:
        # Clean up OCR cache for this leaflet
        clear_ocr_cache(leaflet_id)
        if db:
            db.close()


# ---------------------------------------------------------------------------
# extract_product_images_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.extract_product_images_task",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=600,
    time_limit=900,
)
def extract_product_images_task(self, leaflet_id: str) -> dict:
    """
    Extract product images from page images using bounding boxes.

    This task:
    1. Gets all products for a leaflet
    2. Downloads page images
    3. Extracts product regions using bounding boxes
    4. Encodes images (base64 or file storage)
    5. Scores image quality
    6. Updates product records with image data

    Args:
        leaflet_id: The leaflet ID to process

    Returns:
        Dict with extraction results
    """
    import base64
    from io import BytesIO

    from PIL import Image

    from app.models.leaflet import Leaflet, LeafletPage
    from app.models.product import Product
    from app.core.image_processing.extractor import extract_product_from_page
    from app.core.image_processing.quality import QualityScorer
    from app.core.extraction.schemas import BoundingBox as _BoundingBox
    from app.utils.storage import get_storage_backend

    logger.info(f"Starting product image extraction for leaflet: {leaflet_id}")
    db = get_sync_db_session()

    # Constants
    BASE64_THRESHOLD = 100_000  # 100KB - store smaller images as base64
    JPEG_QUALITY = 85
    BATCH_COMMIT_SIZE = 10  # Commit every N products

    try:
        # Get leaflet
        result = db.execute(
            select(Leaflet).where(Leaflet.leaflet_id == leaflet_id)
        )
        leaflet = result.scalar_one_or_none()

        if leaflet is None:
            raise ValueError(f"Leaflet not found: {leaflet_id}")

        # Get products without images
        products_result = db.execute(
            select(Product)
            .where(Product.leaflet_id == leaflet.id)
            .where(Product.image_storage_type.is_(None))
            .order_by(Product.page_number)
        )
        products = products_result.scalars().all()

        if not products:
            logger.info(f"No products need image extraction for {leaflet_id}")
            return {"success": True, "images_extracted": 0}

        total_products = len(products)
        logger.info(f"Extracting images for {total_products} products")

        # Get pages
        pages_result = db.execute(
            select(LeafletPage)
            .where(LeafletPage.leaflet_id == leaflet.id)
            .order_by(LeafletPage.page_number)
        )
        pages = {p.page_number: p for p in pages_result.scalars().all()}

        # Initialize processors
        quality_scorer = QualityScorer(min_acceptable_score=0.70)
        storage = get_storage_backend()

        # Cache downloaded page images (limit memory by processing page-by-page)
        current_page_num = None
        current_page_image = None

        # Track results
        extracted_count = 0
        failed_count = 0
        skipped_count = 0

        for idx, product in enumerate(products):
            try:
                page = pages.get(product.page_number)
                if not page:
                    logger.warning(f"Page {product.page_number} not found for product {product.id}")
                    skipped_count += 1
                    continue

                # Load page image only when page changes (memory optimization)
                if product.page_number != current_page_num:
                    # Free previous page image memory
                    if current_page_image is not None:
                        current_page_image.close()
                        current_page_image = None

                    try:
                        image_bytes = run_async(storage.download_file(page.image_path))
                        current_page_image = Image.open(BytesIO(image_bytes))
                        current_page_num = product.page_number
                        logger.debug(f"Loaded page {product.page_number} image")
                    except Exception as e:
                        logger.error(f"Failed to download page {product.page_number}: {e}")
                        skipped_count += 1
                        continue

                # Validate bounding box exists
                if not all([product.bbox_x is not None, product.bbox_y is not None,
                           product.bbox_width is not None, product.bbox_height is not None]):
                    logger.warning(f"Product {product.id} has no bounding box")
                    skipped_count += 1
                    continue

                # Create bounding box dict for the convenience function
                bbox = {
                    "x": product.bbox_x,
                    "y": product.bbox_y,
                    "width": product.bbox_width,
                    "height": product.bbox_height,
                }

                # Log bounding box details for debugging
                page_w, page_h = current_page_image.size
                logger.debug(
                    f"Extracting image for product {product.id}: "
                    f"bbox=({bbox['x']},{bbox['y']},{bbox['width']}x{bbox['height']}) "
                    f"from page {product.page_number} ({page_w}x{page_h})"
                )

                # Validate bounding box is within page bounds
                if bbox['x'] < 0 or bbox['y'] < 0:
                    logger.warning(f"Product {product.id} has negative bbox coordinates, adjusting")
                    bbox['x'] = max(0, bbox['x'])
                    bbox['y'] = max(0, bbox['y'])

                if bbox['x'] + bbox['width'] > page_w:
                    logger.warning(f"Product {product.id} bbox extends beyond page width, adjusting")
                    bbox['width'] = page_w - bbox['x']

                if bbox['y'] + bbox['height'] > page_h:
                    logger.warning(f"Product {product.id} bbox extends beyond page height, adjusting")
                    bbox['height'] = page_h - bbox['y']

                # Check for suspiciously small bounding boxes
                if bbox['width'] < 100 or bbox['height'] < 100:
                    logger.warning(
                        f"Product {product.id} has small bbox ({bbox['width']}x{bbox['height']}), "
                        f"this may indicate VLM detection issues"
                    )

                # Extract product image using the convenience function (handles PIL directly)
                extracted_image, error = extract_product_from_page(
                    current_page_image,
                    bbox,
                    padding=2,  # Minimal padding around bounding box
                )

                if error or extracted_image is None:
                    logger.warning(f"Failed to extract image for product {product.id}: {error}")
                    failed_count += 1
                    continue

                # Score image quality
                quality_report = quality_scorer.analyze(extracted_image)

                # Convert to JPEG bytes
                img_buffer = BytesIO()
                save_image = extracted_image
                if save_image.mode in ('RGBA', 'LA', 'P'):
                    save_image = save_image.convert('RGB')
                save_image.save(img_buffer, format='JPEG', quality=JPEG_QUALITY)
                img_bytes = img_buffer.getvalue()
                img_size = len(img_bytes)

                # Get dimensions before closing
                img_width, img_height = extracted_image.size

                # Free extracted image memory
                extracted_image.close()

                # Decide storage type based on size
                if img_size < BASE64_THRESHOLD:
                    # Store as base64 for small images (faster loading, no extra request)
                    base64_data = base64.b64encode(img_bytes).decode('utf-8')
                    product.image_storage_type = "base64"
                    product.image_base64 = f"data:image/jpeg;base64,{base64_data}"
                    product.image_url = None
                    product.image_path = None
                else:
                    # Store in MinIO for larger images
                    product_image_path = f"leaflets/{leaflet_id}/products/page{product.page_number:02d}_{product.id}.jpg"
                    try:
                        run_async(storage.upload_file(
                            img_bytes,
                            product_image_path,
                            content_type="image/jpeg"
                        ))
                        # Generate a long-lived URL (24 hours) for the stored image
                        image_url = run_async(storage.get_file_url(product_image_path, expires_in=86400))

                        product.image_storage_type = "file"
                        product.image_base64 = None
                        product.image_url = image_url
                        product.image_path = product_image_path
                    except Exception as storage_err:
                        logger.warning(f"Failed to store image in MinIO for product {product.id}: {storage_err}, falling back to base64")
                        # Fallback to base64
                        base64_data = base64.b64encode(img_bytes).decode('utf-8')
                        product.image_storage_type = "base64"
                        product.image_base64 = f"data:image/jpeg;base64,{base64_data}"
                        product.image_url = None
                        product.image_path = None

                # Update common image fields
                product.image_format = "JPEG"
                product.image_width = img_width
                product.image_height = img_height
                product.image_size_bytes = img_size
                # Convert numpy float64 to Python float for SQLAlchemy
                product.image_quality_score = float(quality_report.overall_score)

                extracted_count += 1

                # Batch commit for better performance
                if extracted_count % BATCH_COMMIT_SIZE == 0:
                    db.commit()
                    logger.debug(f"Progress: {extracted_count}/{total_products} images extracted")

            except Exception as e:
                logger.error(f"Failed to process product {product.id}: {e}", exc_info=True)
                failed_count += 1
                # Rollback to recover from any DB errors
                db.rollback()
                continue

        # Final commit
        db.commit()

        # Cleanup
        if current_page_image is not None:
            current_page_image.close()

        logger.info(
            f"Image extraction completed for {leaflet_id}: "
            f"{extracted_count} extracted, {failed_count} failed, {skipped_count} skipped"
        )

        return {
            "success": True,
            "leaflet_id": leaflet_id,
            "images_extracted": extracted_count,
            "images_failed": failed_count,
            "images_skipped": skipped_count,
            "total_products": total_products,
        }

    except Exception as e:
        logger.error(f"Image extraction failed for {leaflet_id}: {e}", exc_info=True)
        raise

    finally:
        if db:
            db.close()
