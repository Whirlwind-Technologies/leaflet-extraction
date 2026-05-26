"""
Analytics API Endpoints.

This module provides endpoints for analytics, reporting,
and usage statistics.

Example Usage:
    GET /api/v1/analytics/summary - Live summary stats (source of truth)
    GET /api/v1/analytics/dashboard - Dashboard stats
    GET /api/v1/analytics/costs - Cost breakdown
    GET /api/v1/analytics/quality - Quality metrics
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_read, get_current_organization, get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.leaflet import Leaflet, LeafletStatus
from app.models.product import Product, ReviewStatus
from app.models.analytics import CostTracking, UsageMetrics, FeedbackLog
from app.models.organization_user import OrganizationUser
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class DashboardStats(BaseModel):
    """Dashboard statistics."""
    period_days: int
    leaflets: dict
    products: dict
    costs: dict
    quality: dict
    trends: dict


class CostBreakdown(BaseModel):
    """Cost breakdown."""
    total_cost: float
    period_cost: float
    input_tokens: int
    output_tokens: int
    by_provider: dict
    by_model: dict
    daily_costs: List[dict]


class QualityMetrics(BaseModel):
    """Quality metrics."""
    extraction_success_rate: float
    auto_approval_rate: float
    validation_pass_rate: float
    avg_confidence: float
    error_rate: float
    correction_rate: float


class UsageSummary(BaseModel):
    """Usage summary."""
    total_leaflets: int
    total_products: int
    total_pages: int
    total_api_calls: int
    total_cost: float
    period: str


class TrendDataPoint(BaseModel):
    """Single data point for trend chart."""
    date: str
    value: float


class ExportStats(BaseModel):
    """Export statistics."""
    total_exports: int
    csv_exports: int
    json_exports: int
    excel_exports: int


class AnalyticsSummary(BaseModel):
    """Live analytics summary computed from the same queries as the product list and leaflet list pages.

    Every number here is guaranteed to match what the All Products page,
    Review Queue page, and Leaflets page display.
    """

    # Product counts by review status (matches GET /api/v1/products/stats)
    total_products: int = Field(0, description="Total products across all statuses")
    auto_approved: int = Field(0, description="Products automatically approved (high confidence)")
    approved: int = Field(0, description="Products manually approved by reviewer")
    pending: int = Field(0, description="Products awaiting review")
    rejected: int = Field(0, description="Products rejected by reviewer")
    needs_correction: int = Field(0, description="Products flagged for correction")

    # Derived product metrics
    total_approved: int = Field(0, description="auto_approved + approved (all approved products)")
    total_awaiting_review: int = Field(0, description="pending + needs_correction")
    auto_approval_rate: float = Field(0.0, description="Percentage of products auto-approved")
    avg_confidence: float = Field(0.0, description="Average confidence score (0-100 scale)")
    validation_pass_rate: float = Field(0.0, description="Percentage of products passing validation")
    high_priority_count: int = Field(0, description="Products with review_priority >= 70")

    # Leaflet counts
    total_leaflets: int = Field(0, description="Total leaflets")
    leaflets_completed: int = Field(0, description="Leaflets with status COMPLETED")
    leaflets_processing: int = Field(0, description="Leaflets currently processing/extracting")
    leaflets_failed: int = Field(0, description="Leaflets with status FAILED")
    leaflets_by_status: dict = Field(default_factory=dict, description="Count per leaflet status")

    # Period filtering info
    start_date: Optional[str] = Field(None, description="Start date filter (ISO format) or null for all time")
    end_date: Optional[str] = Field(None, description="End date filter (ISO format) or null for all time")


# --- Endpoints ---


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Get live analytics summary",
    description=(
        "Returns live-computed analytics that are guaranteed to match the numbers "
        "shown on the All Products, Review Queue, and Leaflets pages. "
        "Supports optional date range filtering on Product.created_at / Leaflet.created_at."
    ),
)
async def get_analytics_summary(
    start_date: Optional[date] = Query(
        None,
        description="Include products/leaflets created on or after this date (YYYY-MM-DD)",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Include products/leaflets created on or before this date (YYYY-MM-DD)",
    ),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    """Compute live analytics summary from the same query patterns used by the list pages.

    This endpoint eliminates the mismatch problem by using the exact same
    query shape as ``GET /api/v1/products/stats`` and ``GET /api/v1/leaflets``.
    Products are scoped via ``Product.organization_id`` (denormalized column)
    and leaflets via ``Leaflet.organization_id``, both matching the
    authenticated user's current organization.

    Args:
        start_date: Optional lower bound for created_at filters.
        end_date: Optional upper bound for created_at filters.
        current_user: Authenticated user from JWT token.
        current_org: Current organization context.
        db: Async database session.

    Returns:
        AnalyticsSummary with all metrics computed live.
    """
    # ------------------------------------------------------------------
    # 1. PRODUCT COUNTS — mirrors GET /api/v1/products/stats exactly
    # ------------------------------------------------------------------
    # Use the same query pattern as the products stats endpoint: filter
    # via Product.organization_id (denormalized for performance).
    product_base = select(
        Product.review_status,
        func.count(Product.id).label("cnt"),
    ).where(Product.organization_id == current_org.id)

    if start_date:
        product_base = product_base.where(
            Product.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        product_base = product_base.where(
            Product.created_at <= datetime.combine(end_date, datetime.max.time())
        )

    product_base = product_base.group_by(Product.review_status)
    result = await db.execute(product_base)

    status_counts: dict[str, int] = {}
    total_products = 0
    for row in result.all():
        status_val = row.review_status.value if hasattr(row.review_status, "value") else str(row.review_status)
        status_counts[status_val] = row.cnt
        total_products += row.cnt

    auto_approved = status_counts.get("auto_approved", 0)
    approved = status_counts.get("approved", 0)
    pending = status_counts.get("pending", 0)
    rejected = status_counts.get("rejected", 0)
    needs_correction = status_counts.get("needs_correction", 0)

    total_approved = auto_approved + approved
    total_awaiting = pending + needs_correction
    auto_approval_rate = (auto_approved / max(total_products, 1)) * 100

    # ------------------------------------------------------------------
    # 2. QUALITY METRICS — avg confidence & validation pass rate
    # ------------------------------------------------------------------
    quality_query = select(
        func.avg(Product.confidence),
        func.count(case((Product.validation_passed == True, 1))),  # noqa: E712
        func.count(case((Product.review_priority >= 70, 1))),
        func.count(Product.id),
    ).where(Product.organization_id == current_org.id)

    if start_date:
        quality_query = quality_query.where(
            Product.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        quality_query = quality_query.where(
            Product.created_at <= datetime.combine(end_date, datetime.max.time())
        )

    quality_result = await db.execute(quality_query)
    avg_conf, validated_count, high_priority_count, quality_total = quality_result.one()

    avg_confidence = round((avg_conf or 0) * 100, 1)
    validation_pass_rate = round((validated_count / max(quality_total, 1)) * 100, 1)

    # ------------------------------------------------------------------
    # 3. LEAFLET COUNTS — mirrors GET /api/v1/leaflets list
    # ------------------------------------------------------------------
    leaflet_base = select(
        Leaflet.status,
        func.count(Leaflet.id).label("cnt"),
    ).where(Leaflet.organization_id == current_org.id)

    if start_date:
        leaflet_base = leaflet_base.where(
            Leaflet.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        leaflet_base = leaflet_base.where(
            Leaflet.created_at <= datetime.combine(end_date, datetime.max.time())
        )

    leaflet_base = leaflet_base.group_by(Leaflet.status)
    leaflet_result = await db.execute(leaflet_base)

    leaflets_by_status: dict[str, int] = {}
    total_leaflets = 0
    for row in leaflet_result.all():
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        leaflets_by_status[status_val] = row.cnt
        total_leaflets += row.cnt

    leaflets_completed = leaflets_by_status.get("completed", 0)
    leaflets_processing = (
        leaflets_by_status.get("processing", 0)
        + leaflets_by_status.get("extracting", 0)
        + leaflets_by_status.get("validating", 0)
    )
    leaflets_failed = leaflets_by_status.get("failed", 0)

    logger.info(
        "Analytics summary computed",
        extra={
            "organization_id": str(current_org.id),
            "total_products": total_products,
            "total_leaflets": total_leaflets,
            "auto_approved": auto_approved,
            "pending": pending,
        },
    )

    return AnalyticsSummary(
        total_products=total_products,
        auto_approved=auto_approved,
        approved=approved,
        pending=pending,
        rejected=rejected,
        needs_correction=needs_correction,
        total_approved=total_approved,
        total_awaiting_review=total_awaiting,
        auto_approval_rate=round(auto_approval_rate, 1),
        avg_confidence=avg_confidence,
        validation_pass_rate=validation_pass_rate,
        high_priority_count=high_priority_count,
        total_leaflets=total_leaflets,
        leaflets_completed=leaflets_completed,
        leaflets_processing=leaflets_processing,
        leaflets_failed=leaflets_failed,
        leaflets_by_status=leaflets_by_status,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
    )


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="Get dashboard statistics",
    description="Get comprehensive dashboard statistics.",
)
async def get_dashboard_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """Get dashboard statistics for the current organization."""
    service = AnalyticsService(db)
    stats = await service.get_dashboard_stats(current_org.id, days)

    return DashboardStats(
        period_days=stats["period_days"],
        leaflets=stats["leaflets"],
        products=stats["products"],
        costs=stats["costs"],
        quality=stats["quality"],
        trends=stats["trends"],
    )


@router.get(
    "/costs",
    response_model=CostBreakdown,
    summary="Get cost breakdown",
    description="Get detailed cost breakdown.",
)
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> CostBreakdown:
    """Get detailed cost breakdown."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get leaflet IDs for this organization to filter costs
    org_leaflets = select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
    period_org_leaflets = select(Leaflet.id).where(
        and_(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= cutoff,
        )
    )

    # Total cost (filter via leaflet_id)
    total_query = select(func.sum(CostTracking.total_cost)).where(
        CostTracking.leaflet_id.in_(org_leaflets)
    )
    total_result = await db.execute(total_query)
    total_cost = total_result.scalar() or 0

    # Period cost
    period_query = select(func.sum(CostTracking.total_cost)).where(
        and_(
            CostTracking.leaflet_id.in_(period_org_leaflets),
            CostTracking.processed_at >= cutoff,
        )
    )
    period_result = await db.execute(period_query)
    period_cost = period_result.scalar() or 0

    # Token usage
    tokens_query = select(
        func.sum(CostTracking.input_tokens),
        func.sum(CostTracking.output_tokens),
    ).where(
        and_(
            CostTracking.leaflet_id.in_(period_org_leaflets),
            CostTracking.processed_at >= cutoff,
        )
    )
    tokens_result = await db.execute(tokens_query)
    input_tokens, output_tokens = tokens_result.one()

    # By provider
    provider_query = (
        select(
            CostTracking.provider_type,
            func.sum(CostTracking.total_cost),
        )
        .where(
            and_(
                CostTracking.leaflet_id.in_(period_org_leaflets),
                CostTracking.processed_at >= cutoff,
            )
        )
        .group_by(CostTracking.provider_type)
    )
    provider_result = await db.execute(provider_query)
    by_provider = {k: float(v or 0) for k, v in provider_result.all()}

    # By model
    model_query = (
        select(
            CostTracking.model_name,
            func.sum(CostTracking.total_cost),
        )
        .where(
            and_(
                CostTracking.leaflet_id.in_(period_org_leaflets),
                CostTracking.processed_at >= cutoff,
            )
        )
        .group_by(CostTracking.model_name)
    )
    model_result = await db.execute(model_query)
    by_model = {k: float(v or 0) for k, v in model_result.all()}

    # Daily costs
    daily_costs = []
    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())

        # Leaflets for this day
        day_leaflets = select(Leaflet.id).where(
            and_(
                Leaflet.organization_id == current_org.id,
                Leaflet.created_at >= day_start,
                Leaflet.created_at <= day_end,
            )
        )

        day_query = select(func.sum(CostTracking.total_cost)).where(
            and_(
                CostTracking.leaflet_id.in_(day_leaflets),
                CostTracking.processed_at >= day_start,
                CostTracking.processed_at <= day_end,
            )
        )
        day_result = await db.execute(day_query)
        day_cost = day_result.scalar() or 0

        daily_costs.append({
            "date": day.isoformat(),
            "cost": float(day_cost or 0),
        })
    
    return CostBreakdown(
        total_cost=float(total_cost or 0),
        period_cost=float(period_cost or 0),
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        by_provider=by_provider,
        by_model=by_model,
        daily_costs=daily_costs,
    )


