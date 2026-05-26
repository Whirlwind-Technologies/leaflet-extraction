"""
Pytest Configuration and Fixtures.

This module provides shared fixtures and configuration for all tests.

Fixture scoping strategy:
- test_engine: session-scoped (create/drop tables once per test session)
- db_session: function-scoped (fresh session per test, rolled back after each test)
- client: function-scoped (fresh ASGI client per test, uses the function-scoped session)
- All data fixtures (users, orgs, tokens): function-scoped
"""

import os
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set testing environment
os.environ["ENVIRONMENT"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "leaflet_db")
# CORS_ORIGINS must be a valid JSON array or comma-separated string for pydantic_settings
os.environ["CORS_ORIGINS"] = '["http://localhost:3000", "http://localhost:8000"]'

from app.config import settings
from app.main import app
from app.models import Base, User
from app.models.organization import Organization, OrganizationStatus, OrganizationType
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.models.organization_invitation import OrganizationInvitation, InvitationStatus
from app.utils.database import get_db
from app.utils.security import hash_password, create_access_token


# Test database URL
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/test_{settings.postgres_db}"
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create test database engine (session-scoped).

    Creates all tables once at the start of the test session and drops
    them at the end. Individual test isolation is handled by the
    function-scoped db_session fixture using transaction rollback.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    def _drop_all(conn):
        """Drop all tables handling circular FKs."""
        from sqlalchemy import text
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    async with engine.begin() as conn:
        await conn.run_sync(_drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(_drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a function-scoped database session with transaction rollback.

    Uses a savepoint so that session.commit() inside tests/fixtures commits
    the savepoint (making changes visible within the session) while the
    outer transaction is rolled back after the test, ensuring full isolation.
    """
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        await conn.begin_nested()

        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            @event.listens_for(
                session.sync_session, "after_transaction_end"
            )
            def _restart_savepoint(sync_session, trans):
                if trans.nested and not trans._parent.nested:
                    sync_session.begin_nested()

            yield session

        await transaction.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a function-scoped test client with database session override.

    Each test gets a fresh AsyncClient that shares the same rolled-back
    transaction as the db_session fixture, ensuring the test's DB writes
    are visible to the ASGI app and vice versa.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=hash_password("TestPassword123"),
        full_name="Test User",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def test_superuser(db_session: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password=hash_password("AdminPassword123"),
        full_name="Admin User",
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create authentication headers for test user."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(test_superuser: User) -> dict:
    """Create authentication headers for admin user."""
    token = create_access_token(data={"sub": str(test_superuser.id)})
    return {"Authorization": f"Bearer {token}"}


# Organization fixtures
@pytest_asyncio.fixture
async def test_organization(db_session: AsyncSession, test_user: User) -> Organization:
    """Create a test organization."""
    org = Organization(
        id=uuid4(),
        name="Test Organization",
        slug="test-organization",
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.ACTIVE,
        business_email="contact@testorg.com",
        business_phone="+1-555-0100",
        requested_by_user_id=test_user.id,
    )

    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Add user as owner
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=org.id,
        user_id=test_user.id,
        role=OrganizationRole.OWNER,
        is_active=True,
    )

    db_session.add(org_user)
    await db_session.commit()

    return org


@pytest_asyncio.fixture
async def test_organization_2(db_session: AsyncSession) -> Organization:
    """Create a second test organization for isolation tests."""
    # Create second user
    user2 = User(
        id=uuid4(),
        email="user2@example.com",
        hashed_password=hash_password("TestPassword123"),
        full_name="Test User 2",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user2)
    await db_session.commit()

    # Create second organization
    org2 = Organization(
        id=uuid4(),
        name="Test Organization 2",
        slug="test-organization-2",
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.ACTIVE,
        business_email="contact@testorg2.com",
        requested_by_user_id=user2.id,
    )

    db_session.add(org2)
    await db_session.commit()
    await db_session.refresh(org2)

    # Add user as owner
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=org2.id,
        user_id=user2.id,
        role=OrganizationRole.OWNER,
        is_active=True,
    )

    db_session.add(org_user)
    await db_session.commit()

    return org2


@pytest_asyncio.fixture
async def pending_organization(
    db_session: AsyncSession, test_user: User
) -> Organization:
    """Create a pending approval organization."""
    org = Organization(
        id=uuid4(),
        name="Pending Corp",
        slug="pending-corp",
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.PENDING_APPROVAL,
        business_email="contact@pendingcorp.com",
        business_phone="+1-555-0200",
        requested_by_user_id=test_user.id,
    )

    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Add user as owner (inactive until approved)
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=org.id,
        user_id=test_user.id,
        role=OrganizationRole.OWNER,
        is_active=False,
    )

    db_session.add(org_user)
    await db_session.commit()

    return org


@pytest_asyncio.fixture
async def test_member_user(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """Create a test member user."""
    user = User(
        id=uuid4(),
        email="member@example.com",
        hashed_password=hash_password("MemberPassword123"),
        full_name="Member User",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add as member
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=test_organization.id,
        user_id=user.id,
        role=OrganizationRole.MEMBER,
        is_active=True,
    )

    db_session.add(org_user)
    await db_session.commit()

    return user


@pytest_asyncio.fixture
async def test_admin_user(
    db_session: AsyncSession, test_organization: Organization
) -> User:
    """Create a test admin user."""
    user = User(
        id=uuid4(),
        email="orgadmin@example.com",
        hashed_password=hash_password("AdminPassword123"),
        full_name="Org Admin User",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add as admin
    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=test_organization.id,
        user_id=user.id,
        role=OrganizationRole.ADMIN,
        is_active=True,
    )

    db_session.add(org_user)
    await db_session.commit()

    return user


# Token fixtures with organization context
@pytest_asyncio.fixture
async def valid_token(test_user: User, test_organization: Organization) -> str:
    """Create a valid JWT token with organization context."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "org_id": str(test_organization.id),
            "role": "owner",
        }
    )
    return token


