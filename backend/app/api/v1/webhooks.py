"""
Webhooks Management Endpoints.

This module provides endpoints for managing webhooks for
receiving notifications about processing events, including
SSRF-safe webhook testing and paginated delivery logs.

Example Usage:
    POST /api/v1/webhooks - Create webhook
    GET /api/v1/webhooks - List webhooks
    POST /api/v1/webhooks/{id}/test - Send a test event
    GET /api/v1/webhooks/{id}/deliveries - View delivery history
    DELETE /api/v1/webhooks/{id} - Delete webhook
"""

import logging
import math
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_organization, get_db
from app.models.webhook import Webhook, WebhookDelivery, WebhookEvent
from app.models.user import User
from app.models.organization import Organization
from app.services.webhook_service import WebhookService
from app.utils.exceptions import NotFoundError, ValidationException
from app.utils.url_validation import validate_webhook_url

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=10)
    events: List[str] = Field(default=[WebhookEvent.PROCESSING_COMPLETED.value])
    description: Optional[str] = None
    headers: Optional[dict] = None
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=120)


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=10)
    events: Optional[List[str]] = None
    description: Optional[str] = None
    headers: Optional[dict] = None
    is_active: Optional[bool] = None
    retry_count: Optional[int] = Field(None, ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=120)


class WebhookResponse(BaseModel):
    """Schema for webhook response."""

    id: UUID
    name: str
    url: str
    events: List[str]
    description: Optional[str]
    is_active: bool
    retry_count: int
    timeout_seconds: int
    failure_count: int
    total_deliveries: int
    total_failures: int
    last_triggered_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookCreateResponse(BaseModel):
    """Schema for webhook creation response.

    Wraps the webhook data with the signing secret, which is only
    returned once at creation time.
    """

    webhook: WebhookResponse
    secret: str


class WebhookDeliveryResponse(BaseModel):
    """Schema for a single webhook delivery log entry."""

    id: UUID
    event_type: str
    status_code: Optional[int] = None
    success: bool
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookDeliveryListResponse(BaseModel):
    """Paginated delivery list response."""

    deliveries: List[WebhookDeliveryResponse]
    total: int
    page: int
    pages: int


class WebhookTestResponse(BaseModel):
    """Schema for webhook test response."""

    success: bool
    status_code: Optional[int] = None
    response_time_ms: int
    error: Optional[str] = None


class WebhookStats(BaseModel):
    """Webhook statistics."""

    total_webhooks: int
    active_webhooks: int
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    success_rate: float


# ---------------------------------------------------------------------------
# Helper: build WebhookResponse from ORM model
# ---------------------------------------------------------------------------

