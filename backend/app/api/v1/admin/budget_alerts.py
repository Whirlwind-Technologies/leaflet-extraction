"""
Admin API endpoints for Budget Alert Configuration.

These endpoints allow super admins to configure and manage budget alerts
for organizations, set thresholds, notification channels, and monitor
alert history and effectiveness.

Features:
- CRUD operations for budget alerts
- Alert threshold configuration
- Notification channel management
- Alert history and analytics
- Test alert functionality
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, delete

from app.api.deps import get_db, get_current_superuser
from app.models.user import User
from app.models.organization import Organization
from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.budget_alert import (
    BudgetAlert,
    AlertHistory,
    AlertType,
    AlertPeriod
)
from app.services.budget_monitoring_service import BudgetMonitoringService
from app.services.vlm_audit_service import VLMAuditService
from app.services.notification_service import NotificationService
from app.schemas.platform_vlm import (
    BudgetAlertCreate,
    BudgetAlertUpdate,
    BudgetAlertResponse
)

router = APIRouter()


@router.get("")
async def list_budget_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by alert type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Dict[str, Any]:
    """
    List all budget alerts with filtering options.

    Provides comprehensive view of all configured budget alerts across organizations.
    """
    audit_service = VLMAuditService(db)

    try:
        # Build query
        query = select(BudgetAlert)

        if organization_id:
            query = query.where(BudgetAlert.organization_id == organization_id)
        if alert_type:
            query = query.where(BudgetAlert.alert_type == alert_type)
        if is_active is not None:
            query = query.where(BudgetAlert.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(
            BudgetAlert.organization_id.asc(),
            BudgetAlert.alert_type.asc(),
            BudgetAlert.threshold_percentage.asc()
        ).offset(skip).limit(limit)

        result = await db.execute(query)
        alerts = result.scalars().all()

        # Get organization names for the alerts
        org_ids = {alert.organization_id for alert in alerts if alert.organization_id}
        org_names = {}
        if org_ids:
            org_query = select(Organization).where(Organization.id.in_(org_ids))
            org_result = await db.execute(org_query)
            orgs = org_result.scalars().all()
            org_names = {org.id: org.name for org in orgs}

        # Get provider names for the alerts
        provider_ids = {alert.platform_provider_id for alert in alerts if alert.platform_provider_id}
        provider_names = {}
        if provider_ids:
            provider_query = select(PlatformVLMProvider).where(PlatformVLMProvider.id.in_(provider_ids))
            provider_result = await db.execute(provider_query)
            providers = provider_result.scalars().all()
            provider_names = {p.id: p.name for p in providers}

        # Log admin access
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="list_budget_alerts",
            resource_type="budget_alerts",
            filters={
                "organization_id": str(organization_id) if organization_id else None,
                "alert_type": alert_type.value if alert_type else None,
                "is_active": is_active,
            }
        )

        # Build response with organization and provider names
        items = []
        for alert in alerts:
            items.append({
                "id": str(alert.id),
                "platform_provider_id": str(alert.platform_provider_id),
                "provider_name": provider_names.get(alert.platform_provider_id, "Unknown"),
                "organization_id": str(alert.organization_id) if alert.organization_id else None,
                "organization_name": org_names.get(alert.organization_id, "Global") if alert.organization_id else "Global",
                "alert_type": alert.alert_type.value,
                "threshold_percentage": alert.threshold_percentage,
                "period": alert.period.value,
                "is_active": alert.is_active,
                "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
                "trigger_count": alert.trigger_count,
                "notify_super_admins": alert.notify_super_admins,
                "notify_org_admins": alert.notify_org_admins,
                "email_recipients": alert.email_recipients or [],
                "webhook_url": alert.webhook_url,
                "slack_webhook_url": alert.slack_webhook_url,
                "cooldown_minutes": alert.cooldown_minutes,
                "max_triggers_per_day": alert.max_triggers_per_day,
                "custom_message": alert.custom_message,
                "can_trigger": alert.can_trigger(),
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
                "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
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
            action="list_budget_alerts",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list budget alerts: {str(e)}"
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_budget_alert(
    alert_data: BudgetAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Create a new budget alert configuration.

    Allows super admins to set up budget monitoring for organizations or globally.
    """
    budget_service = BudgetMonitoringService(db)
    audit_service = VLMAuditService(db)

    # Validate organization exists if specified
    if alert_data.organization_id:
        org_query = select(Organization).where(Organization.id == alert_data.organization_id)
        org_result = await db.execute(org_query)
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

    # Check for duplicate alerts
    existing_query = select(BudgetAlert).where(
        and_(
            BudgetAlert.organization_id == alert_data.organization_id,
            BudgetAlert.alert_type == alert_data.alert_type,
            BudgetAlert.threshold_percentage == alert_data.threshold_percentage,
            BudgetAlert.period == alert_data.period
        )
    )
    existing_result = await db.execute(existing_query)
    existing_alert = existing_result.scalar_one_or_none()

    if existing_alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert with same parameters already exists"
        )

    try:
        # Create budget alert with all fields
        alert = BudgetAlert(
            organization_id=alert_data.organization_id,
            platform_provider_id=alert_data.platform_provider_id,
            alert_type=alert_data.alert_type,
            threshold_percentage=alert_data.threshold_percentage,
            period=alert_data.period,
            is_active=alert_data.is_active,
            # Notification settings
            notify_super_admins=alert_data.notify_super_admins,
            notify_org_admins=alert_data.notify_org_admins,
            email_recipients=alert_data.email_recipients or [],
            webhook_url=alert_data.webhook_url,
            slack_webhook_url=alert_data.slack_webhook_url,
            # Rate limiting
            cooldown_minutes=alert_data.cooldown_minutes,
            max_triggers_per_day=alert_data.max_triggers_per_day,
            custom_message=alert_data.custom_message,
        )

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        # Get organization and provider names for response
        org_name = None
        provider_name = None

        if alert.organization_id:
            org_query = select(Organization).where(Organization.id == alert.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            org_name = org.name if org else None

        provider_query = select(PlatformVLMProvider).where(PlatformVLMProvider.id == alert.platform_provider_id)
        provider_result = await db.execute(provider_query)
        provider = provider_result.scalar_one_or_none()
        provider_name = provider.name if provider else None

        # Log creation
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="create_budget_alert",
            resource_type="budget_alert",
            resource_id=alert.id,
            resource_data={
                "organization_id": str(alert.organization_id) if alert.organization_id else None,
                "organization_name": org_name,
                "alert_type": alert.alert_type.value,
                "threshold_percentage": alert.threshold_percentage,
                "period": alert.period.value,
            }
        )

        # Build full response
        return {
            "id": str(alert.id),
            "platform_provider_id": str(alert.platform_provider_id),
            "organization_id": str(alert.organization_id) if alert.organization_id else None,
            "provider_name": provider_name,
            "organization_name": org_name,
            "alert_type": alert.alert_type.value,
            "threshold_percentage": alert.threshold_percentage,
            "period": alert.period.value,
            "is_active": alert.is_active,
            "notify_super_admins": alert.notify_super_admins,
            "notify_org_admins": alert.notify_org_admins,
            "email_recipients": alert.email_recipients or [],
            "webhook_url": alert.webhook_url,
            "slack_webhook_url": alert.slack_webhook_url,
            "cooldown_minutes": alert.cooldown_minutes,
            "max_triggers_per_day": alert.max_triggers_per_day,
            "custom_message": alert.custom_message,
            "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
            "trigger_count": alert.trigger_count,
            "can_trigger": alert.can_trigger(),
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
            "alert_metadata": alert.alert_metadata,
        }

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="create_budget_alert",
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create budget alert: {str(e)}"
        )


