"""
Webhook Model Module.

This module defines the Webhook model for notifying external systems
when processing events occur (completed, failed, etc.).

Example Usage:
    from app.models.webhook import Webhook, WebhookEvent
    
    webhook = Webhook(
        user_id=user.id,
        name="My Integration",
        url="https://leafxtract.com/webhook",
        events=[WebhookEvent.PROCESSING_COMPLETED]
    )
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
import uuid
import secrets
import hashlib
import hmac

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin

logger = logging.getLogger(__name__)

# Maximum size for stored response bodies (10 KB).
MAX_RESPONSE_BODY_LENGTH = 10_240


class WebhookEvent(str, Enum):
    """
    Webhook event types.
    
    Attributes:
        LEAFLET_UPLOADED: Leaflet uploaded
        PROCESSING_STARTED: Processing started
        PROCESSING_COMPLETED: Processing completed successfully
        PROCESSING_FAILED: Processing failed
        REVIEW_REQUIRED: Products require review
        REVIEW_COMPLETED: Review completed
        EXPORT_READY: Export is ready
        PRODUCT_UPDATED: Product was updated
    """
    LEAFLET_UPLOADED = "leaflet.uploaded"
    PROCESSING_STARTED = "leaflet.processing.started"
    PROCESSING_COMPLETED = "leaflet.processing.completed"
    PROCESSING_FAILED = "leaflet.processing.failed"
    REVIEW_REQUIRED = "leaflet.review.required"
    REVIEW_COMPLETED = "leaflet.review.completed"
    EXPORT_READY = "leaflet.export.ready"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_APPROVED = "product.approved"
    PRODUCT_REJECTED = "product.rejected"


class Webhook(BaseModel, TimestampMixin):
    """
    Webhook configuration for external notifications.
    
    Attributes:
        id: Unique identifier (UUID)
        user_id: Owner user ID
        name: User-friendly name
        url: Webhook endpoint URL
        secret: Secret for signing payloads
        events: List of subscribed events
        is_active: Whether webhook is active
        retry_count: Number of retry attempts
        last_triggered_at: Last trigger timestamp
        failure_count: Consecutive failure count
    """
    
    __tablename__ = "webhooks"
    
    # Owner
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID"
    )

    # Organization ownership
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this webhook belongs to"
    )

    # Configuration
    name = Column(
        String(100),
        nullable=False,
        comment="User-friendly name"
    )
    
    url = Column(
        String(500),
        nullable=False,
        comment="Webhook endpoint URL"
    )
    
    secret = Column(
        String(500),
        nullable=False,
        comment="Fernet-encrypted secret for HMAC signing"
    )
    
    # Events
    events = Column(
        ARRAY(String),
        nullable=False,
        default=[WebhookEvent.PROCESSING_COMPLETED.value],
        comment="Subscribed event types"
    )
    
    # Headers (optional custom headers)
    headers = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Custom HTTP headers"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether webhook is active"
    )
    
    # Retry configuration
    retry_count = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Number of retry attempts"
    )
    
    retry_delay_seconds = Column(
        Integer,
        nullable=False,
        default=60,
        comment="Delay between retries in seconds"
    )
    
    timeout_seconds = Column(
        Integer,
        nullable=False,
        default=30,
        comment="Request timeout in seconds"
    )
    
    # Usage tracking
    last_triggered_at = Column(
        DateTime,
        nullable=True,
        comment="Last successful trigger"
    )
    
    last_error = Column(
        Text,
        nullable=True,
        comment="Last error message"
    )
    
    last_error_at = Column(
        DateTime,
        nullable=True,
        comment="Last error timestamp"
    )
    
    # Failure handling
    failure_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Consecutive failure count"
    )
    
    max_failures = Column(
        Integer,
        nullable=False,
        default=10,
        comment="Max failures before auto-disable"
    )
    
    # Statistics
    total_deliveries = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total successful deliveries"
    )
    
    total_failures = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total failed deliveries"
    )
    
    # Metadata
    description = Column(
        Text,
        nullable=True,
        comment="Optional description"
    )

    metadata_ = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional metadata",
        name="metadata_"
    )

    # Soft delete support — set instead of hard deleting so that
    # in-flight deliveries are not orphaned.
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="Soft-delete timestamp (NULL = active, set = deleted)",
    )

    # Relationships
    user = relationship("User", back_populates="webhooks")
    deliveries = relationship(
        "WebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan"
    )
    
    @classmethod
    def generate_secret(cls) -> str:
        """Generate a new webhook secret.

        Returns:
            A 64-character hex string suitable for HMAC-SHA256 signing.
        """
        return secrets.token_hex(32)

    def set_secret(self, raw_secret: str) -> None:
        """Encrypt and store a webhook signing secret.

        Uses Fernet encryption (same scheme as VLM API keys) so the
        secret is never stored in plain text in the database.

        Args:
            raw_secret: The plain-text secret to encrypt and store.
        """
        from app.utils.security import encrypt_api_key

        self.secret = encrypt_api_key(raw_secret)

    def get_secret(self) -> str:
        """Decrypt and return the webhook signing secret.

        Handles backward compatibility: if the stored value is not a
        valid Fernet token (i.e. it was stored before encryption was
        introduced), the raw value is returned as-is.

        Returns:
            The plain-text signing secret.
        """
        from app.utils.security import decrypt_api_key

        try:
            return decrypt_api_key(self.secret)
        except (ValueError, Exception):
            # Legacy plain-text secret — return as-is for backward
            # compatibility during the transition period.
            logger.debug(
                "Webhook secret appears to be plain text (legacy); "
                "returning as-is for webhook %s",
                self.id,
            )
            return self.secret

    def sign_payload(self, payload: str) -> str:
        """Sign a payload with HMAC-SHA256.

        The signing secret is decrypted from the database before use.

        Args:
            payload: JSON payload string.

        Returns:
            Hex-encoded signature prefixed with ``sha256=``.
        """
        raw_secret = self.get_secret()
        signature = hmac.new(
            raw_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"
    
    def is_subscribed(self, event: WebhookEvent) -> bool:
        """Check if webhook is subscribed to an event."""
        return event.value in self.events or "*" in self.events
    
    def record_success(self):
        """Record successful delivery."""
        self.last_triggered_at = datetime.utcnow()
        self.failure_count = 0
        self.total_deliveries += 1
        self.last_error = None
        self.last_error_at = None
    
    def record_failure(self, error: str):
        """Record failed delivery."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_error = error
        self.last_error_at = datetime.utcnow()
        
        # Auto-disable if too many failures
        if self.failure_count >= self.max_failures:
            self.is_active = False
    
    def reset_failures(self):
        """Reset failure count."""
        self.failure_count = 0
        self.last_error = None
        self.last_error_at = None


