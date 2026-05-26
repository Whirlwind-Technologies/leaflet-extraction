"""
Webhook Service Module.

This module provides functionality for sending webhook notifications
to external systems when events occur.

All webhook dispatches -- both real events and test sends -- record a
``WebhookDelivery`` row so that delivery history is fully auditable.

Example Usage:
    from app.services.webhook_service import WebhookService

    service = WebhookService(db)
    await service.send_event(
        organization_id=org.id,
        event=WebhookEvent.PROCESSING_COMPLETED,
        payload={"leaflet_id": "LEAF_123"}
    )
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import (
    Webhook,
    WebhookDelivery,
    WebhookEvent,
    MAX_RESPONSE_BODY_LENGTH,
)
from app.utils.url_validation import is_private_url
from app.config import settings

logger = logging.getLogger(__name__)

# Maximum timeout (in seconds) enforced for test sends regardless
# of the webhook's own timeout_seconds value.
TEST_SEND_TIMEOUT_SECONDS = 10


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of *headers* with sensitive values redacted.

    We store request headers in the delivery log for debugging, but
    authorization-style headers should not be persisted in cleartext.

    Args:
        headers: Original header dict.

    Returns:
        New dict with sensitive values replaced by ``"[REDACTED]"``.
    """
    sensitive_keys = frozenset({
        "authorization",
        "x-api-key",
        "x-webhook-signature",
    })
    return {
        k: ("[REDACTED]" if k.lower() in sensitive_keys else v)
        for k, v in headers.items()
    }


