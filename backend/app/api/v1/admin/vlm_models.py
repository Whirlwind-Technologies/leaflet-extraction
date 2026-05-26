"""
Admin API endpoints for managing VLM Models.

This module provides CRUD endpoints for managing the VLM model registry,
allowing superusers to add, update, and remove available models without code changes.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_superuser
from app.models.user import User
from app.models.vlm_model import VLMModel
from app.schemas.vlm_model import (
    VLMModelCreate,
    VLMModelUpdate,
    VLMModelResponse,
    VLMModelListResponse,
    VLMProviderTypeInfo,
    VLMProviderTypesResponse,
    VLMModelSimple,
)

router = APIRouter(prefix="/vlm-models", tags=["admin-vlm-models"])


# Provider type display names
PROVIDER_DISPLAY_NAMES = {
    "anthropic": "Anthropic Claude",
    "openai": "OpenAI",
    "google": "Google Gemini",
    "azure_openai": "Azure OpenAI",
    "aws_bedrock": "AWS Bedrock",
    "custom": "Custom Provider",
}

PROVIDER_DESCRIPTIONS = {
    "anthropic": "Anthropic's Claude models with excellent vision and reasoning capabilities",
    "openai": "OpenAI's GPT models with strong general-purpose performance",
    "google": "Google's Gemini models with large context windows",
    "azure_openai": "OpenAI models deployed on Microsoft Azure",
    "aws_bedrock": "Foundation models via AWS Bedrock service",
    "custom": "Custom or self-hosted models",
}


@router.get(
    "/",
    response_model=VLMModelListResponse,
    summary="List all VLM models",
    description="Get all VLM models in the registry. Superuser only.",
)
async def list_vlm_models(
    provider_type: Optional[str] = Query(None, description="Filter by provider type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """List all VLM models in the registry."""

    # Build query
    query = select(VLMModel)

    if provider_type:
        query = query.where(VLMModel.provider_type == provider_type)

    if is_active is not None:
        query = query.where(VLMModel.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Add ordering and pagination
    query = query.order_by(VLMModel.provider_type, VLMModel.sort_order, VLMModel.display_name)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    models = result.scalars().all()

    return VLMModelListResponse(
        items=[VLMModelResponse.model_validate(m) for m in models],
        total=total,
    )


@router.get(
    "/providers",
    response_model=VLMProviderTypesResponse,
    summary="Get all provider types with their models",
    description="Get all provider types and their available models. This is the primary endpoint for populating model selection dropdowns.",
)
async def get_provider_types(
    include_inactive: bool = Query(False, description="Include inactive models"),
    include_deprecated: bool = Query(False, description="Include deprecated models"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all provider types with their available models."""

    # Build query for active models
    query = select(VLMModel).order_by(VLMModel.provider_type, VLMModel.sort_order)

    if not include_inactive:
        query = query.where(VLMModel.is_active == True)

    if not include_deprecated:
        query = query.where(VLMModel.is_deprecated == False)

    result = await db.execute(query)
    all_models = result.scalars().all()

    # Group models by provider type
    providers_dict = {}
    for model in all_models:
        if model.provider_type not in providers_dict:
            providers_dict[model.provider_type] = {
                "models": [],
                "default_model_id": None,
            }

        providers_dict[model.provider_type]["models"].append(
            VLMModelSimple(
                model_id=model.model_id,
                display_name=model.display_name,
                is_default=model.is_default,
                is_deprecated=model.is_deprecated,
                input_cost_per_1m=model.input_cost_per_1m,
                output_cost_per_1m=model.output_cost_per_1m,
            )
        )

        if model.is_default:
            providers_dict[model.provider_type]["default_model_id"] = model.model_id

    # Build response
    providers = []
    for provider_type in ["anthropic", "openai", "google", "azure_openai", "aws_bedrock", "custom"]:
        if provider_type in providers_dict:
            providers.append(
                VLMProviderTypeInfo(
                    provider_type=provider_type,
                    display_name=PROVIDER_DISPLAY_NAMES.get(provider_type, provider_type.title()),
                    description=PROVIDER_DESCRIPTIONS.get(provider_type),
                    models=providers_dict[provider_type]["models"],
                    default_model_id=providers_dict[provider_type]["default_model_id"],
                )
            )

    return VLMProviderTypesResponse(providers=providers)


