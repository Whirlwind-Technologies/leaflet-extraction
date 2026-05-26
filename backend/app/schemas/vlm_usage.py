"""
VLM Usage Cost Query Schemas.

This module defines Pydantic schemas for the date-range cost query endpoint
at GET /api/v1/vlm-providers/usage/costs.

The endpoint aggregates data from the organization_vlm_usage table, which
stores per-hour usage rollups with cost, token, and business metrics.

Example Usage:
    from app.schemas.vlm_usage import (
        CostPeriod, CostGroupBy, CostQueryParams, VLMCostResponse,
    )

    # Validate query parameters
    params = CostQueryParams(period=CostPeriod.THIS_MONTH)
    start, end = params.resolve_dates()

    # Build response
    response = VLMCostResponse(period=..., summary=..., by_provider=..., daily_breakdown=...)
"""

import enum
from datetime import date as DateType, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CostPeriod(str, enum.Enum):
    """
    Supported period presets for cost queries.

    Attributes:
        LAST_7_DAYS: Rolling 7-day window ending today.
        LAST_30_DAYS: Rolling 30-day window ending today.
        THIS_MONTH: Current calendar month (1st through today).
        LAST_MONTH: Previous complete calendar month.
        THIS_YEAR: Current calendar year (Jan 1 through today).
        ALL_TIME: All available data (no date filter applied).
        CUSTOM: User-specified start_date and end_date.
    """

    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


