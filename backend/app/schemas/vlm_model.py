"""
VLM Model Schemas.

Pydantic schemas for VLM Model API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class VLMModelBase(BaseModel):
    """Base schema for VLM Model."""

    provider_type: str = Field(..., description="VLM provider type (anthropic, openai, google, etc.)")
    model_id: str = Field(..., description="Model identifier used in API calls")
    display_name: str = Field(..., description="Human-readable display name")
    description: Optional[str] = Field(None, description="Optional description of the model")
    max_tokens: int = Field(8192, description="Maximum output tokens")
    context_window: Optional[int] = Field(None, description="Maximum context window size")
    temperature_default: float = Field(0.1, description="Default temperature setting")
    input_cost_per_1m: float = Field(3.0, description="Cost per 1M input tokens in USD")
    output_cost_per_1m: float = Field(15.0, description="Cost per 1M output tokens in USD")
    supports_vision: bool = Field(True, description="Whether the model supports image input")
    supports_tools: bool = Field(False, description="Whether the model supports tool/function calling")
    is_default: bool = Field(False, description="Whether this is the default model for the provider")
    is_active: bool = Field(True, description="Whether this model is available for use")
    is_deprecated: bool = Field(False, description="Whether this model is deprecated")
    deprecation_date: Optional[datetime] = Field(None, description="When the model will be/was deprecated")
    replacement_model_id: Optional[str] = Field(None, description="Model ID to migrate to when deprecated")
    release_date: Optional[datetime] = Field(None, description="When the model was released")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Additional model capabilities")
    sort_order: int = Field(100, description="Order for display in UI (lower = higher priority)")


class VLMModelCreate(VLMModelBase):
    """Schema for creating a VLM Model."""
    pass


class VLMModelUpdate(BaseModel):
    """Schema for updating a VLM Model."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    temperature_default: Optional[float] = None
    input_cost_per_1m: Optional[float] = None
    output_cost_per_1m: Optional[float] = None
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    is_deprecated: Optional[bool] = None
    deprecation_date: Optional[datetime] = None
    replacement_model_id: Optional[str] = None
    release_date: Optional[datetime] = None
    capabilities: Optional[Dict[str, Any]] = None
    sort_order: Optional[int] = None


class VLMModelResponse(VLMModelBase):
    """Schema for VLM Model response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VLMModelListResponse(BaseModel):
    """Schema for listing VLM Models."""

    items: List[VLMModelResponse]
    total: int


class VLMModelSimple(BaseModel):
    """Simplified model info for dropdowns."""

    model_id: str
    display_name: str
    is_default: bool = False
    is_deprecated: bool = False
    input_cost_per_1m: float
    output_cost_per_1m: float

    class Config:
        from_attributes = True


class VLMProviderTypeInfo(BaseModel):
    """Info about a VLM provider type and its available models."""

    provider_type: str
    display_name: str
    description: Optional[str] = None
    models: List[VLMModelSimple]
    default_model_id: Optional[str] = None


class VLMProviderTypesResponse(BaseModel):
    """Response with all provider types and their models."""

    providers: List[VLMProviderTypeInfo]