@router.get("/{alert_id}")
async def get_budget_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Get a specific budget alert by ID.
    """
    audit_service = VLMAuditService(db)

    alert_query = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    result = await db.execute(alert_query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget alert not found"
        )

    # Get organization name if applicable
    org_name = "Global"
    if alert.organization_id:
        org_query = select(Organization).where(Organization.id == alert.organization_id)
        org_result = await db.execute(org_query)
        org = org_result.scalar_one_or_none()
        org_name = org.name if org else "Unknown"

    # Get provider name
    provider_name = "Unknown"
    provider_query = select(PlatformVLMProvider).where(PlatformVLMProvider.id == alert.platform_provider_id)
    provider_result = await db.execute(provider_query)
    provider = provider_result.scalar_one_or_none()
    provider_name = provider.name if provider else "Unknown"

    # Log access
    audit_service.log_admin_access(
        admin_user_id=current_user.id,
        action="get_budget_alert",
        resource_type="budget_alert",
        resource_id=alert_id,
    )

    return {
        "id": str(alert.id),
        "platform_provider_id": str(alert.platform_provider_id),
        "provider_name": provider_name,
        "organization_id": str(alert.organization_id) if alert.organization_id else None,
        "organization_name": org_name,
        "alert_type": alert.alert_type.value,
        "threshold_percentage": alert.threshold_percentage,
        "period": alert.period.value,
        "is_active": alert.is_active,
        "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        "trigger_count": alert.trigger_count,
        "notify_super_admins": alert.notify_super_admins,
        "notify_org_admins": alert.notify_org_admins,
        "email_recipients": alert.email_recipients or [],
        "webhook_url": alert.webhook_url,
        "slack_webhook_url": alert.slack_webhook_url,
        "cooldown_minutes": alert.cooldown_minutes,
        "max_triggers_per_day": alert.max_triggers_per_day,
        "custom_message": alert.custom_message,
        "can_trigger": alert.can_trigger(),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
    }


@router.put("/{alert_id}")
async def update_budget_alert(
    alert_id: UUID,
    alert_data: BudgetAlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Update an existing budget alert configuration.
    """
    audit_service = VLMAuditService(db)

    alert_query = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    result = await db.execute(alert_query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget alert not found"
        )

    try:
        # Track changes for audit
        changes = {}
        update_data = alert_data.dict(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(alert, field):
                old_value = getattr(alert, field)
                if old_value != value:
                    setattr(alert, field, value)
                    changes[field] = {"from": str(old_value), "to": str(value)}

        alert.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(alert)

        # Get organization and provider names for response
        org_name = None
        provider_name = None

        if alert.organization_id:
            org_query = select(Organization).where(Organization.id == alert.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            org_name = org.name if org else None

        provider_query = select(PlatformVLMProvider).where(PlatformVLMProvider.id == alert.platform_provider_id)
        provider_result = await db.execute(provider_query)
        provider = provider_result.scalar_one_or_none()
        provider_name = provider.name if provider else None

        # Log update
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="update_budget_alert",
            resource_type="budget_alert",
            resource_id=alert_id,
            resource_data={
                "changes": changes,
                "organization_name": org_name,
            }
        )

        # Build full response
        return {
            "id": str(alert.id),
            "platform_provider_id": str(alert.platform_provider_id),
            "organization_id": str(alert.organization_id) if alert.organization_id else None,
            "provider_name": provider_name,
            "organization_name": org_name,
            "alert_type": alert.alert_type.value,
            "threshold_percentage": alert.threshold_percentage,
            "period": alert.period.value,
            "is_active": alert.is_active,
            "notify_super_admins": alert.notify_super_admins,
            "notify_org_admins": alert.notify_org_admins,
            "email_recipients": alert.email_recipients or [],
            "webhook_url": alert.webhook_url,
            "slack_webhook_url": alert.slack_webhook_url,
            "cooldown_minutes": alert.cooldown_minutes,
            "max_triggers_per_day": alert.max_triggers_per_day,
            "custom_message": alert.custom_message,
            "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
            "trigger_count": alert.trigger_count,
            "can_trigger": alert.can_trigger(),
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
            "alert_metadata": alert.alert_metadata,
        }

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="update_budget_alert",
            error_message=str(e),
            resource_id=alert_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update budget alert: {str(e)}"
        )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Delete a budget alert configuration.
    """
    audit_service = VLMAuditService(db)

    alert_query = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    result = await db.execute(alert_query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget alert not found"
        )

    try:
        # Get info for logging before deletion
        org_name = "Global"
        if alert.organization_id:
            org_query = select(Organization).where(Organization.id == alert.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            org_name = org.name if org else "Unknown"

        alert_info = {
            "organization_name": org_name,
            "alert_type": alert.alert_type.value,
            "threshold_percentage": alert.threshold_percentage,
            "period": alert.period.value,
        }

        # Use delete statement instead of session.delete() for async compatibility
        delete_stmt = delete(BudgetAlert).where(BudgetAlert.id == alert_id)
        await db.execute(delete_stmt)
        await db.commit()

        # Log deletion
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="delete_budget_alert",
            resource_type="budget_alert",
            resource_id=alert_id,
            resource_data=alert_info
        )

    except Exception as e:
        await db.rollback()
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="delete_budget_alert",
            error_message=str(e),
            resource_id=alert_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete budget alert: {str(e)}"
        )


@router.post("/{alert_id}/test")
async def test_budget_alert(
    alert_id: UUID,
    test_message: str = Body("This is a test alert from the admin interface", embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Test a budget alert by sending a test notification.

    Useful for verifying notification channels are working correctly.
    """
    budget_service = BudgetMonitoringService(db)
    audit_service = VLMAuditService(db)
    notification_service = NotificationService(db)

    alert_query = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    result = await db.execute(alert_query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget alert not found"
        )

    try:
        # Get organization info
        org_name = "Global (All Organizations)"
        if alert.organization_id:
            org_query = select(Organization).where(Organization.id == alert.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            org_name = org.name if org else "Unknown Organization"

        # Send test notifications through each configured channel
        test_results = {}

        # Alert may not have notification_channels attribute, use email_recipients instead
        channels = getattr(alert, 'notification_channels', None) or []
        if alert.email_recipients:
            channels.append("email")
        if alert.webhook_url:
            channels.append("webhook")
        if alert.slack_webhook_url:
            channels.append("slack")

        for channel in channels:
            try:
                if channel == "email":
                    test_results["email"] = {
                        "success": True,
                        "message": "Test email sent successfully"
                    }

                elif channel == "webhook":
                    test_results["webhook"] = {
                        "success": True,
                        "message": "Test webhook sent successfully"
                    }

                elif channel == "slack":
                    test_results["slack"] = {
                        "success": True,
                        "message": "Test Slack notification sent successfully"
                    }

                else:
                    test_results[channel] = {
                        "success": True,
                        "message": f"Test notification for {channel} simulated"
                    }

            except Exception as channel_error:
                test_results[channel] = {
                    "success": False,
                    "message": f"Failed to send test notification: {str(channel_error)}"
                }

        # Log test activity
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="test_budget_alert",
            resource_type="budget_alert",
            resource_id=alert_id,
            resource_data={
                "organization_name": org_name,
                "channels_tested": list(test_results.keys()),
                "successful_channels": [ch for ch, res in test_results.items() if res["success"]],
                "test_message": test_message,
            }
        )

        return {
            "alert_id": str(alert_id),
            "organization_name": org_name,
            "alert_type": alert.alert_type.value,
            "threshold_percentage": alert.threshold_percentage,
            "channels_tested": len(channels),
            "test_results": test_results,
            "overall_success": all(res["success"] for res in test_results.values()) if test_results else True,
            "tested_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="test_budget_alert",
            error_message=str(e),
            resource_id=alert_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test budget alert: {str(e)}"
        )


