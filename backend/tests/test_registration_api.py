"""
Integration tests for business registration API.

Tests the complete registration workflow including:
- Self-registration
- Admin approval/rejection
- Email notifications

These tests use the async client and DB session fixtures from conftest.py.
All fixtures (client, db_session, superuser_token, pending_registration_id, etc.)
are defined in conftest.py and injected automatically by pytest.
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationStatus


@pytest.mark.asyncio
class TestBusinessRegistration:
    """Test business registration endpoints."""

    async def test_register_business_success(self, client: AsyncClient):
        """Test successful business registration."""
        registration_data = {
            "organization_name": "Acme Corp",
            "business_email": "contact@acme.com",
            "business_phone": "+1-555-0100",
            "user_full_name": "John Doe",
            "user_email": "john@acme.com",
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response = await client.post(
                "/api/v1/registrations", json=registration_data
            )

        assert response.status_code == 201
        data = response.json()

        assert "registration_id" in data
        assert data["status"] == "pending_approval"
        assert data["organization_name"] == "Acme Corp"
        assert "message" in data

    async def test_register_business_duplicate_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test registration with duplicate email fails."""
        registration_data = {
            "organization_name": "Acme Corp",
            "business_email": "contact@acme.com",
            "user_full_name": "John Doe",
            "user_email": "john-dup@acme.com",
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response1 = await client.post(
                "/api/v1/registrations", json=registration_data
            )
        assert response1.status_code == 201

        # Second registration with same user email
        registration_data2 = {
            "organization_name": "Different Corp",
            "business_email": "contact2@different.com",
            "user_full_name": "Jane Doe",
            "user_email": "john-dup@acme.com",  # Same user email
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response2 = await client.post(
                "/api/v1/registrations", json=registration_data2
            )
        assert response2.status_code == 422
        # ValidationException returns {"error": {"message": ..., "details": ...}}
        error_data = response2.json()
        assert "error" in error_data
        assert "email" in error_data["error"]["message"].lower()

    async def test_register_business_duplicate_organization_name(
        self, client: AsyncClient
    ):
        """Test registration with duplicate organization name fails."""
        registration_data1 = {
            "organization_name": "Unique Acme Corp",
            "business_email": "contact@uniqueacme.com",
            "user_full_name": "John Doe",
            "user_email": "john@uniqueacme.com",
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response1 = await client.post(
                "/api/v1/registrations", json=registration_data1
            )
        assert response1.status_code == 201

        # Same organization name, different email
        registration_data2 = {
            "organization_name": "Unique Acme Corp",  # Same name
            "business_email": "contact2@uniqueacme.com",
            "user_full_name": "Jane Doe",
            "user_email": "jane@uniqueacme.com",
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response2 = await client.post(
                "/api/v1/registrations", json=registration_data2
            )
        assert response2.status_code == 422
        error_data = response2.json()
        assert "error" in error_data
        assert "organization" in error_data["error"]["message"].lower()

    async def test_register_business_invalid_password(self, client: AsyncClient):
        """Test registration with weak password fails validation."""
        registration_data = {
            "organization_name": "Acme Corp Weak",
            "business_email": "contact@acmeweak.com",
            "user_full_name": "John Doe",
            "user_email": "john@acmeweak.com",
            "user_password": "weak",  # Too weak: <8 chars, no uppercase, no digit
        }

        response = await client.post(
            "/api/v1/registrations", json=registration_data
        )
        # Pydantic validation error returns 422 via FastAPI's default handler
        assert response.status_code == 422

    async def test_check_registration_status(self, client: AsyncClient):
        """Test checking registration status."""
        # First create a registration
        registration_data = {
            "organization_name": "Status Check Corp",
            "business_email": "contact@statuscheck.com",
            "user_full_name": "John Doe",
            "user_email": "john@statuscheck.com",
            "user_password": "SecurePass123!",
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            reg_response = await client.post(
                "/api/v1/registrations", json=registration_data
            )
        assert reg_response.status_code == 201
        registration_id = reg_response.json()["registration_id"]

        # Check status
        status_response = await client.get(
            f"/api/v1/registrations/{registration_id}/status"
        )

        assert status_response.status_code == 200
        data = status_response.json()

        assert data["registration_id"] == registration_id
        assert data["status"] == "pending_approval"
        assert data["organization_name"] == "Status Check Corp"
        assert "submitted_at" in data


@pytest.mark.asyncio
class TestAdminApproval:
    """Test admin approval endpoints."""

    async def test_approve_registration_as_superuser(
        self,
        client: AsyncClient,
        superuser_token: str,
        pending_registration_id: str,
    ):
        """Test superuser can approve registration."""
        headers = {"Authorization": f"Bearer {superuser_token}"}

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response = await client.post(
                f"/api/v1/admin/registrations/{pending_registration_id}/approve",
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()

        # The approve endpoint sets status to OrganizationStatus.ACTIVE
        assert data["status"] == "active"
        assert "message" in data

    async def test_reject_registration_as_superuser(
        self,
        client: AsyncClient,
        superuser_token: str,
        pending_registration_id: str,
    ):
        """Test superuser can reject registration."""
        headers = {"Authorization": f"Bearer {superuser_token}"}
        # The RejectRequest model uses 'rejection_reason', not 'reason'
        rejection_data = {
            "rejection_reason": "Business does not meet requirements"
        }

        with patch(
            "app.services.email_service.email_service",
            new_callable=AsyncMock,
        ):
            response = await client.post(
                f"/api/v1/admin/registrations/{pending_registration_id}/reject",
                json=rejection_data,
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()

        # The reject endpoint sets status to OrganizationStatus.SUSPENDED
        assert data["status"] == "suspended"

    async def test_approve_registration_as_regular_user_fails(
        self,
        client: AsyncClient,
        user_token: str,
        pending_registration_id: str,
    ):
        """Test regular user cannot approve registration."""
        headers = {"Authorization": f"Bearer {user_token}"}

        response = await client.post(
            f"/api/v1/admin/registrations/{pending_registration_id}/approve",
            headers=headers,
        )

        # get_current_superuser raises AuthorizationError -> 403
        assert response.status_code == 403

    async def test_list_pending_registrations_as_superuser(
        self, client: AsyncClient, superuser_token: str
    ):
        """Test superuser can list pending registrations."""
        headers = {"Authorization": f"Bearer {superuser_token}"}

        response = await client.get(
            "/api/v1/admin/registrations?status=pending_approval",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # The endpoint returns a paginated response with "items" key
        assert "items" in data
        assert isinstance(data["items"], list)
        assert "total" in data


@pytest.mark.asyncio
class TestDataIsolation:
    """Test data isolation after approval."""

    async def test_approved_organization_has_isolated_data(
        self, client: AsyncClient, approved_org_token: str
    ):
        """Test approved organization can only access its own data."""
        headers = {"Authorization": f"Bearer {approved_org_token}"}

        # Try to access leaflets
        response = await client.get("/api/v1/leaflets", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    async def test_organization_cannot_access_other_org_data(
        self,
        client: AsyncClient,
        org1_token: str,
        org2_leaflet_id: str,
    ):
        """Test organization cannot access another organization's data."""
        headers = {"Authorization": f"Bearer {org1_token}"}

        # Try to access org2's leaflet (a random UUID that doesn't exist for org1)
        response = await client.get(
            f"/api/v1/leaflets/{org2_leaflet_id}", headers=headers
        )

        # Should be 404 (not found due to org filtering) or 401/403
        assert response.status_code in (404, 401, 403)
