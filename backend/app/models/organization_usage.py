"""
Organization VLM Usage Model Module.

This module defines models for tracking platform VLM provider usage
per organization for cost allocation and reporting.

Example Usage:
    from app.models.organization_usage import OrganizationVLMUsage

    usage = OrganizationVLMUsage(
        organization_id=org_id,
        platform_provider_id=provider_id,
        usage_date=date.today(),
        usage_hour=14,
        request_count=25,
        input_tokens=50000,
        output_tokens=12000,
        total_cost=15.75
    )
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Date,
    Integer,
    BigInteger,
    Numeric,
    Float,
    String,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class OrganizationVLMUsage(Base):
    """
    Track platform VLM provider usage per organization.

    This model records usage metrics for platform VLM providers broken down
    by organization, date, and hour. This enables accurate cost allocation
    when organizations use platform keys instead of their own.

    Attributes:
        id: Unique identifier (UUID)
        organization_id: Organization that used the platform provider
        platform_provider_id: Platform provider that was used

        usage_date: Date of usage (YYYY-MM-DD)
        usage_hour: Hour of usage (0-23, null for daily aggregates)

        request_count: Number of API requests made
        input_tokens: Total input tokens consumed
        output_tokens: Total output tokens generated
        total_cost: Total cost in USD (with 4 decimal precision)

        leaflet_count: Number of leaflets processed
        page_count: Number of pages processed
        product_count: Number of products extracted
        average_confidence: Average extraction confidence score

        created_at: When this usage record was created
    """

    __tablename__ = "organization_vlm_usage"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique usage record identifier"
    )

    # Foreign Keys
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that used the platform provider"
    )

    platform_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_vlm_providers.id", ondelete="SET NULL"),
        nullable=True,  # Can be null if provider is deleted
        index=True,
        comment="Platform provider that was used"
    )

    # Time Dimensions
    usage_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of usage (YYYY-MM-DD)"
    )

    usage_hour = Column(
        Integer,
        nullable=True,
        comment="Hour of usage (0-23, null for daily aggregates)"
    )

    # Usage Metrics
    request_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of API requests made"
    )

    input_tokens = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Total input tokens consumed"
    )

    output_tokens = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Total output tokens generated"
    )

    total_cost = Column(
        Numeric(10, 4),  # Up to $999,999.9999
        nullable=False,
        default=Decimal("0.0000"),
        comment="Total cost in USD (4 decimal precision)"
    )

    # Business Metrics
    leaflet_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of leaflets processed"
    )

    page_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages processed"
    )

    product_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of products extracted"
    )

    average_confidence = Column(
        Float,
        nullable=True,
        comment="Average extraction confidence score (0.0-1.0)"
    )

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        comment="When this usage record was created"
    )

    # Relationships
    organization = relationship(
        "Organization",
        doc="Organization that used the platform provider"
    )

    platform_provider = relationship(
        "PlatformVLMProvider",
        doc="Platform provider that was used"
    )

    # Constraints and Indexes
    __table_args__ = (
        # Unique constraint to prevent duplicate usage records
        UniqueConstraint(
            "organization_id",
            "platform_provider_id",
            "usage_date",
            "usage_hour",
            name="uq_org_provider_date_hour"
        ),

        # Check constraints for data integrity
        CheckConstraint("usage_hour IS NULL OR (usage_hour >= 0 AND usage_hour <= 23)", name="check_usage_hour_range"),
        CheckConstraint("request_count >= 0", name="check_request_count_non_negative"),
        CheckConstraint("input_tokens >= 0", name="check_input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="check_output_tokens_non_negative"),
        CheckConstraint("total_cost >= 0", name="check_total_cost_non_negative"),
        CheckConstraint("leaflet_count >= 0", name="check_leaflet_count_non_negative"),
        CheckConstraint("page_count >= 0", name="check_page_count_non_negative"),
        CheckConstraint("product_count >= 0", name="check_product_count_non_negative"),
        CheckConstraint("average_confidence IS NULL OR (average_confidence >= 0.0 AND average_confidence <= 1.0)", name="check_avg_confidence_range"),

        # Performance indexes
        Index("idx_org_usage_org_date", "organization_id", "usage_date"),
        Index("idx_org_usage_provider_date", "platform_provider_id", "usage_date"),
        Index("idx_org_usage_date_hour", "usage_date", "usage_hour"),
        Index("idx_org_usage_created", "created_at"),
    )

    def add_usage(
        self,
        request_count: int = 1,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        leaflet_count: int = 0,
        page_count: int = 0,
        product_count: int = 0,
        confidence_score: Optional[float] = None
    ):
        """
        Add usage metrics to this record.

        This method aggregates usage data, updating counters and recalculating
        averages where appropriate.
        """
        self.request_count += request_count
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_cost += Decimal(str(cost))
        self.leaflet_count += leaflet_count
        self.page_count += page_count
        self.product_count += product_count

        # Update average confidence with weighted average
        if confidence_score is not None:
            if self.average_confidence is None:
                self.average_confidence = confidence_score
            else:
                # Weight by number of requests
                old_weight = self.request_count - request_count
                new_weight = request_count
                total_weight = old_weight + new_weight

                if total_weight > 0:
                    self.average_confidence = (
                        (self.average_confidence * old_weight + confidence_score * new_weight)
                        / total_weight
                    )

    @property
    def total_tokens(self) -> int:
        """Get total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def cost_per_request(self) -> float:
        """Get average cost per request."""
        if self.request_count == 0:
            return 0.0
        return float(self.total_cost) / self.request_count

    @property
    def cost_per_token(self) -> float:
        """Get average cost per token."""
        total_tokens = self.total_tokens
        if total_tokens == 0:
            return 0.0
        return float(self.total_cost) / total_tokens

    @property
    def cost_per_leaflet(self) -> float:
        """Get average cost per leaflet."""
        if self.leaflet_count == 0:
            return 0.0
        return float(self.total_cost) / self.leaflet_count

    @property
    def products_per_leaflet(self) -> float:
        """Get average products extracted per leaflet."""
        if self.leaflet_count == 0:
            return 0.0
        return self.product_count / self.leaflet_count

    @property
    def pages_per_leaflet(self) -> float:
        """Get average pages processed per leaflet."""
        if self.leaflet_count == 0:
            return 0.0
        return self.page_count / self.leaflet_count

    def to_dict(self) -> dict:
        """Convert usage record to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "platform_provider_id": str(self.platform_provider_id) if self.platform_provider_id else None,
            "usage_date": self.usage_date.isoformat(),
            "usage_hour": self.usage_hour,
            "request_count": self.request_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": float(self.total_cost),
            "leaflet_count": self.leaflet_count,
            "page_count": self.page_count,
            "product_count": self.product_count,
            "average_confidence": self.average_confidence,
            "cost_per_request": self.cost_per_request,
            "cost_per_token": self.cost_per_token,
            "cost_per_leaflet": self.cost_per_leaflet,
            "products_per_leaflet": self.products_per_leaflet,
            "pages_per_leaflet": self.pages_per_leaflet,
            "created_at": self.created_at.isoformat()
        }

    def __repr__(self) -> str:
        """String representation of OrganizationVLMUsage."""
        hour_str = f":{self.usage_hour:02d}" if self.usage_hour is not None else ""
        return (
            f"<OrganizationVLMUsage(org={self.organization_id}, "
            f"provider={self.platform_provider_id}, "
            f"date={self.usage_date}{hour_str}, "
            f"requests={self.request_count}, "
            f"cost=${self.total_cost})>"
        )


class OrganizationUsageSummary(Base):
    """
    Pre-aggregated organization usage summaries.

    This model stores pre-calculated monthly and yearly summaries
    for faster reporting and dashboard performance.
    """

    __tablename__ = "organization_usage_summaries"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique summary record identifier"
    )

    # Dimensions
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization being summarized"
    )

    summary_period = Column(
        Date,
        nullable=False,
        index=True,
        comment="Start of summary period (first day of month/year)"
    )

    period_type = Column(
        String(10),
        nullable=False,
        comment="Type of period (monthly, yearly)"
    )

    # Aggregated Metrics
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total API requests in period"
    )

    total_input_tokens = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Total input tokens in period"
    )

    total_output_tokens = Column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Total output tokens in period"
    )

    total_cost = Column(
        Numeric(12, 4),  # Up to $99,999,999.9999
        nullable=False,
        default=Decimal("0.0000"),
        comment="Total cost in period"
    )

    total_leaflets = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total leaflets processed in period"
    )

    total_pages = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pages processed in period"
    )

    total_products = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total products extracted in period"
    )

    average_confidence = Column(
        Float,
        nullable=True,
        comment="Weighted average confidence for period"
    )

    # Provider Usage Breakdown (JSON)
    provider_breakdown = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Cost breakdown by provider {provider_id: {cost, requests, ...}}"
    )

    # Metadata
    last_updated = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        onupdate=lambda: datetime.now(timezone.utc),
        comment="When this summary was last updated"
    )

    # Relationships
    organization = relationship(
        "Organization",
        doc="Organization being summarized"
    )

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "summary_period",
            "period_type",
            name="uq_org_summary_period_type"
        ),
        CheckConstraint("period_type IN ('monthly', 'yearly')", name="check_period_type"),
        Index("idx_org_summary_org_period", "organization_id", "summary_period"),
        Index("idx_org_summary_period_type", "summary_period", "period_type"),
    )

    def __repr__(self) -> str:
        """String representation of OrganizationUsageSummary."""
        return (
            f"<OrganizationUsageSummary(org={self.organization_id}, "
            f"period={self.summary_period}, type={self.period_type}, "
            f"cost=${self.total_cost})>"
        )