@pytest_asyncio.fixture
async def member_token(
    test_member_user: User, test_organization: Organization
) -> str:
    """Create a member JWT token."""
    token = create_access_token(
        data={
            "sub": str(test_member_user.id),
            "org_id": str(test_organization.id),
            "role": "member",
        }
    )
    return token


@pytest_asyncio.fixture
async def admin_token(
    test_admin_user: User, test_organization: Organization
) -> str:
    """Create an admin JWT token."""
    token = create_access_token(
        data={
            "sub": str(test_admin_user.id),
            "org_id": str(test_organization.id),
            "role": "admin",
        }
    )
    return token


@pytest_asyncio.fixture
async def superuser_token(test_superuser: User) -> str:
    """Create a superuser JWT token."""
    token = create_access_token(
        data={
            "sub": str(test_superuser.id),
        }
    )
    return token


@pytest_asyncio.fixture
async def user_token(test_user: User, test_organization: Organization) -> str:
    """Create a regular user token (alias for valid_token)."""
    token = create_access_token(
        data={
            "sub": str(test_user.id),
            "org_id": str(test_organization.id),
            "role": "owner",
        }
    )
    return token


@pytest_asyncio.fixture
async def org_tokens(
    db_session: AsyncSession,
    test_user: User,
    test_organization: Organization,
    test_organization_2: Organization,
) -> tuple[str, str]:
    """Create tokens for two different organizations."""
    from sqlalchemy import select

    token1 = create_access_token(
        data={
            "sub": str(test_user.id),
            "org_id": str(test_organization.id),
            "role": "owner",
        }
    )

    # Get user2 from the DB using the shared session
    result = await db_session.execute(
        select(User).where(User.email == "user2@example.com")
    )
    user2 = result.scalar_one()

    token2 = create_access_token(
        data={
            "sub": str(user2.id),
            "org_id": str(test_organization_2.id),
            "role": "owner",
        }
    )

    return token1, token2


