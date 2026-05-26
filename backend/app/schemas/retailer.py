"""
Retailer Pydantic Schemas.

This module provides request/response schemas for retailer CRUD operations.

Example Usage:
    from app.schemas.retailer import RetailerCreate, RetailerResponse

    # Create retailer
    retailer_data = RetailerCreate(
        name="SuperMart",
        country="US",
        currency="USD"
    )
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


class RetailerBase(BaseSchema):
    """
    Base retailer schema with common fields.

    Attributes:
        name: Retailer name (required)
        country: Default country code (ISO 3166-1 alpha-2)
        currency: Default currency code (ISO 4217)
        language: Default language code (ISO 639-1)
        logo_url: Optional retailer logo URL
        external_id: Optional external identifier for integrations
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Retailer name"
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Default country code (ISO 3166-1 alpha-2)"
    )
    currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Default currency code (ISO 4217)"
    )
    language: Optional[str] = Field(
        default=None,
        max_length=5,
        description="Default language code (ISO 639-1)"
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional retailer logo URL"
    )
    external_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional external identifier for integration with other systems"
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase country code."""
        if v:
            return v.upper()
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase currency code."""
        if v:
            return v.upper()
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validate and lowercase language code."""
        if v:
            return v.lower()
        return v


class RetailerCreate(RetailerBase):
    """
    Schema for creating a retailer.

    Inherits all fields from RetailerBase.
    """

    pass


class RetailerUpdate(BaseSchema):
    """
    Schema for updating a retailer.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Retailer name"
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Default country code (ISO 3166-1 alpha-2)"
    )
    currency: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Default currency code (ISO 4217)"
    )
    language: Optional[str] = Field(
        default=None,
        max_length=5,
        description="Default language code (ISO 639-1)"
    )
    logo_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional retailer logo URL"
    )
    external_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional external identifier for integration with other systems"
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether retailer is active"
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase country code."""
        if v:
            return v.upper()
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase currency code."""
        if v:
            return v.upper()
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validate and lowercase language code."""
        if v:
            return v.lower()
        return v


class RetailerResponse(RetailerBase, IDSchema, TimestampSchema):
    """
    Schema for retailer response data.

    Includes all base fields plus ID, timestamps, and organization info.
    """

    organization_id: UUID = Field(description="Organization ID")
    is_active: bool = Field(description="Whether retailer is active")


class RetailerListResponse(BaseSchema):
    """
    Schema for listing retailers.

    Used for the dropdown/select component.
    """

    id: UUID = Field(description="Unique identifier")
    name: str = Field(description="Retailer name")
    country: Optional[str] = Field(default=None, description="Default country code")
    currency: Optional[str] = Field(default=None, description="Default currency code")
    language: Optional[str] = Field(default=None, description="Default language code")
    logo_url: Optional[str] = Field(default=None, description="Logo URL")
    external_id: Optional[str] = Field(default=None, description="External identifier")
    is_active: bool = Field(description="Whether retailer is active")