@router.get(
    "/{model_id}",
    response_model=VLMModelResponse,
    summary="Get a VLM model by ID",
    description="Get details of a specific VLM model. Superuser only.",
)
async def get_vlm_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Get a VLM model by its UUID."""

    result = await db.execute(select(VLMModel).where(VLMModel.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VLM model not found",
        )

    return VLMModelResponse.model_validate(model)


@router.post(
    "/",
    response_model=VLMModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new VLM model",
    description="Add a new model to the registry. Superuser only.",
)
async def create_vlm_model(
    model_data: VLMModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Create a new VLM model in the registry."""

    # Check if model already exists
    existing = await db.execute(
        select(VLMModel).where(
            VLMModel.provider_type == model_data.provider_type,
            VLMModel.model_id == model_data.model_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model {model_data.model_id} already exists for provider {model_data.provider_type}",
        )

    # If this is set as default, unset other defaults for this provider
    if model_data.is_default:
        await db.execute(
            select(VLMModel)
            .where(
                VLMModel.provider_type == model_data.provider_type,
                VLMModel.is_default == True,
            )
        )
        # Update any existing defaults
        result = await db.execute(
            select(VLMModel).where(
                VLMModel.provider_type == model_data.provider_type,
                VLMModel.is_default == True,
            )
        )
        for existing_default in result.scalars().all():
            existing_default.is_default = False

    # Create the model
    model = VLMModel(**model_data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)

    return VLMModelResponse.model_validate(model)


@router.patch(
    "/{model_id}",
    response_model=VLMModelResponse,
    summary="Update a VLM model",
    description="Update an existing model in the registry. Superuser only.",
)
async def update_vlm_model(
    model_id: UUID,
    model_data: VLMModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Update a VLM model in the registry."""

    result = await db.execute(select(VLMModel).where(VLMModel.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VLM model not found",
        )

    # If setting as default, unset other defaults for this provider
    if model_data.is_default is True and not model.is_default:
        result = await db.execute(
            select(VLMModel).where(
                VLMModel.provider_type == model.provider_type,
                VLMModel.is_default == True,
                VLMModel.id != model_id,
            )
        )
        for existing_default in result.scalars().all():
            existing_default.is_default = False

    # Update fields
    update_data = model_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)

    await db.commit()
    await db.refresh(model)

    return VLMModelResponse.model_validate(model)


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a VLM model",
    description="Remove a model from the registry. Superuser only.",
)
async def delete_vlm_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Delete a VLM model from the registry."""

    result = await db.execute(select(VLMModel).where(VLMModel.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VLM model not found",
        )

    await db.delete(model)
    await db.commit()


@router.post(
    "/{model_id}/set-default",
    response_model=VLMModelResponse,
    summary="Set a model as default for its provider",
    description="Set a model as the default for its provider type. Superuser only.",
)
async def set_default_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Set a model as the default for its provider type."""

    result = await db.execute(select(VLMModel).where(VLMModel.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VLM model not found",
        )

    if not model.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set an inactive model as default",
        )

    # Unset other defaults for this provider
    result = await db.execute(
        select(VLMModel).where(
            VLMModel.provider_type == model.provider_type,
            VLMModel.is_default == True,
            VLMModel.id != model_id,
        )
    )
    for existing_default in result.scalars().all():
        existing_default.is_default = False

    model.is_default = True
    await db.commit()
    await db.refresh(model)

    return VLMModelResponse.model_validate(model)


@router.post(
    "/{model_id}/deprecate",
    response_model=VLMModelResponse,
    summary="Mark a model as deprecated",
    description="Mark a model as deprecated, optionally specifying a replacement. Superuser only.",
)
async def deprecate_model(
    model_id: UUID,
    replacement_model_id: Optional[str] = Query(None, description="Model ID to recommend as replacement"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Mark a model as deprecated."""

    result = await db.execute(select(VLMModel).where(VLMModel.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VLM model not found",
        )

    model.is_deprecated = True
    model.replacement_model_id = replacement_model_id

    # If this was the default, try to set the replacement as default
    if model.is_default and replacement_model_id:
        result = await db.execute(
            select(VLMModel).where(
                VLMModel.provider_type == model.provider_type,
                VLMModel.model_id == replacement_model_id,
            )
        )
        replacement = result.scalar_one_or_none()
        if replacement and replacement.is_active:
            model.is_default = False
            replacement.is_default = True

    await db.commit()
    await db.refresh(model)

    return VLMModelResponse.model_validate(model)
