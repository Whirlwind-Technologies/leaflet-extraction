"""
Budget Monitoring Service Module.

This service monitors platform VLM provider budgets and triggers alerts
when thresholds are exceeded. Supports configurable alert rules and
multiple notification channels.

Example Usage:
    from app.services.budget_monitoring_service import BudgetMonitoringService

    service = BudgetMonitoringService(db_session, notification_service)
    await service.check_all_budget_thresholds()
    await service.create_budget_alert(provider_id, AlertType.WARNING, 80, AlertPeriod.MONTHLY)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import Session

from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.budget_alert import BudgetAlert, AlertHistory, AlertType, AlertPeriod
from app.models.organization import Organization
from app.models.organization_usage import OrganizationVLMUsage
from app.services.notification_service import NotificationService
from app.models.system_notification import NotificationType, NotificationSeverity

logger = logging.getLogger(__name__)


class BudgetMonitoringService:
    """
    Service for monitoring VLM provider budgets and triggering alerts.

    This service handles:
    - Budget threshold monitoring
    - Alert creation and management
    - Notification delivery via multiple channels
    - Usage reports and analytics
    - Alert history and audit trail
    """

    def __init__(self, db_session: Session, notification_service: Optional[NotificationService] = None):
        """
        Initialize the budget monitoring service.

        Args:
            db_session: Database session (sync or async)
            notification_service: Service for sending notifications (optional)
        """
        self.db = db_session
        self.notification_service = notification_service or NotificationService(db_session)

    async def check_all_budget_thresholds(self) -> List[Dict[str, Any]]:
        """
        Check budget thresholds for all active platform providers.

        This method should be called periodically (e.g., every 15 minutes)
        to monitor budget usage and trigger alerts as needed.

        Returns:
            List[Dict]: List of triggered alerts with details
        """
        triggered_alerts = []

        # Get all active platform providers
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(PlatformVLMProvider).where(PlatformVLMProvider.is_active == True)
            )
        else:
            result = self.db.execute(
                select(PlatformVLMProvider).where(PlatformVLMProvider.is_active == True)
            )

        providers = result.scalars().all()

        for provider in providers:
            try:
                provider_alerts = await self._check_provider_budget_thresholds(provider)
                triggered_alerts.extend(provider_alerts)
            except Exception as e:
                logger.exception(f"Error checking budget thresholds for provider {provider.id}: {e}")

        logger.info(f"Budget monitoring completed. Triggered {len(triggered_alerts)} alerts.")
        return triggered_alerts

    async def create_budget_alert(
        self,
        platform_provider_id: uuid.UUID,
        alert_type: AlertType,
        threshold_percentage: int,
        period: AlertPeriod,
        organization_id: Optional[uuid.UUID] = None,
        notify_super_admins: bool = True,
        notify_org_admins: bool = False,
        email_recipients: Optional[List[str]] = None,
        webhook_url: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        custom_message: Optional[str] = None,
        cooldown_minutes: int = 60,
        max_triggers_per_day: int = 10
    ) -> BudgetAlert:
        """
        Create a new budget alert rule.

        Args:
            platform_provider_id: Provider to monitor
            alert_type: Type/severity of alert
            threshold_percentage: Percentage threshold (0-100)
            period: Monitoring period (daily, monthly, hourly)
            organization_id: Specific organization to monitor (optional)
            notify_super_admins: Whether to notify super admins
            notify_org_admins: Whether to notify organization admins
            email_recipients: Additional email addresses
            webhook_url: Webhook URL for external notifications
            slack_webhook_url: Slack webhook URL
            custom_message: Custom alert message template
            cooldown_minutes: Minimum minutes between notifications
            max_triggers_per_day: Maximum triggers per day

        Returns:
            BudgetAlert: Created alert rule
        """
        alert = BudgetAlert(
            platform_provider_id=platform_provider_id,
            organization_id=organization_id,
            alert_type=alert_type,
            threshold_percentage=threshold_percentage,
            period=period,
            notify_super_admins=notify_super_admins,
            notify_org_admins=notify_org_admins,
            email_recipients=email_recipients,
            webhook_url=webhook_url,
            slack_webhook_url=slack_webhook_url,
            custom_message=custom_message,
            cooldown_minutes=cooldown_minutes,
            max_triggers_per_day=max_triggers_per_day
        )

        self.db.add(alert)

        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        logger.info(
            f"Created budget alert: provider={platform_provider_id}, "
            f"type={alert_type.value}, threshold={threshold_percentage}%, "
            f"period={period.value}, org={organization_id}"
        )

        return alert

    async def get_budget_alerts(
        self,
        platform_provider_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None
    ) -> List[BudgetAlert]:
        """
        Get budget alert rules with optional filtering.

        Args:
            platform_provider_id: Filter by provider (optional)
            organization_id: Filter by organization (optional)
            is_active: Filter by active status (optional)

        Returns:
            List[BudgetAlert]: Matching alert rules
        """
        query = select(BudgetAlert)
        conditions = []

        if platform_provider_id:
            conditions.append(BudgetAlert.platform_provider_id == platform_provider_id)

        if organization_id:
            conditions.append(BudgetAlert.organization_id == organization_id)

        if is_active is not None:
            conditions.append(BudgetAlert.is_active == is_active)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(
            BudgetAlert.platform_provider_id,
            BudgetAlert.threshold_percentage
        )

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        return result.scalars().all()

    async def update_budget_alert(
        self,
        alert_id: uuid.UUID,
        **updates
    ) -> Optional[BudgetAlert]:
        """
        Update an existing budget alert rule.

        Args:
            alert_id: Alert to update
            **updates: Fields to update

        Returns:
            BudgetAlert: Updated alert, or None if not found
        """
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(BudgetAlert).where(BudgetAlert.id == alert_id)
            )
        else:
            result = self.db.execute(
                select(BudgetAlert).where(BudgetAlert.id == alert_id)
            )

        alert = result.scalar_one_or_none()

        if not alert:
            return None

        # Update provided fields
        for field, value in updates.items():
            if hasattr(alert, field):
                setattr(alert, field, value)

        alert.updated_at = datetime.now(timezone.utc)

        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        return alert

    async def delete_budget_alert(self, alert_id: uuid.UUID) -> bool:
        """
        Delete a budget alert rule.

        Args:
            alert_id: Alert to delete

        Returns:
            bool: True if deleted, False if not found
        """
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(BudgetAlert).where(BudgetAlert.id == alert_id)
            )
        else:
            result = self.db.execute(
                select(BudgetAlert).where(BudgetAlert.id == alert_id)
            )

        alert = result.scalar_one_or_none()

        if not alert:
            return False

        self.db.delete(alert)

        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        return True

    async def generate_usage_report(
        self,
        organization_id: Optional[uuid.UUID] = None,
        provider_id: Optional[uuid.UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Generate usage and cost report.

        Args:
            organization_id: Filter by organization (optional)
            provider_id: Filter by provider (optional)
            start_date: Start of date range (optional)
            end_date: End of date range (optional)
            period: Aggregation period (daily, monthly)

        Returns:
            Dict: Usage report with costs and metrics
        """
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        if not end_date:
            end_date = datetime.now(timezone.utc).date()

        # Build query conditions
        conditions = [
            OrganizationVLMUsage.usage_date >= start_date,
            OrganizationVLMUsage.usage_date <= end_date
        ]

        if organization_id:
            conditions.append(OrganizationVLMUsage.organization_id == organization_id)

        if provider_id:
            conditions.append(OrganizationVLMUsage.platform_provider_id == provider_id)

        # Aggregate data
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    func.sum(OrganizationVLMUsage.request_count).label('total_requests'),
                    func.sum(OrganizationVLMUsage.input_tokens).label('total_input_tokens'),
                    func.sum(OrganizationVLMUsage.output_tokens).label('total_output_tokens'),
                    func.sum(OrganizationVLMUsage.total_cost).label('total_cost'),
                    func.sum(OrganizationVLMUsage.leaflet_count).label('total_leaflets'),
                    func.sum(OrganizationVLMUsage.page_count).label('total_pages'),
                    func.sum(OrganizationVLMUsage.product_count).label('total_products'),
                    func.avg(OrganizationVLMUsage.average_confidence).label('avg_confidence'),
                    func.count(func.distinct(OrganizationVLMUsage.usage_date)).label('active_days')
                ).where(and_(*conditions))
            )
        else:
            result = self.db.execute(
                select(
                    func.sum(OrganizationVLMUsage.request_count).label('total_requests'),
                    func.sum(OrganizationVLMUsage.input_tokens).label('total_input_tokens'),
                    func.sum(OrganizationVLMUsage.output_tokens).label('total_output_tokens'),
                    func.sum(OrganizationVLMUsage.total_cost).label('total_cost'),
                    func.sum(OrganizationVLMUsage.leaflet_count).label('total_leaflets'),
                    func.sum(OrganizationVLMUsage.page_count).label('total_pages'),
                    func.sum(OrganizationVLMUsage.product_count).label('total_products'),
                    func.avg(OrganizationVLMUsage.average_confidence).label('avg_confidence'),
                    func.count(func.distinct(OrganizationVLMUsage.usage_date)).label('active_days')
                ).where(and_(*conditions))
            )

        row = result.first()

        # Get breakdown by provider
        provider_breakdown = await self._get_provider_breakdown(
            organization_id, start_date, end_date
        )

        # Get trend data
        trend_data = await self._get_usage_trend(
            organization_id, provider_id, start_date, end_date, period
        )

        return {
            'summary': {
                'total_requests': row.total_requests or 0,
                'total_input_tokens': row.total_input_tokens or 0,
                'total_output_tokens': row.total_output_tokens or 0,
                'total_tokens': (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
                'total_cost': float(row.total_cost or 0),
                'total_leaflets': row.total_leaflets or 0,
                'total_pages': row.total_pages or 0,
                'total_products': row.total_products or 0,
                'average_confidence': float(row.avg_confidence or 0),
                'active_days': row.active_days or 0,
                'cost_per_request': float(row.total_cost or 0) / max(row.total_requests or 1, 1),
                'cost_per_leaflet': float(row.total_cost or 0) / max(row.total_leaflets or 1, 1),
            },
            'provider_breakdown': provider_breakdown,
            'trend_data': trend_data,
            'report_parameters': {
                'organization_id': str(organization_id) if organization_id else None,
                'provider_id': str(provider_id) if provider_id else None,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'period': period
            }
        }

    def check_and_alert(
        self,
        organization_id: Optional[uuid.UUID] = None,
        alert_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Check budget thresholds and trigger alerts if exceeded.

        This is the primary method called after VLM usage to check if any
        budget thresholds have been exceeded and trigger appropriate alerts.
        Supports both sync and async database sessions.

        Args:
            organization_id: Organization to check (optional, checks all if None)
            alert_context: Additional context for the alert (e.g., extraction_session, task)

        Returns:
            List[Dict]: List of triggered alerts with details
        """
        triggered_alerts = []
        alert_context = alert_context or {}

        try:
            # Build query for active budget alerts
            query = (
                select(BudgetAlert)
                .where(BudgetAlert.is_active == True)
            )

            # Filter by organization if specified
            if organization_id:
                query = query.where(
                    or_(
                        BudgetAlert.organization_id == organization_id,
                        BudgetAlert.organization_id.is_(None)  # Global alerts
                    )
                )

            # Execute query - this method is designed for sync sessions only
            # For async sessions, use check_all_budget_thresholds() instead
            from sqlalchemy.ext.asyncio import AsyncSession
            if isinstance(self.db, AsyncSession):
                logger.warning("check_and_alert called with async session - use check_all_budget_thresholds() instead")
                return []

            result = self.db.execute(query)
            alerts = result.scalars().all()

            if not alerts:
                return []  # No alerts to check

            # Get unique provider IDs from alerts
            provider_ids = set(alert.platform_provider_id for alert in alerts)

            if not provider_ids:
                return []  # No providers to check

            # Load providers
            provider_query = (
                select(PlatformVLMProvider)
                .where(PlatformVLMProvider.id.in_(provider_ids))
                .where(PlatformVLMProvider.is_active == True)
            )
            provider_result = self.db.execute(provider_query)
            providers = {p.id: p for p in provider_result.scalars().all()}

            # Check each alert
            for alert in alerts:
                provider = providers.get(alert.platform_provider_id)
                if not provider:
                    continue

                # Check if alert can be triggered (cooldown, rate limits)
                if not alert.can_trigger():
                    continue

                # Get current usage and budget limit
                current_usage, budget_limit = self._get_usage_and_limit(provider, alert.period)

                if budget_limit is None or budget_limit <= 0:
                    continue  # No budget limit set

                # Calculate usage percentage
                usage_percentage = (float(current_usage) / float(budget_limit)) * 100

                # Check if threshold is exceeded
                if usage_percentage >= alert.threshold_percentage:
                    # Trigger the alert
                    alert.trigger_alert()

                    # Create alert message
                    alert_message = alert.get_alert_message(float(current_usage), float(budget_limit))

                    # Record in history
                    history = AlertHistory(
                        budget_alert_id=alert.id,
                        platform_provider_id=provider.id,
                        organization_id=alert.organization_id,
                        alert_type=alert.alert_type,
                        threshold_percentage=alert.threshold_percentage,
                        period=alert.period,
                        current_usage=Decimal(str(current_usage)),
                        budget_limit=Decimal(str(budget_limit)),
                        usage_percentage=usage_percentage,
                        alert_message=alert_message,
                        notifications_sent={
                            'context': alert_context,
                            'system_notification': 'pending'
                        }
                    )
                    self.db.add(history)

                    # Send system notification synchronously
                    notification_results = self._send_alert_notifications_sync(
                        alert, provider, usage_percentage, float(current_usage), float(budget_limit)
                    )
                    history.notifications_sent = {
                        'context': alert_context,
                        **notification_results
                    }

                    triggered_alert = {
                        'alert_id': str(alert.id),
                        'history_id': str(history.id),
                        'provider_id': str(provider.id),
                        'provider_name': provider.name,
                        'organization_id': str(alert.organization_id) if alert.organization_id else None,
                        'alert_type': alert.alert_type.value,
                        'threshold_percentage': alert.threshold_percentage,
                        'usage_percentage': round(usage_percentage, 2),
                        'current_usage': float(current_usage),
                        'budget_limit': float(budget_limit),
                        'period': alert.period.value,
                        'message': alert_message,
                        'notifications_sent': notification_results,
                        'context': alert_context
                    }
                    triggered_alerts.append(triggered_alert)

                    logger.warning(
                        f"Budget alert triggered: {provider.name} {alert.alert_type.value} "
                        f"({usage_percentage:.1f}% of {alert.period.value} budget) "
                        f"context={alert_context}"
                    )

            # Commit all changes
            self.db.commit()

        except Exception as e:
            logger.exception(f"Error in check_and_alert: {e}")
            try:
                self.db.rollback()
            except:
                pass

        if triggered_alerts:
            logger.info(f"Budget check completed. Triggered {len(triggered_alerts)} alerts.")

        return triggered_alerts

    def _send_alert_notifications_sync(
        self,
        alert: BudgetAlert,
        provider: PlatformVLMProvider,
        usage_percentage: float,
        current_usage: float,
        budget_limit: float
    ) -> Dict[str, Any]:
        """Send alert notifications synchronously via configured channels."""
        notification_results = {}

        try:
            # Send system notification
            if alert.notify_super_admins or alert.notify_org_admins:
                try:
                    from app.models.system_notification import SystemNotification

                    # Create system notification directly
                    notification = SystemNotification(
                        title=f"Budget Alert: {provider.name}",
                        message=alert.get_alert_message(current_usage, budget_limit),
                        notification_type=NotificationType.BUDGET_WARNING,
                        severity=(
                            NotificationSeverity.CRITICAL
                            if alert.alert_type in [AlertType.CRITICAL, AlertType.EXHAUSTED]
                            else NotificationSeverity.WARNING
                        ),
                        target_organization_id=alert.organization_id,
                        target_role="super_admin" if alert.notify_super_admins else "org_admin",
                        metadata={
                            'provider_id': str(provider.id),
                            'provider_name': provider.name,
                            'usage_percentage': usage_percentage,
                            'current_usage': current_usage,
                            'budget_limit': budget_limit,
                            'period': alert.period.value,
                            'alert_type': alert.alert_type.value
                        }
                    )
                    self.db.add(notification)

                    notification_results['system_notification'] = {
                        'status': 'success',
                        'notification_id': str(notification.id)
                    }
                except Exception as e:
                    logger.exception(f"Error creating system notification: {e}")
                    notification_results['system_notification'] = {
                        'status': 'failed',
                        'error': str(e)
                    }

            # Bridge to the async delivery helpers from this sync method.
            # Safe because _send_alert_notifications_sync is only called
            # from synchronous Celery contexts where no event loop runs.
            import asyncio

            def _run(coro):
                try:
                    return asyncio.run(coro)
                except RuntimeError as e:
                    logger.warning(f"Could not bridge async delivery: {e}")
                    return {'status': 'failed', 'error': str(e)}

            # Email notifications
            if alert.email_recipients:
                notification_results['email'] = _run(self._deliver_email_alerts(
                    alert, provider, usage_percentage, current_usage, budget_limit
                ))

            # Outbound webhook notifications
            if alert.webhook_url:
                notification_results['webhook'] = _run(self._deliver_webhook_alert(
                    alert, provider, usage_percentage, current_usage, budget_limit,
                    alert.webhook_url, slack=False
                ))

            # Slack-formatted webhook
            if alert.slack_webhook_url:
                notification_results['slack'] = _run(self._deliver_webhook_alert(
                    alert, provider, usage_percentage, current_usage, budget_limit,
                    alert.slack_webhook_url, slack=True
                ))

        except Exception as e:
            logger.exception(f"Error sending alert notifications: {e}")
            notification_results['error'] = str(e)

        return notification_results

    async def get_alert_history(
        self,
        provider_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        alert_type: Optional[AlertType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AlertHistory]:
        """
        Get historical alert triggers.

        Args:
            provider_id: Filter by provider (optional)
            organization_id: Filter by organization (optional)
            alert_type: Filter by alert type (optional)
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List[AlertHistory]: Historical alert records
        """
        query = (
            select(AlertHistory)
            .order_by(desc(AlertHistory.triggered_at))
            .limit(limit)
            .offset(offset)
        )

        conditions = []

        if provider_id:
            conditions.append(AlertHistory.platform_provider_id == provider_id)

        if organization_id:
            conditions.append(AlertHistory.organization_id == organization_id)

        if alert_type:
            conditions.append(AlertHistory.alert_type == alert_type)

        if conditions:
            query = query.where(and_(*conditions))

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        return result.scalars().all()

    # Private helper methods

    async def _check_provider_budget_thresholds(
        self,
        provider: PlatformVLMProvider
    ) -> List[Dict[str, Any]]:
        """Check budget thresholds for a specific provider."""
        triggered_alerts = []

        # Get active alerts for this provider
        alerts = await self.get_budget_alerts(
            platform_provider_id=provider.id,
            is_active=True
        )

        for alert in alerts:
            try:
                if alert.can_trigger():
                    triggered = await self._check_alert_threshold(provider, alert)
                    if triggered:
                        triggered_alerts.append(triggered)
            except Exception as e:
                logger.exception(f"Error checking alert {alert.id}: {e}")

        return triggered_alerts

    async def _check_alert_threshold(
        self,
        provider: PlatformVLMProvider,
        alert: BudgetAlert
    ) -> Optional[Dict[str, Any]]:
        """Check if a specific alert threshold has been exceeded."""
        # Get current usage based on period
        current_usage, budget_limit = self._get_usage_and_limit(provider, alert.period)

        if budget_limit is None or budget_limit <= 0:
            return None  # No budget limit set

        # Calculate usage percentage
        usage_percentage = (current_usage / budget_limit) * 100

        # Check if threshold is exceeded
        if usage_percentage >= alert.threshold_percentage:
            # Trigger the alert
            alert.trigger_alert()

            # Create alert message
            alert_message = alert.get_alert_message(current_usage, budget_limit)

            # Record in history
            history = AlertHistory(
                budget_alert_id=alert.id,
                platform_provider_id=provider.id,
                organization_id=alert.organization_id,
                alert_type=alert.alert_type,
                threshold_percentage=alert.threshold_percentage,
                period=alert.period,
                current_usage=Decimal(str(current_usage)),
                budget_limit=Decimal(str(budget_limit)),
                usage_percentage=usage_percentage,
                alert_message=alert_message
            )
            self.db.add(history)

            # Send notifications
            notification_results = await self._send_alert_notifications(
                alert, provider, usage_percentage, current_usage, budget_limit
            )
            history.notifications_sent = notification_results

            # Commit changes
            if hasattr(self.db, 'commit'):
                self.db.commit()
            else:
                await self.db.commit()

            logger.warning(
                f"Budget alert triggered: {provider.name} {alert.alert_type.value} "
                f"({usage_percentage:.1f}% of {alert.period.value} budget)"
            )

            return {
                'alert_id': str(alert.id),
                'provider_id': str(provider.id),
                'provider_name': provider.name,
                'alert_type': alert.alert_type.value,
                'threshold_percentage': alert.threshold_percentage,
                'usage_percentage': usage_percentage,
                'current_usage': current_usage,
                'budget_limit': budget_limit,
                'period': alert.period.value,
                'message': alert_message,
                'notifications_sent': notification_results
            }

        return None

    def _get_usage_and_limit(
        self,
        provider: PlatformVLMProvider,
        period: AlertPeriod
    ) -> Tuple[float, Optional[float]]:
        """Get current usage and budget limit for the specified period."""
        if period == AlertPeriod.MONTHLY:
            return provider.current_month_spent, provider.monthly_budget
        elif period == AlertPeriod.DAILY:
            return provider.current_day_spent, provider.daily_budget
        elif period == AlertPeriod.HOURLY:
            return float(provider.current_hour_requests), float(provider.max_requests_per_hour)
        else:
            return 0.0, None

    async def _send_alert_notifications(
        self,
        alert: BudgetAlert,
        provider: PlatformVLMProvider,
        usage_percentage: float,
        current_usage: float,
        budget_limit: float
    ) -> Dict[str, Any]:
        """Send alert notifications via configured channels."""
        notification_results = {}

        try:
            # Send system notification
            if alert.notify_super_admins or alert.notify_org_admins:
                notification = await self.notification_service.send_budget_warning_notification(
                    provider_name=provider.name,
                    organization_id=alert.organization_id,
                    usage_percentage=usage_percentage,
                    budget_amount=budget_limit,
                    current_usage=current_usage,
                    period=alert.period.value
                )
                notification_results['system_notification'] = {
                    'status': 'success',
                    'notification_id': str(notification.id)
                }

            # Email notifications
            if alert.email_recipients:
                notification_results['email'] = await self._deliver_email_alerts(
                    alert, provider, usage_percentage, current_usage, budget_limit
                )

            # Outbound webhook notifications
            if alert.webhook_url:
                notification_results['webhook'] = await self._deliver_webhook_alert(
                    alert, provider, usage_percentage, current_usage, budget_limit,
                    alert.webhook_url, slack=False
                )

            # Slack-formatted webhook
            if alert.slack_webhook_url:
                notification_results['slack'] = await self._deliver_webhook_alert(
                    alert, provider, usage_percentage, current_usage, budget_limit,
                    alert.slack_webhook_url, slack=True
                )

        except Exception as e:
            logger.exception(f"Error sending alert notifications: {e}")
            notification_results['error'] = str(e)

        return notification_results

    async def _deliver_email_alerts(
        self,
        alert: BudgetAlert,
        provider: PlatformVLMProvider,
        usage_percentage: float,
        current_usage: float,
        budget_limit: float,
    ) -> Dict[str, Any]:
        """Send the budget alert to each configured email recipient."""
        from app.services.email_service import email_service

        subject = (
            f"[Budget Alert] {provider.name}: "
            f"{usage_percentage:.1f}% of {alert.period.value} budget"
        )
        html_body = (
            f"<p>Provider <b>{provider.name}</b> has reached "
            f"<b>{usage_percentage:.1f}%</b> of its {alert.period.value} budget.</p>"
            f"<ul>"
            f"<li>Usage: {current_usage:.2f}</li>"
            f"<li>Limit: {budget_limit:.2f}</li>"
            f"<li>Threshold: {alert.threshold_percentage:.0f}%</li>"
            f"<li>Alert type: {alert.alert_type.value}</li>"
            f"</ul>"
        )

        recipients = list(alert.email_recipients or [])
        delivered: list[str] = []
        failed: list[Dict[str, str]] = []

        for recipient in recipients:
            try:
                await email_service._send_email(
                    to_email=recipient,
                    to_name=None,
                    subject=subject,
                    html_body=html_body,
                )
                delivered.append(recipient)
            except Exception as e:
                logger.exception(f"Budget alert email to {recipient} failed: {e}")
                failed.append({'recipient': recipient, 'error': str(e)})

        return {
            'status': 'success' if not failed else 'partial' if delivered else 'failed',
            'delivered': delivered,
            'failed': failed,
        }

    async def _deliver_webhook_alert(
        self,
        alert: BudgetAlert,
        provider: PlatformVLMProvider,
        usage_percentage: float,
        current_usage: float,
        budget_limit: float,
        url: str,
        slack: bool,
    ) -> Dict[str, Any]:
        """POST the alert as JSON to a webhook (generic or Slack)."""
        import httpx

        if slack:
            text = (
                f":rotating_light: *Budget alert*: `{provider.name}` is at "
                f"{usage_percentage:.1f}% of its {alert.period.value} budget "
                f"({current_usage:.2f} / {budget_limit:.2f})."
            )
            payload: Dict[str, Any] = {"text": text}
        else:
            payload = {
                "event": "budget.alert",
                "alert_id": str(alert.id),
                "alert_type": alert.alert_type.value,
                "period": alert.period.value,
                "threshold_percentage": alert.threshold_percentage,
                "usage_percentage": usage_percentage,
                "current_usage": current_usage,
                "budget_limit": budget_limit,
                "provider": {
                    "id": str(provider.id),
                    "name": provider.name,
                },
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
            return {
                'status': 'success' if response.is_success else 'failed',
                'url': url,
                'http_status': response.status_code,
            }
        except Exception as e:
            logger.exception(f"Budget alert webhook POST to {url} failed: {e}")
            return {'status': 'failed', 'url': url, 'error': str(e)}

    async def _get_provider_breakdown(
        self,
        organization_id: Optional[uuid.UUID],
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get cost breakdown by provider."""
        query = (
            select(
                OrganizationVLMUsage.platform_provider_id,
                func.sum(OrganizationVLMUsage.total_cost).label('total_cost'),
                func.sum(OrganizationVLMUsage.request_count).label('total_requests'),
                func.sum(OrganizationVLMUsage.input_tokens).label('total_input_tokens'),
                func.sum(OrganizationVLMUsage.output_tokens).label('total_output_tokens')
            )
            .where(
                and_(
                    OrganizationVLMUsage.usage_date >= start_date,
                    OrganizationVLMUsage.usage_date <= end_date
                )
            )
            .group_by(OrganizationVLMUsage.platform_provider_id)
        )

        if organization_id:
            query = query.where(OrganizationVLMUsage.organization_id == organization_id)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        breakdown = []
        for row in result:
            if row.platform_provider_id:
                # Get provider name
                provider_result = await self.db.execute(
                    select(PlatformVLMProvider.name, PlatformVLMProvider.provider_type)
                    .where(PlatformVLMProvider.id == row.platform_provider_id)
                ) if hasattr(self.db, 'execute') else self.db.execute(
                    select(PlatformVLMProvider.name, PlatformVLMProvider.provider_type)
                    .where(PlatformVLMProvider.id == row.platform_provider_id)
                )
                provider_info = provider_result.first()

                breakdown.append({
                    'provider_id': str(row.platform_provider_id),
                    'provider_name': provider_info.name if provider_info else 'Unknown',
                    'provider_type': provider_info.provider_type.value if provider_info else 'unknown',
                    'total_cost': float(row.total_cost or 0),
                    'total_requests': row.total_requests or 0,
                    'total_input_tokens': row.total_input_tokens or 0,
                    'total_output_tokens': row.total_output_tokens or 0
                })

        return breakdown

    async def _get_usage_trend(
        self,
        organization_id: Optional[uuid.UUID],
        provider_id: Optional[uuid.UUID],
        start_date: date,
        end_date: date,
        period: str
    ) -> List[Dict[str, Any]]:
        """Get usage trend data over time."""
        # Group by date for daily trends, or by month for monthly trends
        if period == "daily":
            date_col = OrganizationVLMUsage.usage_date
        else:
            # For monthly, we'd group by year-month
            # This is a simplified version - you might want to use extract() for proper month grouping
            date_col = OrganizationVLMUsage.usage_date

        query = (
            select(
                date_col.label('period'),
                func.sum(OrganizationVLMUsage.total_cost).label('cost'),
                func.sum(OrganizationVLMUsage.request_count).label('requests')
            )
            .where(
                and_(
                    OrganizationVLMUsage.usage_date >= start_date,
                    OrganizationVLMUsage.usage_date <= end_date
                )
            )
            .group_by(date_col)
            .order_by(date_col)
        )

        conditions = []
        if organization_id:
            conditions.append(OrganizationVLMUsage.organization_id == organization_id)
        if provider_id:
            conditions.append(OrganizationVLMUsage.platform_provider_id == provider_id)

        if conditions:
            query = query.where(and_(*conditions))

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        trend_data = []
        for row in result:
            trend_data.append({
                'period': row.period.isoformat() if hasattr(row.period, 'isoformat') else str(row.period),
                'cost': float(row.cost or 0),
                'requests': row.requests or 0
            })

        return trend_data