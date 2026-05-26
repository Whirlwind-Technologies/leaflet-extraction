"""
Analytics Model Module.

This module defines models for tracking analytics, metrics,
and usage statistics for the platform.

Example Usage:
    from app.models.analytics import UsageMetrics, CostTracking
    
    # Record daily metrics
    metrics = UsageMetrics(
        user_id=user.id,
        date=date.today(),
        leaflets_processed=5,
        products_extracted=150
    )
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class UsageMetrics(BaseModel, TimestampMixin):
    """
    Daily usage metrics per user.
    
    Tracks daily usage statistics for analytics and reporting.
    
    Attributes:
        user_id: User ID
        date: Date of metrics
        leaflets_uploaded: Leaflets uploaded
        leaflets_processed: Successfully processed
        leaflets_failed: Failed processing
        products_extracted: Products extracted
        products_auto_approved: Auto-approved products
        products_reviewed: Manually reviewed products
        api_calls: API calls made
        api_tokens_used: Total API tokens consumed
        api_cost: Total API cost
    """
    
    __tablename__ = "usage_metrics"
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_usage_metrics_user_date'),
    )
    
    # User reference
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    # Date
    date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of metrics"
    )
    
    # Leaflet metrics
    leaflets_uploaded = Column(
        Integer, nullable=False, default=0,
        comment="Leaflets uploaded"
    )
    
    leaflets_processed = Column(
        Integer, nullable=False, default=0,
        comment="Successfully processed"
    )
    
    leaflets_failed = Column(
        Integer, nullable=False, default=0,
        comment="Failed processing"
    )
    
    total_pages_processed = Column(
        Integer, nullable=False, default=0,
        comment="Total pages processed"
    )
    
    # Product metrics
    products_extracted = Column(
        Integer, nullable=False, default=0,
        comment="Products extracted"
    )
    
    products_auto_approved = Column(
        Integer, nullable=False, default=0,
        comment="Auto-approved products"
    )
    
    products_reviewed = Column(
        Integer, nullable=False, default=0,
        comment="Manually reviewed products"
    )
    
    products_approved = Column(
        Integer, nullable=False, default=0,
        comment="Approved after review"
    )
    
    products_rejected = Column(
        Integer, nullable=False, default=0,
        comment="Rejected products"
    )
    
    # Quality metrics
    avg_confidence = Column(
        Float, nullable=True,
        comment="Average confidence score"
    )
    
    avg_validation_pass_rate = Column(
        Float, nullable=True,
        comment="Average validation pass rate"
    )
    
    # API metrics
    api_calls = Column(
        Integer, nullable=False, default=0,
        comment="VLM API calls made"
    )
    
    api_input_tokens = Column(
        Integer, nullable=False, default=0,
        comment="Input tokens consumed"
    )
    
    api_output_tokens = Column(
        Integer, nullable=False, default=0,
        comment="Output tokens consumed"
    )
    
    api_cost = Column(
        Numeric(10, 4), nullable=False, default=Decimal("0"),
        comment="Total API cost in USD"
    )
    
    # Processing time
    total_processing_time_seconds = Column(
        Integer, nullable=False, default=0,
        comment="Total processing time"
    )
    
    avg_processing_time_seconds = Column(
        Float, nullable=True,
        comment="Average processing time per leaflet"
    )

    # Storage metrics
    storage_used_bytes = Column(
        Integer, nullable=True,
        comment="Storage used in bytes"
    )

    # Export metrics
    exports_csv = Column(
        Integer, nullable=False, default=0,
        comment="CSV exports"
    )
    
    exports_json = Column(
        Integer, nullable=False, default=0,
        comment="JSON exports"
    )
    
    exports_excel = Column(
        Integer, nullable=False, default=0,
        comment="Excel exports"
    )
    
    # Webhook metrics
    webhooks_sent = Column(
        Integer, nullable=False, default=0,
        comment="Webhooks sent"
    )
    
    webhooks_failed = Column(
        Integer, nullable=False, default=0,
        comment="Webhooks failed"
    )
    
    # Relationships
    user = relationship("User", back_populates="usage_metrics")


class CostTracking(BaseModel, TimestampMixin):
    """
    Per-leaflet cost tracking.
    
    Tracks detailed cost breakdown for each leaflet processed.
    """
    
    __tablename__ = "cost_tracking"
    
    # References
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    leaflet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leaflets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Leaflet ID"
    )
    
    vlm_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vlm_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="VLM provider used"
    )
    
    # Timestamp
    processed_at = Column(
        DateTime, nullable=False,
        default=datetime.utcnow,
        comment="Processing timestamp"
    )
    
    # Provider info
    provider_type = Column(
        String(50), nullable=False,
        comment="Provider type (anthropic, openai, etc.)"
    )
    
    model_name = Column(
        String(100), nullable=False,
        comment="Model used"
    )
    
    # Token usage
    input_tokens = Column(
        Integer, nullable=False, default=0,
        comment="Input tokens"
    )
    
    output_tokens = Column(
        Integer, nullable=False, default=0,
        comment="Output tokens"
    )
    
    total_tokens = Column(
        Integer, nullable=False, default=0,
        comment="Total tokens"
    )
    
    # Cost breakdown (Numeric for fixed-point decimal precision)
    input_cost = Column(
        Numeric(10, 4), nullable=False, default=Decimal("0"),
        comment="Input token cost"
    )

    output_cost = Column(
        Numeric(10, 4), nullable=False, default=Decimal("0"),
        comment="Output token cost"
    )

    total_cost = Column(
        Numeric(10, 4), nullable=False, default=Decimal("0"),
        comment="Total cost"
    )
    
    # Leaflet info
    page_count = Column(
        Integer, nullable=True,
        comment="Number of pages"
    )
    
    product_count = Column(
        Integer, nullable=True,
        comment="Products extracted"
    )
    
    # Pricing info (at time of processing, Numeric for precision)
    input_price_per_1m = Column(
        Numeric(10, 4), nullable=True,
        comment="Input price per 1M tokens"
    )

    output_price_per_1m = Column(
        Numeric(10, 4), nullable=True,
        comment="Output price per 1M tokens"
    )
    
    # Metadata
    metadata_ = Column(
        "metadata_",
        JSONB, nullable=True, default=dict,
        comment="Additional metadata"
    )

    # Relationships
    user = relationship("User", back_populates="cost_tracking")


class ProcessingStats(BaseModel, TimestampMixin):
    """
    Aggregate processing statistics.
    
    Stores pre-computed statistics for dashboard display.
    """
    
    __tablename__ = "processing_stats"
    
    # User reference (null for system-wide stats)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="User ID (null for system-wide)"
    )
    
    # Time period
    period_type = Column(
        String(20), nullable=False,
        index=True,
        comment="Period type: daily, weekly, monthly, all_time"
    )
    
    period_start = Column(
        Date, nullable=False,
        index=True,
        comment="Period start date"
    )
    
    period_end = Column(
        Date, nullable=False,
        comment="Period end date"
    )
    
    # Aggregate metrics
    total_leaflets = Column(Integer, nullable=False, default=0)
    successful_leaflets = Column(Integer, nullable=False, default=0)
    failed_leaflets = Column(Integer, nullable=False, default=0)
    
    total_products = Column(Integer, nullable=False, default=0)
    auto_approved_products = Column(Integer, nullable=False, default=0)
    reviewed_products = Column(Integer, nullable=False, default=0)
    
    total_pages = Column(Integer, nullable=False, default=0)
    
    avg_confidence = Column(Float, nullable=True)
    avg_products_per_leaflet = Column(Float, nullable=True)
    avg_processing_time = Column(Float, nullable=True)
    
    total_cost = Column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Success rates
    extraction_success_rate = Column(Float, nullable=True)
    auto_approval_rate = Column(Float, nullable=True)
    validation_pass_rate = Column(Float, nullable=True)
    
    # Top retailers
    top_retailers = Column(JSONB, nullable=True)
    
    # Error breakdown
    error_breakdown = Column(JSONB, nullable=True)
    
    # Computed at
    computed_at = Column(
        DateTime, nullable=False,
        default=datetime.utcnow,
        comment="When stats were computed"
    )


class FeedbackLog(BaseModel, TimestampMixin):
    """
    User feedback and correction log.
    
    Tracks corrections made during review for model improvement.
    """
    
    __tablename__ = "feedback_logs"
    
    # References
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Product ID"
    )
    
    leaflet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leaflets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Leaflet ID"
    )
    
    # Feedback type
    feedback_type = Column(
        String(50), nullable=False,
        index=True,
        comment="Type: field_correction, bbox_adjustment, rejection, etc."
    )
    
    # Field that was corrected
    field_name = Column(
        String(50), nullable=True,
        comment="Field that was corrected"
    )
    
    # Original and corrected values
    original_value = Column(
        JSONB, nullable=True,
        comment="Original extracted value"
    )
    
    corrected_value = Column(
        JSONB, nullable=True,
        comment="Corrected value"
    )
    
    # Confidence before correction
    original_confidence = Column(
        Float, nullable=True,
        comment="Original confidence score"
    )
    
    # Context
    page_number = Column(
        Integer, nullable=True,
        comment="Page number"
    )
    
    retailer = Column(
        String(200), nullable=True,
        comment="Retailer name"
    )
    
    # Analysis
    error_category = Column(
        String(50), nullable=True,
        comment="Categorized error type"
    )
    
    severity = Column(
        String(20), nullable=True,
        comment="Error severity: low, medium, high"
    )
    
    # Notes
    notes = Column(
        Text, nullable=True,
        comment="Reviewer notes"
    )
    
    # Metadata
    metadata_ = Column(
        "metadata_",
        JSONB, nullable=True, default=dict,
        comment="Additional metadata"
    )

    # Used for training
    used_for_training = Column(
        Boolean, nullable=False, default=False,
        comment="Whether used for model fine-tuning"
    )
    
    # Relationships
    user = relationship("User", back_populates="feedback_logs")


class ErrorPattern(BaseModel, TimestampMixin):
    """
    Detected error patterns for improvement.
    
    Aggregates similar errors to identify systematic issues.
    """
    
    __tablename__ = "error_patterns"
    
    # Pattern identification
    pattern_hash = Column(
        String(64), nullable=False, unique=True,
        index=True,
        comment="Hash of pattern characteristics"
    )
    
    # Pattern details
    error_type = Column(
        String(50), nullable=False,
        index=True,
        comment="Type of error"
    )
    
    field_affected = Column(
        String(50), nullable=True,
        comment="Field affected"
    )
    
    description = Column(
        Text, nullable=False,
        comment="Pattern description"
    )
    
    # Occurrence stats
    occurrence_count = Column(
        Integer, nullable=False, default=1,
        comment="Number of occurrences"
    )
    
    first_seen_at = Column(
        DateTime, nullable=False,
        default=datetime.utcnow,
        comment="First occurrence"
    )
    
    last_seen_at = Column(
        DateTime, nullable=False,
        default=datetime.utcnow,
        comment="Last occurrence"
    )
    
    # Context patterns
    retailers_affected = Column(
        ARRAY(String), nullable=True,
        comment="Retailers where pattern occurs"
    )
    
    # Resolution
    is_resolved = Column(
        Boolean, nullable=False, default=False,
        comment="Whether pattern is resolved"
    )
    
    resolution_notes = Column(
        Text, nullable=True,
        comment="How pattern was resolved"
    )
    
    resolved_at = Column(
        DateTime, nullable=True,
        comment="Resolution timestamp"
    )
    
    # Priority
    priority = Column(
        Integer, nullable=False, default=0,
        comment="Priority for fixing (higher = more important)"
    )
    
    # Examples
    example_feedback_ids = Column(
        ARRAY(UUID(as_uuid=True)), nullable=True,
        comment="Example feedback log IDs"
    )
    
    # Prompt improvement
    suggested_prompt_change = Column(
        Text, nullable=True,
        comment="Suggested prompt improvement"
    )