@pytest_asyncio.fixture
async def multi_org_user_token(
    db_session: AsyncSession,
    test_organization: Organization,
    test_organization_2: Organization,
) -> str:
    """Create a user that belongs to multiple organizations."""
    user = User(
        id=uuid4(),
        email="multiorg@example.com",
        hashed_password=hash_password("MultiOrgPassword123"),
        full_name="Multi Org User",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.commit()

    # Add to both organizations
    org_user1 = OrganizationUser(
        id=uuid4(),
        organization_id=test_organization.id,
        user_id=user.id,
        role=OrganizationRole.MEMBER,
        is_active=True,
    )

    org_user2 = OrganizationUser(
        id=uuid4(),
        organization_id=test_organization_2.id,
        user_id=user.id,
        role=OrganizationRole.ADMIN,
        is_active=True,
    )

    db_session.add_all([org_user1, org_user2])
    await db_session.commit()

    token = create_access_token(
        data={
            "sub": str(user.id),
            "org_id": str(test_organization.id),
            "role": "member",
        }
    )

    return token


# Invitation fixtures
@pytest_asyncio.fixture
async def test_invitation(
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
) -> OrganizationInvitation:
    """Create a test invitation."""
    from datetime import datetime, timedelta
    import secrets

    invitation = OrganizationInvitation(
        id=uuid4(),
        organization_id=test_organization.id,
        invited_by_user_id=test_user.id,
        email="invitee@example.com",
        role=OrganizationRole.MEMBER,
        token=secrets.token_urlsafe(48),
        status=InvitationStatus.PENDING,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    db_session.add(invitation)
    await db_session.commit()
    await db_session.refresh(invitation)

    return invitation


@pytest_asyncio.fixture
async def expired_invitation_token(
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
) -> str:
    """Create an expired invitation token."""
    from datetime import datetime, timedelta
    import secrets

    invitation = OrganizationInvitation(
        id=uuid4(),
        organization_id=test_organization.id,
        invited_by_user_id=test_user.id,
        email="expired@example.com",
        role=OrganizationRole.MEMBER,
        token=secrets.token_urlsafe(48),
        status=InvitationStatus.PENDING,
        expires_at=datetime.utcnow() - timedelta(days=1),  # Expired
    )

    db_session.add(invitation)
    await db_session.commit()

    return invitation.token


@pytest_asyncio.fixture
async def revoked_invitation_token(
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
) -> str:
    """Create a revoked invitation token."""
    from datetime import datetime, timedelta
    import secrets

    invitation = OrganizationInvitation(
        id=uuid4(),
        organization_id=test_organization.id,
        invited_by_user_id=test_user.id,
        email="revoked@example.com",
        role=OrganizationRole.MEMBER,
        token=secrets.token_urlsafe(48),
        status=InvitationStatus.REVOKED,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    db_session.add(invitation)
    await db_session.commit()

    return invitation.token


@pytest_asyncio.fixture
async def accepted_invitation_token(
    db_session: AsyncSession,
    test_organization: Organization,
    test_user: User,
) -> str:
    """Create an already-accepted invitation token."""
    from datetime import datetime, timedelta
    import secrets

    invitation = OrganizationInvitation(
        id=uuid4(),
        organization_id=test_organization.id,
        invited_by_user_id=test_user.id,
        email="accepted@example.com",
        role=OrganizationRole.MEMBER,
        token=secrets.token_urlsafe(48),
        status=InvitationStatus.ACCEPTED,
        expires_at=datetime.utcnow() + timedelta(days=7),
        accepted_at=datetime.utcnow(),
        accepted_by_user_id=test_user.id,
    )

    db_session.add(invitation)
    await db_session.commit()

    return invitation.token


@pytest_asyncio.fixture
async def pending_registration_id(pending_organization: Organization) -> str:
    """Get the ID of a pending registration."""
    return str(pending_organization.id)


@pytest_asyncio.fixture
async def approved_org_token(db_session: AsyncSession) -> str:
    """Create an approved organization and return owner token."""
    user = User(
        id=uuid4(),
        email="approvedorg@example.com",
        hashed_password=hash_password("ApprovedPassword123"),
        full_name="Approved Org Owner",
        is_active=True,
        is_verified=True,
    )

    db_session.add(user)
    await db_session.commit()

    org = Organization(
        id=uuid4(),
        name="Approved Organization",
        slug="approved-organization",
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.ACTIVE,
        business_email="contact@approved.com",
        requested_by_user_id=user.id,
    )

    db_session.add(org)
    await db_session.commit()

    org_user = OrganizationUser(
        id=uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        is_active=True,
    )

    db_session.add(org_user)
    await db_session.commit()

    token = create_access_token(
        data={
            "sub": str(user.id),
            "org_id": str(org.id),
            "role": "owner",
        }
    )

    return token


@pytest_asyncio.fixture
async def org1_token(test_user: User, test_organization: Organization) -> str:
    """Token for organization 1."""
    return create_access_token(
        data={
            "sub": str(test_user.id),
            "org_id": str(test_organization.id),
            "role": "owner",
        }
    )


@pytest_asyncio.fixture
async def org2_leaflet_id() -> str:
    """Placeholder for organization 2 leaflet ID."""
    return str(uuid4())


@pytest_asyncio.fixture
async def user_id() -> str:
    """Placeholder user ID for removal tests."""
    return str(uuid4())


@pytest_asyncio.fixture
async def owner_id(test_user: User) -> str:
    """Get the ID of the organization owner."""
    return str(test_user.id)


@pytest_asyncio.fixture
async def last_admin_id() -> str:
    """Placeholder for last admin ID."""
    return str(uuid4())


@pytest_asyncio.fixture
async def org1_api_key() -> str:
    """Placeholder API key for organization 1."""
    import secrets
    return secrets.token_urlsafe(32)


@pytest_asyncio.fixture
async def readonly_api_key() -> str:
    """Placeholder read-only API key."""
    import secrets
    return secrets.token_urlsafe(32)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")
