"""
Platform Quota Schemas.

This module defines Pydantic schemas for the Platform AI Provider Leaflet Limit
feature. Organizations get a limited number of free leaflet extractions using
the platform's shared AI provider. After exhausting the limit, they must
configure their own VLM provider to continue.

Enforcement is at **extraction time** (when ``extract_products_task`` starts),
NOT at upload time, so users can upload PDFs and configure a provider before
extracting.

Endpoint summary:
    GET  /api/v1/organizations/current/platform-quota
        Returns the current org's platform usage quota.

    PATCH /api/v1/admin/organizations/{org_id}
        Superuser can update org settings including ``platform_leaflet_limit``.

WebSocket message type:
    ``platform_limit_reached`` -- published when extraction is blocked.

Example Usage:
    from app.schemas.platform_quota import (
        PlatformQuotaResponse,
        PlatformQuotaErrorDetails,
        OrganizationPlatformSettingsUpdate,
    )

    # Build quota response
    response = PlatformQuotaResponse(
        limit=10, used=7, remaining=3,
        has_own_provider=False, is_unlimited=False,
    )

    # Superuser updates org limit
    update = OrganizationPlatformSettingsUpdate(platform_leaflet_limit=20)
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# GET /api/v1/organizations/current/platform-quota -- Response
# ---------------------------------------------------------------------------


class PlatformQuotaResponse(BaseModel):
    """
    Response schema for the platform AI provider usage quota.

    Returned by ``GET /api/v1/organizations/current/platform-quota``.

    When the organization has its own active VLM provider, the platform
    limit does not apply and ``is_unlimited`` is True.

    When ``platform_leaflet_limit`` on the organization is 0, the limit
    is considered unlimited (admin override) and ``is_unlimited`` is True.

    Attributes:
        limit: Maximum number of free platform extractions (0 = unlimited).
        used: Number of extractions already consumed on the platform provider.
        remaining: Extractions left before the limit is reached (null when unlimited).
        has_own_provider: Whether the org has at least one active VLM provider.
        is_unlimited: True when limit does not apply (own provider or limit=0).

    Example:
        >>> PlatformQuotaResponse(limit=10, used=7, remaining=3,
        ...     has_own_provider=False, is_unlimited=False)
    """

    limit: int = Field(
        ...,
        ge=0,
        description=(
            "Maximum number of free leaflet extractions using the platform AI provider. "
            "0 means unlimited (admin override)."
        ),
        json_schema_extra={"examples": [10]},
    )
    used: int = Field(
        ...,
        ge=0,
        description="Number of platform extractions the organization has used so far.",
        json_schema_extra={"examples": [7]},
    )
    remaining: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Number of platform extractions remaining. "
            "Null when the organization is unlimited (own provider or admin override)."
        ),
        json_schema_extra={"examples": [3]},
    )
    has_own_provider: bool = Field(
        ...,
        description="Whether the organization has at least one active VLM provider configured.",
        json_schema_extra={"examples": [False]},
    )
    is_unlimited: bool = Field(
        ...,
        description=(
            "True when the platform limit does not apply. This happens when "
            "the org has its own provider OR the admin set the limit to 0."
        ),
        json_schema_extra={"examples": [False]},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "limit": 10,
                    "used": 7,
                    "remaining": 3,
                    "has_own_provider": False,
                    "is_unlimited": False,
                },
                {
                    "limit": 10,
                    "used": 10,
                    "remaining": 0,
                    "has_own_provider": False,
                    "is_unlimited": False,
                },
                {
                    "limit": 0,
                    "used": 42,
                    "remaining": None,
                    "has_own_provider": True,
                    "is_unlimited": True,
                },
            ]
        }
    )


# ---------------------------------------------------------------------------
# Error details embedded in PlatformLimitExceededError.details
# ---------------------------------------------------------------------------


class PlatformQuotaErrorDetails(BaseModel):
    """
    Structured details for the ``PLATFORM_LIMIT_REACHED`` error.

    Embedded in the ``details`` field of the ``APIException.to_dict()``
    error response when the organization has exhausted its free platform
    extractions.

    Attributes:
        limit: The configured limit for this organization.
        used: How many extractions have been consumed.
        remaining: Always 0 when this error fires.
        action_url: Frontend path where the user can add a provider.
        action_text: CTA button text for the frontend.

    Example JSON in error response:
        {
            "error": {
                "code": "PLATFORM_LIMIT_REACHED",
                "message": "Your organization has used all 10 free ...",
                "details": {
                    "limit": 10,
                    "used": 10,
                    "remaining": 0,
                    "action_url": "/settings?tab=ai-providers",
                    "action_text": "Add AI Provider"
                }
            }
        }
    """

    limit: int = Field(
        ...,
        ge=0,
        description="The platform leaflet limit for this organization.",
    )
    used: int = Field(
        ...,
        ge=0,
        description="Number of platform extractions consumed.",
    )
    remaining: int = Field(
        0,
        ge=0,
        description="Extractions remaining (always 0 when error fires).",
    )
    action_url: str = Field(
        default="/settings?tab=ai-providers",
        description="Frontend path where user can add their own VLM provider.",
    )
    action_text: str = Field(
        default="Add AI Provider",
        description="CTA button text for the frontend to display.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "limit": 10,
                    "used": 10,
                    "remaining": 0,
                    "action_url": "/settings?tab=ai-providers",
                    "action_text": "Add AI Provider",
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# WebSocket message payload for platform_limit_reached
# ---------------------------------------------------------------------------


class PlatformLimitReachedMessage(BaseModel):
    """
    WebSocket message payload when extraction is blocked by the platform limit.

    Published via the progress publisher when ``extract_products_task``
    determines that the organization has exhausted its free platform
    extractions and has no own VLM provider.

    Message envelope (set by progress publisher):
        {
            "leaflet_id": "<leaflet_id>",
            "event_type": "error",
            "progress": -1,
            "message": "Platform AI limit reached. ...",
            "timestamp": "<ISO 8601>",
            "data": {
                "error_code": "PLATFORM_LIMIT_REACHED",
                "limit": 10,
                "used": 10,
                "action_url": "/settings",
                "action_text": "Add AI Provider"
            }
        }

    The ``data`` dict is what gets passed to ``publish_error(details=...)``.

    Attributes:
        error_code: Machine-readable error code for frontend routing.
        limit: The platform limit.
        used: Extractions consumed.
        action_url: Where to redirect user.
        action_text: CTA label.
    """

    error_code: str = Field(
        default="PLATFORM_LIMIT_REACHED",
        description="Machine-readable error code for frontend routing.",
    )
    limit: int = Field(
        ...,
        ge=0,
        description="Platform leaflet extraction limit.",
    )
    used: int = Field(
        ...,
        ge=0,
        description="Number of platform extractions consumed.",
    )
    action_url: str = Field(
        default="/settings?tab=ai-providers",
        description="Frontend path for adding own provider.",
    )
    action_text: str = Field(
        default="Add AI Provider",
        description="CTA button text.",
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/organizations/{org_id} -- Request body
# ---------------------------------------------------------------------------


class OrganizationPlatformSettingsUpdate(BaseModel):
    """
    Request schema for superuser to update an organization's platform settings.

    Used by ``PATCH /api/v1/admin/organizations/{org_id}``.

    Only ``platform_leaflet_limit`` is included for now; additional admin-level
    fields can be added later without breaking backward compatibility.

    Validation:
        - ``platform_leaflet_limit`` must be >= 0.
        - 0 means unlimited (no platform limit enforced).
        - Positive integers set the exact limit.

    Attributes:
        platform_leaflet_limit: New platform extraction limit for the org.

    Example:
        >>> OrganizationPlatformSettingsUpdate(platform_leaflet_limit=20)
    """

    platform_leaflet_limit: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Maximum number of free leaflet extractions using the platform AI provider. "
            "0 means unlimited (no limit enforced). Must be >= 0."
        ),
        json_schema_extra={"examples": [10, 20, 0]},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"platform_leaflet_limit": 20},
                {"platform_leaflet_limit": 0},
            ]
        }
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/organizations/{org_id} -- Response body
# ---------------------------------------------------------------------------


class OrganizationPlatformSettingsResponse(BaseModel):
    """
    Response schema after updating an organization's platform settings.

    Attributes:
        id: Organization UUID.
        name: Organization display name.
        platform_leaflet_limit: Current platform extraction limit.
        platform_leaflets_used: Number of platform extractions consumed.
        message: Confirmation message.

    Example:
        >>> OrganizationPlatformSettingsResponse(
        ...     id="...", name="Acme Corp",
        ...     platform_leaflet_limit=20,
        ...     platform_leaflets_used=7,
        ...     message="Platform settings updated",
        ... )
    """

    id: str = Field(..., description="Organization UUID.")
    name: str = Field(..., description="Organization display name.")
    platform_leaflet_limit: int = Field(
        ...,
        ge=0,
        description="Current platform extraction limit (0 = unlimited).",
    )
    platform_leaflets_used: int = Field(
        ...,
        ge=0,
        description="Number of platform extractions consumed so far.",
    )
    message: str = Field(
        default="Platform settings updated",
        description="Confirmation message.",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Acme Corp",
                    "platform_leaflet_limit": 20,
                    "platform_leaflets_used": 7,
                    "message": "Platform settings updated",
                }
            ]
        },
    )
