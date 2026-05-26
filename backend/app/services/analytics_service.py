"""
Analytics Service Module.

This module provides analytics and reporting functionality
for tracking usage, costs, and quality metrics.

Example Usage:
    from app.services.analytics_service import AnalyticsService
    
    service = AnalyticsService(db)
    stats = await service.get_dashboard_stats(user_id)
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leaflet import Leaflet, LeafletStatus
from app.models.product import Product, ReviewStatus
from app.models.analytics import (
    UsageMetrics,
    CostTracking,
    ProcessingStats,
    FeedbackLog,
    ErrorPattern,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for analytics and reporting.
    
    Provides dashboard statistics, usage tracking, and reporting.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_stats(
        self,
        organization_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard statistics.
        
        Args:
            user_id: User ID
            days: Number of days to include
            
        Returns:
            Dashboard statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Leaflet stats
        leaflet_stats = await self._get_leaflet_stats(organization_id, cutoff)

        # Product stats
        product_stats = await self._get_product_stats(organization_id, cutoff)

        # Cost stats
        cost_stats = await self._get_cost_stats(organization_id, cutoff, leaflet_stats.get("period_total", 1))

        # Quality metrics
        quality_stats = await self._get_quality_stats(organization_id, cutoff)

        # Trend data
        trends = await self._get_trend_data(organization_id, days)
        
        return {
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "leaflets": leaflet_stats,
            "products": product_stats,
            "costs": cost_stats,
            "quality": quality_stats,
            "trends": trends,
        }
    
    async def _get_leaflet_stats(
        self,
        organization_id: UUID,
        cutoff: datetime,
    ) -> Dict[str, Any]:
        """Get leaflet statistics."""
        # Total counts
        total_query = select(func.count(Leaflet.id)).where(
            Leaflet.organization_id == organization_id
        )
        total_result = await self.db.execute(total_query)
        total = total_result.scalar() or 0
        
        # Period counts
        period_query = select(func.count(Leaflet.id)).where(
            and_(
                Leaflet.organization_id == organization_id,
                Leaflet.created_at >= cutoff,
            )
        )
        period_result = await self.db.execute(period_query)
        period_total = period_result.scalar() or 0
        
        # Status breakdown
        status_query = (
            select(Leaflet.status, func.count(Leaflet.id))
            .where(Leaflet.organization_id == organization_id)
            .group_by(Leaflet.status)
        )
        status_result = await self.db.execute(status_query)
        status_counts = {
            str(status.value) if status else "unknown": count
            for status, count in status_result.all()
        }
        
        # Page counts
        pages_query = select(func.sum(Leaflet.page_count)).where(
            and_(
                Leaflet.organization_id == organization_id,
                Leaflet.created_at >= cutoff,
            )
        )
        pages_result = await self.db.execute(pages_query)
        total_pages = pages_result.scalar() or 0
        
        return {
            "total": total,
            "period_total": period_total,
            "total_pages": total_pages,
            "by_status": status_counts,
            "completed": status_counts.get("completed", 0),
            "processing": status_counts.get("processing", 0) + status_counts.get("extracting", 0),
            "failed": status_counts.get("failed", 0),
        }
    
    async def _get_product_stats(
        self,
        organization_id: UUID,
        cutoff: datetime,
    ) -> Dict[str, Any]:
        """Get product statistics.

        Uses Product.organization_id (denormalized column) for filtering
        to match the same query pattern as GET /api/v1/products/stats,
        ensuring consistent counts across all pages.
        """
        # Total products (all time) — use denormalized organization_id
        total_query = select(func.count(Product.id)).where(
            Product.organization_id == organization_id
        )
        total_result = await self.db.execute(total_query)
        total = total_result.scalar() or 0

        # Period products
        period_query = select(func.count(Product.id)).where(
            and_(
                Product.organization_id == organization_id,
                Product.created_at >= cutoff,
            )
        )
        period_result = await self.db.execute(period_query)
        period_total = period_result.scalar() or 0

        # Status breakdown (all time)
        status_query = (
            select(Product.review_status, func.count(Product.id))
            .where(Product.organization_id == organization_id)
            .group_by(Product.review_status)
        )
        status_result = await self.db.execute(status_query)
        status_counts = {
            str(status.value) if status else "unknown": count
            for status, count in status_result.all()
        }

        # Average confidence (period)
        conf_query = select(func.avg(Product.confidence)).where(
            and_(
                Product.organization_id == organization_id,
                Product.created_at >= cutoff,
                Product.confidence.isnot(None),
            )
        )
        conf_result = await self.db.execute(conf_query)
        avg_confidence = conf_result.scalar() or 0

        auto_approved = status_counts.get("auto_approved", 0)
        approved = status_counts.get("approved", 0)

        return {
            "total": total,
            "period_total": period_total,
            "by_status": status_counts,
            "auto_approved": auto_approved,
            "approved": approved,
            "total_approved": auto_approved + approved,
            "pending_review": status_counts.get("pending", 0),
            "needs_correction": status_counts.get("needs_correction", 0),
            "rejected": status_counts.get("rejected", 0),
            "avg_confidence": round(avg_confidence * 100, 1) if avg_confidence else 0,
        }
    
    async def _get_cost_stats(
        self,
        organization_id: UUID,
        cutoff: datetime,
        period_leaflet_count: int = 1,
    ) -> Dict[str, Any]:
        """Get cost statistics."""
        # Get leaflet IDs for this organization to filter costs
        org_leaflets = select(Leaflet.id).where(Leaflet.organization_id == organization_id)

        # Total cost (filter via leaflet_id)
        total_query = select(func.sum(CostTracking.total_cost)).where(
            CostTracking.leaflet_id.in_(org_leaflets)
        )
        total_result = await self.db.execute(total_query)
        total_cost = total_result.scalar() or 0

        # Period leaflets
        period_org_leaflets = select(Leaflet.id).where(
            and_(
                Leaflet.organization_id == organization_id,
                Leaflet.created_at >= cutoff,
            )
        )

        # Period cost
        period_query = select(func.sum(CostTracking.total_cost)).where(
            and_(
                CostTracking.leaflet_id.in_(period_org_leaflets),
                CostTracking.processed_at >= cutoff,
            )
        )
        period_result = await self.db.execute(period_query)
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
        tokens_result = await self.db.execute(tokens_query)
        input_tokens, output_tokens = tokens_result.one()

        # Cost by provider
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
        provider_result = await self.db.execute(provider_query)
        cost_by_provider = dict(provider_result.all())
        
        return {
            "total_cost": round(total_cost, 4),
            "period_cost": round(period_cost, 4),
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "total_tokens": (input_tokens or 0) + (output_tokens or 0),
            "by_provider": cost_by_provider,
            "avg_cost_per_leaflet": round(
                period_cost / max(period_leaflet_count, 1),
                4
            ),
        }
    
    async def _get_quality_stats(
        self,
        organization_id: UUID,
        cutoff: datetime,
    ) -> Dict[str, Any]:
        """Get quality statistics.

        Uses Product.organization_id (denormalized column) for filtering
        to match the same query pattern as GET /api/v1/products/stats.
        """
        # Validation pass rate and auto-approval rate in a single query
        quality_query = select(
            func.count(case((Product.validation_passed == True, 1))),  # noqa: E712
            func.count(case((Product.review_status == ReviewStatus.AUTO_APPROVED, 1))),
            func.count(Product.id),
        ).where(
            and_(
                Product.organization_id == organization_id,
                Product.created_at >= cutoff,
            )
        )

        quality_result = await self.db.execute(quality_query)
        passed, auto_approved, total = quality_result.one()

        validation_rate = (passed / max(total, 1)) * 100
        auto_rate = (auto_approved / max(total, 1)) * 100

        # Extraction success rate (completed leaflets / attempted)
        success_query = select(
            func.count(case((Leaflet.status == LeafletStatus.COMPLETED, 1))),
            func.count(Leaflet.id),
        ).where(
            and_(
                Leaflet.organization_id == organization_id,
                Leaflet.created_at >= cutoff,
                Leaflet.status.in_([
                    LeafletStatus.COMPLETED,
                    LeafletStatus.FAILED,
                    LeafletStatus.REVIEWING,
                ])
            )
        )

        success_result = await self.db.execute(success_query)
        completed, attempted = success_result.one()

        success_rate = (completed / max(attempted, 1)) * 100

        return {
            "validation_pass_rate": round(validation_rate, 1),
            "auto_approval_rate": round(auto_rate, 1),
            "extraction_success_rate": round(success_rate, 1),
        }
    
    async def _get_trend_data(
        self,
        organization_id: UUID,
        days: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get trend data for charts."""
        # Daily leaflet counts
        leaflet_trend = []
        product_trend = []
        cost_trend = []
        
        for i in range(days - 1, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            # Leaflets
            leaflet_query = select(func.count(Leaflet.id)).where(
                and_(
                    Leaflet.organization_id == organization_id,
                    Leaflet.created_at >= day_start,
                    Leaflet.created_at <= day_end,
                )
            )
            leaflet_result = await self.db.execute(leaflet_query)
            leaflet_count = leaflet_result.scalar() or 0
            
            leaflet_trend.append({
                "date": day.isoformat(),
                "count": leaflet_count,
            })
            
            # Products — use denormalized organization_id for consistency
            product_query = select(func.count(Product.id)).where(
                and_(
                    Product.organization_id == organization_id,
                    Product.created_at >= day_start,
                    Product.created_at <= day_end,
                )
            )
            product_result = await self.db.execute(product_query)
            product_count = product_result.scalar() or 0

            product_trend.append({
                "date": day.isoformat(),
                "count": product_count,
            })

            # Cost — CostTracking doesn't have organization_id, so filter via leaflet_id
            day_leaflets = select(Leaflet.id).where(
                and_(
                    Leaflet.organization_id == organization_id,
                    Leaflet.created_at >= day_start,
                    Leaflet.created_at <= day_end,
                )
            )
            cost_query = select(func.sum(CostTracking.total_cost)).where(
                and_(
                    CostTracking.leaflet_id.in_(day_leaflets),
                    CostTracking.processed_at >= day_start,
                    CostTracking.processed_at <= day_end,
                )
            )
            cost_result = await self.db.execute(cost_query)
            day_cost = cost_result.scalar() or 0
            
            cost_trend.append({
                "date": day.isoformat(),
                "cost": round(day_cost, 4),
            })
        
        return {
            "leaflets": leaflet_trend,
            "products": product_trend,
            "costs": cost_trend,
        }
    
    async def record_cost(
        self,
        user_id: UUID,
        leaflet_id: UUID,
        vlm_provider_id: Optional[UUID],
        provider_type: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        input_price_per_1m: float,
        output_price_per_1m: float,
        page_count: int = 0,
        product_count: int = 0,
    ) -> CostTracking:
        """
        Record cost for a leaflet processing.

        Args:
            user_id: User ID
            leaflet_id: Leaflet ID
            vlm_provider_id: VLM provider ID (optional)
            provider_type: Provider type string
            model_name: Model name
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            input_price_per_1m: Input price per 1M tokens
            output_price_per_1m: Output price per 1M tokens
            page_count: Number of pages
            product_count: Products extracted

        Returns:
            CostTracking record
        """
        input_cost = (input_tokens / 1_000_000) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * output_price_per_1m
        total_cost = input_cost + output_cost

        cost = CostTracking(
            user_id=user_id,
            leaflet_id=leaflet_id,
            vlm_provider_id=vlm_provider_id,
            provider_type=provider_type,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=round(input_cost, 6),
            output_cost=round(output_cost, 6),
            total_cost=round(total_cost, 6),
            page_count=page_count,
            product_count=product_count,
            input_price_per_1m=input_price_per_1m,
            output_price_per_1m=output_price_per_1m,
        )
        
        self.db.add(cost)
        await self.db.commit()
        
        return cost
    
    async def record_feedback(
        self,
        user_id: UUID,
        product_id: UUID,
        leaflet_id: UUID,
        feedback_type: str,
        field_name: Optional[str] = None,
        original_value: Any = None,
        corrected_value: Any = None,
        original_confidence: Optional[float] = None,
        page_number: Optional[int] = None,
        retailer: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> FeedbackLog:
        """
        Record user feedback/correction.

        Args:
            user_id: User ID
            product_id: Product ID
            leaflet_id: Leaflet ID
            feedback_type: Type of feedback
            field_name: Field corrected
            original_value: Original value
            corrected_value: Corrected value
            original_confidence: Original confidence score
            page_number: Page number
            retailer: Retailer name
            notes: Reviewer notes

        Returns:
            FeedbackLog record
        """
        feedback = FeedbackLog(
            user_id=user_id,
            product_id=product_id,
            leaflet_id=leaflet_id,
            feedback_type=feedback_type,
            field_name=field_name,
            original_value=original_value,
            corrected_value=corrected_value,
            original_confidence=original_confidence,
            page_number=page_number,
            retailer=retailer,
            notes=notes,
        )
        
        self.db.add(feedback)
        await self.db.commit()
        
        return feedback
    
    async def get_error_patterns(
        self,
        user_id: Optional[UUID] = None,
        min_occurrences: int = 3,
        unresolved_only: bool = True,
    ) -> List[ErrorPattern]:
        """
        Get detected error patterns.
        
        Args:
            user_id: Filter by user (None for all)
            min_occurrences: Minimum occurrences
            unresolved_only: Only unresolved patterns
            
        Returns:
            List of error patterns
        """
        query = select(ErrorPattern).where(
            ErrorPattern.occurrence_count >= min_occurrences
        )
        
        if unresolved_only:
            query = query.where(ErrorPattern.is_resolved == False)
        
        query = query.order_by(ErrorPattern.occurrence_count.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def analyze_feedback_patterns(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Analyze feedback to identify patterns.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of identified patterns
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Group feedback by field and type
        pattern_query = (
            select(
                FeedbackLog.field_name,
                FeedbackLog.feedback_type,
                func.count(FeedbackLog.id).label('count'),
            )
            .where(FeedbackLog.created_at >= cutoff)
            .group_by(FeedbackLog.field_name, FeedbackLog.feedback_type)
            .having(func.count(FeedbackLog.id) >= 3)
            .order_by(func.count(FeedbackLog.id).desc())
        )
        
        result = await self.db.execute(pattern_query)
        
        patterns = []
        for field_name, feedback_type, count in result.all():
            patterns.append({
                "field": field_name,
                "type": feedback_type,
                "count": count,
                "priority": "high" if count >= 10 else "medium" if count >= 5 else "low",
            })
        
        return patterns