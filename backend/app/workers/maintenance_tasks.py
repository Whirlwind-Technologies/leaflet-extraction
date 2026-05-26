"""
Maintenance tasks — cleanup, stats, monitoring, budget, and notifications.

Contains Celery tasks for periodic housekeeping and operational monitoring:
- ``cleanup_old_files_task``: Delete old leaflet files from storage.
- ``update_stats_task``: Compute and cache processing statistics.
- ``aggregate_usage_data_task``: Aggregate VLM usage data for reporting.
- ``monitor_budgets_task``: Check budget thresholds and trigger alerts.
- ``cleanup_audit_logs_task``: Purge old audit log entries.
- ``cleanup_notifications_task``: Purge old/expired notifications.
- ``reset_spending_counters_task``: Reset stale spending counters.
- ``send_contact_emails_task``: Deliver contact-form notification and
  confirmation emails.

Tasks that already had explicit short ``name=`` parameters (e.g.
``"aggregate_usage_data"``) keep those names.  Tasks whose names were
auto-generated from the original module path use
``name="app.workers.tasks.<func_name>"`` to preserve compatibility.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import func as sa_func, select, update

from app.workers.celery_app import celery_app
from app.workers.db_helpers import get_sync_db_session, run_async

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# cleanup_old_files_task
# ---------------------------------------------------------------------------

@celery_app.task(name="app.workers.tasks.cleanup_old_files_task")
def cleanup_old_files_task(days_old: int = 30) -> dict:
    """
    Clean up old files from storage.

    Removes files for leaflets that were deleted or are older than specified days.

    Args:
        days_old: Delete files older than this many days

    Returns:
        Dict with cleanup results
    """
    logger.info(f"Starting cleanup of files older than {days_old} days")
    db = get_sync_db_session()

    try:
        from app.models.leaflet import Leaflet
        from app.utils.storage import get_storage_backend

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        # Find old completed/failed leaflets
        result = db.execute(
            select(Leaflet).where(
                Leaflet.created_at < cutoff_date,
                Leaflet.status.in_(['completed', 'failed', 'cancelled']),
            )
        )
        old_leaflets = result.scalars().all()

        storage = get_storage_backend()
        deleted_count = 0

        for leaflet in old_leaflets:
            try:
                # Delete all files for this leaflet
                prefix = f"leaflets/{leaflet.leaflet_id}/"
                count = run_async(storage.delete_folder(prefix))
                deleted_count += count
                logger.debug(f"Deleted {count} files for leaflet {leaflet.leaflet_id}")
            except Exception as e:
                logger.warning(f"Failed to delete files for {leaflet.leaflet_id}: {e}")

        logger.info(f"Cleanup completed: deleted {deleted_count} files")

        return {
            "success": True,
            "leaflets_processed": len(old_leaflets),
            "files_deleted": deleted_count,
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# update_stats_task
# ---------------------------------------------------------------------------

@celery_app.task(name="app.workers.tasks.update_stats_task")
def update_stats_task() -> dict:
    """
    Update processing statistics.

    Calculates and caches various metrics about processing performance.

    Returns:
        Dict with current stats
    """
    logger.info("Updating processing statistics")
    db = get_sync_db_session()

    try:
        from sqlalchemy import func
        from app.models.leaflet import Leaflet, LeafletStatus
        from app.models.product import Product
        from app.utils.cache import set_cache

        # Count leaflets by status
        status_counts = {}
        for status in LeafletStatus:
            result = db.execute(
                select(func.count(Leaflet.id)).where(Leaflet.status == status)
            )
            status_counts[status.value] = result.scalar()

        # Count total products
        result = db.execute(select(func.count(Product.id)))
        total_products = result.scalar()

        # Average processing time (for completed leaflets)
        result = db.execute(
            select(func.avg(
                func.extract('epoch', Leaflet.processing_completed_at) -
                func.extract('epoch', Leaflet.processing_started_at)
            )).where(
                Leaflet.status == LeafletStatus.COMPLETED,
                Leaflet.processing_started_at.isnot(None),
                Leaflet.processing_completed_at.isnot(None),
            )
        )
        avg_processing_time = result.scalar() or 0

        stats = {
            "leaflet_counts": status_counts,
            "total_products": total_products,
            "avg_processing_time_seconds": round(avg_processing_time, 2),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache stats
        run_async(set_cache("processing_stats", stats, ttl=3600))

        logger.info(f"Stats updated: {stats}")

        return stats

    except Exception as e:
        logger.error(f"Stats update failed: {e}")
        return {"success": False, "error": str(e)}

    finally:
        db.close()


# ---------------------------------------------------------------------------
# aggregate_usage_data_task
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="aggregate_usage_data")
def aggregate_usage_data_task(self, organization_id: Optional[str] = None, days_back: int = 1):
    """
    Aggregate VLM usage data for reporting and billing.

    This task processes raw usage logs into aggregated summaries for
    efficient reporting and cost tracking.
    """
    db = None
    try:
        db = get_sync_db_session()

        from app.services.budget_monitoring_service import BudgetMonitoringService
        from app.models.organization_usage import OrganizationVLMUsage
        from app.models.vlm_audit_log import VLMProviderAuditLog, AuditEventStatus
        from sqlalchemy import and_

        budget_service = BudgetMonitoringService(db)

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)

        logger.info(f"Starting usage aggregation for {start_date.date()} to {end_date.date()}")

        # Build query for successful platform provider usage
        audit_query = select(VLMProviderAuditLog).where(
            and_(
                VLMProviderAuditLog.created_at >= start_date,
                VLMProviderAuditLog.created_at <= end_date,
                VLMProviderAuditLog.event_status == AuditEventStatus.SUCCESS,
                VLMProviderAuditLog.platform_provider_id.isnot(None)
            )
        )

        if organization_id:
            audit_query = audit_query.where(
                VLMProviderAuditLog.organization_id == UUID(organization_id)
            )

        audit_logs = db.execute(audit_query).scalars().all()

        # Group by organization, provider, and date
        usage_groups = {}
        for log in audit_logs:
            if not log.organization_id or not log.platform_provider_id:
                continue

            date_key = log.created_at.date()
            group_key = (log.organization_id, log.platform_provider_id, date_key)

            if group_key not in usage_groups:
                usage_groups[group_key] = {
                    'request_count': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cost': 0,
                    'processing_time_total': 0,
                    'first_request': log.created_at,
                    'last_request': log.created_at,
                }

            group = usage_groups[group_key]
            group['request_count'] += 1
            group['input_tokens'] += log.input_tokens or 0
            group['output_tokens'] += log.output_tokens or 0
            group['cost'] += float(log.cost or 0)
            group['processing_time_total'] += log.processing_time_ms or 0

            if log.created_at < group['first_request']:
                group['first_request'] = log.created_at
            if log.created_at > group['last_request']:
                group['last_request'] = log.created_at

        # Create or update usage records
        processed_count = 0
        for (org_id, provider_id, usage_date), usage_data in usage_groups.items():
            # Check if record already exists
            existing_query = select(OrganizationVLMUsage).where(
                and_(
                    OrganizationVLMUsage.organization_id == org_id,
                    OrganizationVLMUsage.platform_provider_id == provider_id,
                    OrganizationVLMUsage.usage_date == usage_date
                )
            )
            existing_record = db.execute(existing_query).scalar_one_or_none()

            if existing_record:
                # Replace (SET) instead of accumulate (ADD) to stay idempotent.
                # If this task re-runs for the same date range, values are
                # recomputed from audit logs rather than double-counted.
                existing_record.request_count = usage_data['request_count']
                existing_record.input_tokens = usage_data['input_tokens']
                existing_record.output_tokens = usage_data['output_tokens']
                existing_record.cost = usage_data['cost']
                existing_record.avg_processing_time_ms = (
                    usage_data['processing_time_total'] / usage_data['request_count']
                    if usage_data['request_count'] > 0 else 0
                )
                existing_record.last_request_at = usage_data['last_request']
                existing_record.updated_at = datetime.now(timezone.utc)
            else:
                # Create new record
                new_record = OrganizationVLMUsage(
                    organization_id=org_id,
                    platform_provider_id=provider_id,
                    usage_date=usage_date,
                    request_count=usage_data['request_count'],
                    input_tokens=usage_data['input_tokens'],
                    output_tokens=usage_data['output_tokens'],
                    cost=usage_data['cost'],
                    avg_processing_time_ms=(
                        usage_data['processing_time_total'] / usage_data['request_count']
                        if usage_data['request_count'] > 0 else 0
                    ),
                    first_request_at=usage_data['first_request'],
                    last_request_at=usage_data['last_request'],
                )
                db.add(new_record)

            processed_count += 1

        db.commit()

        logger.info(f"Usage aggregation completed: {processed_count} records processed")

        return {
            "success": True,
            "organization_id": organization_id,
            "days_back": days_back,
            "records_processed": processed_count,
        }

    except Exception as e:
        logger.error(f"Usage aggregation failed: {e}", exc_info=True)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# monitor_budgets_task
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="monitor_budgets")
def monitor_budgets_task(self, organization_id: Optional[str] = None):
    """Monitor budget thresholds and trigger alerts."""
    db = None
    try:
        db = get_sync_db_session()

        from app.services.budget_monitoring_service import BudgetMonitoringService

        budget_service = BudgetMonitoringService(db)

        logger.info(f"Starting budget monitoring for organization: {organization_id or 'all'}")

        # Get organizations to check
        if organization_id:
            org_ids = [UUID(organization_id)]
        else:
            from app.models.organization import Organization
            orgs = db.execute(select(Organization).where(Organization.is_active == True)).scalars().all()
            org_ids = [org.id for org in orgs]

        alerts_triggered = 0

        for org_id in org_ids:
            try:
                # check_and_alert returns a list of triggered alerts
                triggered_alerts = budget_service.check_and_alert(
                    organization_id=org_id,
                    alert_context={'task': 'budget_monitoring'}
                )

                if triggered_alerts:
                    alerts_triggered += len(triggered_alerts)

            except Exception as e:
                logger.error(f"Budget monitoring failed for organization {org_id}: {e}", exc_info=True)
                continue

        db.commit()

        logger.info(f"Budget monitoring completed: {alerts_triggered} alerts triggered")

        return {
            "success": True,
            "organization_id": organization_id,
            "organizations_checked": len(org_ids),
            "alerts_triggered": alerts_triggered,
        }

    except Exception as e:
        logger.error(f"Budget monitoring task failed: {e}", exc_info=True)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# cleanup_audit_logs_task
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="cleanup_audit_logs")
def cleanup_audit_logs_task(self, retention_days: int = 90, organization_id: Optional[str] = None):
    """Clean up old audit logs based on retention policy."""
    db = None
    try:
        db = get_sync_db_session()

        from app.models.vlm_audit_log import VLMProviderAuditLog
        from sqlalchemy import and_

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        logger.info(f"Starting audit log cleanup: retaining {retention_days} days, cutoff: {cutoff_date}")

        # Build cleanup query
        query = select(VLMProviderAuditLog).where(
            VLMProviderAuditLog.created_at < cutoff_date
        )
        if organization_id:
            query = query.where(VLMProviderAuditLog.organization_id == UUID(organization_id))

        logs_to_delete = db.execute(query).scalars().all()
        total_deleted = 0

        for log in logs_to_delete:
            try:
                db.delete(log)
                total_deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete audit log {log.id}: {e}")
                continue

        db.commit()

        logger.info(f"Audit log cleanup completed: {total_deleted} records deleted")

        return {
            "success": True,
            "retention_days": retention_days,
            "organization_id": organization_id,
            "total_deleted": total_deleted,
        }

    except Exception as e:
        logger.error(f"Audit log cleanup failed: {e}", exc_info=True)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# cleanup_notifications_task
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="cleanup_notifications")
def cleanup_notifications_task(self, days_old: int = 30):
    """
    Clean up old and expired notifications.

    This task removes notifications that are:
    - Older than the specified number of days
    - Expired (past their expires_at timestamp)
    """
    db = None
    try:
        db = get_sync_db_session()

        from app.models.system_notification import SystemNotification
        from sqlalchemy import or_

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        now = datetime.now(timezone.utc)

        logger.info(f"Starting notification cleanup: days_old={days_old}, cutoff={cutoff_date}")

        # Find notifications to delete
        query = select(SystemNotification).where(
            or_(
                SystemNotification.expires_at < now,
                SystemNotification.created_at < cutoff_date
            )
        )

        notifications_to_delete = db.execute(query).scalars().all()
        total_deleted = 0

        for notification in notifications_to_delete:
            try:
                db.delete(notification)
                total_deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete notification {notification.id}: {e}")
                continue

        db.commit()

        logger.info(f"Notification cleanup completed: {total_deleted} records deleted")

        return {
            "success": True,
            "days_old": days_old,
            "total_deleted": total_deleted,
        }

    except Exception as e:
        logger.error(f"Notification cleanup failed: {e}", exc_info=True)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# reset_spending_counters_task
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="reset_spending_counters")
def reset_spending_counters_task(self):
    """
    Reset stale spending counters for all VLM providers.

    Runs hourly via Celery beat. Uses SQL-level UPDATEs with staleness
    conditions in the WHERE clause so that resets are no-ops if
    ``record_usage()`` has already updated ``last_used_at`` to the current
    period. This prevents the reset task from racing with concurrent
    ``record_usage()`` calls and zeroing out freshly-recorded costs.

    Covers both:
    - PlatformVLMProvider (month, day, hour counters)
    - VLMProvider (month counter only)
    """
    db = None
    try:
        db = get_sync_db_session()

        from app.models.platform_vlm_provider import PlatformVLMProvider
        from app.models.vlm_provider import VLMProvider

        # --- Platform VLM Providers (month, day, hour) ---
        # Each UPDATE only affects rows whose last_used_at is in a previous
        # period AND whose counter is non-zero, making it safe against
        # concurrent record_usage() calls that update last_used_at atomically.

        # Monthly reset: only reset if last_used_at is in a previous month
        monthly_result = db.execute(
            update(PlatformVLMProvider)
            .where(
                PlatformVLMProvider.last_used_at.isnot(None),
                sa_func.date_trunc("month", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("month", sa_func.now()),
                PlatformVLMProvider.current_month_spent > 0,
            )
            .values(current_month_spent=Decimal("0"))
        )
        platform_monthly_reset = monthly_result.rowcount

        # Daily reset: only reset if last_used_at is in a previous day
        daily_result = db.execute(
            update(PlatformVLMProvider)
            .where(
                PlatformVLMProvider.last_used_at.isnot(None),
                sa_func.date_trunc("day", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("day", sa_func.now()),
                PlatformVLMProvider.current_day_spent > 0,
            )
            .values(current_day_spent=Decimal("0"))
        )
        platform_daily_reset = daily_result.rowcount

        # Hourly reset: only reset if last_used_at is in a previous hour
        hourly_result = db.execute(
            update(PlatformVLMProvider)
            .where(
                PlatformVLMProvider.last_used_at.isnot(None),
                sa_func.date_trunc("hour", PlatformVLMProvider.last_used_at)
                < sa_func.date_trunc("hour", sa_func.now()),
                PlatformVLMProvider.current_hour_requests > 0,
            )
            .values(current_hour_requests=0)
        )
        platform_hourly_reset = hourly_result.rowcount

        # --- Organization / User VLM Providers (month only) ---
        org_result = db.execute(
            update(VLMProvider)
            .where(
                VLMProvider.last_used_at.isnot(None),
                sa_func.date_trunc("month", VLMProvider.last_used_at)
                < sa_func.date_trunc("month", sa_func.now()),
                VLMProvider.current_month_spent > 0,
            )
            .values(current_month_spent=Decimal("0"))
        )
        org_resets = org_result.rowcount

        db.commit()

        platform_resets = max(
            platform_monthly_reset, platform_daily_reset, platform_hourly_reset
        )

        logger.info(
            f"Spending counter reset completed: "
            f"{platform_monthly_reset} platform monthly, "
            f"{platform_daily_reset} platform daily, "
            f"{platform_hourly_reset} platform hourly, "
            f"{org_resets} org providers reset"
        )

        return {
            "success": True,
            "platform_providers_reset": platform_resets,
            "org_providers_reset": org_resets,
        }

    except Exception as e:
        logger.error(f"Spending counter reset failed: {e}", exc_info=True)
        if db:
            db.rollback()
        raise
    finally:
        if db:
            db.close()


# ---------------------------------------------------------------------------
# send_contact_emails_task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.workers.tasks.send_contact_emails_task",
    queue="default",
    max_retries=3,
    soft_time_limit=120,   # 2 minutes
    time_limit=150,        # 2.5 minutes hard limit
)
def send_contact_emails_task(
    self,
    name: str,
    email: str,
    message: str,
) -> dict:
    """Send notification and confirmation emails for a contact form submission.

    This task is dispatched by the ``POST /api/v1/contact`` endpoint after
    all spam checks pass.  It sends two emails:

    1. **Notification** to the configured contact address (or superusers)
       informing them of the new submission.
    2. **Confirmation** to the visitor acknowledging receipt.

    Both emails are rendered from Jinja2 templates and sent via the
    existing ``EmailService._send_email()`` helper.

    Args:
        self: Celery task instance (for retries).
        name: Sender's full name.
        email: Sender's email address.
        message: The contact message body.

    Returns:
        Dict with ``notification_sent`` and ``confirmation_sent`` booleans.
    """
    from datetime import datetime, timezone

    from app.services.email_service import email_service
    from app.config import settings as app_settings

    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    notification_sent = False
    confirmation_sent = False

    # ---- 1. Notification email to support address + superusers ----
    try:
        notification_html = email_service.jinja_env.get_template(
            "contact_notification.html"
        ).render(
            sender_name=name,
            sender_email=email,
            sender_message=message,
            submitted_at=submitted_at,
        )

        notification_subject = f"New Contact Form Submission — {name}"

        # Primary recipient: contact_email override, or support_email
        primary_recipient = (
            app_settings.contact_email or app_settings.support_email
        )

        # Collect all unique recipient emails to avoid duplicates
        recipients_sent: set = set()

        # 1a. Send to the primary support/contact address with reply_to
        #     set to the visitor's email so staff can reply directly.
        try:
            run_async(
                email_service._send_email(
                    to_email=primary_recipient,
                    to_name=None,
                    subject=notification_subject,
                    html_body=notification_html,
                    reply_to=email,
                )
            )
            notification_sent = True
            recipients_sent.add(primary_recipient.lower())
        except Exception as send_exc:
            logger.error(
                "Failed to send contact notification to support address "
                "(%s): %s",
                primary_recipient,
                send_exc,
            )

        # Superuser notifications removed — support_email (info@leafxtract.com)
        # is the single contact-form recipient. Superusers access that inbox.

    except Exception as exc:
        logger.error(
            "Failed to send contact notification email (sender=%s): %s",
            email,
            exc,
        )
        # Don't retry just for the notification; still try confirmation below.

    # ---- 2. Confirmation email to the visitor ----
    try:
        confirmation_html = email_service.jinja_env.get_template(
            "contact_confirmation.html"
        ).render(
            sender_name=name,
            sender_email=email,
        )

        run_async(
            email_service._send_email(
                to_email=email,
                to_name=name,
                subject="We received your message — LeafXtract",
                html_body=confirmation_html,
            )
        )
        confirmation_sent = True

    except Exception as exc:
        logger.error(
            "Failed to send contact confirmation email (sender=%s): %s",
            email,
            exc,
        )
        # Retry the entire task on confirmation failure so the visitor
        # eventually receives their acknowledgement.
        raise self.retry(
            exc=exc,
            countdown=60 * (self.request.retries + 1),
        )

    logger.info(
        "Contact form emails processed (sender=%s, notification=%s, "
        "confirmation=%s)",
        email,
        notification_sent,
        confirmation_sent,
    )

    return {
        "notification_sent": notification_sent,
        "confirmation_sent": confirmation_sent,
    }
