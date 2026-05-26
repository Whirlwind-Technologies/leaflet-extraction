"""
User Pydantic Schemas.

This module provides schemas for user authentication and management.

Example Usage:
    from app.schemas.user import UserCreate, UserResponse, Token
    
    # Create user
    user_data = UserCreate(
        email="user@example.com",
        password="securepassword",
        full_name="John Doe"
    )
    
    # Token response
    token = Token(access_token="...", token_type="bearer")
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


class UserBase(BaseSchema):
    """
    Base user schema with common fields.
    
    Attributes:
        email: User's email address
        full_name: User's full name
    """
    
    email: EmailStr = Field(description="User's email address")
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User's full name"
    )


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    
    Attributes:
        email: User's email address
        password: User's password (will be hashed)
        full_name: User's full name (optional)
        
    Example:
        >>> user = UserCreate(
        ...     email="user@example.com",
        ...     password="securepassword123",
        ...     full_name="John Doe"
        ... )
    """
    
    password: str = Field(
        min_length=8,
        max_length=100,
        description="User's password"
    )
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class BusinessRegistration(UserBase):
    """
    Schema for business account registration.

    Includes both user and organization information.

    Attributes:
        email: User's email address (account owner)
        password: User's password
        full_name: User's full name
        organization_name: Business/organization name
        business_email: Business contact email
        business_phone: Business phone (optional)
    """

    password: str = Field(
        min_length=8,
        max_length=100,
        description="User's password"
    )
    organization_name: str = Field(
        min_length=2,
        max_length=200,
        description="Organization/company name"
    )
    business_email: EmailStr = Field(
        description="Business contact email"
    )
    business_phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Business phone number"
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseSchema):
    """
    Schema for updating user information.
    
    All fields are optional - only provided fields will be updated.
    
    Attributes:
        email: New email address
        full_name: New full name
        password: New password
        settings: User settings/preferences
    """
    
    email: Optional[EmailStr] = Field(default=None, description="New email")
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="New full name"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=100,
        description="New password"
    )
    settings: Optional[dict] = Field(default=None, description="User settings")


class UserResponse(UserBase, IDSchema, TimestampSchema):
    """
    Schema for user response data.
    
    Attributes:
        id: User's unique identifier
        email: User's email address
        full_name: User's full name
        is_active: Whether account is active
        is_verified: Whether email is verified
        is_superuser: Whether user has admin privileges
        last_login: Last login timestamp
        login_count: Number of times user has logged in
        created_at: Account creation timestamp
        updated_at: Last update timestamp
        
    Example:
        >>> user = UserResponse(
        ...     id=uuid4(),
        ...     email="user@example.com",
        ...     full_name="John Doe",
        ...     is_active=True,
        ...     is_verified=True,
        ...     created_at=datetime.now(),
        ...     updated_at=datetime.now()
        ... )
    """
    
    is_active: bool = Field(description="Whether account is active")
    is_verified: bool = Field(description="Whether email is verified")
    is_superuser: bool = Field(default=False, description="Whether user has admin privileges")
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp"
    )
    login_count: int = Field(default=0, description="Number of logins")
    settings: dict = Field(default_factory=dict, description="User settings")


class UserInDB(UserResponse):
    """
    Schema for user data in database (includes hashed password).
    
    This schema is for internal use only and should never be
    returned in API responses.
    """
    
    hashed_password: str = Field(description="Hashed password")


# Authentication Schemas

class Token(BaseSchema):
    """
    JWT token response schema.
    
    Attributes:
        access_token: JWT access token
        token_type: Token type (always "bearer")
        expires_in: Token expiration in seconds
        refresh_token: Optional refresh token
        
    Example:
        >>> token = Token(
        ...     access_token="eyJhbGciOiJIUzI1NiIs...",
        ...     token_type="bearer",
        ...     expires_in=1800
        ... )
    """
    
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Expiration time in seconds")
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token"
    )


class TokenPayload(BaseSchema):
    """
    JWT token payload schema.
    
    Attributes:
        sub: Subject (user ID)
        exp: Expiration timestamp
        iat: Issued at timestamp
        type: Token type (access/refresh)
    """
    
    sub: str = Field(description="Subject (user ID)")
    exp: int = Field(description="Expiration timestamp")
    iat: Optional[int] = Field(default=None, description="Issued at")
    type: str = Field(default="access", description="Token type")


class LoginRequest(BaseSchema):
    """
    Login request schema.
    
    Attributes:
        email: User's email address
        password: User's password
        
    Example:
        >>> login = LoginRequest(
        ...     email="user@example.com",
        ...     password="securepassword"
        ... )
    """
    
    email: EmailStr = Field(description="Email address")
    password: str = Field(description="Password")


class RefreshTokenRequest(BaseSchema):
    """
    Refresh token request schema.
    
    Attributes:
        refresh_token: The refresh token to use
    """
    
    refresh_token: str = Field(description="Refresh token")


class PasswordResetRequest(BaseSchema):
    """
    Password reset request schema.
    
    Attributes:
        email: Email address for password reset
    """
    
    email: EmailStr = Field(description="Email address")


class PasswordResetConfirm(BaseSchema):
    """
    Password reset confirmation schema.
    
    Attributes:
        token: Password reset token
        new_password: New password
    """
    
    token: str = Field(description="Reset token")
    new_password: str = Field(
        min_length=8,
        max_length=100,
        description="New password"
    )


class ChangePasswordRequest(BaseSchema):
    """
    Change password request schema.
    
    Attributes:
        current_password: Current password
        new_password: New password
    """
    
    current_password: str = Field(description="Current password")
    new_password: str = Field(
        min_length=8,
        max_length=100,
        description="New password"
    )


# API Key Schemas

class APIKeyCreate(BaseSchema):
    """
    Schema for creating an API key.
    
    Attributes:
        name: Human-readable name for the key
        description: Description of key usage
        scopes: Permissions for this key
        expires_in_days: Days until expiration (optional)
        
    Example:
        >>> key = APIKeyCreate(
        ...     name="Production API Key",
        ...     scopes=["read:leaflets", "write:leaflets"]
        ... )
    """
    
    name: str = Field(max_length=255, description="Key name")
    description: Optional[str] = Field(default=None, description="Description")
    scopes: List[str] = Field(
        default_factory=list,
        description="Permissions"
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiration"
    )


class APIKeyResponse(IDSchema, TimestampSchema):
    """
    Schema for API key response.
    
    Note: The full key is only shown once upon creation.
    
    Attributes:
        id: Key identifier
        name: Key name
        key_prefix: First 8 characters of key
        scopes: Permissions
        is_active: Whether key is active
        last_used: When key was last used
        expires_at: Expiration date
    """
    
    name: str = Field(description="Key name")
    key_prefix: str = Field(description="Key prefix for identification")
    description: Optional[str] = Field(default=None, description="Description")
    scopes: List[str] = Field(description="Permissions")
    is_active: bool = Field(description="Whether key is active")
    last_used: Optional[datetime] = Field(default=None, description="Last used")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration")


class APIKeyCreated(APIKeyResponse):
    """
    Schema for newly created API key.
    
    Includes the full key which is only shown once.
    
    Attributes:
        key: The full API key (shown only once)
    """
    
    key: str = Field(description="Full API key (save this - shown only once)")