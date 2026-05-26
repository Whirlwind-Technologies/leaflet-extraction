"""
Products API Endpoints.

This module provides endpoints for product data management,
review operations, and batch processing.

Example Usage:
    GET /api/v1/products - List products
    GET /api/v1/products/{id} - Get product details
    POST /api/v1/products/{id}/review - Submit product review
    POST /api/v1/products/batch-review - Batch review products
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_read, require_write, get_current_organization, get_db
from app.models.leaflet import Leaflet
from app.models.organization import Organization
from app.models.product import Product, ProductReview, ReviewStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.product import (
    ProductBatchFetchRequest,
    ProductBatchReviewCreate,
    ProductBatchReviewResponse,
    ProductListParams,
    ProductListResponse,
    ProductResponse,
    ProductReviewCreate,
    ProductReviewResponse,
    ProductUpdate,
)
from app.utils.exceptions import NotFoundError, ValidationException

logger = logging.getLogger(__name__)
router = APIRouter()


def serialize_product_for_list(
    product: Product, include_base64: bool = False
) -> Dict[str, Any]:
    """
    Safely serialize a product for list responses.

    This helper explicitly converts the product to a dictionary
    to avoid Pydantic validation issues with computed properties.

    Args:
        product: The Product ORM instance to serialize.
        include_base64: If True, always include the full image_base64 data
            in the response.  Defaults to False for list endpoints to keep
            payloads small.  Even when False, products whose only image
            source is base64 (image_storage_type='base64' with no
            image_url) will still have their base64 data included so that
            they are not rendered without images in the UI.

    Returns:
        Dictionary suitable for JSON serialization.
    """
    # Include base64 image data when:
    # 1. Explicitly requested (single-product detail endpoint), OR
    # 2. The product's ONLY image source is base64 (image_storage_type='base64').
    #    These are small images (<100KB) so including them in list responses is
    #    acceptable.  Without this, base64-only products would have NO image
    #    in list views because image_url and image_path are both None.
    is_base64_only = (
        product.image_storage_type == "base64"
        and product.image_base64
        and not product.image_url
    )
    should_include_base64 = include_base64 or is_base64_only
    # image.data and image_base64 carry the same value for backwards compatibility:
    # - image.data: used by newer frontend components (nested under image object)
    # - image_base64: used by legacy API consumers expecting flat field
    image_base64_value = product.image_base64 if should_include_base64 else None
    image_data_value = product.image_base64 if should_include_base64 else None

    return {
        "id": product.id,
        "leaflet_id": product.leaflet_id,
        "page_number": product.page_number,
        "brand": product.brand,
        "product_code": product.product_code,
        "product_name": product.product_name,
        "quantity": product.quantity,
        "units": product.units,
        "size": product.size,
        "regular_price": float(product.regular_price) if product.regular_price is not None else None,
        "discounted_price": float(product.discounted_price) if product.discounted_price is not None else None,
        "discount_percentage": float(product.discount_percentage) if product.discount_percentage is not None else None,
        "currency": product.currency,
        "product_id": product.product_id,
        "promotional_info": product.promotional_info,
        "suggested_category": product.suggested_category,
        "category": product.category,
        "category_confidence": float(product.category_confidence) if product.category_confidence is not None else None,
        "category_alternatives": product.category_alternatives or [],
        "bounding_box": {
            "x": product.bbox_x or 0,
            "y": product.bbox_y or 0,
            "width": product.bbox_width or 1,
            "height": product.bbox_height or 1,
        },
        "image": {
            "storage_type": product.image_storage_type or "base64",
            "data": image_data_value,
            "url": product.image_url,
            "path": product.image_path,  # Include path for client-side URL refresh
            "format": product.image_format or "JPEG",
            "dimensions": {
                "width": product.image_width or 0,
                "height": product.image_height or 0,
            },
            "size_bytes": product.image_size_bytes,
            "quality_score": float(product.image_quality_score) if product.image_quality_score is not None else None,
        } if product.image_storage_type else None,
        "image_storage_type": product.image_storage_type,
        "image_base64": image_base64_value,
        "image_url": product.image_url,
        "image_path": product.image_path,  # Include path for potential URL refresh
        "thumbnail_url": None,  # Not implemented yet
        "image_width": product.image_width,
        "image_height": product.image_height,
        "image_size_bytes": product.image_size_bytes,
        "image_quality_score": float(product.image_quality_score) if product.image_quality_score is not None else None,
        "confidence": float(product.confidence) if product.confidence is not None else None,
        "field_confidence": product.field_confidence,
        "uncertainty_flags": product.uncertainty_flags or [],
        "review_status": product.review_status.value if hasattr(product.review_status, 'value') else product.review_status,
        "review_priority": product.review_priority or 0,
        "reviewed_by": product.reviewed_by,
        "reviewed_at": product.reviewed_at,
        "validation_passed": product.validation_passed if product.validation_passed is not None else True,
        "validation_errors": product.validation_errors or [],
        "is_corrected": product.is_corrected or False,
        "is_split_product": product.is_split_product or False,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


@router.get(
    "/stats",
    summary="Get product statistics",
    description="Get aggregated statistics for products by review status.",
)
async def get_product_stats(
    leaflet_id: Optional[str] = Query(None, description="Filter by leaflet (UUID or human-readable ID)"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get product statistics by review status.

    Returns counts for total, approved, pending, rejected, auto_approved,
    and needs_correction products.

    Args:
        leaflet_id: Optional filter by leaflet (UUID or human-readable ID)
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Dictionary with product counts by status
    """
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)

    # Base query for status counts
    query = select(
        Product.review_status,
        func.count(Product.id).label('count')
    ).where(Product.leaflet_id.in_(user_leaflets))

    # Apply leaflet filter if provided
    if leaflet_id:
        try:
            uuid_leaflet_id = UUID(leaflet_id)
            query = query.where(Product.leaflet_id == uuid_leaflet_id)
        except ValueError:
            # It's a human-readable ID (like LEAF_2025_...)
            if current_user.is_superuser:
                leaflet_lookup = select(Leaflet.id).where(Leaflet.leaflet_id == leaflet_id)
            else:
                leaflet_lookup = select(Leaflet.id).where(
                    and_(
                        Leaflet.leaflet_id == leaflet_id,
                        Leaflet.organization_id == current_org.id
                    )
                )
            query = query.where(Product.leaflet_id.in_(leaflet_lookup))

    query = query.group_by(Product.review_status)

    result = await db.execute(query)
    rows = result.all()

    # Initialize all possible statuses to 0
    stats = {
        "total": 0,
        "approved": 0,
        "auto_approved": 0,
        "pending": 0,
        "rejected": 0,
        "needs_correction": 0,
    }

    # Populate from query results
    for row in rows:
        status = row.review_status.value if hasattr(row.review_status, 'value') else str(row.review_status)
        stats[status] = row.count
        stats["total"] += row.count

    logger.info(f"Product stats for leaflet={leaflet_id}: {stats}")

    return stats