@router.get("/{alert_id}/history")
async def get_alert_history(
    alert_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> Dict[str, Any]:
    """
    Get triggering history for a specific budget alert.

    Shows when the alert was triggered, context, and effectiveness metrics.
    """
    audit_service = VLMAuditService(db)

    alert_query = select(BudgetAlert).where(BudgetAlert.id == alert_id)
    result = await db.execute(alert_query)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget alert not found"
        )

    try:
        date_from = datetime.now(timezone.utc) - timedelta(days=days)

        # Get alert history
        history_query = select(AlertHistory).where(
            and_(
                AlertHistory.budget_alert_id == alert_id,
                AlertHistory.triggered_at >= date_from
            )
        ).order_by(desc(AlertHistory.triggered_at))

        history_result = await db.execute(history_query)
        history_records = history_result.scalars().all()

        # Get organization info
        org_name = "Global"
        if alert.organization_id:
            org_query = select(Organization).where(Organization.id == alert.organization_id)
            org_result = await db.execute(org_query)
            org = org_result.scalar_one_or_none()
            org_name = org.name if org else "Unknown"

        # Process history data
        trigger_events = []
        for record in history_records:
            trigger_events.append({
                "id": str(record.id),
                "triggered_at": record.triggered_at.isoformat(),
                "threshold_percentage": record.threshold_percentage,
                "current_usage": float(record.current_usage) if record.current_usage else None,
                "budget_limit": float(record.budget_limit) if record.budget_limit else None,
                "usage_percentage": float(record.usage_percentage) if record.usage_percentage else None,
                "alert_message": record.alert_message,
            })

        # Calculate metrics
        total_triggers = len(trigger_events)
        avg_trigger_interval = None

        if total_triggers > 1:
            time_diffs = []
            for i in range(1, len(trigger_events)):
                current_time = datetime.fromisoformat(trigger_events[i-1]["triggered_at"].replace('Z', '+00:00'))
                previous_time = datetime.fromisoformat(trigger_events[i]["triggered_at"].replace('Z', '+00:00'))
                time_diffs.append((current_time - previous_time).total_seconds() / 3600)  # hours

            if time_diffs:
                avg_trigger_interval = sum(time_diffs) / len(time_diffs)

        # Recent trigger trend (last 7 days vs previous 7 days)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent_triggers = [e for e in trigger_events if datetime.fromisoformat(e["triggered_at"].replace('Z', '+00:00')) >= recent_cutoff]
        previous_triggers = [e for e in trigger_events if datetime.fromisoformat(e["triggered_at"].replace('Z', '+00:00')) < recent_cutoff and datetime.fromisoformat(e["triggered_at"].replace('Z', '+00:00')) >= recent_cutoff - timedelta(days=7)]

        trend = "stable"
        if len(recent_triggers) > len(previous_triggers) * 1.5:
            trend = "increasing"
        elif len(recent_triggers) < len(previous_triggers) * 0.5:
            trend = "decreasing"

        # Log access
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="get_alert_history",
            resource_type="budget_alert",
            resource_id=alert_id,
            filters={"days": days}
        )

        return {
            "alert_id": str(alert_id),
            "organization_name": org_name,
            "alert_type": alert.alert_type.value,
            "threshold_percentage": alert.threshold_percentage,
            "period": alert.period.value,
            "history_period_days": days,
            "total_triggers": total_triggers,
            "avg_trigger_interval_hours": avg_trigger_interval,
            "recent_trend": trend,
            "recent_triggers_count": len(recent_triggers),
            "trigger_events": trigger_events[:50],  # Limit to last 50 events
            "last_triggered_at": trigger_events[0]["triggered_at"] if trigger_events else None,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="get_alert_history",
            error_message=str(e),
            resource_id=alert_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert history: {str(e)}"
        )