def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert a Webhook ORM object into a WebhookResponse schema."""
    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        events=webhook.events,
        description=webhook.description,
        is_active=webhook.is_active,
        retry_count=webhook.retry_count,
        timeout_seconds=webhook.timeout_seconds,
        failure_count=webhook.failure_count,
        total_deliveries=webhook.total_deliveries,
        total_failures=webhook.total_failures,
        last_triggered_at=webhook.last_triggered_at,
        last_error=webhook.last_error,
        created_at=webhook.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=WebhookCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description=(
        "Create a new webhook for receiving notifications. "
        "The signing secret is returned only once at creation time."
    ),
)
async def create_webhook(
    webhook_data: WebhookCreate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreateResponse:
    """Create a new webhook.

    Args:
        webhook_data: Webhook configuration from request body.
        current_user: Authenticated user from JWT token.
        current_org: Current organization from dependency injection.
        db: Async database session.

    Returns:
        WebhookCreateResponse with the webhook data and signing secret.

    Raises:
        ValidationException: If events are invalid, webhook limit reached,
            or URL points to a private/internal IP.
    """
    # SSRF prevention: block private/internal IPs.
    validate_webhook_url(webhook_data.url)

    # Validate events.
    valid_events = {e.value for e in WebhookEvent}
    for event in webhook_data.events:
        if event not in valid_events and event != "*":
            raise ValidationException(
                errors=[{"field": "events", "message": f"Invalid event: {event}"}],
                message=f"Invalid event: {event}",
            )

    # Check webhook limit per organization (max 10, excluding soft-deleted).
    existing_count = await db.execute(
        select(func.count(Webhook.id)).where(
            Webhook.organization_id == current_org.id,
            Webhook.deleted_at.is_(None),
        )
    )
    if existing_count.scalar_one() >= 10:
        raise ValidationException(
            errors=[{
                "field": "webhooks",
                "message": "Maximum number of webhooks (10) reached",
            }],
            message="Maximum number of webhooks (10) reached for this organization",
        )

    # Generate signing secret and encrypt for storage.
    raw_secret = Webhook.generate_secret()

    webhook = Webhook(
        user_id=current_user.id,
        organization_id=current_org.id,
        name=webhook_data.name,
        url=webhook_data.url,
        secret="",  # Placeholder; set_secret encrypts below
        events=webhook_data.events,
        description=webhook_data.description,
        headers=webhook_data.headers or {},
        retry_count=webhook_data.retry_count,
        timeout_seconds=webhook_data.timeout_seconds,
    )
    webhook.set_secret(raw_secret)

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(
        "Webhook created",
        extra={"user": current_user.email, "webhook_name": webhook.name},
    )

    return WebhookCreateResponse(
        webhook=_webhook_to_response(webhook),
        secret=raw_secret,
    )


@router.get(
    "/",
    response_model=List[WebhookResponse],
    summary="List webhooks",
    description="List all webhooks for the current organization.",
)
async def list_webhooks(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[WebhookResponse]:
    """List all webhooks for the current organization.

    Soft-deleted webhooks are always excluded.
    """
    query = select(Webhook).where(
        Webhook.organization_id == current_org.id,
        Webhook.deleted_at.is_(None),
    )

    if not include_inactive:
        query = query.where(Webhook.is_active == True)  # noqa: E712

    query = query.order_by(Webhook.created_at.desc())

    result = await db.execute(query)
    webhooks = result.scalars().all()

    return [_webhook_to_response(w) for w in webhooks]


@router.get(
    "/events",
    summary="List available events",
    description="Get a list of all available webhook events.",
)
async def list_webhook_events() -> List[dict]:
    """List available webhook events."""
    return [
        {
            "event": event.value,
            "description": _get_event_description(event),
        }
        for event in WebhookEvent
    ]


def _get_event_description(event: WebhookEvent) -> str:
    """Get description for webhook event."""
    descriptions = {
        WebhookEvent.LEAFLET_UPLOADED: "Triggered when a leaflet is uploaded",
        WebhookEvent.PROCESSING_STARTED: "Triggered when processing begins",
        WebhookEvent.PROCESSING_COMPLETED: "Triggered when processing completes successfully",
        WebhookEvent.PROCESSING_FAILED: "Triggered when processing fails",
        WebhookEvent.REVIEW_REQUIRED: "Triggered when products require review",
        WebhookEvent.REVIEW_COMPLETED: "Triggered when all reviews are completed",
        WebhookEvent.EXPORT_READY: "Triggered when an export is ready",
        WebhookEvent.PRODUCT_UPDATED: "Triggered when a product is updated",
        WebhookEvent.PRODUCT_APPROVED: "Triggered when a product is approved",
        WebhookEvent.PRODUCT_REJECTED: "Triggered when a product is rejected",
    }
    return descriptions.get(event, "")


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
    description="Get details for a specific webhook.",
)
async def get_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Get webhook details."""
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)
    return _webhook_to_response(webhook)


