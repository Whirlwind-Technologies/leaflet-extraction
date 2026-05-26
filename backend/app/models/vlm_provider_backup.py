"""
VLM Provider Backup Model Module.

This module defines models for encrypted backup and recovery of platform
VLM provider configurations for disaster recovery purposes.

Example Usage:
    from app.models.vlm_provider_backup import VLMProviderBackup, BackupType

    backup = VLMProviderBackup(
        platform_provider_id=provider_id,
        backup_type=BackupType.MANUAL,
        created_by_user_id=admin_user_id,
        backup_note="Pre-production deployment backup"
    )
    backup.create_backup(provider_config)
"""

import enum
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    String,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from cryptography.fernet import Fernet

from app.models.base import Base
from app.config import settings


class BackupType(str, enum.Enum):
    """
    VLM provider backup types.

    Attributes:
        MANUAL: Manual backup created by admin
        SCHEDULED: Automated scheduled backup
        PRE_DELETION: Backup created before deletion
        PRE_UPDATE: Backup created before major update
        MIGRATION: Backup for system migration
        EMERGENCY: Emergency backup during incidents
    """
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PRE_DELETION = "pre_deletion"
    PRE_UPDATE = "pre_update"
    MIGRATION = "migration"
    EMERGENCY = "emergency"


class BackupStatus(str, enum.Enum):
    """
    Backup status enumeration.

    Attributes:
        ACTIVE: Backup is active and available
        ARCHIVED: Backup is archived but accessible
        EXPIRED: Backup has expired and may be deleted
        CORRUPTED: Backup failed integrity check
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


class VLMProviderBackup(Base):
    """
    Encrypted backup of platform VLM provider configurations.

    This model provides secure backup and recovery capabilities for platform
    VLM provider configurations, including API keys and settings.

    Attributes:
        id: Unique identifier (UUID)
        platform_provider_id: Source platform provider
        backup_type: Type of backup (manual, scheduled, etc.)

        # Encrypted Backup Data
        encrypted_config: Encrypted provider configuration
        backup_hash: SHA-256 hash for integrity verification
        encryption_key_id: Identifier for encryption key used

        # Metadata
        provider_name: Name of provider at time of backup
        provider_type: Type of provider at time of backup
        config_version: Version of configuration format
        backup_note: Admin notes about the backup

        # Retention and Status
        status: Current backup status
        expires_at: When backup should be deleted
        auto_delete: Whether to auto-delete on expiry

        # Verification
        last_verified_at: Last integrity check timestamp
        verification_passed: Result of last integrity check

        # Administrative
        created_by_user_id: Admin who created the backup
        restored_by_user_id: Admin who restored from backup (if applicable)
        restored_at: When backup was restored

        created_at: Creation timestamp
    """

    __tablename__ = "vlm_provider_backups"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique backup identifier"
    )

    # Source Reference
    platform_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_vlm_providers.id", ondelete="SET NULL"),
        nullable=True,  # Can be null if provider is deleted
        index=True,
        comment="Source platform provider (null if deleted)"
    )

    backup_type = Column(
        Enum(BackupType, create_type=False),
        nullable=False,
        index=True,
        comment="Type of backup (manual, scheduled, etc.)"
    )

    # Encrypted Backup Data
    encrypted_config = Column(
        Text,
        nullable=False,
        comment="Encrypted provider configuration (JSON)"
    )

    backup_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash for integrity verification"
    )

    encryption_key_id = Column(
        String(100),
        nullable=False,
        default="default",
        comment="Identifier for encryption key used"
    )

    # Provider Metadata (preserved for deleted providers)
    provider_name = Column(
        String(100),
        nullable=False,
        comment="Name of provider at time of backup"
    )

    provider_type = Column(
        String(50),
        nullable=False,
        comment="Type of provider at time of backup"
    )

    config_version = Column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version of configuration format"
    )

    backup_note = Column(
        Text,
        nullable=True,
        comment="Admin notes about the backup"
    )

    # Status and Retention
    status = Column(
        Enum(BackupStatus, create_type=False),
        nullable=False,
        default=BackupStatus.ACTIVE,
        index=True,
        comment="Current backup status"
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When backup should be deleted (null = never)"
    )

    auto_delete = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to auto-delete on expiry"
    )

    # Integrity Verification
    last_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last integrity check timestamp"
    )

    verification_passed = Column(
        Boolean,
        nullable=True,
        comment="Result of last integrity check"
    )

    # Administrative Tracking
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Admin who created the backup"
    )

    restored_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who restored from backup (if applicable)"
    )

    restored_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When backup was restored"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="NOW()",
        index=True,
        comment="Creation timestamp"
    )

    # Relationships
    platform_provider = relationship(
        "PlatformVLMProvider",
        doc="Source platform provider"
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        doc="Admin who created the backup"
    )

    restored_by = relationship(
        "User",
        foreign_keys=[restored_by_user_id],
        doc="Admin who restored from backup"
    )

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="check_expires_after_creation"),

        # Performance indexes
        Index("idx_backup_provider_created", "platform_provider_id", "created_at"),
        Index("idx_backup_created_by", "created_by_user_id", "created_at"),
        Index("idx_backup_type_created", "backup_type", "created_at"),
        Index("idx_backup_status_expires", "status", "expires_at"),
        Index("idx_backup_provider_type", "provider_type", "created_at"),

        # Cleanup indexes
        Index("idx_backup_auto_delete_expires", "auto_delete", "expires_at"),  # For cleanup jobs
    )

    # Encryption key (derived from settings)
    _fernet = None

    @classmethod
    def _get_fernet(cls) -> Fernet:
        """Get Fernet encryption instance for backups."""
        if cls._fernet is None:
            # Use SECRET_KEY to derive backup encryption key
            import base64
            key = hashlib.sha256(f"{settings.secret_key}_backup".encode()).digest()
            cls._fernet = Fernet(base64.urlsafe_b64encode(key))
        return cls._fernet

    def create_backup(self, provider_config: Dict[str, Any]) -> str:
        """
        Create encrypted backup of provider configuration.

        Args:
            provider_config: Provider configuration to backup

        Returns:
            str: Backup hash for verification

        Raises:
            ValueError: If configuration is invalid
        """
        if not provider_config:
            raise ValueError("Provider configuration cannot be empty")

        # Convert config to JSON
        config_json = json.dumps(provider_config, sort_keys=True, ensure_ascii=False)

        # Calculate hash before encryption
        self.backup_hash = hashlib.sha256(config_json.encode()).hexdigest()

        # Encrypt the configuration
        fernet = self._get_fernet()
        self.encrypted_config = fernet.encrypt(config_json.encode()).decode()

        # Set default expiry (1 year for manual backups, 30 days for scheduled)
        if self.expires_at is None:
            if self.backup_type == BackupType.MANUAL:
                self.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
            else:
                self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        return self.backup_hash

    def restore_config(self) -> Dict[str, Any]:
        """
        Restore and decrypt provider configuration.

        Returns:
            dict: Decrypted provider configuration

        Raises:
            ValueError: If backup is corrupted or cannot be decrypted
        """
        if self.status == BackupStatus.CORRUPTED:
            raise ValueError("Cannot restore from corrupted backup")

        if self.status == BackupStatus.EXPIRED:
            raise ValueError("Cannot restore from expired backup")

        try:
            # Decrypt the configuration
            fernet = self._get_fernet()
            config_json = fernet.decrypt(self.encrypted_config.encode()).decode()

            # Verify integrity
            calculated_hash = hashlib.sha256(config_json.encode()).hexdigest()
            if calculated_hash != self.backup_hash:
                self.status = BackupStatus.CORRUPTED
                self.verification_passed = False
                self.last_verified_at = datetime.now(timezone.utc)
                raise ValueError("Backup integrity check failed - data may be corrupted")

            # Parse JSON
            config = json.loads(config_json)

            # Update verification status
            self.verification_passed = True
            self.last_verified_at = datetime.now(timezone.utc)

            return config

        except Exception as e:
            self.status = BackupStatus.CORRUPTED
            self.verification_passed = False
            self.last_verified_at = datetime.now(timezone.utc)
            raise ValueError(f"Failed to restore backup: {str(e)}")

    def verify_integrity(self) -> bool:
        """
        Verify backup integrity without full restoration.

        Returns:
            bool: True if backup is intact, False if corrupted
        """
        try:
            # Attempt to decrypt and verify hash
            config = self.restore_config()
            return True
        except ValueError:
            return False

    def mark_restored(self, restored_by_user_id: uuid.UUID):
        """
        Mark backup as restored by a user.

        Args:
            restored_by_user_id: ID of user who performed the restore
        """
        self.restored_by_user_id = restored_by_user_id
        self.restored_at = datetime.now(timezone.utc)

    def extend_retention(self, days: int):
        """
        Extend backup retention period.

        Args:
            days: Number of days to extend retention
        """
        if self.expires_at:
            self.expires_at += timedelta(days=days)
        else:
            self.expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    def archive(self):
        """Archive the backup (preserves data but marks as archived)."""
        self.status = BackupStatus.ARCHIVED

    @property
    def is_expired(self) -> bool:
        """Check if backup has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_restorable(self) -> bool:
        """Check if backup can be restored."""
        return (
            self.status in [BackupStatus.ACTIVE, BackupStatus.ARCHIVED]
            and not self.is_expired
        )

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get number of days until expiry."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    @property
    def size_bytes(self) -> int:
        """Get approximate backup size in bytes."""
        return len(self.encrypted_config.encode())

    def to_dict(self, include_config: bool = False) -> dict:
        """
        Convert backup to dictionary for API responses.

        Args:
            include_config: Whether to include decrypted config (admin only)

        Returns:
            dict: Backup information
        """
        result = {
            "id": str(self.id),
            "platform_provider_id": str(self.platform_provider_id) if self.platform_provider_id else None,
            "backup_type": self.backup_type.value,
            "backup_hash": self.backup_hash,
            "provider_name": self.provider_name,
            "provider_type": self.provider_type,
            "config_version": self.config_version,
            "backup_note": self.backup_note,
            "status": self.status.value,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "auto_delete": self.auto_delete,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
            "verification_passed": self.verification_passed,
            "restored_at": self.restored_at.isoformat() if self.restored_at else None,
            "is_expired": self.is_expired,
            "is_restorable": self.is_restorable,
            "days_until_expiry": self.days_until_expiry,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
        }

        # Add user IDs if available
        if self.created_by_user_id:
            result["created_by_user_id"] = str(self.created_by_user_id)
        if self.restored_by_user_id:
            result["restored_by_user_id"] = str(self.restored_by_user_id)

        # Include decrypted config only if explicitly requested (admin access)
        if include_config and self.is_restorable:
            try:
                result["config"] = self.restore_config()
            except ValueError:
                result["config"] = None
                result["config_error"] = "Failed to decrypt configuration"

        return result

    def __repr__(self) -> str:
        """String representation of VLMProviderBackup."""
        return (
            f"<VLMProviderBackup(id={self.id}, provider={self.platform_provider_id}, "
            f"type={self.backup_type.value}, status={self.status.value}, "
            f"created_at={self.created_at}, expires_at={self.expires_at})>"
        )


# Default retention periods for different backup types
DEFAULT_RETENTION_DAYS = {
    BackupType.MANUAL: 365,      # 1 year
    BackupType.SCHEDULED: 30,    # 30 days
    BackupType.PRE_DELETION: 90, # 90 days
    BackupType.PRE_UPDATE: 30,   # 30 days
    BackupType.MIGRATION: 180,   # 6 months
    BackupType.EMERGENCY: 365,   # 1 year
}