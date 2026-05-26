"""
Unit and Integration Tests for Registration Approval System.

Tests the complete registration approval workflow including:
- Personal user registration (pending approval)
- Business user registration (pending approval)
- Login blocking for inactive users
- Admin approve/reject functionality
- Edge cases and security checks

All tests use async patterns and the existing fixture infrastructure.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.user import User
from app.models.organization import Organization, OrganizationType, OrganizationStatus
from app.models.organization_user import OrganizationUser


class TestPersonalRegistration:
    """Tests for personal user registration endpoint."""

    @pytest.mark.asyncio
    async def test_personal_registration_creates_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that personal registration creates a user with is_active=False."""
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123",
            "full_name": "New User",
        }

        # Mock the email service to prevent actual emails
        with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register",
                json=registration_data,
            )

        assert response.status_code == 201
        data = response.json()

        # Verify response includes expected fields
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["is_active"] is False
        assert data["is_verified"] is False
        assert "message" in data
        assert "pending approval" in data["message"].lower()

        # Verify user in database
        result = await db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.is_active is False
        assert user.is_verified is False

    @pytest.mark.asyncio
    async def test_personal_registration_returns_pending_message(
        self, client: AsyncClient
    ):
        """Test that personal registration response includes pending approval message."""
        registration_data = {
            "email": "pending@example.com",
            "password": "SecurePass123",
            "full_name": "Pending User",
        }

        with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register",
                json=registration_data,
            )

        assert response.status_code == 201
        data = response.json()

        assert "message" in data
        assert "pending approval" in data["message"].lower()
        assert "administrator" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_personal_registration_creates_personal_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that personal registration creates a PERSONAL organization automatically."""
        registration_data = {
            "email": "orguser@example.com",
            "password": "SecurePass123",
            "full_name": "Org User",
        }

        with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register",
                json=registration_data,
            )

        assert response.status_code == 201

        # Get the user
        result = await db_session.execute(
            select(User).where(User.email == "orguser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None

        # Verify organization was created
        assert user.default_organization_id is not None

        result = await db_session.execute(
            select(Organization).where(Organization.id == user.default_organization_id)
        )
        org = result.scalar_one_or_none()

        assert org is not None
        assert org.organization_type == OrganizationType.PERSONAL
        assert org.status == OrganizationStatus.ACTIVE  # Personal orgs are auto-active


class TestBusinessRegistration:
    """Tests for business registration endpoint."""

    @pytest.mark.asyncio
    async def test_business_registration_creates_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that business registration creates user with is_active=False."""
        registration_data = {
            "email": "business@example.com",
            "password": "SecurePass123",
            "full_name": "Business Owner",
            "organization_name": "Test Business Corp",
            "business_email": "contact@testbiz.com",
            "business_phone": "+1-555-0100",
        }

        with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register/business",
                json=registration_data,
            )

        assert response.status_code == 201
        data = response.json()

        # Verify user is inactive
        assert data["is_active"] is False
        assert data["is_verified"] is False

        # Verify user in database
        result = await db_session.execute(
            select(User).where(User.email == "business@example.com")
        )
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_business_registration_creates_pending_organization(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that business registration creates organization with PENDING_APPROVAL status."""
        registration_data = {
            "email": "bizowner@example.com",
            "password": "SecurePass123",
            "full_name": "Biz Owner",
            "organization_name": "Pending Business Inc",
            "business_email": "contact@pendingbiz.com",
            "business_phone": "+1-555-0200",
        }

        with patch("app.api.v1.auth._send_registration_notifications", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register/business",
                json=registration_data,
            )

        assert response.status_code == 201

        # Get the user and organization
        result = await db_session.execute(
            select(User).where(User.email == "bizowner@example.com")
        )
        user = result.scalar_one_or_none()

        result = await db_session.execute(
            select(Organization).where(Organization.id == user.default_organization_id)
        )
        org = result.scalar_one_or_none()

        assert org is not None
        assert org.organization_type == OrganizationType.BUSINESS
        assert org.status == OrganizationStatus.PENDING_APPROVAL


class TestLoginBlocking:
    """Tests for login blocking of inactive users."""

    @pytest.mark.asyncio
    async def test_inactive_personal_user_cannot_log_in(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that inactive personal user gets 403 with pending approval message."""
        # Create inactive personal user
        from app.utils.security import hash_password

        user = User(
            id=uuid4(),
            email="inactive@example.com",
            hashed_password=hash_password("TestPass123"),
            full_name="Inactive User",
            is_active=False,
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        # Create personal organization
        org = Organization(
            id=uuid4(),
            name="Inactive User's Workspace",
            slug="inactive-user-workspace",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
            business_email=user.email,
            requested_by_user_id=user.id,
        )
        db_session.add(org)
        await db_session.flush()

        user.default_organization_id = org.id

        # Create membership
        membership = OrganizationUser(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            is_active=True,
        )
        db_session.add(membership)
        await db_session.commit()

        # Try to log in
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "TestPass123",
            },
        )

        assert response.status_code == 403
        data = response.json()

        # Verify error message indicates pending approval
        assert "detail" in data
        detail = data["detail"]
        assert "pending approval" in detail["message"].lower()
        assert detail["status"] == "pending_approval"

    @pytest.mark.asyncio
    async def test_inactive_business_user_cannot_log_in(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that inactive business user gets 403 with business registration pending message."""
        from app.utils.security import hash_password

        user = User(
            id=uuid4(),
            email="bizuser@example.com",
            hashed_password=hash_password("BizPass123"),
            full_name="Business User",
            is_active=False,
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        # Create pending business organization
        org = Organization(
            id=uuid4(),
            name="Pending Business",
            slug="pending-business",
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_email="contact@pendingbiz.com",
            requested_by_user_id=user.id,
        )
        db_session.add(org)
        await db_session.flush()

        user.default_organization_id = org.id

        membership = OrganizationUser(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            is_active=False,
        )
        db_session.add(membership)
        await db_session.commit()

        # Try to log in
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "bizuser@example.com",
                "password": "BizPass123",
            },
        )

        assert response.status_code == 403
        data = response.json()

        detail = data["detail"]
        assert "pending approval" in detail["message"].lower() or "business registration" in detail["message"].lower()
        assert detail["status"] == "pending_approval"

    @pytest.mark.asyncio
    async def test_active_user_can_log_in_normally(
        self, client: AsyncClient, test_user: User
    ):
        """Test that active user can log in and receives tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


class TestAdminApprove:
    """Tests for admin approval endpoint."""

    @pytest.mark.asyncio
    async def test_superuser_can_approve_pending_user(
        self, client: AsyncClient, db_session: AsyncSession, test_superuser: User
    ):
        """Test that superuser can approve a pending user."""
        from app.utils.security import hash_password, create_access_token

        # Create pending user
        pending_user = User(
            id=uuid4(),
            email="pending@example.com",
            hashed_password=hash_password("PendingPass123"),
            full_name="Pending User",
            is_active=False,
            is_verified=False,
        )
        db_session.add(pending_user)
        await db_session.flush()

        # Create organization
        org = Organization(
            id=uuid4(),
            name="Pending Org",
            slug="pending-org",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
            business_email=pending_user.email,
            requested_by_user_id=pending_user.id,
        )
        db_session.add(org)
        await db_session.flush()

        pending_user.default_organization_id = org.id
        await db_session.commit()

        # Approve as superuser
        token = create_access_token(data={"sub": str(test_superuser.id)})

        with patch("app.api.v1.admin.users.email_service.send_registration_approved", new_callable=AsyncMock):
            response = await client.post(
                f"/api/v1/admin/users/{pending_user.id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert data["is_active"] is True
        assert data["is_verified"] is True

        # Verify user in database
        await db_session.refresh(pending_user)
        assert pending_user.is_active is True
        assert pending_user.is_verified is True

    @pytest.mark.asyncio
    async def test_cannot_approve_already_active_user(
        self, client: AsyncClient, test_user: User, test_superuser: User
    ):
        """Test that approving an already-active user returns 400 error."""
        from app.utils.security import create_access_token

        token = create_access_token(data={"sub": str(test_superuser.id)})

        response = await client.post(
            f"/api/v1/admin/users/{test_user.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "already approved" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_cannot_approve_yourself(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that a superuser cannot approve their own account."""
        from app.utils.security import hash_password, create_access_token

        # Create inactive superuser
        inactive_super = User(
            id=uuid4(),
            email="inactivesuper@example.com",
            hashed_password=hash_password("SuperPass123"),
            full_name="Inactive Super",
            is_active=False,
            is_verified=False,
            is_superuser=True,
        )
        db_session.add(inactive_super)
        await db_session.commit()

        token = create_access_token(data={"sub": str(inactive_super.id)})

        response = await client.post(
            f"/api/v1/admin/users/{inactive_super.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "cannot approve your own" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_non_superuser_cannot_approve(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test that regular user cannot access approve endpoint."""
        from app.utils.security import hash_password, create_access_token

        # Create another pending user
        pending_user = User(
            id=uuid4(),
            email="anotherpending@example.com",
            hashed_password=hash_password("Pass123"),
            full_name="Another Pending",
            is_active=False,
            is_verified=False,
        )
        db_session.add(pending_user)
        await db_session.commit()

        # Try to approve as regular user
        token = create_access_token(data={"sub": str(test_user.id)})

        response = await client.post(
            f"/api/v1/admin/users/{pending_user.id}/approve",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


class TestAdminReject:
    """Tests for admin rejection endpoint."""

    @pytest.mark.asyncio
    async def test_superuser_can_reject_pending_user(
        self, client: AsyncClient, db_session: AsyncSession, test_superuser: User
    ):
        """Test that superuser can reject a pending user."""
        from app.utils.security import hash_password, create_access_token

        # Create pending user
        pending_user = User(
            id=uuid4(),
            email="rejectme@example.com",
            hashed_password=hash_password("RejectPass123"),
            full_name="Reject Me",
            is_active=False,
            is_verified=False,
        )
        db_session.add(pending_user)
        await db_session.flush()

        # Create organization
        org = Organization(
            id=uuid4(),
            name="Reject Org",
            slug="reject-org",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
            business_email=pending_user.email,
            requested_by_user_id=pending_user.id,
        )
        db_session.add(org)
        await db_session.flush()

        pending_user.default_organization_id = org.id
        await db_session.commit()

        # Reject as superuser
        token = create_access_token(data={"sub": str(test_superuser.id)})

        with patch("app.api.v1.admin.users.email_service.send_registration_rejected", new_callable=AsyncMock):
            response = await client.post(
                f"/api/v1/admin/users/{pending_user.id}/reject",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "rejected" in data["message"].lower()

        # Verify user is still inactive
        await db_session.refresh(pending_user)
        assert pending_user.is_active is False

        # Verify organization is suspended
        await db_session.refresh(org)
        assert org.status == OrganizationStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_reject_with_reason(
        self, client: AsyncClient, db_session: AsyncSession, test_superuser: User
    ):
        """Test that rejection reason is stored and returned correctly."""
        from app.utils.security import hash_password, create_access_token

        pending_user = User(
            id=uuid4(),
            email="rejectreason@example.com",
            hashed_password=hash_password("Pass123"),
            full_name="Reject Reason",
            is_active=False,
            is_verified=False,
        )
        db_session.add(pending_user)
        await db_session.flush()

        org = Organization(
            id=uuid4(),
            name="Reject Reason Org",
            slug="reject-reason-org",
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_email="contact@rejectreason.com",
            requested_by_user_id=pending_user.id,
        )
        db_session.add(org)
        await db_session.flush()

        pending_user.default_organization_id = org.id
        await db_session.commit()

        token = create_access_token(data={"sub": str(test_superuser.id)})
        rejection_reason = "Business does not meet requirements"

        with patch("app.api.v1.admin.users.email_service.send_registration_rejected", new_callable=AsyncMock):
            response = await client.post(
                f"/api/v1/admin/users/{pending_user.id}/reject",
                headers={"Authorization": f"Bearer {token}"},
                json={"rejection_reason": rejection_reason},
            )

        assert response.status_code == 200
        data = response.json()

        assert data["rejection_reason"] == rejection_reason

        # Verify reason is stored on organization
        await db_session.refresh(org)
        assert org.rejection_reason == rejection_reason

    @pytest.mark.asyncio
    async def test_cannot_reject_superuser(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that superuser accounts cannot be rejected."""
        from app.utils.security import hash_password, create_access_token

        # Create inactive superuser
        inactive_super = User(
            id=uuid4(),
            email="inactivesuper2@example.com",
            hashed_password=hash_password("SuperPass123"),
            full_name="Inactive Super 2",
            is_active=False,
            is_verified=False,
            is_superuser=True,
        )
        db_session.add(inactive_super)
        await db_session.commit()

        # Create another superuser to do the rejection
        active_super = User(
            id=uuid4(),
            email="activesuper@example.com",
            hashed_password=hash_password("ActivePass123"),
            full_name="Active Super",
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db_session.add(active_super)
        await db_session.commit()

        token = create_access_token(data={"sub": str(active_super.id)})

        response = await client.post(
            f"/api/v1/admin/users/{inactive_super.id}/reject",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "cannot reject a superuser" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_non_superuser_cannot_reject(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test that regular user cannot access reject endpoint."""
        from app.utils.security import hash_password, create_access_token

        # Create pending user
        pending_user = User(
            id=uuid4(),
            email="pendingforreject@example.com",
            hashed_password=hash_password("Pass123"),
            full_name="Pending For Reject",
            is_active=False,
            is_verified=False,
        )
        db_session.add(pending_user)
        await db_session.commit()

        # Try to reject as regular user
        token = create_access_token(data={"sub": str(test_user.id)})

        response = await client.post(
            f"/api/v1/admin/users/{pending_user.id}/reject",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


class TestEdgeCases:
    """Tests for edge cases and post-approval scenarios."""

    @pytest.mark.asyncio
    async def test_rejected_user_still_cannot_log_in(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that rejected user still gets 403 on login attempt."""
        from app.utils.security import hash_password

        user = User(
            id=uuid4(),
            email="rejected@example.com",
            hashed_password=hash_password("RejectedPass123"),
            full_name="Rejected User",
            is_active=False,
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        org = Organization(
            id=uuid4(),
            name="Rejected Org",
            slug="rejected-org",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.SUSPENDED,
            business_email=user.email,
            requested_by_user_id=user.id,
            rejection_reason="Test rejection",
        )
        db_session.add(org)
        await db_session.flush()

        user.default_organization_id = org.id
        await db_session.commit()

        # Try to log in
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "rejected@example.com",
                "password": "RejectedPass123",
            },
        )

        assert response.status_code == 403
        data = response.json()

        detail = data["detail"]
        assert "suspended" in detail["message"].lower()
        assert detail["status"] == "suspended"

    @pytest.mark.asyncio
    async def test_approved_user_can_log_in(
        self, client: AsyncClient, db_session: AsyncSession, test_superuser: User
    ):
        """Test that approved user can successfully log in."""
        from app.utils.security import hash_password, create_access_token

        # Create pending user
        user = User(
            id=uuid4(),
            email="toapprove@example.com",
            hashed_password=hash_password("ApprovePass123"),
            full_name="To Approve",
            is_active=False,
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        org = Organization(
            id=uuid4(),
            name="To Approve Org",
            slug="to-approve-org",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
            business_email=user.email,
            requested_by_user_id=user.id,
        )
        db_session.add(org)
        await db_session.flush()

        user.default_organization_id = org.id

        membership = OrganizationUser(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            is_active=True,
        )
        db_session.add(membership)
        await db_session.commit()

        # Approve the user
        token = create_access_token(data={"sub": str(test_superuser.id)})

        with patch("app.api.v1.admin.users.email_service.send_registration_approved", new_callable=AsyncMock):
            approve_response = await client.post(
                f"/api/v1/admin/users/{user.id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert approve_response.status_code == 200

        # Now try to log in
        await db_session.refresh(user)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "toapprove@example.com",
                "password": "ApprovePass123",
            },
        )

        assert login_response.status_code == 200
        login_data = login_response.json()

        assert "access_token" in login_data
        assert "refresh_token" in login_data
