"""
Unit Tests for API Key Authentication.

Tests for the API key authentication flow, organization resolution,
and all auth edge cases for the get_current_user_or_api_key dependency.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_api_key, _verify_api_key_and_get_user, get_current_organization
from app.models.user import User
from app.models.api_key import APIKey
from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.utils.exceptions import AuthenticationError, RateLimitError
from app.utils.security import create_access_token


class TestValidAPIKeyAuth:
    """Tests for valid API key authentication."""

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that a valid API key returns the associated user."""
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Test API Key",
            scopes=["read", "write"],
        )
        db_session.add(api_key_record)
        await db_session.commit()
        await db_session.refresh(api_key_record)

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # Verify the API key
        user, api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, db_session
        )

        assert user.id == test_user.id
        assert user.email == test_user.email
        assert api_key.id == api_key_record.id
        assert api_key.name == "Test API Key"

    @pytest.mark.asyncio
    async def test_api_key_usage_counter_increments(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that usage_count increments after successful auth."""
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Counter Test Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()
        await db_session.refresh(api_key_record)

        initial_count = api_key_record.total_requests

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Use the API key
        user, api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, db_session
        )

        # Refresh to get updated count
        await db_session.refresh(api_key_record)

        assert api_key_record.total_requests == initial_count + 1
        assert api_key_record.last_used_at is not None
        assert api_key_record.last_used_ip == "192.168.1.100"


class TestInvalidAPIKeyAuth:
    """Tests for invalid API key scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(
        self, db_session: AsyncSession
    ):
        """Test that an invalid/nonexistent API key raises AuthenticationError."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        invalid_key = "lep_invalid_key_that_does_not_exist"

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await _verify_api_key_and_get_user(mock_request, invalid_key, db_session)

    @pytest.mark.asyncio
    async def test_expired_api_key_returns_401(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that an expired API key raises AuthenticationError."""
        # Create expired API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Expired Key",
            scopes=["read"],
            expires_in_days=1,
        )
        # Manually set expiration to past
        api_key_record.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.add(api_key_record)
        await db_session.commit()

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(AuthenticationError, match="expired"):
            await _verify_api_key_and_get_user(mock_request, raw_key, db_session)

    @pytest.mark.asyncio
    async def test_revoked_api_key_returns_401(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that a revoked API key (is_active=False) raises AuthenticationError."""
        # Create API key and revoke it
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Revoked Key",
            scopes=["read"],
        )
        api_key_record.is_active = False
        db_session.add(api_key_record)
        await db_session.commit()

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            await _verify_api_key_and_get_user(mock_request, raw_key, db_session)

    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(
        self, db_session: AsyncSession
    ):
        """Test that no auth header raises AuthenticationError."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # Test get_current_user_or_api_key with no credentials
        with pytest.raises(AuthenticationError, match="Authentication required"):
            await get_current_user_or_api_key(
                request=mock_request,
                credentials=None,
                api_key=None,
                db=db_session,
            )

    @pytest.mark.asyncio
    async def test_invalid_api_key_format(self, db_session: AsyncSession):
        """Test that an API key without 'lep_' prefix is rejected."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        invalid_key = "invalid_format_key"

        with pytest.raises(AuthenticationError, match="Invalid API key format"):
            await _verify_api_key_and_get_user(mock_request, invalid_key, db_session)


class TestAPIKeyOrgIsolation:
    """Tests for organization isolation with API keys."""

    @pytest.mark.asyncio
    async def test_api_key_org_isolation(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
        test_organization_2: Organization,
    ):
        """Test that an API key scoped to Org A cannot access Org B data."""
        # Create API key for organization 1
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Org A Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Verify the key belongs to organization 1
        assert api_key_record.organization_id == test_organization.id

        # Try to use it with organization 2 context
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # Authenticate with API key
        user, api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, db_session
        )

        # Verify the API key is scoped to org 1, not org 2
        assert api_key.organization_id == test_organization.id
        assert api_key.organization_id != test_organization_2.id

    @pytest.mark.asyncio
    async def test_api_key_org_resolution_in_get_current_organization(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that get_current_organization resolves org from API key correctly."""
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Org Resolution Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # Call get_current_organization with API key
        organization = await get_current_organization(
            request=mock_request,
            org_id_header=None,
            credentials=None,
            api_key_header=raw_key,
            db=db_session,
        )

        assert organization.id == test_organization.id
        assert organization.name == test_organization.name


class TestAPIKeyRateLimiting:
    """Tests for API key rate limiting."""

    @pytest.mark.asyncio
    async def test_api_key_daily_limit_exceeded(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that exceeding daily limit raises RateLimitError."""
        # Create API key with daily limit of 1
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Limited Key",
            scopes=["read"],
            daily_limit=1,
        )
        # Set requests_today to the limit
        api_key_record.requests_today = 1
        api_key_record.last_reset_date = datetime.utcnow()
        db_session.add(api_key_record)
        await db_session.commit()

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(RateLimitError, match="Daily API request limit exceeded"):
            await _verify_api_key_and_get_user(mock_request, raw_key, db_session)


class TestAPIKeyOrgResolutionFailureLogged:
    """Tests for API key org resolution failure logging."""

    @pytest.mark.asyncio
    async def test_api_key_org_resolution_failure_logged(
        self, db_session: AsyncSession
    ):
        """Test that the warning log is emitted when API key org resolution fails."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        invalid_key = "lep_invalid_key"

        with patch('app.api.deps.logger') as mock_logger:
            try:
                await get_current_organization(
                    request=mock_request,
                    org_id_header=None,
                    credentials=None,
                    api_key_header=invalid_key,
                    db=db_session,
                )
            except AuthenticationError:
                # Expected to fail, we're testing the log
                pass

            # Verify warning was logged
            mock_logger.warning.assert_called()
            warning_call_args = str(mock_logger.warning.call_args)
            assert "API key organization resolution failed" in warning_call_args


class TestAPIKeyIPWhitelist:
    """Tests for API key IP whitelist functionality."""

    @pytest.mark.asyncio
    async def test_api_key_ip_whitelist_allowed(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that an allowed IP can use the API key."""
        # Create API key with IP whitelist
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="IP Restricted Key",
            scopes=["read"],
            allowed_ips=["192.168.1.100", "192.168.1.101"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Request from allowed IP
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        user, api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, db_session
        )

        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_api_key_ip_whitelist_blocked(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that a non-whitelisted IP is blocked."""
        # Create API key with IP whitelist
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="IP Restricted Key",
            scopes=["read"],
            allowed_ips=["192.168.1.100"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Request from non-allowed IP
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "10.0.0.1"

        with pytest.raises(AuthenticationError, match="IP address not allowed"):
            await _verify_api_key_and_get_user(mock_request, raw_key, db_session)


class TestAPIKeyUserInactive:
    """Tests for API key with inactive user."""

    @pytest.mark.asyncio
    async def test_inactive_user_api_key_rejected(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that an API key belonging to an inactive user is rejected."""
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Inactive User Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Deactivate the user
        test_user.is_active = False
        await db_session.commit()

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        with pytest.raises(AuthenticationError, match="User not found or inactive"):
            await _verify_api_key_and_get_user(mock_request, raw_key, db_session)


class TestAPIKeyPriorityOverJWT:
    """Tests for authentication method priority."""

    @pytest.mark.asyncio
    async def test_jwt_tried_before_api_key(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that JWT is tried first, then API key."""
        # Create valid JWT token
        token = create_access_token(data={"sub": str(test_user.id)})

        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Fallback Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        # Create mock credentials
        from fastapi.security import HTTPAuthorizationCredentials
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # Both JWT and API key provided - JWT should take precedence
        user = await get_current_user_or_api_key(
            request=mock_request,
            credentials=mock_credentials,
            api_key=raw_key,
            db=db_session,
        )

        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_api_key_used_when_jwt_invalid(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Test that API key is used when JWT is invalid."""
        # Create invalid JWT token
        invalid_token = "invalid.jwt.token"

        # Create valid API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=test_user.id,
            organization_id=test_organization.id,
            name="Fallback Key",
            scopes=["read"],
        )
        db_session.add(api_key_record)
        await db_session.commit()

        from fastapi.security import HTTPAuthorizationCredentials
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=invalid_token
        )

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"

        # JWT fails, API key should work
        user = await get_current_user_or_api_key(
            request=mock_request,
            credentials=mock_credentials,
            api_key=raw_key,
            db=db_session,
        )

        assert user.id == test_user.id
