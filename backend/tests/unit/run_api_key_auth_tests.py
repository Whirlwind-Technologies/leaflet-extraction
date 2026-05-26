"""
Standalone Test Runner for API Key Authentication Tests.

Run this file directly with Python to bypass pytest conftest issues:
    python tests/unit/run_api_key_auth_tests.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set environment before importing app modules
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-minimum-32-chars"
os.environ["POSTGRES_DB"] = "test_leaflet_db"

from app.models import Base, User
from app.models.api_key import APIKey
from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.api.deps import _verify_api_key_and_get_user, get_current_user_or_api_key, get_current_organization
from app.utils.exceptions import AuthenticationError, RateLimitError
from app.utils.security import hash_password, create_access_token


# Test database URL (in-memory SQLite for simplicity)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record_pass(self, test_name):
        self.passed += 1
        print(f"✓ {test_name}")

    def record_fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"✗ {test_name}: {error}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\nFailed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}")
                print(f"    {error}")
        print(f"{'='*60}")
        return self.failed == 0


async def setup_database():
    """Create test database and tables."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


async def create_test_fixtures(session: AsyncSession):
    """Create test user and organization."""
    # Create test user
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=hash_password("TestPassword123"),
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    # Create test organization
    org = Organization(
        id=uuid4(),
        name="Test Organization",
        slug="test-organization",
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.ACTIVE,
        business_email="contact@testorg.com",
        requested_by_user_id=user.id,
    )
    session.add(org)
    await session.flush()

    # Add user to organization
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        is_active=True,
    )
    session.add(org_user)
    await session.commit()

    return user, org


async def test_valid_api_key_returns_user(session: AsyncSession, user: User, org: Organization, results: TestResults):
    """Test that a valid API key returns the associated user."""
    try:
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=user.id,
            organization_id=org.id,
            name="Test API Key",
            scopes=["read", "write"],
        )
        session.add(api_key_record)
        await session.commit()
        await session.refresh(api_key_record)

        # Create mock request
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        # Verify the API key
        returned_user, returned_api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, session
        )

        assert returned_user.id == user.id
        assert returned_user.email == user.email
        assert returned_api_key.id == api_key_record.id
        assert returned_api_key.name == "Test API Key"

        results.record_pass("test_valid_api_key_returns_user")
    except Exception as e:
        results.record_fail("test_valid_api_key_returns_user", str(e))


async def test_api_key_usage_counter_increments(session: AsyncSession, user: User, org: Organization, results: TestResults):
    """Test that usage_count increments after successful auth."""
    try:
        # Create API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=user.id,
            organization_id=org.id,
            name="Counter Test Key",
            scopes=["read"],
        )
        session.add(api_key_record)
        await session.commit()
        await session.refresh(api_key_record)

        initial_count = api_key_record.total_requests

        # Create mock request
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"

        # Use the API key
        returned_user, returned_api_key = await _verify_api_key_and_get_user(
            mock_request, raw_key, session
        )

        # Refresh to get updated count
        await session.refresh(api_key_record)

        assert api_key_record.total_requests == initial_count + 1
        assert api_key_record.last_used_at is not None
        assert api_key_record.last_used_ip == "192.168.1.100"

        results.record_pass("test_api_key_usage_counter_increments")
    except Exception as e:
        results.record_fail("test_api_key_usage_counter_increments", str(e))


async def test_invalid_api_key_returns_401(session: AsyncSession, results: TestResults):
    """Test that an invalid API key raises AuthenticationError."""
    try:
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        invalid_key = "lep_invalid_key_that_does_not_exist"

        try:
            await _verify_api_key_and_get_user(mock_request, invalid_key, session)
            raise AssertionError("Expected AuthenticationError but none was raised")
        except AuthenticationError as e:
            assert "Invalid API key" in str(e)

        results.record_pass("test_invalid_api_key_returns_401")
    except Exception as e:
        results.record_fail("test_invalid_api_key_returns_401", str(e))


