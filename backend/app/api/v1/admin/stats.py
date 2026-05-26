"""
Admin System Statistics Endpoints.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.models.user import User
from app.models.leaflet import Leaflet, LeafletStatus
from app.models.product import Product

logger = logging.getLogger(__name__)
router = APIRouter()


class SystemStats(BaseModel):
    """System-wide statistics."""
    total_users: int
    active_users: int
    total_leaflets: int
    total_products: int
    total_cost: float
    leaflets_today: int
    leaflets_this_week: int
    leaflets_this_month: int
    avg_products_per_leaflet: float
    processing_success_rate: float


@router.get(
    "",
    response_model=SystemStats,
    summary="Get system statistics",
    description="Get system-wide statistics (admin only).",
)
async def get_system_stats(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> SystemStats:
    """Get system-wide statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # User counts
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users_result.scalar() or 0

    # Leaflet counts
    total_leaflets_result = await db.execute(select(func.count(Leaflet.id)))
    total_leaflets = total_leaflets_result.scalar() or 0

    leaflets_today_result = await db.execute(
        select(func.count(Leaflet.id)).where(Leaflet.created_at >= today_start)
    )
    leaflets_today = leaflets_today_result.scalar() or 0

    leaflets_week_result = await db.execute(
        select(func.count(Leaflet.id)).where(Leaflet.created_at >= week_start)
    )
    leaflets_week = leaflets_week_result.scalar() or 0

    leaflets_month_result = await db.execute(
        select(func.count(Leaflet.id)).where(Leaflet.created_at >= month_start)
    )
    leaflets_month = leaflets_month_result.scalar() or 0

    # Product count
    total_products_result = await db.execute(select(func.count(Product.id)))
    total_products = total_products_result.scalar() or 0

    # Cost
    total_cost_result = await db.execute(
        select(func.sum(Leaflet.processing_cost))
    )
    total_cost = total_cost_result.scalar() or 0.0

    # Success rate
    completed_result = await db.execute(
        select(func.count(Leaflet.id)).where(
            Leaflet.status.in_([LeafletStatus.COMPLETED, LeafletStatus.REVIEWING])
        )
    )
    completed = completed_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(Leaflet.id)).where(Leaflet.status == LeafletStatus.FAILED)
    )
    failed = failed_result.scalar() or 0

    success_rate = (completed / max(completed + failed, 1)) * 100

    # Avg products per leaflet
    avg_products = total_products / max(total_leaflets, 1)

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_leaflets=total_leaflets,
        total_products=total_products,
        total_cost=float(total_cost or 0),
        leaflets_today=leaflets_today,
        leaflets_this_week=leaflets_week,
        leaflets_this_month=leaflets_month,
        avg_products_per_leaflet=round(avg_products, 1),
        processing_success_rate=round(success_rate, 1),
    )
