"""
VLM Providers Management Endpoints.

This module provides endpoints for managing VLM provider configurations
including API keys, model selection, and cost tracking.

Example Usage:
    POST /api/v1/vlm-providers - Create provider config
    GET /api/v1/vlm-providers - List providers
    PUT /api/v1/vlm-providers/{id}/default - Set as default
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError
from sqlalchemy import select, and_, func, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_organization, get_db
from app.models.vlm_provider import VLMProvider, VLMProviderType, DEFAULT_MODELS
from app.models.vlm_model import VLMModel
from app.models.organization_usage import OrganizationVLMUsage
from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.user import User
from app.models.organization import Organization
from app.schemas.vlm_usage import (
    CostPeriod,
    CostGroupBy,
    CostQueryParams,
    CostPeriodInfo,
    CostSummary,
    CostByProvider,
    CostBreakdownPoint,
    VLMCostResponse,
)
from app.utils.cache import get_cache, set_cache
from app.utils.exceptions import NotFoundError, ValidationException

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Schemas ---

class VLMProviderCreate(BaseModel):
    """Schema for creating a VLM provider."""
    provider_type: VLMProviderType
    name: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=10)
    api_endpoint: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: int = Field(default=8192, ge=100, le=32000)
    temperature: float = Field(default=0.1, ge=0, le=2)
    monthly_budget: Optional[float] = Field(None, ge=0)
    is_default: bool = False
    config: Optional[dict] = None


class VLMProviderUpdate(BaseModel):
    """Schema for updating a VLM provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, min_length=10)
    api_endpoint: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = Field(None, ge=100, le=32000)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    monthly_budget: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class VLMProviderResponse(BaseModel):
    """Schema for VLM provider response."""
    id: UUID
    provider_type: str
    name: str
    provider_display_name: str
    api_endpoint: Optional[str]
    model_name: str
    max_tokens: int
    temperature: float
    is_default: bool
    is_active: bool
    monthly_budget: Optional[float]
    total_spent: float
    current_month_spent: float
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    last_used_at: Optional[datetime]
    masked_api_key: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class VLMModelInfo(BaseModel):
    """Information about a VLM model."""
    model_id: str
    display_name: str
    description: Optional[str] = None
    max_tokens: int
    input_cost_per_1m: float
    output_cost_per_1m: float
    is_default: bool = False
    is_deprecated: bool = False
    supports_vision: bool = True


class VLMProviderTypeInfo(BaseModel):
    """Information about a VLM provider type."""
    type: str
    display_name: str
    default_model: str
    default_max_tokens: int
    input_cost_per_1m: float
    output_cost_per_1m: float
    requires_endpoint: bool
    models: List[VLMModelInfo] = []  # Available models for this provider


class VLMProviderUsageStats(BaseModel):
    """Usage statistics for a VLM provider."""
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    current_month_cost: float
    budget_remaining: Optional[float]
    budget_usage_percent: Optional[float]


# --- Endpoints ---

@router.get(
    "/types",
    response_model=List[VLMProviderTypeInfo],
    summary="List provider types",
    description="Get information about available VLM provider types and their models.",
)
async def list_provider_types(
    db: AsyncSession = Depends(get_db),
) -> List[VLMProviderTypeInfo]:
    """List available VLM provider types and their models from the database."""
    types = []

    # Fetch all active models from database
    result = await db.execute(
        select(VLMModel)
        .where(VLMModel.is_active == True)
        .order_by(VLMModel.provider_type, VLMModel.sort_order, VLMModel.display_name)
    )
    db_models = result.scalars().all()

    # Group models by provider type
    models_by_provider = {}
    for model in db_models:
        if model.provider_type not in models_by_provider:
            models_by_provider[model.provider_type] = []
        models_by_provider[model.provider_type].append(model)

    # Build response for each provider type
    for provider_type in VLMProviderType:
        provider_type_str = provider_type.value
        provider_models = models_by_provider.get(provider_type_str, [])

        # Get default model info
        default_model = next((m for m in provider_models if m.is_default), None)
        if not default_model and provider_models:
            default_model = provider_models[0]

        # Fall back to hardcoded defaults if no models in database
        if not provider_models:
            defaults = DEFAULT_MODELS.get(provider_type, {})
            if not defaults:
                continue  # Skip providers with no config

            types.append(VLMProviderTypeInfo(
                type=provider_type_str,
                display_name=_get_provider_display_name(provider_type),
                default_model=defaults.get("model_name", ""),
                default_max_tokens=defaults.get("max_tokens", 8192),
                input_cost_per_1m=defaults.get("input_cost_per_1m", 3.0),
                output_cost_per_1m=defaults.get("output_cost_per_1m", 15.0),
                requires_endpoint=provider_type in [
                    VLMProviderType.AZURE_OPENAI,
                    VLMProviderType.CUSTOM,
                ],
                models=[
                    VLMModelInfo(
                        model_id=defaults.get("model_name", ""),
                        display_name=defaults.get("model_name", ""),
                        max_tokens=defaults.get("max_tokens", 8192),
                        input_cost_per_1m=defaults.get("input_cost_per_1m", 3.0),
                        output_cost_per_1m=defaults.get("output_cost_per_1m", 15.0),
                        is_default=True,
                    )
                ],
            ))
        else:
            # Use models from database
            model_infos = [
                VLMModelInfo(
                    model_id=m.model_id,
                    display_name=m.display_name,
                    description=m.description,
                    max_tokens=m.max_tokens,
                    input_cost_per_1m=m.input_cost_per_1m,
                    output_cost_per_1m=m.output_cost_per_1m,
                    is_default=m.is_default,
                    is_deprecated=m.is_deprecated,
                    supports_vision=m.supports_vision,
                )
                for m in provider_models
            ]

            types.append(VLMProviderTypeInfo(
                type=provider_type_str,
                display_name=_get_provider_display_name(provider_type),
                default_model=default_model.model_id if default_model else "",
                default_max_tokens=default_model.max_tokens if default_model else 8192,
                input_cost_per_1m=default_model.input_cost_per_1m if default_model else 3.0,
                output_cost_per_1m=default_model.output_cost_per_1m if default_model else 15.0,
                requires_endpoint=provider_type in [
                    VLMProviderType.AZURE_OPENAI,
                    VLMProviderType.CUSTOM,
                ],
                models=model_infos,
            ))

    return types


