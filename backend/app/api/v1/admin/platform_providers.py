"""
Super Admin API endpoints for Platform VLM Provider Management.

These endpoints are restricted to super admins only and provide full control
over the platform-level VLM providers used as fallbacks for organizations.

Features:
- CRUD operations for platform providers
- Priority management and provider ordering
- Budget configuration and monitoring
- Provider testing and health checks
- Bulk operations for provider management

Security:
- Super admin access required for all endpoints
- Audit logging for all operations
- API key encryption/decryption handling
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc

from app.api.deps import get_db, get_current_superuser
from app.models.user import User
from app.models.platform_vlm_provider import (
    PlatformVLMProvider,
    PlatformVLMProviderType,
    PLATFORM_DEFAULT_MODELS
)
from app.models.organization_usage import OrganizationVLMUsage
from app.services.platform_vlm_service import PlatformVLMProviderService
from app.services.vlm_audit_service import VLMAuditService
from app.core.extraction.multi_provider_client import MultiProviderVLMClient, ProviderNotSupportedError
from app.schemas.platform_vlm import (
    PlatformProviderCreate,
    PlatformProviderUpdate,
    PlatformProviderResponse,
    PlatformProviderListResponse,
    ProviderTestResponse,
    ProviderStatsResponse,
    BulkProviderOperation,
    ProviderHealthCheck
)

router = APIRouter()


@router.get("", response_model=PlatformProviderListResponse)
async def list_platform_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    provider_type: Optional[PlatformVLMProviderType] = Query(None, description="Filter by provider type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    order_by: str = Query("priority", description="Order by field (priority, created_at, name)"),
    order_dir: str = Query("asc", description="Order direction (asc, desc)"),
) -> PlatformProviderListResponse:
    """
    List all platform VLM providers with filtering and pagination.

    Super admin only endpoint for viewing all platform providers.
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    # Build query
    query = select(PlatformVLMProvider)

    if provider_type:
        query = query.where(PlatformVLMProvider.provider_type == provider_type)
    if is_active is not None:
        query = query.where(PlatformVLMProvider.is_active == is_active)

    # Order by
    order_column = getattr(PlatformVLMProvider, order_by, PlatformVLMProvider.priority)
    if order_dir == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(asc(order_column))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    providers = result.scalars().all()

    # Log admin access
    audit_service.log_admin_access(
        admin_user_id=user_id,
        action="list_platform_providers",
        resource_type="platform_providers",
        filters={
            "provider_type": provider_type.value if provider_type else None,
            "is_active": is_active,
            "limit": limit,
            "skip": skip,
        }
    )

    return PlatformProviderListResponse(
        providers=[PlatformProviderResponse.from_orm(p) for p in providers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PlatformProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_provider(
    provider_data: PlatformProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> PlatformProviderResponse:
    """
    Create a new platform VLM provider.

    Super admin only endpoint for adding new platform providers.
    """
    # Capture user ID early to avoid lazy loading issues after DB operations
    user_id = current_user.id

    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    try:
        # Get default values for this provider type
        provider_defaults = PLATFORM_DEFAULT_MODELS.get(provider_data.provider_type, {})

        # Create provider
        provider = PlatformVLMProvider(
            name=provider_data.name,
            provider_type=provider_data.provider_type,
            model_name=provider_data.model_name or provider_defaults.get("model_name", ""),
            api_endpoint=provider_data.api_endpoint,
            priority=provider_data.priority,
            monthly_budget=provider_data.monthly_budget,
            daily_budget=provider_data.daily_budget,
            max_requests_per_hour=provider_data.hourly_rate_limit or provider_defaults.get("max_requests_per_hour", 1000),
            max_tokens=provider_data.max_tokens or provider_defaults.get("max_tokens", 8192),
            temperature=provider_data.temperature or provider_defaults.get("temperature", 0.1),
            config=provider_data.config or {},
            is_active=provider_data.is_active,
            created_by_user_id=user_id,
        )

        # Set API key using the model's encryption method
        provider.set_api_key(provider_data.api_key)

        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        # Log creation
        audit_service.log_admin_action(
            admin_user_id=user_id,
            action="create_platform_provider",
            resource_type="platform_provider",
            resource_id=provider.id,
            resource_data={
                "name": provider.name,
                "provider_type": provider.provider_type.value,
                "model_name": provider.model_name,
                "priority": provider.priority,
                "monthly_budget": provider.monthly_budget,
                "daily_budget": provider.daily_budget,
            }
        )

        return PlatformProviderResponse.from_orm(provider)

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action="create_platform_provider",
            error_message=str(e),
            request_data=provider_data.dict(exclude={"api_key"})
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create platform provider: {str(e)}"
        )


@router.get("/{provider_id}", response_model=PlatformProviderResponse)
async def get_platform_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> PlatformProviderResponse:
    """
    Get a specific platform provider by ID.
    """
    user_id = current_user.id
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    # Log access
    audit_service.log_admin_access(
        admin_user_id=user_id,
        action="get_platform_provider",
        resource_type="platform_provider",
        resource_id=provider_id,
    )

    return PlatformProviderResponse.from_orm(provider)


@router.put("/{provider_id}", response_model=PlatformProviderResponse)
async def update_platform_provider(
    provider_id: UUID,
    provider_data: PlatformProviderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> PlatformProviderResponse:
    """
    Update an existing platform provider.
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    try:
        # Track changes for audit
        changes = {}
        update_data = provider_data.dict(exclude_unset=True)

        # Map schema fields to model fields
        field_mapping = {
            "hourly_rate_limit": "max_requests_per_hour",
        }

        for field, value in update_data.items():
            if field == "api_key" and value:
                # Encrypt new API key using the model's method
                provider.set_api_key(value)
                changes["api_key"] = "*** updated ***"
            elif field != "api_key":
                # Map field name if needed
                model_field = field_mapping.get(field, field)
                if hasattr(provider, model_field):
                    old_value = getattr(provider, model_field)
                    if old_value != value:
                        setattr(provider, model_field, value)
                        changes[field] = {"from": old_value, "to": value}

        provider.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(provider)

        # Log update
        audit_service.log_admin_action(
            admin_user_id=user_id,
            action="update_platform_provider",
            resource_type="platform_provider",
            resource_id=provider_id,
            resource_data={
                "changes": changes,
                "provider_name": provider.name,
            }
        )

        return PlatformProviderResponse.from_orm(provider)

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action="update_platform_provider",
            error_message=str(e),
            resource_id=provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update platform provider: {str(e)}"
        )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    force: bool = Query(False, description="Force deletion even if provider has usage"),
):
    """
    Delete a platform provider.

    By default, prevents deletion if the provider has recorded usage.
    Use force=true to override this protection.
    """
    user_id = current_user.id
    user_email = current_user.email
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    # Check for existing usage unless forced
    if not force:
        usage_result = await db.execute(
            select(func.count()).where(OrganizationVLMUsage.platform_provider_id == provider_id)
        )
        usage_count = usage_result.scalar()

        if usage_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete provider with {usage_count} usage records. Use force=true to override."
            )

    try:
        provider_name = provider.name
        provider_type = provider.provider_type.value

        await db.delete(provider)
        await db.commit()

        # Log deletion
        audit_service.log_admin_action(
            admin_user_id=user_id,
            action="delete_platform_provider",
            resource_type="platform_provider",
            resource_id=provider_id,
            resource_data={
                "provider_name": provider_name,
                "provider_type": provider_type,
                "forced": force,
            }
        )

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action="delete_platform_provider",
            error_message=str(e),
            resource_id=provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete platform provider: {str(e)}"
        )


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
async def test_platform_provider(
    provider_id: UUID,
    test_prompt: str = Body("Hello, this is a test. Please respond briefly.", embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> ProviderTestResponse:
    """
    Test a platform provider's API connectivity and functionality.
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    try:
        # Test the provider
        client = MultiProviderVLMClient(provider)

        # Simple text completion test
        start_time = datetime.utcnow()
        test_result = await client.test_connection(test_prompt=test_prompt)
        end_time = datetime.utcnow()

        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Log test
        audit_service.log_admin_action(
            admin_user_id=user_id,
            action="test_platform_provider",
            resource_type="platform_provider",
            resource_id=provider_id,
            resource_data={
                "provider_name": provider.name,
                "test_successful": test_result.get("success", False),
                "response_time_ms": response_time_ms,
                "test_prompt_length": len(test_prompt),
            }
        )

        return ProviderTestResponse(
            provider_id=provider_id,
            provider_name=provider.name,
            success=test_result.get("success", False),
            response_time_ms=response_time_ms,
            response_text=test_result.get("content", ""),
            tokens_used=test_result.get("tokens", 0),
            cost_estimate=test_result.get("cost", 0.0),
            error_message=test_result.get("error"),
            tested_at=start_time,
        )

    except ProviderNotSupportedError as e:
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action="test_platform_provider",
            error_message=f"Provider not supported: {str(e)}",
            resource_id=provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider not supported: {str(e)}"
        )
    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action="test_platform_provider",
            error_message=str(e),
            resource_id=provider_id,
        )

        return ProviderTestResponse(
            provider_id=provider_id,
            provider_name=provider.name,
            success=False,
            response_time_ms=0,
            response_text="",
            tokens_used=0,
            cost_estimate=0.0,
            error_message=str(e),
            tested_at=datetime.utcnow(),
        )


@router.get("/{provider_id}/stats", response_model=ProviderStatsResponse)
async def get_provider_stats(
    provider_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days for stats"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> ProviderStatsResponse:
    """
    Get usage statistics for a platform provider.
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    # Get usage stats
    stats = service.get_provider_stats(provider_id, days=days)

    # Log stats access
    audit_service.log_admin_access(
        admin_user_id=user_id,
        action="get_provider_stats",
        resource_type="platform_provider",
        resource_id=provider_id,
        filters={"days": days}
    )

    return ProviderStatsResponse(
        provider_id=provider_id,
        provider_name=provider.name,
        stats_period_days=days,
        **stats
    )


@router.post("/{provider_id}/health-check", response_model=ProviderHealthCheck)
async def check_provider_health(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> ProviderHealthCheck:
    """
    Perform a comprehensive health check on a platform provider.
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    result = await db.execute(
        select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform provider not found"
        )

    # Perform health check
    health_data = service.check_provider_health(provider_id)

    # Log health check
    audit_service.log_admin_action(
        admin_user_id=user_id,
        action="health_check_platform_provider",
        resource_type="platform_provider",
        resource_id=provider_id,
        resource_data={
            "provider_name": provider.name,
            "health_status": health_data.get("status", "unknown"),
            "issues_found": len(health_data.get("issues", [])),
        }
    )

    return ProviderHealthCheck(
        provider_id=provider_id,
        provider_name=provider.name,
        checked_at=datetime.utcnow(),
        **health_data
    )


@router.post("/bulk-operations", response_model=Dict[str, Any])
async def bulk_provider_operations(
    operation: BulkProviderOperation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Perform bulk operations on multiple platform providers.

    Supported operations:
    - activate: Activate selected providers
    - deactivate: Deactivate selected providers
    - update_priority: Update priority order
    - test_all: Test connectivity for all selected providers
    """
    user_id = current_user.id
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    results = {
        "operation": operation.operation,
        "provider_ids": operation.provider_ids,
        "success_count": 0,
        "error_count": 0,
        "results": [],
        "errors": [],
    }

    try:
        for provider_id in operation.provider_ids:
            try:
                if operation.operation == "activate":
                    service.set_provider_active(provider_id, True)
                    results["results"].append({"provider_id": provider_id, "status": "activated"})

                elif operation.operation == "deactivate":
                    service.set_provider_active(provider_id, False)
                    results["results"].append({"provider_id": provider_id, "status": "deactivated"})

                elif operation.operation == "test_all":
                    test_result = await service.test_provider(provider_id)
                    results["results"].append({
                        "provider_id": provider_id,
                        "status": "tested",
                        "success": test_result.get("success", False),
                        "response_time_ms": test_result.get("response_time_ms", 0)
                    })

                elif operation.operation == "update_priority" and operation.priority_updates:
                    new_priority = operation.priority_updates.get(str(provider_id))
                    if new_priority is not None:
                        service.update_provider_priority(provider_id, new_priority)
                        results["results"].append({
                            "provider_id": provider_id,
                            "status": "priority_updated",
                            "new_priority": new_priority
                        })

                results["success_count"] += 1

            except Exception as e:
                results["errors"].append({
                    "provider_id": provider_id,
                    "error": str(e)
                })
                results["error_count"] += 1

        await db.commit()

        # Log bulk operation
        audit_service.log_admin_action(
            admin_user_id=user_id,
            action=f"bulk_operation_{operation.operation}",
            resource_type="platform_providers",
            resource_data={
                "operation": operation.operation,
                "provider_count": len(operation.provider_ids),
                "success_count": results["success_count"],
                "error_count": results["error_count"],
            }
        )

        return results

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=user_id,
            action=f"bulk_operation_{operation.operation}",
            error_message=str(e),
            request_data=operation.dict()
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bulk operation failed: {str(e)}"
        )