@router.get(
    "/{webhook_id}/secret",
    summary="Get webhook secret",
    description="Get the signing secret for a webhook.",
)
async def get_webhook_secret(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get webhook secret."""
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)

    return {
        "secret": webhook.get_secret(),
        "header_name": "X-Webhook-Signature",
        "algorithm": "HMAC-SHA256",
    }


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook (PATCH)",
    description="Update webhook settings. Accepts partial updates.",
)
@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook (PUT)",
    description="Update webhook settings. Accepts partial updates.",
)
async def update_webhook(
    webhook_id: UUID,
    webhook_data: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Update webhook settings.

    Raises:
        ValidationException: If URL points to a private/internal IP
            or events are invalid.
    """
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)

    # SSRF prevention on URL change.
    if webhook_data.url is not None:
        validate_webhook_url(webhook_data.url)
        webhook.url = webhook_data.url

    if webhook_data.name is not None:
        webhook.name = webhook_data.name
    if webhook_data.events is not None:
        valid_events = {e.value for e in WebhookEvent}
        for event in webhook_data.events:
            if event not in valid_events and event != "*":
                raise ValidationException(
                    errors=[{"field": "events", "message": f"Invalid event: {event}"}],
                    message=f"Invalid event: {event}",
                )
        webhook.events = webhook_data.events
    if webhook_data.description is not None:
        webhook.description = webhook_data.description
    if webhook_data.headers is not None:
        webhook.headers = webhook_data.headers
    if webhook_data.is_active is not None:
        webhook.is_active = webhook_data.is_active
        if webhook_data.is_active:
            webhook.reset_failures()
    if webhook_data.retry_count is not None:
        webhook.retry_count = webhook_data.retry_count
    if webhook_data.timeout_seconds is not None:
        webhook.timeout_seconds = webhook_data.timeout_seconds

    await db.commit()
    await db.refresh(webhook)

    logger.info(
        "Webhook updated",
        extra={"user": current_user.email, "webhook_name": webhook.name},
    )

    return _webhook_to_response(webhook)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description="Delete a webhook.",
)
async def delete_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a webhook.

    Sets ``deleted_at`` and deactivates the webhook so that in-flight
    deliveries are not orphaned.  A periodic cleanup task can hard-delete
    webhooks whose ``deleted_at`` is older than 30 days.
    """
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)

    name = webhook.name
    webhook.deleted_at = datetime.utcnow()
    webhook.is_active = False
    await db.commit()

    logger.info(
        "Webhook soft-deleted",
        extra={"user": current_user.email, "webhook_name": name},
    )


# ---------------------------------------------------------------------------
# Test endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description=(
        "Send a test event to the webhook URL and return the result. "
        "A WebhookDelivery record is created for the test send. "
        "Enforces a 10-second timeout."
    ),
)
async def test_webhook(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResponse:
    """Send a test event to the webhook.

    The test payload follows the standard envelope format:
    ```json
    {
      "event": "webhook.test",
      "timestamp": "2026-02-07T12:00:00Z",
      "data": {
        "message": "This is a test webhook from LeafXtract",
        "webhook_id": "<uuid>",
        "organization": "<org name>"
      }
    }
    ```

    The delivery is recorded in the webhook_deliveries table so it
    appears in the delivery log.

    Args:
        webhook_id: UUID of the webhook to test.
        current_user: Authenticated user.
        current_org: Current organization.
        db: Async database session.

    Returns:
        WebhookTestResponse with success flag, status code, latency,
        and error (if any).

    Raises:
        NotFoundError: If webhook does not exist in this organization.
        ValidationException: If URL points to a private/internal IP.
    """
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)

    # SSRF prevention: re-check the URL at test time in case DNS changed.
    validate_webhook_url(webhook.url)

    service = WebhookService(db)
    try:
        delivery = await service.send_test(
            webhook=webhook,
            organization_name=current_org.name,
        )
    finally:
        await service.close()

    return WebhookTestResponse(
        success=delivery.success,
        status_code=delivery.response_status_code,
        response_time_ms=delivery.response_time_ms or 0,
        error=delivery.error_message,
    )


# ---------------------------------------------------------------------------
# Delivery log endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="Get webhook deliveries",
    description="Get paginated delivery history for a webhook.",
)
async def get_webhook_deliveries(
    webhook_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, alias="page_size", description="Items per page"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        pattern="^(pending|success|failed)$",
        description="Filter by delivery status",
    ),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryListResponse:
    """Get paginated delivery history for a webhook.

    Args:
        webhook_id: UUID of the webhook.
        page: 1-based page number.
        limit: Number of records per page (max 100).
        status_filter: Optional filter by "pending", "success", or "failed".
        current_user: Authenticated user.
        current_org: Current organization.
        db: Async database session.

    Returns:
        WebhookDeliveryListResponse with deliveries list and pagination metadata.

    Raises:
        NotFoundError: If webhook does not exist in this organization.
    """
    # Verify webhook ownership.
    await _get_org_webhook(db, webhook_id, current_org.id)

    # Base filters.
    filters = [WebhookDelivery.webhook_id == webhook_id]
    if status_filter:
        filters.append(WebhookDelivery.status == status_filter)

    # Count total matching rows for pagination.
    count_result = await db.execute(
        select(func.count(WebhookDelivery.id)).where(*filters)
    )
    total = count_result.scalar_one()
    pages = max(1, math.ceil(total / limit))

    # Fetch the requested page.
    query = (
        select(WebhookDelivery)
        .where(*filters)
        .order_by(WebhookDelivery.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )

    result = await db.execute(query)
    deliveries = result.scalars().all()

    return WebhookDeliveryListResponse(
        deliveries=[
            WebhookDeliveryResponse(
                id=d.id,
                event_type=d.event_type,
                status_code=d.response_status_code,
                success=d.success if d.success is not None else (d.status == "success"),
                response_time_ms=d.response_time_ms,
                error_message=d.error_message,
                created_at=d.created_at,
            )
            for d in deliveries
        ],
        total=total,
        page=page,
        pages=pages,
    )


# ---------------------------------------------------------------------------
# Regenerate secret
# ---------------------------------------------------------------------------

@router.post(
    "/{webhook_id}/regenerate-secret",
    summary="Regenerate webhook secret",
    description="Generate a new signing secret for a webhook.",
)
async def regenerate_webhook_secret(
    webhook_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Regenerate webhook signing secret."""
    webhook = await _get_org_webhook(db, webhook_id, current_org.id)

    raw_secret = Webhook.generate_secret()
    webhook.set_secret(raw_secret)
    await db.commit()

    logger.info(
        "Webhook secret regenerated",
        extra={"user": current_user.email, "webhook_name": webhook.name},
    )

    return {
        "secret": raw_secret,
        "message": "Secret regenerated successfully. Update your webhook receiver.",
    }


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/stats/summary",
    response_model=WebhookStats,
    summary="Get webhook statistics",
    description="Get summary statistics for all webhooks.",
)
async def get_webhook_stats(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> WebhookStats:
    """Get webhook statistics."""
    service = WebhookService(db)
    stats = await service.get_delivery_stats(current_org.id)

    return WebhookStats(
        total_webhooks=stats["total_webhooks"],
        active_webhooks=stats["active_webhooks"],
        total_deliveries=stats["deliveries"]["total"],
        successful_deliveries=stats["deliveries"]["successful"],
        failed_deliveries=stats["deliveries"]["failed"],
        success_rate=stats["success_rate"],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_org_webhook(
    db: AsyncSession,
    webhook_id: UUID,
    organization_id: UUID,
) -> Webhook:
    """Fetch a non-deleted webhook ensuring it belongs to the given organization.

    Soft-deleted webhooks (``deleted_at IS NOT NULL``) are excluded and
    treated as if they do not exist.

    Args:
        db: Async database session.
        webhook_id: UUID of the webhook.
        organization_id: UUID of the expected organization.

    Returns:
        The Webhook ORM instance.

    Raises:
        NotFoundError: If webhook does not exist, is soft-deleted, or
            belongs to a different organization.
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.organization_id == organization_id,
            Webhook.deleted_at.is_(None),
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise NotFoundError("Webhook", str(webhook_id))

    return webhook
