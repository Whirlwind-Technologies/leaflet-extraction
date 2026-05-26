"""
Admin API endpoints for Provider Backup Management.

Simple backup management for platform providers with restore capabilities.
"""

from typing import List, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_superuser
from app.models.user import User
from app.models.vlm_provider_backup import VLMProviderBackup
from app.services.platform_vlm_service import PlatformVLMProviderService
from app.services.vlm_audit_service import VLMAuditService
from app.schemas.platform_vlm import BackupRestoreRequest

router = APIRouter()


@router.get("")
async def list_provider_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Dict[str, Any]:
    """List all provider backups."""
    audit_service = VLMAuditService(db)

    try:
        # Get total count
        count_query = select(func.count()).select_from(VLMProviderBackup)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get backups with pagination
        query = select(VLMProviderBackup).offset(skip).limit(limit).order_by(VLMProviderBackup.created_at.desc())
        result = await db.execute(query)
        backups = result.scalars().all()

        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="list_provider_backups",
            resource_type="provider_backups"
        )

        # Build response items
        items = []
        for backup in backups:
            # Get backup type value safely
            backup_type_val = backup.backup_type.value if hasattr(backup.backup_type, 'value') else str(backup.backup_type) if backup.backup_type else "manual"

            items.append({
                "id": str(backup.id),
                "provider_id": str(backup.platform_provider_id) if backup.platform_provider_id else None,
                "provider_name": backup.provider_name or "Unknown",
                "provider_type": backup.provider_type or "unknown",
                "backup_type": backup_type_val,
                "backup_data": {},  # Config is encrypted, don't expose
                "description": backup.backup_note,
                "created_by_user_id": str(backup.created_by_user_id) if backup.created_by_user_id else None,
                "created_by_email": "Admin",  # Would need to join with users table to get email
                "created_at": backup.created_at.isoformat() if backup.created_at else None,
                "file_size_bytes": backup.size_bytes if hasattr(backup, 'size_bytes') else len(backup.encrypted_config) if backup.encrypted_config else 0,
                "checksum": backup.backup_hash or "",
                "is_compressed": False,
                "restoration_count": 0,  # Would need additional tracking
                "last_restored_at": backup.restored_at.isoformat() if backup.restored_at else None,
            })

        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="list_provider_backups",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list provider backups: {str(e)}"
        )


@router.post("/{backup_id}/restore")
async def restore_provider_backup(
    backup_id: UUID,
    request: BackupRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """Restore a provider from backup."""
    service = PlatformVLMProviderService(db)
    audit_service = VLMAuditService(db)

    try:
        result = await service.restore_provider_from_backup(
            backup_id=backup_id,
            restore_reason=request.restore_reason,
            restored_by=current_user.id
        )

        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="restore_provider_backup",
            resource_type="provider_backup",
            resource_id=backup_id,
            resource_data={"restore_reason": request.restore_reason}
        )

        return result

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="restore_provider_backup",
            error_message=str(e),
            resource_id=backup_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to restore backup: {str(e)}"
        )


