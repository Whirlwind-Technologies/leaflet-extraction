#!/usr/bin/env python3
"""
Create Super User Script

This script creates a super user account for the LeafXtract platform.
Super users have full administrative privileges including approving business registrations.

Usage:
    python scripts/create_superuser.py

Or via Docker:
    docker-compose exec backend python scripts/create_superuser.py
"""

import asyncio
import sys
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.database import get_async_session_maker
from app.utils.security import hash_password


async def create_superuser() -> None:
    """Create a super user interactively."""
    print("=" * 60)
    print("LeafXtract - Create Super User Account")
    print("=" * 60)
    print()

    # Get user input
    email = input("Email address: ").strip()
    if not email:
        print("Error: Email is required")
        sys.exit(1)

    full_name = input("Full name: ").strip()
    if not full_name:
        print("Error: Full name is required")
        sys.exit(1)

    password = getpass("Password: ")
    if not password:
        print("Error: Password is required")
        sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    password_confirm = getpass("Confirm password: ")
    if password != password_confirm:
        print("Error: Passwords do not match")
        sys.exit(1)

    # Validate password strength
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not (has_upper and has_lower and has_digit):
        print("Error: Password must contain at least one uppercase letter, one lowercase letter, and one digit")
        sys.exit(1)

    print()
    print("Creating super user...")

    # Create user in database
    session_maker = get_async_session_maker()
    async with session_maker() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email.lower()))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Error: User with email {email} already exists")
            sys.exit(1)

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
        await db.commit()
        await db.refresh(user)

        print()
        print("✓ Super user created successfully!")
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Is Superuser: {user.is_superuser}")
        print()
        print("You can now login with these credentials at:")
        print("  http://localhost:3000/login")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(create_superuser())
    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
