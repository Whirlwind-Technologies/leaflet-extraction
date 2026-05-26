"""
System Health API endpoints for admin dashboard.

Provides detailed health information about all system components including
database, Redis, storage (S3), and Celery workers.
"""

from datetime import datetime, timezone
from typing import Optional
import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_superuser
from app.models.user import User


router = APIRouter()


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str
    latency_ms: Optional[float] = None
    details: Optional[dict] = None


class SystemHealthResponse(BaseModel):
    """Complete system health response."""
    overall_status: str
    timestamp: str
    components: list[ComponentHealth]
    environment: str
    version: str


async def check_database_health() -> ComponentHealth:
    """Check database connectivity and response time."""
    import time
    from app.utils.database import check_db_health

    start = time.time()
    try:
        is_healthy = await check_db_health()
        latency = (time.time() - start) * 1000

        if is_healthy:
            return ComponentHealth(
                name="PostgreSQL Database",
                status="healthy",
                message="Connected and responsive",
                latency_ms=round(latency, 2),
                details={"connection": "active"}
            )
        else:
            return ComponentHealth(
                name="PostgreSQL Database",
                status="unhealthy",
                message="Database connection failed",
                latency_ms=round(latency, 2)
            )
    except Exception as e:
        return ComponentHealth(
            name="PostgreSQL Database",
            status="unhealthy",
            message=f"Error: {str(e)}"
        )


async def check_redis_health() -> ComponentHealth:
    """Check Redis connectivity and response time."""
    import time
    from app.utils.cache import check_redis_health as redis_check

    start = time.time()
    try:
        is_healthy = await redis_check()
        latency = (time.time() - start) * 1000

        if is_healthy:
            return ComponentHealth(
                name="Redis Cache",
                status="healthy",
                message="Connected and responsive",
                latency_ms=round(latency, 2),
                details={"connection": "active"}
            )
        else:
            return ComponentHealth(
                name="Redis Cache",
                status="unhealthy",
                message="Redis connection failed",
                latency_ms=round(latency, 2)
            )
    except Exception as e:
        return ComponentHealth(
            name="Redis Cache",
            status="unhealthy",
            message=f"Error: {str(e)}"
        )


async def check_storage_health() -> ComponentHealth:
    """Check S3/storage connectivity."""
    import time
    from app.config import settings

    start = time.time()
    try:
        if settings.storage_mode == "s3":
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )

            # Try to head the bucket
            client.head_bucket(Bucket=settings.s3_bucket_name)
            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="AWS S3 Storage",
                status="healthy",
                message=f"Connected to bucket: {settings.s3_bucket_name}",
                latency_ms=round(latency, 2),
                details={
                    "bucket": settings.s3_bucket_name,
                    "region": settings.aws_region
                }
            )
        elif settings.storage_mode == "local":
            from pathlib import Path
            storage_path = Path(settings.local_storage_path)

            if storage_path.exists() and storage_path.is_dir():
                latency = (time.time() - start) * 1000
                return ComponentHealth(
                    name="Local Storage",
                    status="healthy",
                    message=f"Storage path accessible: {settings.local_storage_path}",
                    latency_ms=round(latency, 2),
                    details={"path": settings.local_storage_path}
                )
            else:
                return ComponentHealth(
                    name="Local Storage",
                    status="unhealthy",
                    message=f"Storage path not accessible: {settings.local_storage_path}"
                )
        else:
            return ComponentHealth(
                name="Storage",
                status="degraded",
                message=f"Unknown storage mode: {settings.storage_mode}"
            )
    except Exception as e:
        return ComponentHealth(
            name="Storage",
            status="unhealthy",
            message=f"Error: {str(e)}"
        )


async def check_celery_health() -> ComponentHealth:
    """Check Celery worker status."""
    import time

    start = time.time()
    try:
        from app.workers.celery_app import celery_app

        # Get active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        latency = (time.time() - start) * 1000

        if active_workers:
            worker_count = len(active_workers)
            worker_names = list(active_workers.keys())

            # Count active tasks
            total_active_tasks = sum(len(tasks) for tasks in active_workers.values())

            return ComponentHealth(
                name="Celery Workers",
                status="healthy",
                message=f"{worker_count} worker(s) active",
                latency_ms=round(latency, 2),
                details={
                    "workers": worker_names,
                    "active_tasks": total_active_tasks
                }
            )
        else:
            return ComponentHealth(
                name="Celery Workers",
                status="unhealthy",
                message="No active workers found",
                latency_ms=round(latency, 2)
            )
    except Exception as e:
        return ComponentHealth(
            name="Celery Workers",
            status="unhealthy",
            message=f"Error: {str(e)}"
        )


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_superuser)
) -> SystemHealthResponse:
    """
    Get detailed system health status.

    Checks all system components and returns their health status.
    Only accessible by superusers.
    """
    from app.config import settings

    # Run all health checks in parallel
    results = await asyncio.gather(
        check_database_health(),
        check_redis_health(),
        check_storage_health(),
        check_celery_health(),
        return_exceptions=True
    )

    components = []
    for result in results:
        if isinstance(result, Exception):
            components.append(ComponentHealth(
                name="Unknown",
                status="unhealthy",
                message=f"Check failed: {str(result)}"
            ))
        else:
            components.append(result)

    # Determine overall status
    statuses = [c.status for c in components]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return SystemHealthResponse(
        overall_status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
        environment=settings.environment,
        version=settings.app_version
    )