class WebhookDelivery(BaseModel, TimestampMixin):
    """
    Webhook delivery attempt record.

    Tracks each attempt to deliver a webhook payload, including the
    full request context (URL, headers, body) and the response received.

    Attributes:
        webhook_id: Foreign key to the parent Webhook.
        event_type: Event that triggered this delivery (e.g., "webhook.test").
        payload: The JSON payload sent in the request body.
        request_url: The URL the request was sent to.
        request_headers: HTTP headers included in the request (sanitized).
        request_body: The serialized JSON body sent.
        status: Delivery status: "pending", "success", or "failed".
        success: Boolean shorthand for status == "success".
        response_status_code: HTTP status code from the target server.
        response_body: Truncated response body (max 10 KB).
        response_time_ms: Round-trip time in milliseconds.
        error_message: Error description if delivery failed.
        attempt_number: Which attempt this record represents (1-based).
        next_retry_at: When the next retry should occur (if scheduled).
        delivered_at: Timestamp of successful delivery.
    """

    __tablename__ = "webhook_deliveries"

    # Webhook reference
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Webhook ID",
    )

    # Event info
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Event type",
    )

    # Payload
    payload = Column(
        JSONB,
        nullable=False,
        comment="Webhook payload",
    )

    # Request context -- captures what was actually sent so delivery
    # logs are self-contained and debuggable.
    request_url = Column(
        String(500),
        nullable=True,
        comment="Target URL the request was sent to",
    )

    request_headers = Column(
        JSONB,
        nullable=True,
        comment="HTTP headers sent with the request (secrets redacted)",
    )

    request_body = Column(
        JSONB,
        nullable=True,
        comment="Serialized JSON body that was POSTed",
    )

    # Delivery status
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Delivery status: pending, success, failed",
    )

    success = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether delivery succeeded (2xx response)",
    )

    # Response info
    response_status_code = Column(
        Integer,
        nullable=True,
        comment="HTTP response status code",
    )

    response_body = Column(
        String(MAX_RESPONSE_BODY_LENGTH),
        nullable=True,
        comment="Response body (truncated to 10 KB max)",
    )

    response_time_ms = Column(
        Integer,
        nullable=True,
        comment="Response time in milliseconds",
    )

    # Error info
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if failed",
    )

    # Retry tracking
    attempt_number = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Attempt number",
    )

    next_retry_at = Column(
        DateTime,
        nullable=True,
        comment="Next retry timestamp",
    )

    # Timestamps
    delivered_at = Column(
        DateTime,
        nullable=True,
        comment="Successful delivery timestamp",
    )

    # Relationships
    webhook = relationship("Webhook", back_populates="deliveries")

    def mark_success(
        self,
        status_code: int,
        response_body: str,
        response_time_ms: int,
    ) -> None:
        """Mark delivery as successful.

        Args:
            status_code: HTTP status code from target server.
            response_body: Raw response body text.
            response_time_ms: Round-trip latency in milliseconds.
        """
        self.status = "success"
        self.success = True
        self.response_status_code = status_code
        self.response_body = (
            response_body[:MAX_RESPONSE_BODY_LENGTH] if response_body else None
        )
        self.response_time_ms = response_time_ms
        self.delivered_at = datetime.utcnow()

    def mark_failed(self, error: str, status_code: Optional[int] = None) -> None:
        """Mark delivery as failed.

        Args:
            error: Human-readable error description.
            status_code: HTTP status code if one was received.
        """
        self.status = "failed"
        self.success = False
        self.error_message = error
        if status_code:
            self.response_status_code = status_code

    def schedule_retry(self, delay_seconds: int) -> None:
        """Schedule a retry after the given delay.

        Args:
            delay_seconds: Seconds to wait before retrying.
        """
        self.attempt_number += 1
        self.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self.status = "pending"
        self.success = False