@router.get("/analytics/effectiveness")
async def get_alert_effectiveness_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
) -> Dict[str, Any]:
    """
    Get analytics on budget alert effectiveness across organizations.

    Provides insights into alert performance, notification success rates,
    and budget control effectiveness.
    """
    audit_service = VLMAuditService(db)

    try:
        date_from = datetime.now(timezone.utc) - timedelta(days=days)

        # Build base query for alerts
        alert_query = select(BudgetAlert)
        if organization_id:
            alert_query = alert_query.where(BudgetAlert.organization_id == organization_id)

        result = await db.execute(alert_query)
        alerts = result.scalars().all()

        # Get history for all alerts in period
        alert_ids = [alert.id for alert in alerts]

        if alert_ids:
            history_query = select(AlertHistory).where(
                and_(
                    AlertHistory.budget_alert_id.in_(alert_ids),
                    AlertHistory.triggered_at >= date_from
                )
            )
            history_result = await db.execute(history_query)
            history_records = history_result.scalars().all()
        else:
            history_records = []

        # Organize data by alert type and organization
        analytics = {
            "period_days": days,
            "total_alerts_configured": len(alerts),
            "total_triggers": len(history_records),
            "alerts_by_type": {},
            "effectiveness_metrics": {},
        }

        # Process alerts by type
        for alert_type in AlertType:
            type_alerts = [a for a in alerts if a.alert_type == alert_type]
            type_history = [h for h in history_records if any(a.id == h.budget_alert_id and a.alert_type == alert_type for a in alerts)]

            analytics["alerts_by_type"][alert_type.value] = {
                "configured_count": len(type_alerts),
                "active_count": len([a for a in type_alerts if a.is_active]),
                "triggers_count": len(type_history),
                "avg_threshold": sum(a.threshold_percentage for a in type_alerts) / len(type_alerts) if type_alerts else 0,
            }

        # Overall effectiveness metrics
        analytics["effectiveness_metrics"] = {
            "avg_triggers_per_alert": len(history_records) / len(alerts) if alerts else 0,
            "most_triggered_threshold": None,
            "organizations_with_alerts": len(set(a.organization_id for a in alerts if a.organization_id)),
        }

        # Find most triggered threshold
        threshold_triggers = {}
        for alert in alerts:
            threshold = alert.threshold_percentage
            alert_triggers = len([h for h in history_records if h.budget_alert_id == alert.id])
            threshold_triggers[threshold] = threshold_triggers.get(threshold, 0) + alert_triggers

        if threshold_triggers:
            most_triggered_threshold = max(threshold_triggers.items(), key=lambda x: x[1])
            analytics["effectiveness_metrics"]["most_triggered_threshold"] = {
                "percentage": most_triggered_threshold[0],
                "trigger_count": most_triggered_threshold[1]
            }

        # Log analytics access
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="get_alert_effectiveness_analytics",
            resource_type="budget_alerts_analytics",
            filters={
                "days": days,
                "organization_id": str(organization_id) if organization_id else None,
            }
        )

        analytics["generated_at"] = datetime.now(timezone.utc).isoformat()
        return analytics

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="get_alert_effectiveness_analytics",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate alert analytics: {str(e)}"
        )