@router.get(
    "/",
    summary="List products",
    description="List products for the current organization with optional filtering.",
)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    leaflet_id: Optional[str] = Query(None, description="Filter by leaflet (UUID or human-readable ID)"),
    page_number: Optional[int] = Query(None, description="Filter by page"),
    review_status: Optional[ReviewStatus] = Query(None, description="Filter by status"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1, description="Min confidence"),
    validation_passed: Optional[bool] = Query(None, description="Filter by validation"),
    search: Optional[str] = Query(None, description="Search product name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List products for the current organization with filtering and pagination.

    Args:
        page: Page number
        page_size: Items per page
        leaflet_id: Filter by leaflet (UUID or human-readable ID like LEAF_2025_...)
        page_number: Filter by page number in leaflet
        review_status: Filter by review status
        brand: Filter by brand name
        min_confidence: Minimum confidence threshold
        validation_passed: Filter by validation status
        search: Search in product name
        sort_by: Field to sort by
        sort_order: Sort direction
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Paginated list of products
    """
    logger.info(f"list_products called: org={current_org.id}, leaflet_id={leaflet_id}, page={page}, page_size={page_size}")

    # Build base query
    # Super users can see all products across all organizations
    if current_user.is_superuser:
        query = select(Product)
        count_query = select(func.count(Product.id))
    else:
        # Regular users see only their organization's products
        query = select(Product).where(Product.organization_id == current_org.id)
        count_query = select(func.count(Product.id)).where(
            Product.organization_id == current_org.id
        )
    
    # Apply filters
    if leaflet_id:
        logger.info(f"Filtering by leaflet_id: {leaflet_id}")
        # Try to parse as UUID first, otherwise lookup by human-readable leaflet_id
        try:
            uuid_leaflet_id = UUID(leaflet_id)
            logger.info(f"Parsed as UUID: {uuid_leaflet_id}")
            query = query.where(Product.leaflet_id == uuid_leaflet_id)
            count_query = count_query.where(Product.leaflet_id == uuid_leaflet_id)
        except ValueError:
            # It's a human-readable ID (like LEAF_2025_...), lookup the actual UUID
            logger.info(f"Treating as human-readable ID: {leaflet_id}")
            leaflet_lookup = select(Leaflet.id).where(
                and_(
                    Leaflet.leaflet_id == leaflet_id,
                    Leaflet.organization_id == current_org.id
                )
            )
            query = query.where(Product.leaflet_id.in_(leaflet_lookup))
            count_query = count_query.where(Product.leaflet_id.in_(leaflet_lookup))
    
    if page_number:
        query = query.where(Product.page_number == page_number)
        count_query = count_query.where(Product.page_number == page_number)
    
    if review_status:
        query = query.where(Product.review_status == review_status)
        count_query = count_query.where(Product.review_status == review_status)
    
    if brand:
        query = query.where(Product.brand.ilike(f"%{brand}%"))
        count_query = count_query.where(Product.brand.ilike(f"%{brand}%"))
    
    if min_confidence is not None:
        query = query.where(Product.confidence >= min_confidence)
        count_query = count_query.where(Product.confidence >= min_confidence)
    
    if validation_passed is not None:
        query = query.where(Product.validation_passed == validation_passed)
        count_query = count_query.where(Product.validation_passed == validation_passed)
    
    if search:
        query = query.where(Product.product_name.ilike(f"%{search}%"))
        count_query = count_query.where(Product.product_name.ilike(f"%{search}%"))

    if category:
        query = query.where(Product.category == category)
        count_query = count_query.where(Product.category == category)

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Apply sorting with a deterministic tiebreaker on Product.id.
    # Without a tiebreaker, rows with identical sort-column values can shift
    # between pages across successive requests, causing the frontend to see
    # duplicates on one page and gaps on the next.
    sort_column = getattr(Product, sort_by, Product.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc(), Product.id.asc())
    else:
        query = query.order_by(sort_column.asc(), Product.id.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    products = result.scalars().all()
    
    # Log review status breakdown for debugging
    status_counts = {}
    for p in products:
        status = p.review_status.value if hasattr(p.review_status, 'value') else str(p.review_status)
        status_counts[status] = status_counts.get(status, 0) + 1
    
    logger.info(
        f"Products API DEBUG: "
        f"leaflet_id={leaflet_id}, "
        f"total_from_count_query={total}, "
        f"products_from_main_query={len(products)}, "
        f"page={page}, "
        f"page_size={page_size}, "
        f"status_breakdown={status_counts}"
    )
    
    # If total doesn't match products length, something is wrong
    if total != len(products) and page == 1 and page_size >= 100:
        logger.warning(
            f"MISMATCH: count_query returned {total} but main query returned {len(products)} products. "
            f"This may indicate a query issue or concurrent modification."
        )
    
    # Safely serialize products
    serialized_products = []
    serialization_errors = []
    for p in products:
        try:
            serialized_products.append(serialize_product_for_list(p))
        except Exception as e:
            logger.error(f"Failed to serialize product {p.id} (status={p.review_status}): {e}")
            serialization_errors.append(str(p.id))
            # Skip products that fail to serialize
            continue
    
    if serialization_errors:
        logger.warning(f"Failed to serialize {len(serialization_errors)} products: {serialization_errors[:10]}")
    
    logger.info(f"Successfully serialized {len(serialized_products)} products")
    
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return {
        "items": serialized_products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get(
    "/debug/status-breakdown",
    summary="Debug: Get product status breakdown",
    description="Returns count of products by review status for debugging.",
)
async def debug_status_breakdown(
    leaflet_id: Optional[str] = Query(None, description="Filter by leaflet ID"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Debug endpoint to check product status breakdown.
    
    This helps diagnose why products might not be showing in the UI.
    """
    from sqlalchemy import func as sql_func
    
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    # Base query
    query = select(
        Product.review_status,
        sql_func.count(Product.id).label('count')
    ).where(Product.leaflet_id.in_(user_leaflets))
    
    if leaflet_id:
        try:
            uuid_leaflet_id = UUID(leaflet_id)
            query = query.where(Product.leaflet_id == uuid_leaflet_id)
        except ValueError:
            if current_user.is_superuser:
                leaflet_lookup = select(Leaflet.id).where(Leaflet.leaflet_id == leaflet_id)
            else:
                leaflet_lookup = select(Leaflet.id).where(
                    and_(
                        Leaflet.leaflet_id == leaflet_id,
                        Leaflet.organization_id == current_org.id
                    )
                )
            query = query.where(Product.leaflet_id.in_(leaflet_lookup))
    
    query = query.group_by(Product.review_status)
    
    result = await db.execute(query)
    rows = result.all()
    
    breakdown = {}
    total = 0
    for row in rows:
        status = row.review_status.value if hasattr(row.review_status, 'value') else str(row.review_status)
        breakdown[status] = row.count
        total += row.count
    
    logger.info(f"Debug status breakdown for leaflet={leaflet_id}: {breakdown}, total={total}")
    
    return {
        "leaflet_id": leaflet_id,
        "total_products": total,
        "status_breakdown": breakdown,
    }


@router.get(
    "/review-queue",
    summary="Get review queue",
    description="Get products that need human review.",
)
async def get_review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    leaflet_id: Optional[str] = Query(None, description="Filter by leaflet (UUID or human-readable ID)"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get products needing review.
    
    Returns products sorted by review priority.
    
    Args:
        page: Page number
        page_size: Items per page
        leaflet_id: Optional filter by leaflet (UUID or human-readable ID)
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Paginated list of products needing review
    """
    logger.info(f"get_review_queue called: leaflet_id={leaflet_id}, user_id={current_user.id}")
    
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    # Build query for pending reviews
    query = select(Product).where(
        Product.leaflet_id.in_(user_leaflets),
        Product.review_status.in_([
            ReviewStatus.PENDING,
            ReviewStatus.NEEDS_CORRECTION,
        ])
    )
    count_query = select(func.count(Product.id)).where(
        Product.leaflet_id.in_(user_leaflets),
        Product.review_status.in_([
            ReviewStatus.PENDING,
            ReviewStatus.NEEDS_CORRECTION,
        ])
    )
    
    if leaflet_id:
        # Try to parse as UUID first, otherwise lookup by human-readable leaflet_id
        try:
            uuid_leaflet_id = UUID(leaflet_id)
            query = query.where(Product.leaflet_id == uuid_leaflet_id)
            count_query = count_query.where(Product.leaflet_id == uuid_leaflet_id)
        except ValueError:
            # It's a human-readable ID (like LEAF_2025_...), lookup the actual UUID
            if current_user.is_superuser:
                leaflet_lookup = select(Leaflet.id).where(Leaflet.leaflet_id == leaflet_id)
            else:
                leaflet_lookup = select(Leaflet.id).where(
                    and_(
                        Leaflet.leaflet_id == leaflet_id,
                        Leaflet.organization_id == current_org.id
                    )
                )
            query = query.where(Product.leaflet_id.in_(leaflet_lookup))
            count_query = count_query.where(Product.leaflet_id.in_(leaflet_lookup))
    
    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Sort by priority (descending) and confidence (ascending)
    query = query.order_by(
        Product.review_priority.desc(),
        Product.confidence.asc(),
    )
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    products = result.scalars().all()
    
    logger.info(f"Review queue: found {len(products)} products needing review, total={total}")
    
    # Safely serialize products
    serialized_products = []
    for p in products:
        try:
            serialized_products.append(serialize_product_for_list(p))
        except Exception as e:
            logger.error(f"Failed to serialize product {p.id}: {e}")
            continue
    
    return {
        "items": serialized_products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


@router.get(
    "/categories",
    summary="Get popular categories",
    description="Get the most common product categories with counts.",
)
async def get_categories(
    limit: int = Query(20, ge=1, le=50, description="Maximum categories to return"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get popular categories from existing products.

    Returns aggregated category counts, useful for populating
    the category dropdown in the review interface.

    Args:
        limit: Maximum number of categories to return
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Dictionary with categories and their counts
    """
    # Default categories to always include
    DEFAULT_CATEGORIES = [
        "Food & Groceries", "Beverages", "Dairy & Eggs", "Meat & Seafood",
        "Fruits & Vegetables", "Bakery", "Frozen Foods", "Snacks & Confectionery",
        "Household & Cleaning", "Personal Care & Beauty", "Health & Pharmacy",
        "Baby & Kids", "Pet Supplies", "Electronics", "Home & Garden", "Other"
    ]

    # Query categories from products
    if current_user.is_superuser:
        # Superusers see categories from all organizations
        query = select(
            Product.category,
            func.count(Product.id).label('count')
        ).where(
            Product.category.isnot(None),
        ).group_by(
            Product.category
        ).order_by(
            func.count(Product.id).desc()
        ).limit(limit)
    else:
        query = select(
            Product.category,
            func.count(Product.id).label('count')
        ).where(
            Product.organization_id == current_org.id,
            Product.category.isnot(None),
        ).group_by(
            Product.category
        ).order_by(
            func.count(Product.id).desc()
        ).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Build response with counts
    categories = [
        {"name": row.category, "count": row.count}
        for row in rows
    ]

    # Add default categories that aren't already in the list
    existing_names = {c["name"] for c in categories}
    for default_cat in DEFAULT_CATEGORIES:
        if default_cat not in existing_names and len(categories) < limit:
            categories.append({"name": default_cat, "count": 0})

    return {
        "categories": categories,
        "total": len(categories),
    }


@router.post(
    "/batch",
    summary="Batch fetch products",
    description="Fetch multiple products by ID in a single request (max 20).",
)
async def batch_get_products(
    request: ProductBatchFetchRequest,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Fetch multiple products by their IDs in a single request.

    Accepts a JSON body with `product_ids` (list of UUID strings, max 20).
    Returns products in the same order as requested. Missing/inaccessible
    products are silently omitted.

    Args:
        request: Validated request with product_ids list
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        Dictionary with products list
    """
    product_uuids = request.product_ids

    # Build query with ownership check
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)

    result = await db.execute(
        select(Product).where(
            Product.id.in_(product_uuids),
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    products = result.scalars().all()

    # Build lookup for preserving requested order
    product_map = {p.id: p for p in products}
    ordered = [product_map[uid] for uid in product_uuids if uid in product_map]

    serialized = []
    for p in ordered:
        try:
            serialized.append(serialize_product_for_list(p))
        except Exception as e:
            logger.error(f"Failed to serialize product {p.id} in batch: {e}")
            continue

    logger.info(f"Batch fetch: requested {len(product_uuids)}, returned {len(serialized)}")

    return {"products": serialized}


@router.get(
    "/{product_id}",
    summary="Get product details",
    description="Get detailed information about a specific product.",
)
async def get_product(
    product_id: UUID,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get product details.
    
    Args:
        product_id: Product UUID
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Product details
        
    Raises:
        NotFoundError: If product not found or not owned by user
    """
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))

    # Single product detail: include base64 image data
    return serialize_product_for_list(product, include_base64=True)


@router.post(
    "/{product_id}/refresh-image-url",
    summary="Refresh product image URL",
    description="Regenerate presigned URL for product image stored in S3/MinIO.",
)
async def refresh_product_image_url(
    product_id: UUID,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Refresh the presigned URL for a product image.
    
    This is useful when the presigned URL has expired.
    Only works for products with storage_type='file'.
    
    Args:
        product_id: Product UUID
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Updated product with new image URL
        
    Raises:
        NotFoundError: If product not found
        ValidationException: If product has no file-stored image
    """
    from app.utils.storage import get_storage_backend
    
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))
    
    if product.image_storage_type != "file" or not product.image_path:
        raise ValidationException("Product does not have a file-stored image")
    
    # Generate new presigned URL (24 hours)
    storage = get_storage_backend()
    new_url = await storage.get_file_url(product.image_path, expires_in=86400)
    
    product.image_url = new_url
    await db.commit()
    
    logger.info(f"Refreshed image URL for product {product_id}")
    
    return {
        "success": True,
        "image_url": new_url,
        "expires_in": 86400,
    }


@router.put(
    "/{product_id}",
    summary="Update product",
    description="Update product data.",
)
async def update_product(
    product_id: UUID,
    update_data: ProductUpdate,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Update product data.
    
    Args:
        product_id: Product UUID
        update_data: Fields to update
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Updated product
        
    Raises:
        NotFoundError: If product not found
    """
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))
    
    # Store previous data for review history
    previous_data = {
        "brand": product.brand,
        "product_code": product.product_code,
        "product_name": product.product_name,
        "quantity": product.quantity,
        "units": product.units,
        "size": product.size,
        "regular_price": float(product.regular_price) if product.regular_price else None,
        "discounted_price": float(product.discounted_price) if product.discounted_price else None,
        "discount_percentage": float(product.discount_percentage) if product.discount_percentage else None,
        "currency": product.currency,
        "product_id": product.product_id,
        "promotional_info": product.promotional_info,
        "category": product.category,
        "bbox_x": product.bbox_x,
        "bbox_y": product.bbox_y,
        "bbox_width": product.bbox_width,
        "bbox_height": product.bbox_height,
    }

    # Store original data if first correction
    if not product.is_corrected and not product.original_data:
        product.original_data = previous_data.copy()

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # Check if we should skip review history (when review will be submitted separately)
    skip_review_history = update_dict.pop("skip_review_history", False)

    # Track changed fields
    changed_fields = []
    new_data = {}

    # Handle bounding box separately
    if "bounding_box" in update_dict:
        bbox = update_dict.pop("bounding_box")
        if product.bbox_x != bbox["x"]:
            changed_fields.append("bbox_x")
            new_data["bbox_x"] = bbox["x"]
        if product.bbox_y != bbox["y"]:
            changed_fields.append("bbox_y")
            new_data["bbox_y"] = bbox["y"]
        if product.bbox_width != bbox["width"]:
            changed_fields.append("bbox_width")
            new_data["bbox_width"] = bbox["width"]
        if product.bbox_height != bbox["height"]:
            changed_fields.append("bbox_height")
            new_data["bbox_height"] = bbox["height"]
        product.bbox_x = bbox["x"]
        product.bbox_y = bbox["y"]
        product.bbox_width = bbox["width"]
        product.bbox_height = bbox["height"]

    for field, value in update_dict.items():
        old_value = getattr(product, field, None)
        # Convert Decimal to float for comparison
        if hasattr(old_value, '__float__'):
            old_value = float(old_value)
        if old_value != value:
            changed_fields.append(field)
            new_data[field] = value
        setattr(product, field, value)

    product.is_corrected = True

    # Create review history entry if there were changes (unless skipped)
    if changed_fields and not skip_review_history:
        review = ProductReview(
            product_id=product.id,
            reviewer_id=current_user.id,
            action="corrected",
            previous_data=previous_data,
            new_data=new_data,
            changed_fields=changed_fields,
            notes=None,
            time_spent_seconds=None,
        )
        db.add(review)

    await db.commit()
    await db.refresh(product)

    logger.info(f"Product updated: {product_id}, changed fields: {changed_fields}, skip_review_history: {skip_review_history}")

    # Return full detail (including base64) for single product update
    return serialize_product_for_list(product, include_base64=True)