@router.post("")
async def create_provider_backup(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Create a new backup of a platform provider configuration.

    Request body:
    - provider_id: UUID of the provider to backup
    - backup_type: Type of backup (manual, scheduled, pre_change)
    - description: Optional description for the backup
    """
    from app.models.platform_vlm_provider import PlatformVLMProvider
    from app.models.vlm_provider_backup import VLMProviderBackup, BackupType

    audit_service = VLMAuditService(db)

    provider_id = data.get("provider_id")
    backup_type_str = data.get("backup_type", "manual")
    description = data.get("description")

    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider_id is required"
        )

    try:
        # Get the provider
        provider_uuid = UUID(provider_id)
        query = select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_uuid)
        result = await db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        # Map backup type string to enum
        backup_type_map = {
            "manual": BackupType.MANUAL,
            "scheduled": BackupType.SCHEDULED,
            "pre_change": BackupType.PRE_UPDATE,
            "pre_deletion": BackupType.PRE_DELETION,
            "pre_update": BackupType.PRE_UPDATE,
        }
        backup_type = backup_type_map.get(backup_type_str, BackupType.MANUAL)

        # Build provider config for backup (exclude sensitive decrypted data)
        provider_config = {
            "name": provider.name,
            "provider_type": provider.provider_type.value if hasattr(provider.provider_type, 'value') else str(provider.provider_type),
            "api_endpoint": provider.api_endpoint,
            "model_name": provider.model_name,
            "max_tokens": provider.max_tokens,
            "temperature": float(provider.temperature) if provider.temperature else 0.0,
            "config": provider.config or {},
            "priority": provider.priority,
            "is_active": provider.is_active,
            "is_default": provider.is_default,
            "monthly_budget": float(provider.monthly_budget) if provider.monthly_budget else None,
            "daily_budget": float(provider.daily_budget) if provider.daily_budget else None,
            "max_requests_per_hour": provider.max_requests_per_hour,
        }

        # Create backup record
        backup = VLMProviderBackup(
            platform_provider_id=provider.id,
            backup_type=backup_type,
            provider_name=provider.name,
            provider_type=provider.provider_type.value if hasattr(provider.provider_type, 'value') else str(provider.provider_type),
            backup_note=description,
            created_by_user_id=current_user.id,
        )

        # Create the encrypted backup
        backup.create_backup(provider_config)

        db.add(backup)
        await db.commit()
        await db.refresh(backup)

        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="create_provider_backup",
            resource_type="provider_backup",
            resource_id=backup.id,
            resource_data={
                "provider_id": str(provider.id),
                "backup_type": backup_type_str,
            }
        )

        return {
            "backup_id": str(backup.id),
            "message": f"Backup created successfully for provider {provider.name}",
        }

    except HTTPException:
        raise
    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="create_provider_backup",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}"
        )


@router.delete("/{backup_id}")
async def delete_provider_backup(
    backup_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """Delete a provider backup."""
    audit_service = VLMAuditService(db)

    try:
        # Get the backup
        query = select(VLMProviderBackup).where(VLMProviderBackup.id == backup_id)
        result = await db.execute(query)
        backup = result.scalar_one_or_none()

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )

        # Delete the backup
        await db.delete(backup)
        await db.commit()

        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="delete_provider_backup",
            resource_type="provider_backup",
            resource_id=backup_id,
            resource_data={"provider_name": backup.provider_name}
        )

        return {"message": "Backup deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="delete_provider_backup",
            error_message=str(e),
            resource_id=backup_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backup: {str(e)}"
        )


@router.get("/{backup_id}/download")
async def download_provider_backup(
    backup_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Download a provider backup as JSON.

    Returns a data URL that can be used for browser downloads.
    """
    import base64
    import json
    from datetime import timedelta, timezone

    audit_service = VLMAuditService(db)

    try:
        # Get the backup
        query = select(VLMProviderBackup).where(VLMProviderBackup.id == backup_id)
        result = await db.execute(query)
        backup = result.scalar_one_or_none()

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )

        # Build export data (without exposing encrypted config directly)
        export_data = {
            "backup_id": str(backup.id),
            "provider_name": backup.provider_name,
            "provider_type": backup.provider_type,
            "backup_type": backup.backup_type.value if hasattr(backup.backup_type, 'value') else str(backup.backup_type),
            "backup_note": backup.backup_note,
            "config_version": backup.config_version,
            "backup_hash": backup.backup_hash,
            "created_at": backup.created_at.isoformat() if backup.created_at else None,
            "created_by_user_id": str(backup.created_by_user_id) if backup.created_by_user_id else None,
            "status": backup.status.value if hasattr(backup.status, 'value') else str(backup.status),
            "is_restorable": backup.is_restorable,
        }

        # Try to include decrypted config if restorable (for full backup download)
        if backup.is_restorable:
            try:
                export_data["config"] = backup.restore_config()
            except Exception:
                export_data["config"] = None
                export_data["config_error"] = "Could not decrypt configuration"

        # Convert to JSON and encode as base64 data URL
        json_content = json.dumps(export_data, indent=2)
        encoded_content = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
        download_url = f"data:application/json;base64,{encoded_content}"

        # Generate filename
        safe_name = backup.provider_name.replace(" ", "_").replace("/", "-")
        created_date = backup.created_at.strftime("%Y%m%d") if backup.created_at else "unknown"
        filename = f"{safe_name}-backup-{created_date}.json"

        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="download_provider_backup",
            resource_type="provider_backup",
            resource_id=backup_id,
            resource_data={"provider_name": backup.provider_name}
        )

        return {
            "download_url": download_url,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "filename": filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="download_provider_backup",
            error_message=str(e),
            resource_id=backup_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download backup: {str(e)}"
        )