def _get_provider_display_name(provider_type: VLMProviderType) -> str:
    """Get display name for provider type."""
    names = {
        VLMProviderType.ANTHROPIC: "Anthropic Claude",
        VLMProviderType.OPENAI: "OpenAI GPT-4",
        VLMProviderType.GOOGLE: "Google Gemini",
        VLMProviderType.AZURE_OPENAI: "Azure OpenAI",
        VLMProviderType.AWS_BEDROCK: "AWS Bedrock",
        VLMProviderType.CUSTOM: "Custom Provider",
    }
    return names.get(provider_type, "Unknown")


@router.post(
    "/",
    response_model=VLMProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create VLM provider",
    description="Create a new VLM provider configuration.",
)
async def create_vlm_provider(
    provider_data: VLMProviderCreate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMProviderResponse:
    """Create a new VLM provider configuration."""
    # Check provider limit (max 5)
    existing_result = await db.execute(
        select(VLMProvider).where(VLMProvider.organization_id == current_org.id)
    )
    existing_providers = existing_result.scalars().all()
    
    if len(existing_providers) >= 5:
        raise ValidationException(
            [{"field": "provider_type", "message": "Maximum number of VLM providers (5) reached"}],
            message="Maximum number of VLM providers (5) reached",
        )
    
    # Auto-set as default if this is the first provider
    is_first_provider = len(existing_providers) == 0
    should_be_default = provider_data.is_default or is_first_provider
    
    # Get defaults for provider type
    defaults = DEFAULT_MODELS.get(provider_data.provider_type, {})
    
    # Validate endpoint requirement
    if provider_data.provider_type in [VLMProviderType.AZURE_OPENAI, VLMProviderType.CUSTOM]:
        if not provider_data.api_endpoint:
            raise ValidationException(
                [{"field": "api_endpoint", "message": f"{provider_data.provider_type.value} requires an API endpoint"}],
                message=f"{provider_data.provider_type.value} requires an API endpoint",
            )
    
    # Create provider (organization-scoped, not user-scoped)
    provider = VLMProvider(
        organization_id=current_org.id,
        provider_type=provider_data.provider_type,
        name=provider_data.name,
        api_endpoint=provider_data.api_endpoint,
        model_name=provider_data.model_name or defaults.get("model_name", ""),
        max_tokens=provider_data.max_tokens,
        temperature=provider_data.temperature,
        monthly_budget=provider_data.monthly_budget,
        is_default=should_be_default,
        config=provider_data.config or {},
    )
    
    # Set encrypted API key
    provider.set_api_key(provider_data.api_key)
    
    # If setting as default, unset other defaults
    if should_be_default and not is_first_provider:
        await _clear_default_provider(db, current_org.id)
    
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    
    logger.info(
        f"User {current_user.email} created VLM provider: {provider.name}"
        f"{' (set as default)' if should_be_default else ''}"
    )
    
    return _provider_to_response(provider)


@router.get(
    "/",
    response_model=List[VLMProviderResponse],
    summary="List VLM providers",
    description="List all VLM provider configurations.",
)
async def list_vlm_providers(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> List[VLMProviderResponse]:
    """List all VLM provider configurations."""
    query = select(VLMProvider).where(VLMProvider.organization_id == current_org.id)
    
    if not include_inactive:
        query = query.where(VLMProvider.is_active == True)
    
    query = query.order_by(VLMProvider.is_default.desc(), VLMProvider.created_at.desc())
    
    result = await db.execute(query)
    providers = result.scalars().all()
    
    return [_provider_to_response(p) for p in providers]


@router.get(
    "/default",
    response_model=Optional[VLMProviderResponse],
    summary="Get default provider",
    description="Get the default VLM provider configuration.",
)
async def get_default_provider(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Optional[VLMProviderResponse]:
    """Get the default VLM provider."""
    result = await db.execute(
        select(VLMProvider).where(
            and_(
                VLMProvider.organization_id == current_org.id,
                VLMProvider.is_default == True,
                VLMProvider.is_active == True,
            )
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        # Return first active provider
        result = await db.execute(
            select(VLMProvider).where(
                and_(
                    VLMProvider.organization_id == current_org.id,
                    VLMProvider.is_active == True,
                )
            ).limit(1)
        )
        provider = result.scalar_one_or_none()
    
    if provider:
        return _provider_to_response(provider)
    return None


class PlatformFallbackInfo(BaseModel):
    """Information about platform fallback provider."""
    provider_name: str = Field(..., description="Name of the platform provider")
    provider_type: str = Field(..., description="Type of provider (anthropic, openai, etc.)")
    model_name: str = Field(..., description="Model being used")
    is_healthy: bool = Field(True, description="Whether the provider is healthy")
    is_available: bool = Field(True, description="Whether the provider is available for use")
    last_used: Optional[datetime] = Field(None, description="Last time this provider was used")
    usage_cost_current_month: Optional[float] = Field(None, description="Cost spent this month")


class VLMStatusResponse(BaseModel):
    """Response for VLM provider status check."""
    has_active_provider: bool = Field(..., description="Whether user has an active provider")
    has_fallback: bool = Field(..., description="Whether system fallback is available")
    can_extract: bool = Field(..., description="Whether extraction is possible")
    default_provider: Optional[str] = Field(None, description="Name of default provider")
    provider_count: int = Field(0, description="Total number of configured providers")
    active_count: int = Field(0, description="Number of active providers")
    message: str = Field(..., description="Status message")
    platform_fallback: Optional[PlatformFallbackInfo] = Field(None, description="Platform fallback provider info")


@router.get(
    "/status",
    response_model=VLMStatusResponse,
    summary="Check VLM provider status",
    description="Check if the user has VLM providers configured and can perform extraction.",
)
async def get_vlm_status(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMStatusResponse:
    """
    Check VLM provider configuration status.

    Returns information about whether the user can perform extractions,
    including fallback availability via platform providers.

    Provider Hierarchy:
    1. Organization-level VLM providers (user's own API keys) - highest priority
    2. Admin-level platform VLM providers (system-wide fallback) - fallback

    Args:
        current_user: Currently authenticated user
        current_org: Current organization
        db: Database session

    Returns:
        VLM status information
    """
    from app.models.platform_vlm_provider import PlatformVLMProvider

    # Get all organization-level providers for user
    result = await db.execute(
        select(VLMProvider).where(VLMProvider.organization_id == current_org.id)
    )
    providers = result.scalars().all()

    provider_count = len(providers)
    active_providers = [p for p in providers if p.is_active]
    active_count = len(active_providers)

    # Find default organization provider
    default_provider = next(
        (p.name for p in active_providers if p.is_default),
        active_providers[0].name if active_providers else None
    )

    # Check for admin-level platform providers as fallback
    platform_result = await db.execute(
        select(PlatformVLMProvider).where(
            PlatformVLMProvider.is_active == True
        ).order_by(PlatformVLMProvider.priority.asc())
    )
    platform_providers = platform_result.scalars().all()
    has_platform_providers = len(platform_providers) > 0

    # Find default platform provider name for display
    platform_provider_name = None
    if has_platform_providers:
        default_platform = next(
            (p for p in platform_providers if p.is_default),
            platform_providers[0] if platform_providers else None
        )
        if default_platform:
            platform_provider_name = default_platform.name

    # Determine extraction capability
    has_active_provider = active_count > 0
    has_fallback = has_platform_providers
    can_extract = has_active_provider or has_fallback

    # Generate message
    if has_active_provider:
        message = f"Ready for extraction using {default_provider or 'configured provider'}."
    elif has_fallback:
        message = f"Using platform provider ({platform_provider_name}). Consider adding your own API key in Settings for dedicated usage."
    else:
        message = "No AI provider configured. Contact your administrator or add your own API key in Settings to enable extraction."

    # Build platform fallback info if available
    platform_fallback_info = None
    if has_platform_providers:
        default_platform = next(
            (p for p in platform_providers if p.is_default),
            platform_providers[0] if platform_providers else None
        )
        if default_platform:
            platform_fallback_info = PlatformFallbackInfo(
                provider_name=f"{default_platform.name} (Platform)",
                provider_type=default_platform.provider_type.value,
                model_name=default_platform.model_name,
                is_healthy=default_platform.is_active and default_platform.check_budget(),
                is_available=default_platform.is_active,
                last_used=default_platform.last_used_at,
                usage_cost_current_month=float(default_platform.current_month_spent or 0),
            )

    return VLMStatusResponse(
        has_active_provider=has_active_provider,
        has_fallback=has_fallback,
        can_extract=can_extract,
        default_provider=default_provider,
        provider_count=provider_count,
        active_count=active_count,
        message=message,
        platform_fallback=platform_fallback_info,
    )


class UsageStatsResponse(BaseModel):
    """Response for aggregated usage statistics."""
    total_leaflets: int = Field(..., description="Total number of leaflets processed")
    total_products: int = Field(..., description="Total products extracted")
    total_input_tokens: int = Field(..., description="Total input tokens used")
    total_output_tokens: int = Field(..., description="Total output tokens used")
    total_tokens: int = Field(..., description="Total tokens (input + output)")
    estimated_cost: float = Field(..., description="Estimated total cost in USD")
    this_month_leaflets: int = Field(0, description="Leaflets processed this month")
    this_month_cost: float = Field(0, description="Cost this month")
    average_tokens_per_page: float = Field(0, description="Average tokens per page")
    provider_breakdown: list = Field(default_factory=list, description="Stats by provider")


@router.get(
    "/usage/stats",
    response_model=UsageStatsResponse,
    summary="Get usage statistics",
    description="Get aggregated usage statistics from processed leaflets.",
)
async def get_usage_stats(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> UsageStatsResponse:
    """
    Get aggregated usage statistics from leaflets.
    
    This provides actual usage data aggregated from all processed leaflets,
    giving accurate statistics even when using the system fallback API key.
    """
    from datetime import datetime
    from sqlalchemy import func
    from app.models.leaflet import Leaflet
    from app.models.product import Product
    
    # Get leaflet stats
    leaflet_result = await db.execute(
        select(
            func.count(Leaflet.id).label('total_leaflets'),
            func.sum(Leaflet.api_tokens_used).label('total_tokens'),
            func.sum(Leaflet.processing_cost).label('total_cost'),
            func.sum(Leaflet.page_count).label('total_pages'),
        ).where(Leaflet.organization_id == current_org.id)
    )
    leaflet_stats = leaflet_result.one()
    
    # Get product count
    product_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.leaflet_id.in_(
                select(Leaflet.id).where(Leaflet.organization_id == current_org.id)
            )
        )
    )
    total_products = product_result.scalar() or 0
    
    # Get this month's stats
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_result = await db.execute(
        select(
            func.count(Leaflet.id).label('month_leaflets'),
            func.sum(Leaflet.processing_cost).label('month_cost'),
        ).where(
            Leaflet.organization_id == current_org.id,
            Leaflet.created_at >= start_of_month,
        )
    )
    month_stats = month_result.one()
    
    # Calculate derived stats
    total_tokens = int(leaflet_stats.total_tokens or 0)
    total_pages = int(leaflet_stats.total_pages or 0)
    
    # Estimate input/output token split (typical is ~80% input, 20% output for vision)
    estimated_input_tokens = int(total_tokens * 0.8)
    estimated_output_tokens = int(total_tokens * 0.2)
    
    avg_tokens_per_page = total_tokens / total_pages if total_pages > 0 else 0
    
    # Get provider-specific stats
    provider_breakdown = []
    
    # First get user's providers with their stats
    providers_result = await db.execute(
        select(VLMProvider).where(VLMProvider.organization_id == current_org.id)
    )
    providers = providers_result.scalars().all()
    
    for provider in providers:
        provider_breakdown.append({
            "name": provider.name,
            "provider_type": provider.provider_type.value,
            "total_requests": provider.total_requests,
            "total_tokens": provider.total_input_tokens + provider.total_output_tokens,
            "total_spent": round(float(provider.total_spent or 0), 4),
            "current_month_spent": round(float(provider.current_month_spent or 0), 4),
        })
    
    # Get platform/system provider cost directly instead of computing by subtraction.
    # The old approach (leaflet_cost - provider_cost) produced negative values because
    # leaflet.processing_cost used hardcoded pricing while providers used real pricing.
    from app.models.platform_vlm_provider import PlatformVLMProvider

    platform_result = await db.execute(
        select(PlatformVLMProvider).where(
            PlatformVLMProvider.is_active == True
        )
    )
    platform_providers = platform_result.scalars().all()

    system_cost = 0.0
    system_tokens = 0
    system_requests = 0
    system_month_spent = 0.0
    for pp in platform_providers:
        system_cost += float(pp.total_spent or 0)
        system_tokens += (pp.total_input_tokens or 0) + (pp.total_output_tokens or 0)
        system_requests += (pp.total_requests or 0)
        system_month_spent += float(pp.current_month_spent or 0)

    if system_tokens > 0 or system_cost > 0:
        provider_breakdown.insert(0, {
            "name": "System API Key (Fallback)",
            "provider_type": "system",
            "total_requests": system_requests,
            "total_tokens": system_tokens,
            "total_spent": round(system_cost, 4),
            "current_month_spent": round(system_month_spent, 4),
        })

    # Derive total cost from provider records (not from leaflet.processing_cost)
    total_provider_cost = sum(p["total_spent"] for p in provider_breakdown)

    return UsageStatsResponse(
        total_leaflets=int(leaflet_stats.total_leaflets or 0),
        total_products=total_products,
        total_input_tokens=estimated_input_tokens,
        total_output_tokens=estimated_output_tokens,
        total_tokens=total_tokens,
        estimated_cost=round(total_provider_cost, 4),
        this_month_leaflets=int(month_stats.month_leaflets or 0),
        this_month_cost=round(float(month_stats.month_cost or 0), 4),
        average_tokens_per_page=round(avg_tokens_per_page, 2),
        provider_breakdown=provider_breakdown,
    )


@router.get(
    "/usage/costs",
    response_model=VLMCostResponse,
    summary="Query VLM costs with date range",
    description=(
        "Retrieve aggregated VLM cost and usage metrics for a date range. "
        "Supports preset periods (last_7_days, this_month, etc.) or custom date ranges. "
        "Data is sourced from the organization_vlm_usage table which contains "
        "per-hour usage rollups. Results include a summary, per-provider breakdown, "
        "and a time series at the requested granularity (day/week/month)."
    ),
)
async def get_usage_costs(
    period: CostPeriod = Query(
        default=CostPeriod.THIS_MONTH,
        description="Preset period or 'custom' for an explicit date range.",
    ),
    start_date: Optional[date] = Query(
        default=None,
        description="Inclusive start date (ISO 8601, YYYY-MM-DD). Required when period=custom.",
    ),
    end_date: Optional[date] = Query(
        default=None,
        description="Inclusive end date (ISO 8601, YYYY-MM-DD). Required when period=custom.",
    ),
    group_by: CostGroupBy = Query(
        default=CostGroupBy.DAY,
        description="Granularity for the breakdown time series: day, week, or month.",
    ),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMCostResponse:
    """
    Query VLM costs with date range filtering.

    Aggregates data from organization_vlm_usage rows for the authenticated
    organization. Returns summary totals, per-provider breakdown, and a
    time series at the requested granularity.

    **Caching:** Completed calendar months are immutable and cached for 24 hours.
    Periods that include today are cached for 5 minutes.
    """
    # --- Validate and resolve dates ---
    try:
        params = CostQueryParams(
            period=period,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )
    except PydanticValidationError as e:
        errors = []
        for err in e.errors():
            field_name = err["loc"][-1] if err["loc"] else "unknown"
            errors.append({"field": str(field_name), "message": err["msg"]})
        raise ValidationException(
            errors=errors,
            message="Invalid cost query parameters",
        )

    resolved_start, resolved_end = params.resolve_dates()

    # --- Check cache ---
    today = date.today()
    first_of_month = today.replace(day=1)
    is_immutable_period = resolved_end < first_of_month
    cache_ttl = 86400 if is_immutable_period else 300  # 24h vs 5min

    cache_key = (
        f"vlm_costs:{current_org.id}:{period.value}"
        f":{resolved_start.isoformat()}:{resolved_end.isoformat()}"
        f":{group_by.value}"
    )
    cached = await get_cache(cache_key)
    if cached and isinstance(cached, dict):
        return VLMCostResponse(**cached)

    # --- Base filter: organization + date range ---
    base_filter = and_(
        OrganizationVLMUsage.organization_id == current_org.id,
        OrganizationVLMUsage.usage_date >= resolved_start,
        OrganizationVLMUsage.usage_date <= resolved_end,
    )

    # --- 1. Summary aggregation ---
    summary_query = select(
        func.coalesce(func.sum(OrganizationVLMUsage.total_cost), 0).label("total_cost"),
        func.coalesce(func.sum(OrganizationVLMUsage.request_count), 0).label("total_requests"),
        func.coalesce(func.sum(OrganizationVLMUsage.input_tokens), 0).label("total_input_tokens"),
        func.coalesce(func.sum(OrganizationVLMUsage.output_tokens), 0).label("total_output_tokens"),
        func.coalesce(func.sum(OrganizationVLMUsage.leaflet_count), 0).label("leaflets_processed"),
        func.coalesce(func.sum(OrganizationVLMUsage.page_count), 0).label("pages_processed"),
        func.coalesce(func.sum(OrganizationVLMUsage.product_count), 0).label("products_extracted"),
    ).where(base_filter)

    summary_result = await db.execute(summary_query)
    s = summary_result.one()

    total_cost_val = float(s.total_cost)
    total_requests_val = int(s.total_requests)
    total_input_tokens_val = int(s.total_input_tokens)
    total_output_tokens_val = int(s.total_output_tokens)
    leaflets_val = int(s.leaflets_processed)

    summary = CostSummary(
        total_cost=round(total_cost_val, 4),
        total_requests=total_requests_val,
        total_input_tokens=total_input_tokens_val,
        total_output_tokens=total_output_tokens_val,
        total_tokens=total_input_tokens_val + total_output_tokens_val,
        leaflets_processed=leaflets_val,
        pages_processed=int(s.pages_processed),
        products_extracted=int(s.products_extracted),
        avg_cost_per_leaflet=(
            round(total_cost_val / leaflets_val, 4) if leaflets_val > 0 else 0.0
        ),
        avg_cost_per_request=(
            round(total_cost_val / total_requests_val, 4) if total_requests_val > 0 else 0.0
        ),
    )

    # --- 2. Per-provider breakdown ---
    provider_query = (
        select(
            OrganizationVLMUsage.platform_provider_id,
            func.sum(OrganizationVLMUsage.total_cost).label("cost"),
            func.sum(OrganizationVLMUsage.request_count).label("requests"),
            func.sum(OrganizationVLMUsage.input_tokens).label("input_tokens"),
            func.sum(OrganizationVLMUsage.output_tokens).label("output_tokens"),
        )
        .where(base_filter)
        .group_by(OrganizationVLMUsage.platform_provider_id)
        .order_by(func.sum(OrganizationVLMUsage.total_cost).desc())
    )
    provider_result = await db.execute(provider_query)
    provider_rows = provider_result.all()

    # Fetch provider details for display names
    provider_ids = [
        row.platform_provider_id
        for row in provider_rows
        if row.platform_provider_id is not None
    ]
    provider_map: dict = {}
    if provider_ids:
        prov_result = await db.execute(
            select(PlatformVLMProvider).where(PlatformVLMProvider.id.in_(provider_ids))
        )
        for p in prov_result.scalars().all():
            provider_map[p.id] = p

    by_provider: List[CostByProvider] = []
    for row in provider_rows:
        prov_cost = float(row.cost or 0)
        prov_input = int(row.input_tokens or 0)
        prov_output = int(row.output_tokens or 0)
        prov_obj = provider_map.get(row.platform_provider_id)

        by_provider.append(CostByProvider(
            provider_id=(
                str(row.platform_provider_id) if row.platform_provider_id else None
            ),
            provider_name=prov_obj.name if prov_obj else "Deleted Provider",
            provider_type=(
                prov_obj.provider_type.value if prov_obj else "unknown"
            ),
            cost=round(prov_cost, 4),
            requests=int(row.requests or 0),
            input_tokens=prov_input,
            output_tokens=prov_output,
            tokens=prov_input + prov_output,
            percentage_of_total=(
                round((prov_cost / total_cost_val) * 100, 1)
                if total_cost_val > 0
                else 0.0
            ),
        ))

    # --- 3. Time-series breakdown ---
    if group_by == CostGroupBy.DAY:
        time_bucket = OrganizationVLMUsage.usage_date.label("bucket")
    elif group_by == CostGroupBy.WEEK:
        time_bucket = func.date_trunc(
            "week", OrganizationVLMUsage.usage_date
        ).cast(Date).label("bucket")
    else:  # MONTH
        time_bucket = func.date_trunc(
            "month", OrganizationVLMUsage.usage_date
        ).cast(Date).label("bucket")

    breakdown_query = (
        select(
            time_bucket,
            func.sum(OrganizationVLMUsage.total_cost).label("cost"),
            func.sum(OrganizationVLMUsage.request_count).label("requests"),
            func.sum(
                OrganizationVLMUsage.input_tokens + OrganizationVLMUsage.output_tokens
            ).label("tokens"),
            func.sum(OrganizationVLMUsage.leaflet_count).label("leaflets"),
        )
        .where(base_filter)
        .group_by("bucket")
        .order_by("bucket")
    )
    breakdown_result = await db.execute(breakdown_query)
    breakdown_rows = breakdown_result.all()

    daily_breakdown = [
        CostBreakdownPoint(
            date=row.bucket,
            cost=round(float(row.cost or 0), 4),
            requests=int(row.requests or 0),
            tokens=int(row.tokens or 0),
            leaflets=int(row.leaflets or 0),
        )
        for row in breakdown_rows
    ]

    # --- 4. Build period info ---
    period_info = CostPeriodInfo(
        start_date=resolved_start,
        end_date=resolved_end,
        period_type=period,
        label=_generate_period_label(period, resolved_start, resolved_end),
    )

    response = VLMCostResponse(
        period=period_info,
        summary=summary,
        by_provider=by_provider,
        daily_breakdown=daily_breakdown,
    )

    # --- 5. Cache the result ---
    await set_cache(cache_key, response.model_dump(mode="json"), ttl=cache_ttl)

    return response


def _generate_period_label(
    period: CostPeriod, start: date, end: date
) -> str:
    """Generate a human-readable label for the resolved period."""
    if period == CostPeriod.LAST_7_DAYS:
        return "Last 7 days"
    if period == CostPeriod.LAST_30_DAYS:
        return "Last 30 days"
    if period == CostPeriod.THIS_MONTH:
        return start.strftime("%B %Y")
    if period == CostPeriod.LAST_MONTH:
        return start.strftime("%B %Y")
    if period == CostPeriod.THIS_YEAR:
        return str(start.year)
    if period == CostPeriod.ALL_TIME:
        return "All time"
    # CUSTOM
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%b %d')} \u2013 {end.strftime('%b %d, %Y')}"
    return f"{start.strftime('%b %d, %Y')} \u2013 {end.strftime('%b %d, %Y')}"


@router.get(
    "/{provider_id}",
    response_model=VLMProviderResponse,
    summary="Get VLM provider",
    description="Get details for a specific VLM provider.",
)
async def get_vlm_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMProviderResponse:
    """Get VLM provider details."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    return _provider_to_response(provider)


@router.get(
    "/{provider_id}/stats",
    response_model=VLMProviderUsageStats,
    summary="Get provider usage stats",
    description="Get usage statistics for a VLM provider.",
)
async def get_provider_stats(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMProviderUsageStats:
    """Get VLM provider usage statistics."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    budget_remaining = None
    budget_usage_percent = None

    total_spent_f = float(provider.total_spent or 0)
    month_spent_f = float(provider.current_month_spent or 0)

    if provider.monthly_budget:
        budget_f = float(provider.monthly_budget)
        budget_remaining = max(0.0, budget_f - month_spent_f)
        budget_usage_percent = (month_spent_f / budget_f) * 100 if budget_f else 0.0

    return VLMProviderUsageStats(
        total_requests=provider.total_requests,
        total_input_tokens=provider.total_input_tokens,
        total_output_tokens=provider.total_output_tokens,
        total_cost=round(total_spent_f, 4),
        current_month_cost=round(month_spent_f, 4),
        budget_remaining=round(budget_remaining, 4) if budget_remaining is not None else None,
        budget_usage_percent=round(budget_usage_percent, 1) if budget_usage_percent is not None else None,
    )


@router.patch(
    "/{provider_id}",
    response_model=VLMProviderResponse,
    summary="Update VLM provider",
    description="Update VLM provider settings.",
)
async def update_vlm_provider(
    provider_id: UUID,
    provider_data: VLMProviderUpdate,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMProviderResponse:
    """Update VLM provider settings."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    # Update fields
    if provider_data.name is not None:
        provider.name = provider_data.name
    if provider_data.api_key is not None:
        provider.set_api_key(provider_data.api_key)
    if provider_data.api_endpoint is not None:
        provider.api_endpoint = provider_data.api_endpoint
    if provider_data.model_name is not None:
        provider.model_name = provider_data.model_name
    if provider_data.max_tokens is not None:
        provider.max_tokens = provider_data.max_tokens
    if provider_data.temperature is not None:
        provider.temperature = provider_data.temperature
    if provider_data.monthly_budget is not None:
        provider.monthly_budget = provider_data.monthly_budget
    if provider_data.is_active is not None:
        provider.is_active = provider_data.is_active
    if provider_data.config is not None:
        provider.config = provider_data.config
    
    await db.commit()
    await db.refresh(provider)
    
    logger.info(f"User {current_user.email} updated VLM provider: {provider.name}")
    
    return _provider_to_response(provider)


@router.put(
    "/{provider_id}/default",
    response_model=VLMProviderResponse,
    summary="Set as default",
    description="Set a VLM provider as the default.",
)
async def set_default_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> VLMProviderResponse:
    """Set a VLM provider as the default."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    if not provider.is_active:
        raise ValidationException(
            [{"field": "is_active", "message": "Cannot set inactive provider as default"}],
            message="Cannot set inactive provider as default",
        )
    
    # Clear other defaults
    await _clear_default_provider(db, current_org.id)
    
    # Set this as default
    provider.is_default = True
    await db.commit()
    await db.refresh(provider)
    
    logger.info(f"User {current_user.email} set default VLM provider: {provider.name}")
    
    return _provider_to_response(provider)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete VLM provider",
    description="Delete a VLM provider configuration.",
)
async def delete_vlm_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Delete a VLM provider configuration."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    name = provider.name
    was_default = provider.is_default
    
    await db.delete(provider)
    await db.commit()
    
    # If we deleted the default provider, set a new one
    if was_default:
        remaining_result = await db.execute(
            select(VLMProvider).where(
                VLMProvider.organization_id == current_org.id,
                VLMProvider.is_active == True,
            ).order_by(VLMProvider.created_at.desc()).limit(1)
        )
        new_default = remaining_result.scalar_one_or_none()
        
        if new_default:
            new_default.is_default = True
            await db.commit()
            logger.info(
                f"Auto-set '{new_default.name}' as new default after deleting '{name}'"
            )
    
    logger.info(f"User {current_user.email} deleted VLM provider: {name}")


@router.post(
    "/{provider_id}/test",
    summary="Test VLM provider",
    description="Test the VLM provider connection.",
)
async def test_vlm_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test VLM provider connection."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    try:
        api_key = provider.get_api_key()
        
        # Test based on provider type
        if provider.provider_type == VLMProviderType.ANTHROPIC:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            # Simple API call to test
            response = client.messages.create(
                model=provider.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {
                "success": True,
                "message": "Connection successful",
                "model": provider.model_name,
            }
        
        elif provider.provider_type == VLMProviderType.OPENAI:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=provider.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {
                "success": True,
                "message": "Connection successful",
                "model": provider.model_name,
            }
        
        elif provider.provider_type == VLMProviderType.GOOGLE:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(provider.model_name)
            response = model.generate_content("Hi")
            return {
                "success": True,
                "message": "Connection successful",
                "model": provider.model_name,
            }
        
        elif provider.provider_type == VLMProviderType.AZURE_OPENAI:
            if not provider.api_endpoint:
                return {
                    "success": False,
                    "message": "Azure OpenAI requires an API endpoint to be configured",
                }
            import openai
            client = openai.AzureOpenAI(
                api_key=api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=provider.api_endpoint,
            )
            response = client.chat.completions.create(
                model=provider.model_name,  # Deployment name
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {
                "success": True,
                "message": "Connection successful",
                "model": provider.model_name,
            }
        
        elif provider.provider_type == VLMProviderType.AWS_BEDROCK:
            import boto3
            import json
            
            config = provider.config or {}
            client = boto3.client(
                "bedrock-runtime",
                region_name=config.get("aws_region", "us-east-1"),
                aws_access_key_id=config.get("aws_access_key_id") or api_key,
                aws_secret_access_key=config.get("aws_secret_access_key"),
            )
            
            # Test with a simple message
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
            }
            
            response = client.invoke_model(
                modelId=provider.model_name,
                body=json.dumps(body),
            )
            
            return {
                "success": True,
                "message": "Connection successful",
                "model": provider.model_name,
            }
        
        else:
            return {
                "success": False,
                "message": f"Testing not implemented for {provider.provider_type.value}",
            }
    
    except ImportError as e:
        return {
            "success": False,
            "message": f"Required package not installed: {str(e)}. Please install the appropriate SDK.",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
        }


@router.post(
    "/{provider_id}/reset-monthly",
    summary="Reset monthly spending",
    description="Reset the monthly spending counter.",
)
async def reset_monthly_spending(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset monthly spending counter."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.id == provider_id,
            VLMProvider.organization_id == current_org.id,
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise NotFoundError("VLM Provider", str(provider_id))
    
    old_spent = float(provider.current_month_spent or 0)
    provider.reset_monthly_spent()
    await db.commit()

    logger.info(
        f"User {current_user.email} reset monthly spending for {provider.name}: "
        f"${old_spent:.4f} -> $0.00"
    )

    return {
        "message": "Monthly spending reset successfully",
        "previous_spent": round(old_spent, 4),
    }


async def _clear_default_provider(db: AsyncSession, organization_id: UUID):
    """Clear default flag from all organization's providers."""
    result = await db.execute(
        select(VLMProvider).where(
            VLMProvider.organization_id == organization_id,
            VLMProvider.is_default == True,
        )
    )
    for provider in result.scalars().all():
        provider.is_default = False


def _provider_to_response(provider: VLMProvider) -> VLMProviderResponse:
    """Convert provider to response schema.

    Explicitly converts Decimal cost fields to float for JSON serialization.
    """
    return VLMProviderResponse(
        id=provider.id,
        provider_type=provider.provider_type.value,
        name=provider.name,
        provider_display_name=provider.provider_display_name,
        api_endpoint=provider.api_endpoint,
        model_name=provider.model_name,
        max_tokens=provider.max_tokens,
        temperature=provider.temperature,
        is_default=provider.is_default,
        is_active=provider.is_active,
        monthly_budget=float(provider.monthly_budget) if provider.monthly_budget is not None else None,
        total_spent=float(provider.total_spent or 0),
        current_month_spent=float(provider.current_month_spent or 0),
        total_requests=provider.total_requests,
        total_input_tokens=provider.total_input_tokens,
        total_output_tokens=provider.total_output_tokens,
        last_used_at=provider.last_used_at,
        masked_api_key=provider.get_masked_api_key(),
        created_at=provider.created_at,
    )