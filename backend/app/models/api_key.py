"""
API Key Model Module.

This module defines the APIKey model for public API authentication.
Allows users to create and manage API keys for programmatic access.

Example Usage:
    from app.models.api_key import APIKey
    
    api_key = APIKey.create_key(
        user_id=user.id,
        name="Production API Key",
        scopes=["read", "write", "export"]
    )
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple
import uuid
import secrets
import hashlib

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, TimestampMixin


class APIKeyScope(str, Enum):
    """
    API key permission scopes.
    
    Attributes:
        READ: Read access to data
        WRITE: Write/modify access
        EXPORT: Export data
        UPLOAD: Upload leaflets
        ADMIN: Administrative access
    """
    READ = "read"
    WRITE = "write"
    EXPORT = "export"
    UPLOAD = "upload"
    DELETE = "delete"
    ADMIN = "admin"


class APIKey(BaseModel, TimestampMixin):
    """
    API Key for public API authentication.
    
    Stores hashed API keys with scopes and rate limits.
    
    Attributes:
        id: Unique identifier (UUID)
        user_id: Owner user ID
        name: User-friendly name
        key_prefix: First 8 characters of key (for identification)
        key_hash: SHA-256 hash of the full key
        scopes: List of permission scopes
        rate_limit: Requests per minute limit
        is_active: Whether key is active
        expires_at: Optional expiration date
        last_used_at: Last usage timestamp
        total_requests: Total requests made
    """
    
    __tablename__ = "api_keys"
    
    # Owner
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID"
    )

    # Organization ownership
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this API key belongs to"
    )

    # Key identification
    name = Column(
        String(100),
        nullable=False,
        comment="User-friendly name"
    )
    
    key_prefix = Column(
        String(12),
        nullable=False,
        index=True,
        comment="First characters of key for identification"
    )
    
    key_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of the full key"
    )
    
    # Permissions
    scopes = Column(
        ARRAY(String),
        nullable=False,
        default=["read"],
        comment="Permission scopes"
    )
    
    # Rate limiting
    rate_limit = Column(
        Integer,
        nullable=False,
        default=60,
        comment="Requests per minute limit"
    )
    
    daily_limit = Column(
        Integer,
        nullable=True,
        comment="Daily request limit (optional)"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether key is active"
    )
    
    expires_at = Column(
        DateTime,
        nullable=True,
        comment="Optional expiration date"
    )
    
    # Usage tracking
    last_used_at = Column(
        DateTime,
        nullable=True,
        comment="Last usage timestamp"
    )
    
    last_used_ip = Column(
        String(45),
        nullable=True,
        comment="Last used IP address"
    )
    
    total_requests = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total requests made"
    )
    
    requests_today = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Requests made today"
    )
    
    last_reset_date = Column(
        DateTime,
        nullable=True,
        comment="Last daily counter reset date"
    )
    
    # Metadata
    description = Column(
        Text,
        nullable=True,
        comment="Optional description"
    )
    
    allowed_ips = Column(
        ARRAY(String),
        nullable=True,
        comment="IP whitelist (optional)"
    )
    
    allowed_origins = Column(
        ARRAY(String),
        nullable=True,
        comment="Origin whitelist for CORS (optional)"
    )
    
    # Note: Using 'metadata_' as column name since 'metadata' is reserved in PostgreSQL
    metadata_ = Column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional metadata"
    )
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a new API key.
        
        Format: lep_<random_string>
        (lep = leaflet extraction platform)
        """
        random_part = secrets.token_urlsafe(32)
        return f"lep_{random_part}"
    
    @classmethod
    def hash_key(cls, key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    @classmethod
    def create_key(
        cls,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        name: str,
        scopes: List[str] = None,
        rate_limit: int = 60,
        daily_limit: int = None,
        expires_in_days: int = None,
        description: str = None,
        allowed_ips: List[str] = None,
    ) -> Tuple["APIKey", str]:
        """
        Create a new API key scoped to an organization.

        Args:
            user_id: Owner user ID
            organization_id: Organization this key belongs to
            name: Friendly name
            scopes: Permission scopes
            rate_limit: Requests per minute
            daily_limit: Daily request limit
            expires_in_days: Days until expiration
            description: Optional description
            allowed_ips: IP whitelist

        Returns:
            Tuple of (APIKey instance, raw key string)
            Note: Raw key is only available at creation time
        """
        raw_key = cls.generate_key()

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = cls(
            user_id=user_id,
            organization_id=organization_id,
            name=name,
            key_prefix=raw_key[:12],
            key_hash=cls.hash_key(raw_key),
            scopes=scopes or ["read"],
            rate_limit=rate_limit,
            daily_limit=daily_limit,
            expires_at=expires_at,
            description=description,
            allowed_ips=allowed_ips,
        )

        return api_key, raw_key
    
    @classmethod
    async def verify_key(cls, db, key: str) -> Optional["APIKey"]:
        """
        Verify an API key and return the key object if valid.
        
        Args:
            db: Database session
            key: Raw API key string
            
        Returns:
            APIKey if valid, None otherwise
        """
        from sqlalchemy import select
        
        key_hash = cls.hash_key(key)
        result = await db.execute(
            select(cls).where(cls.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()
        
        if api_key and api_key.is_valid:
            return api_key
        return None
    
    @property
    def is_valid(self) -> bool:
        """Check if key is valid (active and not expired)."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        
        # Handle timezone-aware vs naive datetimes
        now = datetime.utcnow()
        expires = self.expires_at
        
        # If expires_at is timezone-aware, make it naive by removing tzinfo
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        
        return now > expires
    
    def has_scope(self, scope: str) -> bool:
        """Check if key has a specific scope."""
        return scope in self.scopes or "admin" in self.scopes
    
    def check_ip(self, ip: str) -> bool:
        """Check if IP is allowed."""
        if not self.allowed_ips:
            return True
        return ip in self.allowed_ips
    
    def check_rate_limit(self) -> bool:
        """Check if within rate limit (basic check)."""
        # This is a placeholder - actual rate limiting should use Redis
        return True
    
    def check_daily_limit(self) -> bool:
        """Check if within daily limit."""
        if self.daily_limit is None:
            return True
        
        # Reset counter if new day
        today = datetime.utcnow().date()
        if self.last_reset_date is None:
            return True
        
        # Handle both date and datetime objects
        last_reset = self.last_reset_date
        if hasattr(last_reset, 'date'):
            last_reset = last_reset.date()
        
        if last_reset < today:
            return True
        
        return self.requests_today < self.daily_limit
    
    def record_usage(self, ip: str = None):
        """Record API key usage."""
        now = datetime.utcnow()
        today = now.date()
        
        # Reset daily counter if new day
        should_reset = False
        if self.last_reset_date is None:
            should_reset = True
        else:
            # Handle both date and datetime objects
            last_reset = self.last_reset_date
            if hasattr(last_reset, 'date'):
                last_reset = last_reset.date()
            should_reset = last_reset < today
        
        if should_reset:
            self.requests_today = 0
            self.last_reset_date = now
        
        self.total_requests += 1
        self.requests_today += 1
        self.last_used_at = now
        if ip:
            self.last_used_ip = ip
    
    def revoke(self):
        """Revoke this API key."""
        self.is_active = False
    
    def to_safe_dict(self) -> dict:
        """Return dict without sensitive data."""
        return {
            "id": str(self.id),
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "rate_limit": self.rate_limit,
            "daily_limit": self.daily_limit,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "total_requests": self.total_requests,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }