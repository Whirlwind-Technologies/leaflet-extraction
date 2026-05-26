"""
Authentication API Endpoints.

This module provides endpoints for user authentication including
login, registration, token refresh, and password management.

All new user registrations (personal and business) require admin approval
before the user can log in. Notifications are sent to superusers and
a confirmation email is sent to the registrant.

Example Usage:
    POST /api/v1/auth/register - Register new user (pending approval)
    POST /api/v1/auth/login - Login and get tokens
    POST /api/v1/auth/refresh - Refresh access token
    POST /api/v1/auth/password-reset - Request password reset
"""

import logging
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.organization import Organization

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_read, get_db

bearer_scheme = HTTPBearer(auto_error=False)
from app.models.user import User
from app.utils.rate_limit import create_auth_rate_limit_dependency
from app.schemas.user import (
    BusinessRegistration,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
)
from app.utils.exceptions import (
    AuthenticationError,
    DuplicateError,
    NotFoundError,
    ValidationException,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    hash_password,
    revoke_token,
    verify_password,
    verify_password_reset_token,
)
from app.services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Auth rate limit dependencies (IP-based, per-minute and per-hour windows)
# ---------------------------------------------------------------------------
_login_rate_limit = create_auth_rate_limit_dependency(
    "login", per_minute=5, per_hour=20
)
_register_rate_limit = create_auth_rate_limit_dependency(
    "register", per_minute=3, per_hour=10
)
_password_reset_rate_limit = create_auth_rate_limit_dependency(
    "password_reset", per_minute=3, per_hour=10
)
_refresh_rate_limit = create_auth_rate_limit_dependency(
    "refresh", per_minute=10
)


async def _send_registration_notifications(
    db: AsyncSession,
    user: User,
    organization: "Organization",
) -> None:
    """Send registration notification emails and create in-app notification.

    This is a fire-and-forget helper: errors are logged but never propagated
    so the registration response is not blocked by email delivery failures.

    Args:
        db: Async database session (for querying superusers and creating notifications).
        user: The newly registered user.
        organization: The user's organization (personal or business).
    """
    from app.models.organization import Organization
    from app.services.notification_service import NotificationService
    from app.models.system_notification import NotificationType, NotificationSeverity

    try:
        from app.config import settings as app_settings

        # 1. Fetch all active superusers to receive email notifications
        super_admin_result = await db.execute(
            select(User).where(User.is_superuser == True, User.is_active == True)
        )
        super_admins = list(super_admin_result.scalars().all())

        # 2. Send email notification to support_email (info@leafxtract.com)
        support_email = app_settings.support_email
        if support_email:
            try:
                await email_service.send_registration_alert_to_support(
                    organization=organization,
                    owner=user,
                    support_email=support_email,
                )
            except Exception as email_exc:
                logger.error(
                    f"Failed to send registration alert to support "
                    f"({support_email}): {email_exc}",
                    exc_info=True,
                )

        # 3. Send confirmation email to the registrant
        try:
            await email_service.send_registration_received(
                organization=organization,
                owner=user,
            )
        except Exception as email_exc:
            logger.error(
                f"Failed to send registration received email to {user.email}: {email_exc}",
                exc_info=True,
            )

        # 4. Create in-app notification for superusers
        try:
            notification_service = NotificationService(db)
            await notification_service.create_notification(
                notification_type=NotificationType.USER_ACTION_REQUIRED,
                title="New User Registration",
                message=(
                    f"{user.full_name or user.email} ({user.email}) has registered "
                    f"and requires approval."
                ),
                role_requirement="super_admin",
                severity=NotificationSeverity.INFO,
                action_url="/admin/users",
                action_text="Review User",
                expires_in_hours=168,  # 7 days
                metadata={
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "organization_name": organization.name,
                    "organization_type": organization.organization_type.value,
                },
            )
        except Exception as notif_exc:
            logger.error(
                f"Failed to create in-app registration notification: {notif_exc}",
                exc_info=True,
            )

    except Exception as exc:
        logger.error(
            f"Unexpected error in _send_registration_notifications: {exc}",
            exc_info=True,
        )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new user account with email and password. "
        "The account will be inactive until approved by an administrator."
    ),
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_register_rate_limit),
) -> dict:
    """Register a new user (pending admin approval).

    Creates a personal organization for the user automatically.
    The user account is set to inactive until a superuser approves it.
    Notification emails and in-app alerts are dispatched to all superusers.

    Args:
        user_data: User registration data.
        db: Database session.

    Returns:
        Dict with user data and a message indicating pending approval.

    Raises:
        DuplicateError: If email already exists.
    """
    from app.models.organization import Organization, OrganizationType, OrganizationStatus
    from app.models.organization_user import OrganizationUser, OrganizationRole
    import re

    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email.lower())
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise DuplicateError("User", "email", user_data.email)

    # Create new user -- inactive until approved by an admin
    user = User(
        email=user_data.email.lower(),
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        is_active=False,  # Requires admin approval before login
        is_verified=False,
        settings={},
    )

    db.add(user)
    await db.flush()  # Flush to get user.id without committing

    # Create personal organization for the user
    org_name = f"{user_data.full_name or 'User'}'s Workspace"
    org_slug = re.sub(r'[^a-z0-9-]', '-', org_name.lower()).strip('-')

    # Ensure unique slug
    slug_counter = 1
    original_slug = org_slug
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        if result.scalar_one_or_none() is None:
            break
        org_slug = f"{original_slug}-{slug_counter}"
        slug_counter += 1

    organization = Organization(
        name=org_name,
        slug=org_slug,
        organization_type=OrganizationType.PERSONAL,
        status=OrganizationStatus.ACTIVE,  # Personal orgs are auto-active (user gated by is_active)
        business_email=user.email,
        requested_by_user_id=user.id,
        settings={},
    )

    db.add(organization)
    await db.flush()  # Flush to get organization.id

    # Create organization membership (user as owner)
    membership = OrganizationUser(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        is_active=True,
        invited_by_user_id=None,  # Self-created
    )

    db.add(membership)

    # Set as user's default organization
    user.default_organization_id = organization.id

    await db.commit()
    await db.refresh(user)

    logger.info(
        f"New user registered (pending approval): {user.email} "
        f"with organization: {organization.name}"
    )

    # Send notifications in the background (fire-and-forget; errors are logged)
    await _send_registration_notifications(db, user, organization)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "message": (
            "Registration successful. Your account is pending approval "
            "by an administrator. You will receive an email once your "
            "account is approved."
        ),
    }


@router.post(
    "/register/business",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a business account",
    description="Create a business account pending admin approval.",
)
async def register_business(
    business_data: BusinessRegistration,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_register_rate_limit),
) -> User:
    """
    Register a new business account.

    Creates a business organization with PENDING_APPROVAL status.
    The user account owner will not be able to access the dashboard
    until a super admin approves the organization.

    Args:
        business_data: Business registration data
        db: Database session

    Returns:
        Created user object

    Raises:
        DuplicateError: If email already exists
    """
    from app.models.organization import Organization, OrganizationType, OrganizationStatus
    from app.models.organization_user import OrganizationUser, OrganizationRole
    import re

    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == business_data.email.lower())
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise DuplicateError("User", "email", business_data.email)

    # Check if organization name already exists
    result = await db.execute(
        select(Organization).where(Organization.name == business_data.organization_name)
    )
    existing_org = result.scalar_one_or_none()

    if existing_org:
        raise DuplicateError("Organization", "name", business_data.organization_name)

    # Create new user (inactive until org is approved)
    user = User(
        email=business_data.email.lower(),
        hashed_password=hash_password(business_data.password),
        full_name=business_data.full_name,
        is_active=False,  # Inactive until approved
        is_verified=False,
        settings={},
    )

    db.add(user)
    await db.flush()  # Flush to get user.id

    # Create business organization with PENDING_APPROVAL status
    org_slug = re.sub(r'[^a-z0-9-]', '-', business_data.organization_name.lower()).strip('-')

    # Ensure unique slug
    slug_counter = 1
    original_slug = org_slug
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        if result.scalar_one_or_none() is None:
            break
        org_slug = f"{original_slug}-{slug_counter}"
        slug_counter += 1

    organization = Organization(
        name=business_data.organization_name,
        slug=org_slug,
        organization_type=OrganizationType.BUSINESS,
        status=OrganizationStatus.PENDING_APPROVAL,  # Requires approval
        business_email=business_data.business_email,
        business_phone=business_data.business_phone,
        requested_by_user_id=user.id,
        settings={},
    )

    db.add(organization)
    await db.flush()  # Flush to get organization.id

    # Create organization membership (inactive until org is approved)
    membership = OrganizationUser(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        is_active=False,  # Inactive until approved
        invited_by_user_id=None,  # Self-created
    )

    db.add(membership)

    # Set as user's default organization
    user.default_organization_id = organization.id

    await db.commit()
    await db.refresh(user)

    logger.info(
        f"Business registration created: {user.email} for organization: "
        f"{organization.name} (pending approval)"
    )

    # Send notifications to superusers and confirmation to the registrant
    await _send_registration_notifications(db, user, organization)

    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="Authenticate with email and password to receive access tokens.",
)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_login_rate_limit),
) -> dict:
    """
    Authenticate user and return tokens.
    
    Args:
        login_data: Login credentials
        db: Database session
        
    Returns:
        Access and refresh tokens
        
    Raises:
        AuthenticationError: If credentials are invalid
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == login_data.email.lower())
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        logger.warning(f"Login attempt for unknown email: {login_data.email}")
        raise AuthenticationError("Invalid email or password")
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Invalid password for user: {user.email}")
        raise AuthenticationError("Invalid email or password")

    # Check if user is active
    if not user.is_active:
        # Check organization status to provide specific error message
        from app.models.organization import Organization, OrganizationType, OrganizationStatus

        if user.default_organization_id:
            result = await db.execute(
                select(Organization).where(Organization.id == user.default_organization_id)
            )
            organization = result.scalar_one_or_none()

            if organization:
                # Check suspended/rejected first (applies to both personal and business)
                if organization.status == OrganizationStatus.SUSPENDED:
                    message = "Your account has been suspended"
                    if organization.rejection_reason:
                        message += f": {organization.rejection_reason}"

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "message": message,
                            "status": "suspended",
                            "organization_name": organization.name,
                            "rejection_reason": organization.rejection_reason,
                        }
                    )

                # Personal users pending approval
                if organization.organization_type == OrganizationType.PERSONAL:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "message": (
                                "Your account is pending approval by an administrator. "
                                "You will receive an email once your account is approved."
                            ),
                            "status": "pending_approval",
                        }
                    )

                # Business users with pending org approval
                if organization.status == OrganizationStatus.PENDING_APPROVAL:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "message": "Your business registration is pending approval",
                            "status": "pending_approval",
                            "organization_name": organization.name,
                        }
                    )

        # Fallback for users without an organization or unknown state
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": (
                    "Your account is pending approval by an administrator. "
                    "You will receive an email once your account is approved."
                ),
                "status": "pending_approval",
            }
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    from app.config import settings
    
    logger.info(f"User logged in: {user.email}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Get a new access token using a refresh token.",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_refresh_rate_limit),
) -> dict:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_data: Refresh token
        db: Database session
        
    Returns:
        New access token
        
    Raises:
        AuthenticationError: If refresh token is invalid
    """
    # Decode refresh token
    payload = decode_token(refresh_data.refresh_token)
    
    if payload is None:
        raise AuthenticationError("Invalid or expired refresh token")
    
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")
    
    user_id = payload.get("sub")
    
    # Verify user exists and is active
    from uuid import UUID
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid token payload")
    
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise AuthenticationError("User not found")
    
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    # Create new access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    from app.config import settings
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post(
    "/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request password reset",
    description="Send a password reset email to the user.",
)
async def request_password_reset(
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_password_reset_rate_limit),
) -> dict:
    """
    Request a password reset email.
    
    Args:
        reset_data: Email address for reset
        db: Database session
        
    Returns:
        Success message (always, to prevent email enumeration)
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == reset_data.email.lower())
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Generate reset token
        reset_token = generate_password_reset_token(user.id)

        # Send reset email
        try:
            await email_service.send_password_reset(user, reset_token)
            logger.info(f"Password reset email sent to: {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")
            # Don't reveal the error to prevent email enumeration

    # Always return success to prevent email enumeration
    return {
        "message": "If an account exists with this email, a password reset link has been sent."
    }


@router.post(
    "/password-reset/confirm",
    summary="Confirm password reset",
    description="Reset password using the token from the reset email.",
)
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_password_reset_rate_limit),
) -> dict:
    """
    Reset password using reset token.
    
    Args:
        reset_data: Reset token and new password
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        AuthenticationError: If token is invalid
    """
    # Verify token
    user_id = verify_password_reset_token(reset_data.token)
    
    if user_id is None:
        raise AuthenticationError("Invalid or expired reset token")
    
    # Find user
    from uuid import UUID
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid token payload")
    
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise AuthenticationError("User not found")
    
    # Update password
    user.hashed_password = hash_password(reset_data.new_password)
    await db.commit()
    
    logger.info(f"Password reset completed for: {user.email}")
    
    return {"message": "Password has been reset successfully"}


@router.post(
    "/change-password",
    summary="Change password",
    description="Change password for the current user.",
)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Change password for authenticated user.
    
    Args:
        password_data: Current and new password
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        AuthenticationError: If current password is wrong
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise AuthenticationError("Current password is incorrect")
    
    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    await db.commit()
    
    logger.info(f"Password changed for: {current_user.email}")

    return {"message": "Password changed successfully"}


# Alias routes for frontend compatibility
@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request password reset (alias)",
    description="Alias for /password-reset endpoint.",
)
async def forgot_password(
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_password_reset_rate_limit),
) -> dict:
    """Alias for request_password_reset to match frontend expectations."""
    return await request_password_reset(reset_data, db, _rate_limit)


@router.post(
    "/reset-password",
    summary="Confirm password reset (alias)",
    description="Alias for /password-reset/confirm endpoint.",
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(_password_reset_rate_limit),
) -> dict:
    """Alias for confirm_password_reset to match frontend expectations."""
    return await confirm_password_reset(reset_data, db, _rate_limit)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
async def get_me(
    current_user: User = Depends(require_read),
) -> User:
    """
    Get current user information.

    Supports both JWT token and API key (X-API-Key header) authentication,
    allowing B2B clients to verify their identity.

    Args:
        current_user: Currently authenticated user (via JWT or API key).

    Returns:
        Current user object.
    """
    return current_user


@router.post(
    "/logout",
    summary="Logout",
    description="Logout the current user and revoke their access token.",
)
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Logout current user.

    Adds the current access token's `jti` claim to the Redis
    blacklist for its remaining lifetime, so subsequent requests
    presenting the same token are rejected. The client should
    also discard the token.
    """
    logger.info(f"User logged out: {current_user.email}")

    if credentials is not None:
        payload = decode_token(credentials.credentials)
        if payload is not None:
            await revoke_token(payload)

    return {"message": "Successfully logged out"}