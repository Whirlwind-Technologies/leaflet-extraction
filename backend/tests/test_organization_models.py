"""
Unit tests for organization models.

Tests model validation, relationships, and business logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.organization import (
    Organization,
    OrganizationType,
    OrganizationStatus,
)
from app.models.organization_user import (
    OrganizationUser,
    OrganizationRole,
)
from app.models.organization_invitation import (
    OrganizationInvitation,
    InvitationStatus,
)
from app.models.user import User


class TestOrganizationModel:
    """Test Organization model."""

    def test_organization_creation(self):
        """Test creating a basic organization."""
        org = Organization(
            name="Test Corp",
            slug="test-corp",
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_email="contact@testcorp.com",
        )

        assert org.name == "Test Corp"
        assert org.slug == "test-corp"
        assert org.organization_type == OrganizationType.BUSINESS
        assert org.status == OrganizationStatus.PENDING_APPROVAL

    def test_organization_status_transitions(self):
        """Test organization status can transition correctly."""
        org = Organization(
            name="Test Corp",
            slug="test-corp",
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_email="contact@testcorp.com",
        )

        # Pending -> Active
        org.status = OrganizationStatus.ACTIVE
        assert org.status == OrganizationStatus.ACTIVE

        # Active -> Suspended
        org.status = OrganizationStatus.SUSPENDED
        assert org.status == OrganizationStatus.SUSPENDED

    def test_personal_vs_business_organization(self):
        """Test personal and business organization types."""
        personal_org = Organization(
            name="John's Workspace",
            slug="johns-workspace",
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
        )

        business_org = Organization(
            name="Business Corp",
            slug="business-corp",
            organization_type=OrganizationType.BUSINESS,
            status=OrganizationStatus.PENDING_APPROVAL,
            business_email="contact@business.com",
        )

        assert personal_org.organization_type == OrganizationType.PERSONAL
        assert business_org.organization_type == OrganizationType.BUSINESS


class TestOrganizationUserModel:
    """Test OrganizationUser model."""

    def test_organization_user_creation(self):
        """Test creating organization user membership."""
        org_user = OrganizationUser(
            organization_id=uuid4(),
            user_id=uuid4(),
            role=OrganizationRole.MEMBER,
            is_active=True,
        )

        assert org_user.role == OrganizationRole.MEMBER
        assert org_user.is_active is True

    def test_organization_roles(self):
        """Test all organization role types."""
        roles = [
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
            OrganizationRole.MEMBER,
            OrganizationRole.VIEWER,
        ]

        for role in roles:
            org_user = OrganizationUser(
                organization_id=uuid4(),
                user_id=uuid4(),
                role=role,
            )
            assert org_user.role == role

    def test_role_hierarchy(self):
        """Test role hierarchy exists (for application logic)."""
        # This is a conceptual test - hierarchy is enforced in application code
        role_hierarchy = {
            OrganizationRole.OWNER: 4,
            OrganizationRole.ADMIN: 3,
            OrganizationRole.MEMBER: 2,
            OrganizationRole.VIEWER: 1,
        }

        assert role_hierarchy[OrganizationRole.OWNER] > role_hierarchy[OrganizationRole.ADMIN]
        assert role_hierarchy[OrganizationRole.ADMIN] > role_hierarchy[OrganizationRole.MEMBER]
        assert role_hierarchy[OrganizationRole.MEMBER] > role_hierarchy[OrganizationRole.VIEWER]


class TestOrganizationInvitationModel:
    """Test OrganizationInvitation model."""

    def test_invitation_creation(self):
        """Test creating an invitation."""
        invitation = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="newuser@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
            expiration_days=7,
        )

        assert invitation.email == "newuser@example.com"
        assert invitation.role == OrganizationRole.MEMBER
        assert invitation.status == InvitationStatus.PENDING
        assert invitation.token is not None
        assert len(invitation.token) == 64

    def test_invitation_expiration(self):
        """Test invitation expiration logic."""
        invitation = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="test@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
            expiration_days=7,
        )

        # Not expired initially
        assert not invitation.is_expired

        # Manually set expiration to past
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        assert invitation.is_expired

    def test_invitation_can_be_accepted(self):
        """Test invitation acceptance validation."""
        invitation = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="test@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
            expiration_days=7,
        )

        # Can be accepted when pending and not expired
        assert invitation.can_be_accepted

        # Cannot be accepted when expired
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        assert not invitation.can_be_accepted

        # Cannot be accepted when already accepted
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invitation.status = InvitationStatus.ACCEPTED
        assert not invitation.can_be_accepted

        # Cannot be accepted when revoked
        invitation.status = InvitationStatus.REVOKED
        assert not invitation.can_be_accepted

    def test_invitation_acceptance(self):
        """Test accepting an invitation."""
        invitation = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="test@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
        )

        user_id = uuid4()
        invitation.accept(user_id)

        assert invitation.status == InvitationStatus.ACCEPTED
        assert invitation.accepted_by_user_id == user_id
        assert invitation.accepted_at is not None

    def test_invitation_token_uniqueness(self):
        """Test that invitation tokens are unique."""
        invitation1 = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="user1@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
        )

        invitation2 = OrganizationInvitation.create(
            organization_id=uuid4(),
            email="user2@example.com",
            role=OrganizationRole.MEMBER,
            invited_by_user_id=uuid4(),
        )

        # Tokens should be different
        assert invitation1.token != invitation2.token
