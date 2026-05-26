"""
VLM Provider Audit Log Model Module.

This module defines models for comprehensive audit logging of all VLM operations,
including extraction requests, failovers, budget events, and compliance tracking.

Example Usage:
    from app.models.vlm_audit_log import VLMProviderAuditLog, AuditEventType, AuditEventStatus

    audit_log = VLMProviderAuditLog(
        event_type=AuditEventType.EXTRACTION,
        event_status=AuditEventStatus.SUCCESS,
        platform_provider_id=provider_id,
        organization_id=org_id,
        user_id=user_id,
        input_tokens=1500,
        output_tokens=800,
        cost=0.075
    )
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, NUMERIC
from sqlalchemy.orm import relationship

from app.models.base import Base


class AuditEventType(str, enum.Enum):
    """
    VLM audit event types.

    Attributes:
        EXTRACTION: Product extraction from leaflet page
        FAILOVER: Provider failover event
        BUDGET_WARNING: Budget threshold warning
        BUDGET_EXHAUSTED: Budget completely exhausted
        RATE_LIMIT_HIT: Rate limit reached
        PROVIDER_ERROR: Provider API error
        KEY_CREATED: Platform provider key created
        KEY_UPDATED: Platform provider key updated
        KEY_DELETED: Platform provider key deleted
        KEY_TESTED: Platform provider key tested
        CONFIG_CHANGED: Provider configuration changed
        USAGE_RESET: Usage counters reset (monthly/daily/hourly)
    """
    EXTRACTION = "extraction"
    FAILOVER = "failover"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXHAUSTED = "budget_exhausted"
    RATE_LIMIT_HIT = "rate_limit_hit"
    PROVIDER_ERROR = "provider_error"
    KEY_CREATED = "key_created"
    KEY_UPDATED = "key_updated"
    KEY_DELETED = "key_deleted"
    KEY_TESTED = "key_tested"
    CONFIG_CHANGED = "config_changed"
    USAGE_RESET = "usage_reset"


class AuditEventStatus(str, enum.Enum):
    """
    Audit event status levels.

    Attributes:
        SUCCESS: Operation completed successfully
        FAILURE: Operation failed
        WARNING: Operation completed with warnings
        ERROR: Error occurred during operation
        PARTIAL: Operation partially completed
    """
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    ERROR = "error"
    PARTIAL = "partial"


class ErrorCategory(str, enum.Enum):
    """
    Error categorization for analysis.

    Attributes:
        AUTHENTICATION: API key or authentication errors
        RATE_LIMIT: Rate limiting errors
        BUDGET_LIMIT: Budget/quota exceeded errors
        NETWORK: Network connectivity errors
        TIMEOUT: Request timeout errors
        VALIDATION: Input validation errors
        PROVIDER_ERROR: Provider-side errors
        SYSTEM_ERROR: Internal system errors
    """
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    BUDGET_LIMIT = "budget_limit"
    NETWORK = "network"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    PROVIDER_ERROR = "provider_error"
    SYSTEM_ERROR = "system_error"


class VLMProviderAuditLog(Base):
    """
    Comprehensive audit log for all VLM operations.

    This model provides complete traceability of VLM usage, errors, and
    administrative actions for compliance, debugging, and cost analysis.

    Attributes:
        id: Unique identifier (UUID)

        # Context
        platform_provider_id: Platform provider used
        organization_id: Organization context
        user_id: User who initiated the operation
        leaflet_id: Leaflet being processed (if applicable)

        # Event Details
        event_type: Type of event being logged
        event_status: Success/failure/warning status
        operation_id: Unique ID for tracking related operations

        # API Call Details
        provider_type: Provider type (anthropic, openai, etc.)
        model_name: Model used for the request
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Cost in USD
        latency_ms: Request latency in milliseconds

        # Error Information
        error_type: Categorized error type
        error_message: Detailed error message
        error_code: Provider-specific error code
        retry_count: Number of retry attempts

        # Request Context
        request_ip: Client IP address
        user_agent: Client user agent
        session_id: Session identifier
        api_key_id: API key used (if applicable)

        # Additional Context
        metadata: Structured additional data
        request_payload_hash: Hash of request payload (for integrity)
        response_payload_hash: Hash of response payload

        created_at: Timestamp of the event
    """

    __tablename__ = "vlm_provider_audit_log"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique audit log entry identifier"
    )

    # Context References
    platform_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_vlm_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Platform provider used (null if not applicable)"
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Organization context (null if system-wide)"
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who initiated the operation"
    )

    leaflet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leaflets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Leaflet being processed (if applicable)"
    )

    # Event Classification
    event_type = Column(
        Enum(AuditEventType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        index=True,
        comment="Type of event being logged"
    )

    event_status = Column(
        Enum(AuditEventStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        index=True,
        comment="Success/failure/warning status"
    )

    operation_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Unique ID for tracking related operations"
    )

    # API Call Details
    provider_type = Column(
        String(50),
        nullable=True,
        comment="Provider type (anthropic, openai, google, etc.)"
    )

    model_name = Column(
        String(100),
        nullable=True,
        comment="Model used for the request"
    )

    input_tokens = Column(
        Integer,
        nullable=True,
        comment="Number of input tokens consumed"
    )

    output_tokens = Column(
        Integer,
        nullable=True,
        comment="Number of output tokens generated"
    )

    cost = Column(
        NUMERIC(8, 4),  # Up to $9999.9999
        nullable=True,
        comment="Cost of the operation in USD"
    )

    latency_ms = Column(
        Integer,
        nullable=True,
        comment="Request latency in milliseconds"
    )

    # Error Information
    error_type = Column(
        Enum(ErrorCategory, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
        index=True,
        comment="Categorized error type (null if no error)"
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Detailed error message"
    )

    error_code = Column(
        String(50),
        nullable=True,
        comment="Provider-specific error code"
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts made"
    )

    # Request Context (for compliance and security)
    request_ip = Column(
        INET,
        nullable=True,
        comment="Client IP address"
    )

    user_agent = Column(
        Text,
        nullable=True,
        comment="Client user agent string"
    )

    session_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Session identifier"
    )

    api_key_id = Column(
        String(100),
        nullable=True,
        comment="API key identifier used (if applicable)"
    )

    # Payload Integrity
    request_payload_hash = Column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of request payload for integrity"
    )

    response_payload_hash = Column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of response payload for integrity"
    )

    # Additional Context
    audit_metadata = Column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional structured data and context"
    )

    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        index=True,
        comment="Timestamp when the event occurred"
    )

    # Relationships
    platform_provider = relationship(
        "PlatformVLMProvider",
        doc="Platform provider used for the operation"
    )

    organization = relationship(
        "Organization",
        doc="Organization context for the operation"
    )

    user = relationship(
        "User",
        doc="User who initiated the operation"
    )

    leaflet = relationship(
        "Leaflet",
        doc="Leaflet being processed (if applicable)"
    )

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="check_retry_count_non_negative"),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="check_input_tokens_non_negative"),
        CheckConstraint("output_tokens IS NULL OR output_tokens >= 0", name="check_output_tokens_non_negative"),
        CheckConstraint("cost IS NULL OR cost >= 0", name="check_cost_non_negative"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="check_latency_non_negative"),

        # Performance indexes for common queries
        Index("idx_audit_log_org_created", "organization_id", "created_at"),
        Index("idx_audit_log_user_created", "user_id", "created_at"),
        Index("idx_audit_log_provider_created", "platform_provider_id", "created_at"),
        Index("idx_audit_log_leaflet_created", "leaflet_id", "created_at"),
        Index("idx_audit_log_event_type_created", "event_type", "created_at"),
        Index("idx_audit_log_event_status_created", "event_status", "created_at"),
        Index("idx_audit_log_error_type_created", "error_type", "created_at"),
        Index("idx_audit_log_operation_id", "operation_id"),
        Index("idx_audit_log_session_id", "session_id"),
        Index("idx_audit_log_provider_type", "provider_type", "created_at"),

        # Compliance indexes
        Index("idx_audit_log_request_ip_created", "request_ip", "created_at"),
        Index("idx_audit_log_api_key_created", "api_key_id", "created_at"),

        # Cost analysis indexes
        Index("idx_audit_log_cost_created", "cost", "created_at") # WHERE cost IS NOT NULL
    )

    @property
    def total_tokens(self) -> Optional[int]:
        """Get total tokens (input + output) if both are available."""
        if self.input_tokens is not None and self.output_tokens is not None:
            return self.input_tokens + self.output_tokens
        return None

    @property
    def cost_per_token(self) -> Optional[float]:
        """Get cost per token if both cost and tokens are available."""
        total_tokens = self.total_tokens
        if total_tokens and self.cost and total_tokens > 0:
            return float(self.cost) / total_tokens
        return None

    @property
    def is_error(self) -> bool:
        """Check if this log entry represents an error."""
        return self.event_status in [AuditEventStatus.FAILURE, AuditEventStatus.ERROR]

    @property
    def is_warning(self) -> bool:
        """Check if this log entry represents a warning."""
        return self.event_status in [AuditEventStatus.WARNING, AuditEventStatus.PARTIAL]

    @property
    def is_success(self) -> bool:
        """Check if this log entry represents a successful operation."""
        return self.event_status == AuditEventStatus.SUCCESS

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert audit log to dictionary for API responses.

        Args:
            include_sensitive: Whether to include sensitive data like IP addresses

        Returns:
            dict: Audit log data
        """
        result = {
            "id": str(self.id),
            "event_type": self.event_type.value,
            "event_status": self.event_status.value,
            "operation_id": self.operation_id,
            "provider_type": self.provider_type,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": float(self.cost) if self.cost else None,
            "cost_per_token": self.cost_per_token,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "is_error": self.is_error,
            "is_warning": self.is_warning,
            "is_success": self.is_success,
            "created_at": self.created_at.isoformat(),
            "metadata": self.audit_metadata
        }

        # Add context IDs
        if self.platform_provider_id:
            result["platform_provider_id"] = str(self.platform_provider_id)
        if self.organization_id:
            result["organization_id"] = str(self.organization_id)
        if self.user_id:
            result["user_id"] = str(self.user_id)
        if self.leaflet_id:
            result["leaflet_id"] = str(self.leaflet_id)

        # Include sensitive data only if requested (for compliance exports)
        if include_sensitive:
            result.update({
                "request_ip": str(self.request_ip) if self.request_ip else None,
                "user_agent": self.user_agent,
                "session_id": self.session_id,
                "api_key_id": self.api_key_id,
                "request_payload_hash": self.request_payload_hash,
                "response_payload_hash": self.response_payload_hash
            })

        return result

    def __repr__(self) -> str:
        """String representation of VLMProviderAuditLog."""
        context_parts = []
        if self.organization_id:
            context_parts.append(f"org:{self.organization_id}")
        if self.user_id:
            context_parts.append(f"user:{self.user_id}")
        if self.leaflet_id:
            context_parts.append(f"leaflet:{self.leaflet_id}")

        context = ", ".join(context_parts) if context_parts else "system"

        cost_str = f", cost=${self.cost}" if self.cost else ""

        return (
            f"<VLMProviderAuditLog(id={self.id}, "
            f"type={self.event_type.value}, status={self.event_status.value}, "
            f"provider={self.platform_provider_id}, context=({context})"
            f"{cost_str}, created_at={self.created_at})>"
        )