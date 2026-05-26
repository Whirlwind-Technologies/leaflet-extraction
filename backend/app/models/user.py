"""
User Model Module.

This module defines the User model for authentication and authorization.

Example Usage:
    from app.models.user import User
    
    # Create a new user
    user = User(
        email="user@example.com",
        hashed_password="...",
        full_name="John Doe"
    )
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class User(BaseModel, TimestampMixin):
    """
    User model for authentication and authorization.
    
    Stores user credentials, profile information, and authentication tokens.
    
    Attributes:
        id: Unique user identifier (UUID)
        email: User's email address (unique)
        hashed_password: Bcrypt hashed password
        full_name: User's full name
        is_active: Whether user account is active
        is_superuser: Whether user has superuser privileges
        is_verified: Whether email is verified
        api_key: API key for programmatic access
        last_login: Timestamp of last login
        settings: User preferences and settings (JSON)
        
    Relationships:
        leaflets: Leaflets uploaded by this user
        
    Example:
        >>> user = User(
        ...     email="user@example.com",
        ...     hashed_password=hash_password("secret"),
        ...     full_name="John Doe"
        ... )
        >>> db.add(user)
        >>> await db.commit()
    """
    
    __tablename__ = "users"
    
    # Authentication fields
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address"
    )
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Profile fields
    full_name = Column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    # Status fields
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether user account is active"
    )
    is_superuser = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether user has superuser privileges"
    )
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether email is verified"
    )
    
    # API access
    api_key = Column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
        comment="API key for programmatic access"
    )
    api_key_created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When API key was created"
    )
    
    # Activity tracking
    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last login"
    )
    login_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of logins"
    )
    
    # User settings and preferences
    settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="User preferences and settings"
    )

    # Organization membership
    default_organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
        comment="User's default/active organization for context switching"
    )

    # Relationships
    leaflets = relationship(
        "Leaflet",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # Organization relationships
    organizations = relationship(
        "Organization",
        secondary="organization_users",
        primaryjoin="User.id==OrganizationUser.user_id",
        secondaryjoin="Organization.id==OrganizationUser.organization_id",
        back_populates="users",
        viewonly=True,
        doc="Organizations this user is a member of"
    )

    organization_memberships = relationship(
        "OrganizationUser",
        back_populates="user",
        foreign_keys="OrganizationUser.user_id",
        cascade="all, delete-orphan",
        doc="Organization membership records with roles"
    )

    default_organization = relationship(
        "Organization",
        foreign_keys=[default_organization_id],
        doc="User's default/active organization"
    )
    
    # VLM Providers
    vlm_providers = relationship(
        "VLMProvider",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    # API Keys (new model)
    api_keys = relationship(
        "APIKey",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="APIKey.user_id"
    )
    
    # Webhooks
    webhooks = relationship(
        "Webhook",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    # Analytics
    usage_metrics = relationship(
        "UsageMetrics",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    cost_tracking = relationship(
        "CostTracking",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    
    feedback_logs = relationship(
        "FeedbackLog",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # Notification Preferences
    notification_preferences = relationship(
        "NotificationPreference",
        back_populates="user",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated (active and verified)."""
        return self.is_active and self.is_verified
    
    def get_default_vlm_provider(self):
        """Get user's default VLM provider."""
        for provider in self.vlm_providers:
            if provider.is_default and provider.is_active:
                return provider
        # Return first active provider
        for provider in self.vlm_providers:
            if provider.is_active:
                return provider
        return None