@router.post(
    "/{product_id}/review",
    summary="Submit product review",
    description="Submit a review decision for a product.",
)
async def submit_review(
    product_id: UUID,
    review_data: ProductReviewCreate,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit a product review.
    
    Args:
        product_id: Product UUID
        review_data: Review decision and corrections
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Updated product
        
    Raises:
        NotFoundError: If product not found
    """
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))
    
    # Store previous data
    previous_data = {
        "brand": product.brand,
        "product_code": product.product_code,
        "product_name": product.product_name,
        "quantity": product.quantity,
        "units": product.units,
        "regular_price": product.regular_price,
        "discounted_price": product.discounted_price,
        "discount_percentage": product.discount_percentage,
        "bbox_x": product.bbox_x,
        "bbox_y": product.bbox_y,
        "bbox_width": product.bbox_width,
        "bbox_height": product.bbox_height,
    }
    
    # Apply corrections if provided
    changed_fields = []
    if review_data.corrections:
        for field, value in review_data.corrections.items():
            if hasattr(product, field) and getattr(product, field) != value:
                changed_fields.append(field)
                setattr(product, field, value)
    
    # Handle bounding box corrections
    if review_data.bounding_box:
        bbox = review_data.bounding_box
        if product.bbox_x != bbox.x:
            changed_fields.append("bbox_x")
        if product.bbox_y != bbox.y:
            changed_fields.append("bbox_y")
        if product.bbox_width != bbox.width:
            changed_fields.append("bbox_width")
        if product.bbox_height != bbox.height:
            changed_fields.append("bbox_height")
        
        product.bbox_x = bbox.x
        product.bbox_y = bbox.y
        product.bbox_width = bbox.width
        product.bbox_height = bbox.height
    
    # Update review status
    action = review_data.action.lower()
    if action == "approved":
        product.review_status = ReviewStatus.APPROVED
    elif action == "rejected":
        product.review_status = ReviewStatus.REJECTED
    elif action == "corrected":
        product.review_status = ReviewStatus.APPROVED
        product.is_corrected = True
    elif action == "needs_correction":
        product.review_status = ReviewStatus.NEEDS_CORRECTION
    
    product.reviewed_by = current_user.id
    product.reviewed_at = datetime.utcnow()
    product.review_notes = review_data.notes
    
    # Create review record
    review = ProductReview(
        product_id=product.id,
        reviewer_id=current_user.id,
        action=action,
        previous_data=previous_data,
        new_data=review_data.corrections,
        changed_fields=changed_fields,
        notes=review_data.notes,
        time_spent_seconds=review_data.time_spent_seconds,
    )
    
    db.add(review)
    await db.commit()
    await db.refresh(product)
    
    logger.info(f"Product reviewed: {product_id} - {action}")

    # Return full detail (including base64) for single product review
    return serialize_product_for_list(product, include_base64=True)


@router.post(
    "/batch-review",
    response_model=ProductBatchReviewResponse,
    summary="Batch review products",
    description="Apply the same review decision to multiple products.",
)
async def batch_review(
    batch_data: ProductBatchReviewCreate,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Batch review multiple products.
    
    Args:
        batch_data: Product IDs and review action
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Batch review results
    """
    # Get organization's leaflet IDs (or all for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    processed = 0
    succeeded = 0
    failed = 0
    errors = []
    
    action = batch_data.action.lower()
    
    for product_id in batch_data.product_ids:
        try:
            result = await db.execute(
                select(Product).where(
                    Product.id == product_id,
                    Product.leaflet_id.in_(user_leaflets),
                )
            )
            product = result.scalar_one_or_none()
            
            if product is None:
                errors.append({
                    "product_id": str(product_id),
                    "error": "Product not found"
                })
                failed += 1
                continue
            
            # Update status
            if action == "approved":
                product.review_status = ReviewStatus.APPROVED
            elif action == "rejected":
                product.review_status = ReviewStatus.REJECTED
            
            product.reviewed_by = current_user.id
            product.reviewed_at = datetime.utcnow()
            product.review_notes = batch_data.notes
            
            # Create review record
            review = ProductReview(
                product_id=product.id,
                reviewer_id=current_user.id,
                action=action,
                notes=batch_data.notes,
            )
            db.add(review)
            
            succeeded += 1
            
        except Exception as e:
            errors.append({
                "product_id": str(product_id),
                "error": str(e)
            })
            failed += 1
        
        processed += 1
    
    await db.commit()
    
    logger.info(
        f"Batch review completed: {succeeded} succeeded, {failed} failed"
    )
    
    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors,
    }