class WebhookService:
    """Service for managing and sending webhooks.

    Handles webhook delivery with retries, HMAC signing, request
    context logging, and delivery statistics.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    # ------------------------------------------------------------------
    # Webhook retrieval
    # ------------------------------------------------------------------

    async def get_user_webhooks(
        self,
        organization_id: UUID,
        event: Optional[WebhookEvent] = None,
        active_only: bool = True,
    ) -> List[Webhook]:
        """Get webhooks for an organization.

        Args:
            organization_id: Organization ID.
            event: Filter by event type.
            active_only: Only return active webhooks.

        Returns:
            List of matching Webhook instances.
        """
        query = select(Webhook).where(
            Webhook.organization_id == organization_id,
            Webhook.deleted_at.is_(None),
        )

        if active_only:
            query = query.where(Webhook.is_active == True)  # noqa: E712

        result = await self.db.execute(query)
        webhooks = result.scalars().all()

        if event:
            webhooks = [w for w in webhooks if w.is_subscribed(event)]

        return webhooks

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    async def send_event(
        self,
        organization_id: UUID,
        event: WebhookEvent,
        payload: Dict[str, Any],
        wait: bool = False,
    ) -> List[WebhookDelivery]:
        """Send an event to all subscribed webhooks.

        Args:
            organization_id: Organization ID.
            event: Event type.
            payload: Event payload (the ``data`` portion of the envelope).
            wait: If True, await all deliveries before returning.

        Returns:
            List of WebhookDelivery records created.
        """
        webhooks = await self.get_user_webhooks(organization_id, event)

        if not webhooks:
            logger.debug(
                "No webhooks subscribed to %s for organization %s",
                event.value,
                organization_id,
            )
            return []

        deliveries: List[WebhookDelivery] = []
        tasks = []

        for webhook in webhooks:
            delivery = await self._create_delivery(webhook, event, payload)
            deliveries.append(delivery)

            if wait:
                tasks.append(self._send_webhook(webhook, delivery))
            else:
                asyncio.create_task(self._send_webhook(webhook, delivery))

        if wait and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return deliveries

    # ------------------------------------------------------------------
    # Test send (single webhook, single attempt, 10s timeout)
    # ------------------------------------------------------------------

    async def send_test(
        self,
        webhook: Webhook,
        organization_name: str,
    ) -> WebhookDelivery:
        """Send a test payload to a single webhook and record the delivery.

        Unlike ``send_event``, this method:
          - Uses the ``webhook.test`` event type.
          - Enforces a hard 10-second timeout.
          - Does NOT retry on failure.
          - Always records a ``WebhookDelivery`` row.

        Args:
            webhook: The Webhook to test.
            organization_name: Display name of the organization (included
                in the test payload for verification).

        Returns:
            The WebhookDelivery record with result information.
        """
        event_type = "webhook.test"

        # SSRF prevention: validate URL before sending test request
        if not settings.webhook_allow_private_ips and is_private_url(webhook.url):
            raise ValueError(f"Webhook URL targets a private or internal IP address")

        test_data = {
            "message": "This is a test webhook from LeafXtract",
            "webhook_id": str(webhook.id),
            "organization": organization_name,
        }

        # Build the full envelope that gets POSTed.
        payload_envelope = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": test_data,
        }

        payload_json = json.dumps(payload_envelope, default=str)
        signature = webhook.sign_payload(payload_json)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Signature": signature,
            "User-Agent": "LeafXtract-Webhook/1.0",
        }
        if webhook.headers:
            headers.update(webhook.headers)

        # Create delivery record upfront.
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload_envelope,
            request_url=webhook.url,
            request_headers=_redact_headers(headers),
            request_body=payload_envelope,
            status="pending",
            success=False,
        )
        self.db.add(delivery)
        await self.db.commit()
        await self.db.refresh(delivery)

        # Perform the HTTP request with a hard 10s timeout.
        try:
            start_time = time.time()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook.url,
                    content=payload_json,
                    headers=headers,
                    timeout=TEST_SEND_TIMEOUT_SECONDS,
                )

            response_time_ms = int((time.time() - start_time) * 1000)

            if 200 <= response.status_code < 300:
                delivery.mark_success(
                    status_code=response.status_code,
                    response_body=response.text,
                    response_time_ms=response_time_ms,
                )
            else:
                delivery.mark_failed(
                    error=f"HTTP {response.status_code}: {response.text[:500]}",
                    status_code=response.status_code,
                )
                delivery.response_time_ms = response_time_ms
                delivery.response_body = response.text[:MAX_RESPONSE_BODY_LENGTH]

        except httpx.TimeoutException:
            delivery.mark_failed("Request timed out")
            delivery.response_time_ms = TEST_SEND_TIMEOUT_SECONDS * 1000

        except httpx.ConnectError as exc:
            delivery.mark_failed(f"Connection error: {exc}")
            delivery.response_time_ms = int((time.time() - start_time) * 1000)

        except Exception as exc:
            delivery.mark_failed(f"Unexpected error: {exc}")
            delivery.response_time_ms = 0
            logger.exception(
                "Webhook test delivery error",
                extra={"webhook_id": str(webhook.id)},
            )

        await self.db.commit()
        await self.db.refresh(delivery)
        return delivery

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_delivery(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        payload: Dict[str, Any],
    ) -> WebhookDelivery:
        """Create a pending delivery record for a real event.

        The ``request_url``, ``request_headers``, and ``request_body``
        fields are populated once the actual HTTP request is built inside
        ``_send_webhook``.

        Args:
            webhook: Target webhook.
            event: Event type enum value.
            payload: Data payload to include.

        Returns:
            Persisted WebhookDelivery instance.
        """
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event.value,
            payload=payload,
            request_url=webhook.url,
            status="pending",
            success=False,
        )

        self.db.add(delivery)
        await self.db.commit()
        await self.db.refresh(delivery)

        return delivery

    async def _send_webhook(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery,
    ) -> bool:
        """Attempt to deliver a webhook with retries.

        Performs an SSRF check before every dispatch to guard against
        DNS rebinding attacks (attacker registers webhook with a public
        DNS name that later resolves to an internal IP).

        Args:
            webhook: Webhook configuration.
            delivery: Pre-created delivery record.

        Returns:
            True if delivery succeeded on any attempt.
        """
        # SSRF prevention: re-validate URL at dispatch time to guard
        # against DNS rebinding (public DNS changed to private IP
        # after the webhook was created/last validated).
        if not settings.webhook_allow_private_ips and is_private_url(webhook.url):
            error_msg = (
                "Webhook URL resolves to private/internal IP "
                "(blocked for security — possible DNS rebinding)"
            )
            delivery.mark_failed(error_msg)
            webhook.record_failure(error_msg)
            await self.db.commit()
            logger.warning(
                "Blocked webhook dispatch: URL resolves to private IP",
                extra={
                    "webhook_id": str(webhook.id),
                    "webhook_name": webhook.name,
                    "url": webhook.url,
                },
            )
            return False

        # Skip delivery if webhook was soft-deleted while queued.
        if webhook.deleted_at is not None:
            error_msg = "Webhook was deleted before delivery could complete"
            delivery.mark_failed(error_msg)
            await self.db.commit()
            logger.info(
                "Skipped delivery for soft-deleted webhook",
                extra={
                    "webhook_id": str(webhook.id),
                    "webhook_name": webhook.name,
                },
            )
            return False

        # Build the envelope.
        payload_data = {
            "event": delivery.event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "delivery_id": str(delivery.id),
            "data": delivery.payload,
        }

        payload_json = json.dumps(payload_data, default=str)
        signature = webhook.sign_payload(payload_json)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Signature": signature,
            "X-Webhook-Delivery-ID": str(delivery.id),
            "User-Agent": "LeafXtract-Webhook/1.0",
        }
        if webhook.headers:
            headers.update(webhook.headers)

        # Persist request context on the delivery for auditability.
        delivery.request_headers = _redact_headers(headers)
        delivery.request_body = payload_data

        # Attempt delivery with retries.
        max_attempts = webhook.retry_count + 1
        last_error: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            delivery.attempt_number = attempt

            try:
                start_time = time.time()

                response = await self.client.post(
                    webhook.url,
                    content=payload_json,
                    headers=headers,
                    timeout=webhook.timeout_seconds,
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if 200 <= response.status_code < 300:
                    delivery.mark_success(
                        status_code=response.status_code,
                        response_body=response.text,
                        response_time_ms=response_time_ms,
                    )
                    webhook.record_success()

                    await self.db.commit()

                    logger.info(
                        "Webhook delivered: %s -> %s (attempt %d, %dms)",
                        webhook.name,
                        delivery.event_type,
                        attempt,
                        response_time_ms,
                    )
                    return True
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    delivery.response_status_code = response.status_code
                    delivery.response_body = response.text[:MAX_RESPONSE_BODY_LENGTH]

            except httpx.TimeoutException:
                last_error = "Request timed out"
            except httpx.ConnectError as exc:
                last_error = f"Connection error: {exc}"
            except Exception as exc:
                last_error = f"Error: {exc}"
                logger.exception(
                    "Webhook delivery error: %s",
                    webhook.name,
                )

            # If not the last attempt, schedule a retry with linear backoff.
            if attempt < max_attempts:
                delay = webhook.retry_delay_seconds * attempt
                delivery.schedule_retry(delay)
                await self.db.commit()

                logger.warning(
                    "Webhook delivery failed (attempt %d/%d): %s -> %s. "
                    "Retrying in %ds...",
                    attempt,
                    max_attempts,
                    webhook.name,
                    last_error,
                    delay,
                )

                await asyncio.sleep(delay)

        # All attempts exhausted.
        delivery.mark_failed(last_error)
        webhook.record_failure(last_error)

        await self.db.commit()

        logger.error(
            "Webhook delivery failed permanently: %s -> %s: %s",
            webhook.name,
            delivery.event_type,
            last_error,
        )

        return False

    # ------------------------------------------------------------------
    # Retry & statistics
    # ------------------------------------------------------------------

    async def retry_failed_deliveries(
        self,
        max_age_hours: int = 24,
        limit: int = 100,
    ) -> int:
        """Retry recently failed webhook deliveries.

        Args:
            max_age_hours: Only retry deliveries newer than this.
            limit: Maximum deliveries to process in one batch.

        Returns:
            Number of deliveries retried.
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        query = (
            select(WebhookDelivery)
            .join(Webhook)
            .where(
                and_(
                    WebhookDelivery.status == "failed",
                    WebhookDelivery.created_at >= cutoff,
                    Webhook.is_active == True,  # noqa: E712
                    Webhook.deleted_at.is_(None),
                )
            )
            .limit(limit)
        )

        result = await self.db.execute(query)
        deliveries = result.scalars().all()

        count = 0
        for delivery in deliveries:
            webhook_result = await self.db.execute(
                select(Webhook).where(Webhook.id == delivery.webhook_id)
            )
            webhook = webhook_result.scalar_one_or_none()

            if webhook and delivery.attempt_number < webhook.retry_count + 1:
                await self._send_webhook(webhook, delivery)
                count += 1

        return count

    async def get_delivery_stats(
        self,
        organization_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get webhook delivery statistics for an organization.

        Args:
            organization_id: Organization UUID.
            days: Look-back window in days.

        Returns:
            Statistics dictionary with counts and success rate.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        webhooks_result = await self.db.execute(
            select(Webhook).where(
                Webhook.organization_id == organization_id,
                Webhook.deleted_at.is_(None),
            )
        )
        webhooks = webhooks_result.scalars().all()
        webhook_ids = [w.id for w in webhooks]

        if not webhook_ids:
            return {
                "total_webhooks": 0,
                "active_webhooks": 0,
                "deliveries": {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "pending": 0,
                },
                "success_rate": 0.0,
            }

        deliveries_result = await self.db.execute(
            select(
                WebhookDelivery.status,
                func.count(WebhookDelivery.id),
            )
            .where(
                and_(
                    WebhookDelivery.webhook_id.in_(webhook_ids),
                    WebhookDelivery.created_at >= cutoff,
                )
            )
            .group_by(WebhookDelivery.status)
        )

        status_counts = dict(deliveries_result.all())
        total = sum(status_counts.values())

        return {
            "total_webhooks": len(webhooks),
            "active_webhooks": sum(1 for w in webhooks if w.is_active),
            "period_days": days,
            "deliveries": {
                "total": total,
                "successful": status_counts.get("success", 0),
                "failed": status_counts.get("failed", 0),
                "pending": status_counts.get("pending", 0),
            },
            "success_rate": (
                (status_counts.get("success", 0) / max(total, 1)) * 100
            ),
        }


# ---------------------------------------------------------------------------
# Convenience functions for dispatching common events
# ---------------------------------------------------------------------------

async def send_processing_completed(
    db: AsyncSession,
    organization_id: UUID,
    leaflet_id: str,
    leaflet_data: Dict[str, Any],
) -> None:
    """Send processing-completed webhook to all subscribed endpoints."""
    service = WebhookService(db)
    try:
        await service.send_event(
            organization_id=organization_id,
            event=WebhookEvent.PROCESSING_COMPLETED,
            payload={
                "leaflet_id": leaflet_id,
                "status": "completed",
                **leaflet_data,
            },
        )
    finally:
        await service.close()


async def send_processing_failed(
    db: AsyncSession,
    organization_id: UUID,
    leaflet_id: str,
    error: str,
) -> None:
    """Send processing-failed webhook to all subscribed endpoints."""
    service = WebhookService(db)
    try:
        await service.send_event(
            organization_id=organization_id,
            event=WebhookEvent.PROCESSING_FAILED,
            payload={
                "leaflet_id": leaflet_id,
                "status": "failed",
                "error": error,
            },
        )
    finally:
        await service.close()


async def send_review_required(
    db: AsyncSession,
    organization_id: UUID,
    leaflet_id: str,
    review_count: int,
) -> None:
    """Send review-required webhook to all subscribed endpoints."""
    service = WebhookService(db)
    try:
        await service.send_event(
            organization_id=organization_id,
            event=WebhookEvent.REVIEW_REQUIRED,
            payload={
                "leaflet_id": leaflet_id,
                "products_requiring_review": review_count,
            },
        )
    finally:
        await service.close()