@router.get(
    "/quality",
    response_model=QualityMetrics,
    summary="Get quality metrics",
    description="Get quality metrics for extractions.",
)
async def get_quality_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> QualityMetrics:
    """Get quality metrics.

    Uses Product.organization_id (denormalized column) for filtering
    to match the same query pattern as GET /api/v1/products/stats.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Products stats — use denormalized organization_id for consistency
    products_query = select(
        func.count(Product.id),
        func.count(case((Product.validation_passed == True, 1))),  # noqa: E712
        func.count(case((Product.review_status == ReviewStatus.AUTO_APPROVED, 1))),
        func.avg(Product.confidence),
    ).where(
        and_(
            Product.organization_id == current_org.id,
            Product.created_at >= cutoff,
        )
    )

    products_result = await db.execute(products_query)
    total, validated, auto_approved, avg_conf = products_result.one()
    total = total or 0
    validated = validated or 0
    auto_approved = auto_approved or 0
    avg_conf = avg_conf or 0

    # Leaflet success rate
    leaflet_query = select(
        func.count(case((Leaflet.status == LeafletStatus.COMPLETED, 1))),
        func.count(Leaflet.id),
    ).where(
        and_(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= cutoff,
            Leaflet.status.in_([LeafletStatus.COMPLETED, LeafletStatus.FAILED]),
        )
    )
    leaflet_result = await db.execute(leaflet_query)
    completed, attempted = leaflet_result.one()

    # Correction rate (from feedback) - scope to organization's leaflets
    org_leaflets_for_feedback = select(Leaflet.id).where(
        and_(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= cutoff,
        )
    )
    feedback_query = select(func.count(FeedbackLog.id)).where(
        FeedbackLog.leaflet_id.in_(org_leaflets_for_feedback)
    )
    feedback_result = await db.execute(feedback_query)
    corrections = feedback_result.scalar() or 0

    extraction_rate = (completed / max(attempted, 1)) * 100
    validation_rate = (validated / max(total, 1)) * 100
    auto_rate = (auto_approved / max(total, 1)) * 100
    correction_rate = (corrections / max(total, 1)) * 100
    error_rate = 100 - validation_rate

    return QualityMetrics(
        extraction_success_rate=round(extraction_rate, 1),
        auto_approval_rate=round(auto_rate, 1),
        validation_pass_rate=round(validation_rate, 1),
        avg_confidence=round(avg_conf * 100, 1) if avg_conf else 0,
        error_rate=round(error_rate, 1),
        correction_rate=round(correction_rate, 1),
    )


@router.get(
    "/usage",
    response_model=UsageSummary,
    summary="Get usage summary",
    description="Get usage summary for a period.",
)
async def get_usage_summary(
    period: str = Query("month", pattern="^(day|week|month|year|all)$"),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    """Get usage summary."""
    now = datetime.utcnow()
    
    if period == "day":
        cutoff = now - timedelta(days=1)
    elif period == "week":
        cutoff = now - timedelta(weeks=1)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "year":
        cutoff = now - timedelta(days=365)
    else:
        cutoff = datetime(2000, 1, 1)  # All time
    
    # Leaflets
    leaflet_query = select(
        func.count(Leaflet.id),
        func.sum(Leaflet.page_count),
    ).where(
        and_(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= cutoff,
        )
    )
    leaflet_result = await db.execute(leaflet_query)
    leaflet_count, page_count = leaflet_result.one()
    
    # Products — use denormalized organization_id for consistency
    product_query = select(func.count(Product.id)).where(
        and_(
            Product.organization_id == current_org.id,
            Product.created_at >= cutoff,
        )
    )
    product_result = await db.execute(product_query)
    product_count = product_result.scalar() or 0

    # API calls and cost (filter via leaflet_id since CostTracking has no org column)
    leaflets_in_period = select(Leaflet.id).where(
        and_(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= cutoff,
        )
    )
    cost_query = select(
        func.count(CostTracking.id),
        func.sum(CostTracking.total_cost),
    ).where(
        and_(
            CostTracking.leaflet_id.in_(leaflets_in_period),
            CostTracking.processed_at >= cutoff,
        )
    )
    cost_result = await db.execute(cost_query)
    api_calls, total_cost = cost_result.one()
    
    return UsageSummary(
        total_leaflets=leaflet_count or 0,
        total_products=product_count or 0,
        total_pages=page_count or 0,
        total_api_calls=api_calls or 0,
        total_cost=float(total_cost or 0),
        period=period,
    )


@router.get(
    "/trends/leaflets",
    response_model=List[TrendDataPoint],
    summary="Get leaflet trends",
    description="Get daily leaflet counts for trend chart.",
)
async def get_leaflet_trends(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[TrendDataPoint]:
    """Get daily leaflet counts."""
    trends = []
    
    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        query = select(func.count(Leaflet.id)).where(
            and_(
                Leaflet.organization_id == current_org.id,
                Leaflet.created_at >= day_start,
                Leaflet.created_at <= day_end,
            )
        )
        result = await db.execute(query)
        count = result.scalar() or 0
        
        trends.append(TrendDataPoint(
            date=day.isoformat(),
            value=count,
        ))
    
    return trends


@router.get(
    "/trends/products",
    response_model=List[TrendDataPoint],
    summary="Get product trends",
    description="Get daily product counts for trend chart.",
)
async def get_product_trends(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[TrendDataPoint]:
    """Get daily product counts."""
    trends = []
    
    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        
        # Use denormalized organization_id for consistency
        query = select(func.count(Product.id)).where(
            and_(
                Product.organization_id == current_org.id,
                Product.created_at >= day_start,
                Product.created_at <= day_end,
            )
        )
        result = await db.execute(query)
        count = result.scalar() or 0

        trends.append(TrendDataPoint(
            date=day.isoformat(),
            value=count,
        ))

    return trends


@router.get(
    "/trends/costs",
    response_model=List[TrendDataPoint],
    summary="Get cost trends",
    description="Get daily costs for trend chart.",
)
async def get_cost_trends(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[TrendDataPoint]:
    """Get daily costs."""
    trends = []

    for i in range(days - 1, -1, -1):
        day = date.today() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())

        # Get leaflets for this day to filter costs
        day_leaflets = select(Leaflet.id).where(
            and_(
                Leaflet.organization_id == current_org.id,
                Leaflet.created_at >= day_start,
                Leaflet.created_at <= day_end,
            )
        )

        query = select(func.sum(CostTracking.total_cost)).where(
            and_(
                CostTracking.leaflet_id.in_(day_leaflets),
                CostTracking.processed_at >= day_start,
                CostTracking.processed_at <= day_end,
            )
        )
        result = await db.execute(query)
        cost = result.scalar() or 0

        trends.append(TrendDataPoint(
            date=day.isoformat(),
            value=float(cost or 0),
        ))

    return trends


@router.get(
    "/exports",
    response_model=ExportStats,
    summary="Get export statistics",
    description="Get export statistics.",
)
async def get_export_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> ExportStats:
    """Get export statistics."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get users belonging to this organization
    org_users = select(OrganizationUser.user_id).where(
        and_(
            OrganizationUser.organization_id == current_org.id,
            OrganizationUser.is_active == True
        )
    )

    # Get usage metrics for the period - scope to organization's users
    query = select(
        func.sum(UsageMetrics.exports_csv),
        func.sum(UsageMetrics.exports_json),
        func.sum(UsageMetrics.exports_excel),
    ).where(
        and_(
            UsageMetrics.user_id.in_(org_users),
            UsageMetrics.date >= cutoff.date(),
        )
    )
    result = await db.execute(query)
    csv_exports, json_exports, excel_exports = result.one()
    
    return ExportStats(
        total_exports=(csv_exports or 0) + (json_exports or 0) + (excel_exports or 0),
        csv_exports=csv_exports or 0,
        json_exports=json_exports or 0,
        excel_exports=excel_exports or 0,
    )


@router.get(
    "/top-retailers",
    summary="Get top retailers",
    description="Get top retailers by leaflet count.",
)
async def get_top_retailers(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_read),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get top retailers by leaflet count."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = (
        select(
            Leaflet.retailer,
            func.count(Leaflet.id).label('count'),
            func.sum(Leaflet.page_count).label('pages'),
        )
        .where(
            and_(
                Leaflet.organization_id == current_org.id,
                Leaflet.created_at >= cutoff,
                Leaflet.retailer.isnot(None),
            )
        )
        .group_by(Leaflet.retailer)
        .order_by(func.count(Leaflet.id).desc())
        .limit(limit)
    )
    
    result = await db.execute(query)
    
    return [
        {
            "retailer": retailer,
            "leaflet_count": count,
            "page_count": pages or 0,
        }
        for retailer, count, pages in result.all()
    ]