@router.get(
    "/{product_id}/reviews",
    response_model=List[ProductReviewResponse],
    summary="Get product review history",
    description="Get the review history for a product.",
)
async def get_review_history(
    product_id: UUID,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[ProductReview]:
    """
    Get product review history.
    
    Args:
        product_id: Product UUID
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        List of reviews
        
    Raises:
        NotFoundError: If product not found
    """
    # Verify product exists and belongs to organization (or any for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))
    
    # Get reviews
    reviews_result = await db.execute(
        select(ProductReview)
        .where(ProductReview.product_id == product_id)
        .order_by(ProductReview.created_at.desc())
    )
    
    return reviews_result.scalars().all()


@router.post(
    "/{product_id}/re-extract-image",
    response_model=SuccessResponse,
    summary="Re-extract product image",
    description="Re-extract product image from page using current bounding box.",
)
async def re_extract_product_image(
    product_id: UUID,
    current_user: User = Depends(require_write),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Re-extract product image from the page image.
    
    Uses the current bounding box coordinates to extract
    a fresh image from the page. Useful after bounding box
    adjustments.
    
    Args:
        product_id: Product UUID
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Success status
        
    Raises:
        NotFoundError: If product not found
        ProcessingError: If extraction fails
    """
    from app.models.leaflet import LeafletPage
    from app.core.image_processing.extractor import ImageExtractor
    from app.core.image_processing.quality import QualityScorer
    from app.core.extraction.schemas import BoundingBox
    from app.utils.storage import get_storage_backend
    from PIL import Image
    from io import BytesIO
    import tempfile
    import os
    
    # Verify product exists and belongs to organization (or any for superusers)
    if current_user.is_superuser:
        user_leaflets = select(Leaflet.id)
    else:
        user_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.leaflet_id.in_(user_leaflets),
        )
    )
    product = result.scalar_one_or_none()
    
    if product is None:
        raise NotFoundError("Product", str(product_id))
    
    # Get the page
    page_result = await db.execute(
        select(LeafletPage).where(
            LeafletPage.leaflet_id == product.leaflet_id,
            LeafletPage.page_number == product.page_number,
        )
    )
    page = page_result.scalar_one_or_none()
    
    if page is None:
        raise NotFoundError("Page", str(product.page_number))
    
    # Get leaflet for leaflet_id string
    leaflet_result = await db.execute(
        select(Leaflet).where(Leaflet.id == product.leaflet_id)
    )
    leaflet = leaflet_result.scalar_one_or_none()
    
    if leaflet is None:
        raise NotFoundError("Leaflet", str(product.leaflet_id))
    
    try:
        # Download page image
        storage = get_storage_backend()
        image_bytes = await storage.download_file(page.image_path)
        page_image = Image.open(BytesIO(image_bytes))
        
        # Initialize processors
        extractor = ImageExtractor(padding=2, enhance=True)
        quality_scorer = QualityScorer(min_acceptable_score=0.70)
        
        # Create bounding box
        bbox = BoundingBox(
            x=product.bbox_x,
            y=product.bbox_y,
            width=product.bbox_width,
            height=product.bbox_height,
        )
        
        # Save to temp file for extractor
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            page_image.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # Extract product image
            extraction_result = extractor.extract_product_image(
                page_image_path=tmp_path,
                bounding_box=bbox,
                product_id=str(product.id),
            )
        finally:
            os.unlink(tmp_path)
        
        if not extraction_result.success:
            from app.utils.exceptions import ProcessingError
            raise ProcessingError(f"Failed to extract image: {extraction_result.error}")
        
        # Score image quality
        quality_report = quality_scorer.analyze(extraction_result.image)
        
        # Convert extracted image to bytes for storage
        img_buffer = BytesIO()
        extraction_result.image.save(img_buffer, format='JPEG', quality=90)
        img_bytes = img_buffer.getvalue()
        
        # Determine storage path
        image_filename = f"{leaflet.leaflet_id}_page{product.page_number:02d}_{product.id}.jpg"
        image_path = f"leaflets/{leaflet.leaflet_id}/products/{image_filename}"
        
        # Upload to storage (MinIO)
        await storage.upload_file(
            file_content=img_bytes,
            file_path=image_path,
            content_type="image/jpeg",
        )
        
        # Get presigned URL for the uploaded image
        presigned_url = await storage.get_file_url(image_path, expires_in=86400)  # 24 hour expiry
        
        # Update product record
        product.image_storage_type = "file"
        product.image_base64 = None  # Clear base64 if any
        product.image_url = presigned_url
        product.image_path = image_path  # Store the path for future URL regeneration
        product.image_format = "JPEG"
        product.image_width = extraction_result.image.width
        product.image_height = extraction_result.image.height
        product.image_size_bytes = len(img_bytes)
        product.image_quality_score = quality_report.overall_score
        
        await db.commit()
        
        logger.info(f"Re-extracted image for product {product_id}: {image_path}")
        
        return {
            "success": True,
            "message": "Image re-extracted successfully",
            "data": {
                "product_id": str(product_id),
                "image_quality_score": quality_report.overall_score,
                "storage_type": "file",
                "image_url": presigned_url,
                "image_base64": None,
                "image_width": extraction_result.image.width,
                "image_height": extraction_result.image.height,
            },
        }
        
    except Exception as e:
        logger.error(f"Failed to re-extract image for {product_id}: {e}")
        from app.utils.exceptions import ProcessingError
        raise ProcessingError(f"Image re-extraction failed: {str(e)}")


@router.get(
    "/debug/{leaflet_id}",
    summary="Debug product status",
    description="Debug endpoint to check product status distribution for a leaflet.",
)
async def debug_product_status(
    leaflet_id: str,
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Debug endpoint to check what products are in the database and their statuses.
    
    Args:
        leaflet_id: Leaflet ID (UUID or human-readable)
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Debug information about products in the database
    """
    logger.info(f"Debug endpoint called for leaflet: {leaflet_id}")
    
    # Try to parse as UUID first
    try:
        uuid_leaflet_id = UUID(leaflet_id)
        logger.info(f"Parsed as UUID: {uuid_leaflet_id}")
    except ValueError:
        # Lookup by human-readable ID
        if current_user.is_superuser:
            leaflet_result = await db.execute(
                select(Leaflet.id).where(Leaflet.leaflet_id == leaflet_id)
            )
        else:
            leaflet_result = await db.execute(
                select(Leaflet.id).where(
                    and_(
                        Leaflet.leaflet_id == leaflet_id,
                        Leaflet.organization_id == current_org.id
                    )
                )
            )
        leaflet_row = leaflet_result.first()
        if not leaflet_row:
            return {"error": f"Leaflet not found: {leaflet_id}"}
        uuid_leaflet_id = leaflet_row[0]
        logger.info(f"Looked up UUID: {uuid_leaflet_id}")
    
    # Get ALL products for this leaflet (no filters)
    products_result = await db.execute(
        select(Product).where(Product.leaflet_id == uuid_leaflet_id)
    )
    products = products_result.scalars().all()
    
    # Count by status
    status_counts = {}
    for p in products:
        status = p.review_status.value if hasattr(p.review_status, 'value') else str(p.review_status)
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Get raw status values to check for issues
    raw_statuses = set()
    for p in products:
        raw_statuses.add(str(p.review_status))
    
    # Detailed breakdown
    products_detail = []
    for p in products[:10]:  # First 10 products
        products_detail.append({
            "id": str(p.id),
            "name": p.product_name[:50] if p.product_name else None,
            "review_status": p.review_status.value if hasattr(p.review_status, 'value') else str(p.review_status),
            "review_status_raw": str(p.review_status),
            "confidence": float(p.confidence) if p.confidence else None,
            "validation_passed": p.validation_passed,
        })
    
    return {
        "leaflet_id": str(uuid_leaflet_id),
        "total_products": len(products),
        "status_counts": status_counts,
        "raw_statuses_found": list(raw_statuses),
        "sample_products": products_detail,
    }