async def test_expired_api_key_returns_401(session: AsyncSession, user: User, org: Organization, results: TestResults):
    """Test that an expired API key raises AuthenticationError."""
    try:
        # Create expired API key
        api_key_record, raw_key = APIKey.create_key(
            user_id=user.id,
            organization_id=org.id,
            name="Expired Key",
            scopes=["read"],
            expires_in_days=1,
        )
        # Manually set expiration to past
        api_key_record.expires_at = datetime.utcnow() - timedelta(days=1)
        session.add(api_key_record)
        await session.commit()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        try:
            await _verify_api_key_and_get_user(mock_request, raw_key, session)
            raise AssertionError("Expected AuthenticationError but none was raised")
        except AuthenticationError as e:
            assert "expired" in str(e).lower()

        results.record_pass("test_expired_api_key_returns_401")
    except Exception as e:
        results.record_fail("test_expired_api_key_returns_401", str(e))


async def test_revoked_api_key_returns_401(session: AsyncSession, user: User, org: Organization, results: TestResults):
    """Test that a revoked API key raises AuthenticationError."""
    try:
        # Create API key and revoke it
        api_key_record, raw_key = APIKey.create_key(
            user_id=user.id,
            organization_id=org.id,
            name="Revoked Key",
            scopes=["read"],
        )
        api_key_record.is_active = False
        session.add(api_key_record)
        await session.commit()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        try:
            await _verify_api_key_and_get_user(mock_request, raw_key, session)
            raise AssertionError("Expected AuthenticationError but none was raised")
        except AuthenticationError as e:
            assert "Invalid API key" in str(e)

        results.record_pass("test_revoked_api_key_returns_401")
    except Exception as e:
        results.record_fail("test_revoked_api_key_returns_401", str(e))


async def test_no_auth_header_returns_401(session: AsyncSession, results: TestResults):
    """Test that no auth header raises AuthenticationError."""
    try:
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        try:
            await get_current_user_or_api_key(
                request=mock_request,
                credentials=None,
                api_key=None,
                db=session,
            )
            raise AssertionError("Expected AuthenticationError but none was raised")
        except AuthenticationError as e:
            assert "Authentication required" in str(e)

        results.record_pass("test_no_auth_header_returns_401")
    except Exception as e:
        results.record_fail("test_no_auth_header_returns_401", str(e))


async def test_invalid_api_key_format(session: AsyncSession, results: TestResults):
    """Test that an API key without 'lep_' prefix is rejected."""
    try:
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        invalid_key = "invalid_format_key"

        try:
            await _verify_api_key_and_get_user(mock_request, invalid_key, session)
            raise AssertionError("Expected AuthenticationError but none was raised")
        except AuthenticationError as e:
            assert "Invalid API key format" in str(e)

        results.record_pass("test_invalid_api_key_format")
    except Exception as e:
        results.record_fail("test_invalid_api_key_format", str(e))


async def test_api_key_daily_limit_exceeded(session: AsyncSession, user: User, org: Organization, results: TestResults):
    """Test that exceeding daily limit raises RateLimitError."""
    try:
        # Create API key with daily limit of 1
        api_key_record, raw_key = APIKey.create_key(
            user_id=user.id,
            organization_id=org.id,
            name="Limited Key",
            scopes=["read"],
            daily_limit=1,
        )
        # Set requests_today to the limit
        api_key_record.requests_today = 1
        api_key_record.last_reset_date = datetime.utcnow()
        session.add(api_key_record)
        await session.commit()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        try:
            await _verify_api_key_and_get_user(mock_request, raw_key, session)
            raise AssertionError("Expected RateLimitError but none was raised")
        except RateLimitError as e:
            assert "Daily API request limit exceeded" in str(e)

        results.record_pass("test_api_key_daily_limit_exceeded")
    except Exception as e:
        results.record_fail("test_api_key_daily_limit_exceeded", str(e))


async def run_all_tests():
    """Run all tests."""
    print("Running API Key Authentication Tests\n")
    print("="*60)

    results = TestResults()

    # Setup database
    engine = await setup_database()
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Run tests
    async with async_session_maker() as session:
        user, org = await create_test_fixtures(session)

        # Run each test
        await test_valid_api_key_returns_user(session, user, org, results)
        await test_api_key_usage_counter_increments(session, user, org, results)
        await test_invalid_api_key_returns_401(session, results)
        await test_expired_api_key_returns_401(session, user, org, results)
        await test_revoked_api_key_returns_401(session, user, org, results)
        await test_no_auth_header_returns_401(session, results)
        await test_invalid_api_key_format(session, results)
        await test_api_key_daily_limit_exceeded(session, user, org, results)

    # Cleanup
    await engine.dispose()

    # Print summary
    return results.summary()


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