class CostGroupBy(str, enum.Enum):
    """
    Granularity for the breakdown time series.

    Attributes:
        DAY: One data point per calendar day.
        WEEK: One data point per ISO week (Monday start).
        MONTH: One data point per calendar month.
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------


class CostQueryParams(BaseModel):
    """
    Validated query parameters for the cost endpoint.

    This model is constructed inside the endpoint handler from individual
    Query() parameters so that cross-field validation can execute.

    Attributes:
        period: Preset period or 'custom'.
        start_date: Inclusive start date (required when period=custom).
        end_date: Inclusive end date (required when period=custom).
        group_by: Granularity for the breakdown time series.
    """

    period: CostPeriod = Field(
        default=CostPeriod.THIS_MONTH,
        description="Preset period or 'custom' for an explicit date range.",
    )
    start_date: Optional[DateType] = Field(
        default=None,
        description="Inclusive start date (ISO 8601, YYYY-MM-DD). Required when period=custom.",
    )
    end_date: Optional[DateType] = Field(
        default=None,
        description="Inclusive end date (ISO 8601, YYYY-MM-DD). Required when period=custom.",
    )
    group_by: CostGroupBy = Field(
        default=CostGroupBy.DAY,
        description="Granularity for the breakdown time series: day, week, or month.",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "CostQueryParams":
        """
        Cross-field validation for date parameters.

        Rules applied:
        - period=custom requires both start_date and end_date.
        - end_date >= start_date.
        - Maximum range: 365 days.
        - start_date must not be in the future.
        - end_date is silently clamped to today when in the future.
        """
        today = DateType.today()

        if self.period == CostPeriod.CUSTOM:
            if self.start_date is None or self.end_date is None:
                raise ValueError(
                    "Both start_date and end_date are required when period is 'custom'"
                )
            if self.start_date > today:
                raise ValueError("start_date cannot be in the future")
            # Clamp end_date to today (not an error)
            if self.end_date > today:
                self.end_date = today
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date")
            if (self.end_date - self.start_date).days > 365:
                raise ValueError("Date range cannot exceed 365 days")

        return self

    def resolve_dates(self) -> tuple[DateType, DateType]:
        """
        Resolve the period preset to concrete (start_date, end_date) inclusive.

        Returns:
            Tuple of (start_date, end_date).
        """
        today = DateType.today()

        if self.period == CostPeriod.CUSTOM:
            return self.start_date, self.end_date  # type: ignore[return-value]

        if self.period == CostPeriod.LAST_7_DAYS:
            return today - timedelta(days=6), today

        if self.period == CostPeriod.LAST_30_DAYS:
            return today - timedelta(days=29), today

        if self.period == CostPeriod.THIS_MONTH:
            return today.replace(day=1), today

        if self.period == CostPeriod.LAST_MONTH:
            first_of_this_month = today.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            first_of_prev_month = last_of_prev_month.replace(day=1)
            return first_of_prev_month, last_of_prev_month

        if self.period == CostPeriod.THIS_YEAR:
            return DateType(today.year, 1, 1), today

        # ALL_TIME -- floor date keeps the query range bounded
        return DateType(2020, 1, 1), today


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CostPeriodInfo(BaseModel):
    """
    Metadata describing the resolved query period.

    Attributes:
        start_date: Resolved inclusive start date.
        end_date: Resolved inclusive end date.
        period_type: The period enum value that was requested.
        label: Human-readable label (e.g. "January 2025", "Last 7 days").
    """

    start_date: DateType = Field(description="Inclusive start of the resolved period.")
    end_date: DateType = Field(description="Inclusive end of the resolved period.")
    period_type: CostPeriod = Field(description="The period preset that was used.")
    label: str = Field(
        description="Human-readable period label, e.g. 'January 2025' or 'Last 7 days'."
    )

    model_config = ConfigDict(from_attributes=True)


class CostSummary(BaseModel):
    """
    Aggregate cost and usage metrics for the entire queried period.

    Monetary values are floats rounded to 4 decimal places, matching the
    Numeric(10,4) column in organization_vlm_usage. Token counts are ints
    corresponding to BigInteger columns.

    Attributes:
        total_cost: Total cost in USD for the period.
        total_requests: Total VLM API requests.
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens generated.
        total_tokens: Sum of input and output tokens.
        leaflets_processed: Leaflets processed in the period.
        pages_processed: Pages sent to VLM.
        products_extracted: Products extracted.
        avg_cost_per_leaflet: total_cost / leaflets_processed (0 if none).
        avg_cost_per_request: total_cost / total_requests (0 if none).
    """

    total_cost: float = Field(
        ...,
        description="Total cost in USD for the period.",
        json_schema_extra={"examples": [245.6700]},
    )
    total_requests: int = Field(
        ...,
        description="Total VLM API requests in the period.",
        json_schema_extra={"examples": [890]},
    )
    total_input_tokens: int = Field(
        ...,
        description="Total input tokens consumed.",
        json_schema_extra={"examples": [5600000]},
    )
    total_output_tokens: int = Field(
        ...,
        description="Total output tokens generated.",
        json_schema_extra={"examples": [1200000]},
    )
    total_tokens: int = Field(
        ...,
        description="Total tokens (input + output).",
        json_schema_extra={"examples": [6800000]},
    )
    leaflets_processed: int = Field(
        ...,
        description="Number of leaflets processed in the period.",
        json_schema_extra={"examples": [45]},
    )
    pages_processed: int = Field(
        ...,
        description="Number of pages sent to VLM in the period.",
        json_schema_extra={"examples": [312]},
    )
    products_extracted: int = Field(
        ...,
        description="Number of products extracted in the period.",
        json_schema_extra={"examples": [2450]},
    )
    avg_cost_per_leaflet: float = Field(
        ...,
        description="Average cost per leaflet processed (0 when no leaflets).",
        json_schema_extra={"examples": [5.4593]},
    )
    avg_cost_per_request: float = Field(
        ...,
        description="Average cost per VLM API request (0 when no requests).",
        json_schema_extra={"examples": [0.2760]},
    )

    model_config = ConfigDict(from_attributes=True)


class CostByProvider(BaseModel):
    """
    Cost breakdown for a single platform provider within the queried period.

    Attributes:
        provider_id: UUID of the platform_vlm_provider (null if deleted).
        provider_name: Display name of the provider.
        provider_type: Provider type string (anthropic, openai, google, etc.).
        cost: Total cost attributed to this provider.
        requests: Total requests routed to this provider.
        input_tokens: Input tokens consumed by this provider.
        output_tokens: Output tokens generated by this provider.
        tokens: Total tokens (input + output).
        percentage_of_total: Provider cost as percentage of period total cost.
    """

    provider_id: Optional[str] = Field(
        None,
        description="Platform provider UUID (null when provider has been deleted).",
    )
    provider_name: str = Field(
        ...,
        description="Display name of the provider.",
        json_schema_extra={"examples": ["Anthropic Claude"]},
    )
    provider_type: str = Field(
        ...,
        description="Provider type: anthropic, openai, google, azure_openai, aws_bedrock, custom.",
        json_schema_extra={"examples": ["anthropic"]},
    )
    cost: float = Field(
        ...,
        description="Total cost for this provider in the period.",
        json_schema_extra={"examples": [200.5000]},
    )
    requests: int = Field(
        ...,
        description="Total requests routed to this provider.",
        json_schema_extra={"examples": [750]},
    )
    input_tokens: int = Field(
        ...,
        description="Input tokens consumed by this provider.",
        json_schema_extra={"examples": [4400000]},
    )
    output_tokens: int = Field(
        ...,
        description="Output tokens generated by this provider.",
        json_schema_extra={"examples": [1100000]},
    )
    tokens: int = Field(
        ...,
        description="Total tokens (input + output) for this provider.",
        json_schema_extra={"examples": [5500000]},
    )
    percentage_of_total: float = Field(
        ...,
        description="This provider's cost as a percentage of the period's total cost.",
        json_schema_extra={"examples": [81.6]},
    )

    model_config = ConfigDict(from_attributes=True)


class CostBreakdownPoint(BaseModel):
    """
    A single data point in the time-series breakdown.

    The meaning of the date field varies by group_by:
    - day: the calendar date itself (e.g. 2025-01-15).
    - week: the Monday of the ISO week (e.g. 2025-01-13).
    - month: the first day of the month (e.g. 2025-01-01).

    Attributes:
        date: Start of this time bucket.
        cost: Total cost in this bucket.
        requests: Total VLM API requests in this bucket.
        tokens: Total tokens (input + output) in this bucket.
        leaflets: Leaflets processed in this bucket.
    """

    date: DateType = Field(
        ...,
        description="Start of this time bucket (day, week-Monday, or month-1st).",
    )
    cost: float = Field(
        ...,
        description="Total cost in this bucket.",
        json_schema_extra={"examples": [12.3000]},
    )
    requests: int = Field(
        ...,
        description="Total VLM API requests in this bucket.",
        json_schema_extra={"examples": [45]},
    )
    tokens: int = Field(
        ...,
        description="Total tokens (input + output) in this bucket.",
        json_schema_extra={"examples": [180000]},
    )
    leaflets: int = Field(
        ...,
        description="Leaflets processed in this bucket.",
        json_schema_extra={"examples": [3]},
    )

    model_config = ConfigDict(from_attributes=True)


class VLMCostResponse(BaseModel):
    """
    Top-level response for GET /api/v1/vlm-providers/usage/costs.

    Contains the resolved period metadata, aggregate summary, per-provider
    breakdown, and a time-series at the requested granularity.

    Attributes:
        period: Metadata about the resolved date range.
        summary: Aggregate cost and usage metrics for the full period.
        by_provider: Per-provider cost breakdown sorted by cost descending.
        daily_breakdown: Time-series data points (granularity set by group_by).
    """

    period: CostPeriodInfo = Field(
        ...,
        description="Resolved period metadata.",
    )
    summary: CostSummary = Field(
        ...,
        description="Aggregate cost and usage metrics for the entire period.",
    )
    by_provider: List[CostByProvider] = Field(
        ...,
        description="Per-provider cost breakdown, sorted by cost descending.",
    )
    daily_breakdown: List[CostBreakdownPoint] = Field(
        ...,
        description="Time-series data points at the requested granularity (day/week/month).",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "period": {
                        "start_date": "2025-01-01",
                        "end_date": "2025-01-31",
                        "period_type": "this_month",
                        "label": "January 2025",
                    },
                    "summary": {
                        "total_cost": 245.67,
                        "total_requests": 890,
                        "total_input_tokens": 5600000,
                        "total_output_tokens": 1200000,
                        "total_tokens": 6800000,
                        "leaflets_processed": 45,
                        "pages_processed": 312,
                        "products_extracted": 2450,
                        "avg_cost_per_leaflet": 5.46,
                        "avg_cost_per_request": 0.28,
                    },
                    "by_provider": [
                        {
                            "provider_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "provider_name": "Anthropic Claude",
                            "provider_type": "anthropic",
                            "cost": 200.50,
                            "requests": 750,
                            "input_tokens": 4400000,
                            "output_tokens": 1100000,
                            "tokens": 5500000,
                            "percentage_of_total": 81.6,
                        }
                    ],
                    "daily_breakdown": [
                        {
                            "date": "2025-01-01",
                            "cost": 12.30,
                            "requests": 45,
                            "tokens": 180000,
                            "leaflets": 3,
                        }
                    ],
                }
            ]
        },
    )
