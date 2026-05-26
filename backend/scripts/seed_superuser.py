#!/usr/bin/env python3
"""
Seed Super User Script (Non-Interactive)

This script creates the initial super user account for the LeafXtract platform.
Used during initial deployment to seed the database with an admin account.

Default Credentials:
    Email: admin@leafxtract.com
    Password: Admin123!@#

For production deployments, override these via environment variables:
    SEED_ADMIN_EMAIL=your-email@example.com
    SEED_ADMIN_PASSWORD=YourSecurePassword123!
    SEED_ADMIN_NAME=Admin Name

Usage:
    # Use default credentials
    python scripts/seed_superuser.py

    # Use custom credentials
    SEED_ADMIN_EMAIL=admin@example.com SEED_ADMIN_PASSWORD=MyPass123! python scripts/seed_superuser.py

    # Via Docker
    docker-compose exec backend python scripts/seed_superuser.py

    # Via Docker with custom credentials
    docker-compose exec -e SEED_ADMIN_EMAIL=admin@example.com -e SEED_ADMIN_PASSWORD=MyPass123! backend python scripts/seed_superuser.py

    # Skip if exists (useful in CI/CD)
    python scripts/seed_superuser.py --skip-if-exists
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.user import User
from app.models.organization import Organization, OrganizationType, OrganizationStatus
from app.models.organization_user import OrganizationUser, OrganizationRole
from app.utils.security import hash_password

# Default credentials - CHANGE THESE FOR PRODUCTION
DEFAULT_EMAIL = "admin@leafxtract.com"
DEFAULT_PASSWORD = "Admin123!@#"
DEFAULT_NAME = "System Administrator"


def get_credentials() -> tuple[str, str, str]:
    """
    Get admin credentials from environment or use defaults.

    Falling back to the documented defaults is only allowed when
    settings.environment == 'development'. In any other environment
    the script exits unless SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD
    are explicitly provided, so production deployments cannot ship
    with the publicly known default credentials.
    """
    env_email = os.getenv("SEED_ADMIN_EMAIL")
    env_password = os.getenv("SEED_ADMIN_PASSWORD")
    env_name = os.getenv("SEED_ADMIN_NAME")

    is_dev = (settings.environment or "").lower() == "development"

    if not is_dev:
        missing = [
            name for name, value in (
                ("SEED_ADMIN_EMAIL", env_email),
                ("SEED_ADMIN_PASSWORD", env_password),
            ) if not value
        ]
        if missing:
            print("Error: refusing to seed superuser with default credentials")
            print(f"environment={settings.environment!r}; set: {', '.join(missing)}")
            print("Defaults are only permitted when ENVIRONMENT=development.")
            sys.exit(2)

        if env_password == DEFAULT_PASSWORD or env_email == DEFAULT_EMAIL:
            print("Error: SEED_ADMIN_EMAIL/PASSWORD must not match the documented defaults")
            print("outside of a development environment.")
            sys.exit(2)

    email = env_email or DEFAULT_EMAIL
    password = env_password or DEFAULT_PASSWORD
    full_name = env_name or DEFAULT_NAME
    return email, password, full_name


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    return True, ""


async def seed_superuser(skip_if_exists: bool = False) -> None:
    """Seed the database with a super user account."""
    email, password, full_name = get_credentials()

    print("=" * 60)
    print("LeafXtract - Seed Super User Account")
    print("=" * 60)
    print()
    print(f"Email: {email}")
    print(f"Full Name: {full_name}")
    print(f"Password: {'*' * len(password)}")
    print()

    # Validate password
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        print(f"Error: {error_msg}")
        sys.exit(1)

    # Create database engine and session
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email.lower()))
        existing = result.scalar_one_or_none()

        if existing:
            if skip_if_exists:
                print(f"Super user with email {email} already exists. Skipping...")
                print()
                await engine.dispose()
                return
            else:
                print(f"Error: User with email {email} already exists")
                print("Use --skip-if-exists flag to skip this error")
                await engine.dispose()
                sys.exit(1)

        # Check if any superuser exists
        result = await db.execute(select(User).where(User.is_superuser == True))
        any_superuser = result.scalar_one_or_none()

        if any_superuser and skip_if_exists:
            print("A super user already exists in the database. Skipping...")
            print()
            await engine.dispose()
            return

        print("Creating super user...")

        # Create new super user
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_verified=True,
            is_superuser=True,
            login_count=0,
            settings={},
        )

        db.add(user)
        await db.flush()  # Get user ID

        # Create personal organization for the super user
        org_slug = f"admin-{str(user.id)[:8]}"
        org = Organization(
            name=f"{full_name}'s Workspace",
            slug=org_slug,
            organization_type=OrganizationType.PERSONAL,
            status=OrganizationStatus.ACTIVE,
            business_email=email.lower(),
            requested_by_user_id=user.id,
            approved_by_user_id=user.id,
            approved_at=datetime.now(timezone.utc),
            settings={},
        )

        db.add(org)
        await db.flush()  # Get org ID

        # Set default organization for user
        user.default_organization_id = org.id

        # Create organization membership (OWNER role)
        org_user = OrganizationUser(
            organization_id=org.id,
            user_id=user.id,
            role=OrganizationRole.OWNER,
            is_active=True,
            joined_at=datetime.now(timezone.utc),
        )

        db.add(org_user)

        await db.commit()
        await db.refresh(user)

        print()
        print("=" * 60)
        print("SUCCESS: Super user created!")
        print("=" * 60)
        print()
        print("Account Details:")
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Is Superuser: {user.is_superuser}")
        print(f"  Organization: {org.name}")
        print()
        print("Login Credentials:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print()
        print("IMPORTANT: For production, change the password after first login!")
        print()
        print("Login URL: http://localhost:3000/login")
        print()

    await engine.dispose()


if __name__ == "__main__":
    skip_if_exists = "--skip-if-exists" in sys.argv

    try:
        asyncio.run(seed_superuser(skip_if_exists=skip_if_exists))
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
