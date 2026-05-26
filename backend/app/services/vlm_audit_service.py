"""
VLM Audit Service Module.

This service provides comprehensive audit logging for all VLM operations,
including compliance reporting, data export, and security monitoring.

Example Usage:
    from app.services.vlm_audit_service import VLMAuditService

    audit_service = VLMAuditService(db_session)
    await audit_service.log_extraction_attempt(
        provider_id=provider_id,
        organization_id=org_id,
        user_id=user_id,
        leaflet_id=leaflet_id,
        input_tokens=1500,
        output_tokens=800,
        cost=0.075
    )
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Union, Tuple
from decimal import Decimal

from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.orm import Session

from app.models.vlm_audit_log import (
    VLMProviderAuditLog,
    AuditEventType,
    AuditEventStatus,
    ErrorCategory
)
from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.organization import Organization
from app.models.user import User
from app.models.leaflet import Leaflet

logger = logging.getLogger(__name__)


class VLMAuditService:
    """
    Service for comprehensive VLM audit logging and compliance reporting.

    This service handles:
    - Logging all VLM operations with context
    - Compliance reporting (SOC2, GDPR, etc.)
    - Data export for external audits
    - Security monitoring and anomaly detection
    - Performance analytics and optimization insights
    """

    def __init__(self, db_session: Session):
        """
        Initialize the VLM audit service.

        Args:
            db_session: Database session (sync or async)
        """
        self.db = db_session

    async def log_extraction_attempt(
        self,
        provider_id: Optional[uuid.UUID],
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        leaflet_id: uuid.UUID,
        status: AuditEventStatus,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cost: Optional[float] = None,
        latency_ms: Optional[int] = None,
        provider_type: Optional[str] = None,
        model_name: Optional[str] = None,
        error_type: Optional[ErrorCategory] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        retry_count: int = 0,
        request_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VLMProviderAuditLog:
        """
        Log a VLM extraction attempt with full context.

        Args:
            provider_id: Platform provider used
            organization_id: Organization context
            user_id: User who initiated the request
            leaflet_id: Leaflet being processed
            status: Success/failure status
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost in USD
            latency_ms: Request latency in milliseconds
            provider_type: Provider type (anthropic, openai, etc.)
            model_name: Model used
            error_type: Category of error (if any)
            error_message: Error message (if any)
            error_code: Provider-specific error code (if any)
            retry_count: Number of retries attempted
            request_ip: Client IP address
            user_agent: Client user agent
            session_id: Session identifier
            operation_id: Unique operation identifier
            metadata: Additional context data

        Returns:
            VLMProviderAuditLog: Created audit log entry
        """
        audit_log = VLMProviderAuditLog(
            platform_provider_id=provider_id,
            organization_id=organization_id,
            user_id=user_id,
            leaflet_id=leaflet_id,
            event_type=AuditEventType.EXTRACTION,
            event_status=status,
            operation_id=operation_id,
            provider_type=provider_type,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=Decimal(str(cost)) if cost is not None else None,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
            error_code=error_code,
            retry_count=retry_count,
            request_ip=request_ip,
            user_agent=user_agent,
            session_id=session_id,
            audit_metadata=metadata or {}
        )

        self.db.add(audit_log)

        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        logger.debug(
            f"Logged extraction: provider={provider_id}, org={organization_id}, "
            f"user={user_id}, leaflet={leaflet_id}, status={status.value}, "
            f"tokens={input_tokens}+{output_tokens}, cost=${cost or 0:.4f}"
        )

        return audit_log

    async def log_provider_event(
        self,
        event_type: AuditEventType,
        status: AuditEventStatus,
        provider_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        error_type: Optional[ErrorCategory] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VLMProviderAuditLog:
        """
        Log a provider-related event (failover, key changes, etc.).

        Args:
            event_type: Type of event
            status: Event status
            provider_id: Platform provider involved
            organization_id: Organization context (optional)
            user_id: User who initiated the action (optional)
            error_type: Error category (optional)
            error_message: Error message (optional)
            metadata: Additional context data

        Returns:
            VLMProviderAuditLog: Created audit log entry
        """
        audit_log = VLMProviderAuditLog(
            platform_provider_id=provider_id,
            organization_id=organization_id,
            user_id=user_id,
            event_type=event_type,
            event_status=status,
            error_type=error_type,
            error_message=error_message,
            audit_metadata=metadata or {}
        )

        self.db.add(audit_log)

        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        logger.info(
            f"Logged provider event: type={event_type.value}, status={status.value}, "
            f"provider={provider_id}, org={organization_id}, user={user_id}"
        )

        return audit_log

    async def get_audit_logs(
        self,
        organization_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        provider_id: Optional[uuid.UUID] = None,
        leaflet_id: Optional[uuid.UUID] = None,
        event_type: Optional[AuditEventType] = None,
        event_status: Optional[AuditEventStatus] = None,
        error_type: Optional[ErrorCategory] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        include_sensitive: bool = False
    ) -> List[VLMProviderAuditLog]:
        """
        Query audit logs with flexible filtering.

        Args:
            organization_id: Filter by organization
            user_id: Filter by user
            provider_id: Filter by provider
            leaflet_id: Filter by leaflet
            event_type: Filter by event type
            event_status: Filter by event status
            error_type: Filter by error type
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum records to return
            offset: Number of records to skip
            include_sensitive: Include sensitive data (for compliance)

        Returns:
            List[VLMProviderAuditLog]: Matching audit log entries
        """
        query = (
            select(VLMProviderAuditLog)
            .order_by(desc(VLMProviderAuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )

        conditions = []

        if organization_id:
            conditions.append(VLMProviderAuditLog.organization_id == organization_id)

        if user_id:
            conditions.append(VLMProviderAuditLog.user_id == user_id)

        if provider_id:
            conditions.append(VLMProviderAuditLog.platform_provider_id == provider_id)

        if leaflet_id:
            conditions.append(VLMProviderAuditLog.leaflet_id == leaflet_id)

        if event_type:
            conditions.append(VLMProviderAuditLog.event_type == event_type)

        if event_status:
            conditions.append(VLMProviderAuditLog.event_status == event_status)

        if error_type:
            conditions.append(VLMProviderAuditLog.error_type == error_type)

        if start_date:
            conditions.append(VLMProviderAuditLog.created_at >= start_date)

        if end_date:
            conditions.append(VLMProviderAuditLog.created_at <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        return result.scalars().all()

    async def get_audit_summary(
        self,
        organization_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit summary statistics.

        Args:
            organization_id: Filter by organization
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict: Summary statistics
        """
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)

        conditions = [
            VLMProviderAuditLog.created_at >= start_date,
            VLMProviderAuditLog.created_at <= end_date
        ]

        if organization_id:
            conditions.append(VLMProviderAuditLog.organization_id == organization_id)

        # Overall statistics
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    func.count(VLMProviderAuditLog.id).label('total_events'),
                    func.sum(VLMProviderAuditLog.input_tokens).label('total_input_tokens'),
                    func.sum(VLMProviderAuditLog.output_tokens).label('total_output_tokens'),
                    func.sum(VLMProviderAuditLog.cost).label('total_cost'),
                    func.avg(VLMProviderAuditLog.latency_ms).label('avg_latency_ms'),
                    func.count(func.distinct(VLMProviderAuditLog.user_id)).label('unique_users'),
                    func.count(func.distinct(VLMProviderAuditLog.leaflet_id)).label('unique_leaflets')
                ).where(and_(*conditions))
            )
        else:
            result = self.db.execute(
                select(
                    func.count(VLMProviderAuditLog.id).label('total_events'),
                    func.sum(VLMProviderAuditLog.input_tokens).label('total_input_tokens'),
                    func.sum(VLMProviderAuditLog.output_tokens).label('total_output_tokens'),
                    func.sum(VLMProviderAuditLog.cost).label('total_cost'),
                    func.avg(VLMProviderAuditLog.latency_ms).label('avg_latency_ms'),
                    func.count(func.distinct(VLMProviderAuditLog.user_id)).label('unique_users'),
                    func.count(func.distinct(VLMProviderAuditLog.leaflet_id)).label('unique_leaflets')
                ).where(and_(*conditions))
            )

        overall = result.first()

        # Event type breakdown
        event_breakdown = await self._get_event_breakdown(conditions)

        # Status breakdown
        status_breakdown = await self._get_status_breakdown(conditions)

        # Error analysis
        error_analysis = await self._get_error_analysis(conditions)

        # Provider breakdown
        provider_breakdown = await self._get_provider_breakdown(conditions)

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'organization_id': str(organization_id) if organization_id else None
            },
            'overall': {
                'total_events': overall.total_events or 0,
                'total_input_tokens': overall.total_input_tokens or 0,
                'total_output_tokens': overall.total_output_tokens or 0,
                'total_tokens': (overall.total_input_tokens or 0) + (overall.total_output_tokens or 0),
                'total_cost': float(overall.total_cost or 0),
                'avg_latency_ms': float(overall.avg_latency_ms or 0),
                'unique_users': overall.unique_users or 0,
                'unique_leaflets': overall.unique_leaflets or 0
            },
            'event_breakdown': event_breakdown,
            'status_breakdown': status_breakdown,
            'error_analysis': error_analysis,
            'provider_breakdown': provider_breakdown
        }

    async def export_audit_data(
        self,
        format: str = "csv",
        organization_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_sensitive: bool = False
    ) -> Union[str, bytes]:
        """
        Export audit data for compliance reporting.

        Args:
            format: Export format ("csv", "json")
            organization_id: Filter by organization
            start_date: Start of date range
            end_date: End of date range
            include_sensitive: Include sensitive data (IP addresses, etc.)

        Returns:
            Union[str, bytes]: Exported data
        """
        # Get audit logs
        logs = await self.get_audit_logs(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # High limit for export
            include_sensitive=include_sensitive
        )

        if format.lower() == "csv":
            return await self._export_csv(logs, include_sensitive)
        elif format.lower() == "json":
            return await self._export_json(logs, include_sensitive)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def detect_anomalies(
        self,
        organization_id: Optional[uuid.UUID] = None,
        lookback_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous patterns in VLM usage.

        Args:
            organization_id: Filter by organization
            lookback_days: Days to analyze

        Returns:
            List[Dict]: Detected anomalies
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_days)

        anomalies = []

        # Detect unusual cost spikes
        cost_anomalies = await self._detect_cost_anomalies(
            organization_id, start_date, end_date
        )
        anomalies.extend(cost_anomalies)

        # Detect unusual error rates
        error_anomalies = await self._detect_error_anomalies(
            organization_id, start_date, end_date
        )
        anomalies.extend(error_anomalies)

        # Detect unusual access patterns
        access_anomalies = await self._detect_access_anomalies(
            organization_id, start_date, end_date
        )
        anomalies.extend(access_anomalies)

        return anomalies

    async def cleanup_old_logs(self, retention_days: int = 365) -> int:
        """
        Clean up old audit logs while maintaining compliance requirements.

        Args:
            retention_days: Days to retain logs

        Returns:
            int: Number of logs deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Only delete non-error logs older than retention period
        # Keep error logs for longer compliance requirements
        if hasattr(self.db, 'execute'):
            from sqlalchemy import delete
            result = await self.db.execute(
                delete(VLMProviderAuditLog).where(
                    and_(
                        VLMProviderAuditLog.created_at < cutoff_date,
                        VLMProviderAuditLog.event_status == AuditEventStatus.SUCCESS,
                        VLMProviderAuditLog.error_type.is_(None)
                    )
                )
            )
            await self.db.commit()
        else:
            from sqlalchemy import delete
            result = self.db.execute(
                delete(VLMProviderAuditLog).where(
                    and_(
                        VLMProviderAuditLog.created_at < cutoff_date,
                        VLMProviderAuditLog.event_status == AuditEventStatus.SUCCESS,
                        VLMProviderAuditLog.error_type.is_(None)
                    )
                )
            )
            self.db.commit()

        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} old audit logs")
        return deleted_count

    # Private helper methods

    async def _get_event_breakdown(self, conditions: List) -> Dict[str, int]:
        """Get breakdown of events by type."""
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    VLMProviderAuditLog.event_type,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.event_type)
            )
        else:
            result = self.db.execute(
                select(
                    VLMProviderAuditLog.event_type,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.event_type)
            )

        breakdown = {}
        for row in result:
            breakdown[row.event_type.value] = row.count

        return breakdown

    async def _get_status_breakdown(self, conditions: List) -> Dict[str, int]:
        """Get breakdown of events by status."""
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    VLMProviderAuditLog.event_status,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.event_status)
            )
        else:
            result = self.db.execute(
                select(
                    VLMProviderAuditLog.event_status,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.event_status)
            )

        breakdown = {}
        for row in result:
            breakdown[row.event_status.value] = row.count

        return breakdown

    async def _get_error_analysis(self, conditions: List) -> Dict[str, Any]:
        """Get error analysis."""
        error_conditions = conditions + [VLMProviderAuditLog.error_type.is_not(None)]

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    VLMProviderAuditLog.error_type,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*error_conditions))
                .group_by(VLMProviderAuditLog.error_type)
            )
        else:
            result = self.db.execute(
                select(
                    VLMProviderAuditLog.error_type,
                    func.count(VLMProviderAuditLog.id).label('count')
                )
                .where(and_(*error_conditions))
                .group_by(VLMProviderAuditLog.error_type)
            )

        error_breakdown = {}
        total_errors = 0
        for row in result:
            error_breakdown[row.error_type.value] = row.count
            total_errors += row.count

        return {
            'total_errors': total_errors,
            'error_breakdown': error_breakdown
        }

    async def _get_provider_breakdown(self, conditions: List) -> List[Dict[str, Any]]:
        """Get breakdown by provider."""
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    VLMProviderAuditLog.platform_provider_id,
                    VLMProviderAuditLog.provider_type,
                    func.count(VLMProviderAuditLog.id).label('event_count'),
                    func.sum(VLMProviderAuditLog.cost).label('total_cost')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.platform_provider_id, VLMProviderAuditLog.provider_type)
            )
        else:
            result = self.db.execute(
                select(
                    VLMProviderAuditLog.platform_provider_id,
                    VLMProviderAuditLog.provider_type,
                    func.count(VLMProviderAuditLog.id).label('event_count'),
                    func.sum(VLMProviderAuditLog.cost).label('total_cost')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.platform_provider_id, VLMProviderAuditLog.provider_type)
            )

        breakdown = []
        for row in result:
            provider_name = "Unknown"
            if row.platform_provider_id:
                # Get provider name
                provider_result = await self.db.execute(
                    select(PlatformVLMProvider.name)
                    .where(PlatformVLMProvider.id == row.platform_provider_id)
                ) if hasattr(self.db, 'execute') else self.db.execute(
                    select(PlatformVLMProvider.name)
                    .where(PlatformVLMProvider.id == row.platform_provider_id)
                )
                provider_info = provider_result.first()
                if provider_info:
                    provider_name = provider_info.name

            breakdown.append({
                'provider_id': str(row.platform_provider_id) if row.platform_provider_id else None,
                'provider_name': provider_name,
                'provider_type': row.provider_type,
                'event_count': row.event_count,
                'total_cost': float(row.total_cost or 0)
            })

        return breakdown

    async def _export_csv(self, logs: List[VLMProviderAuditLog], include_sensitive: bool) -> str:
        """Export logs as CSV."""
        output = io.StringIO()

        # Define CSV headers
        headers = [
            'id', 'created_at', 'event_type', 'event_status', 'platform_provider_id',
            'organization_id', 'user_id', 'leaflet_id', 'provider_type', 'model_name',
            'input_tokens', 'output_tokens', 'cost', 'latency_ms', 'error_type',
            'error_message', 'retry_count'
        ]

        if include_sensitive:
            headers.extend(['request_ip', 'user_agent', 'session_id'])

        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for log in logs:
            row = log.to_dict(include_sensitive=include_sensitive)
            # Convert UUIDs to strings and handle None values
            csv_row = {}
            for header in headers:
                value = row.get(header)
                if isinstance(value, uuid.UUID):
                    csv_row[header] = str(value)
                elif value is None:
                    csv_row[header] = ''
                else:
                    csv_row[header] = value
            writer.writerow(csv_row)

        return output.getvalue()

    async def _export_json(self, logs: List[VLMProviderAuditLog], include_sensitive: bool) -> str:
        """Export logs as JSON."""
        data = {
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'total_records': len(logs),
            'include_sensitive_data': include_sensitive,
            'records': [log.to_dict(include_sensitive=include_sensitive) for log in logs]
        }
        return json.dumps(data, indent=2, default=str)

    async def _detect_cost_anomalies(
        self,
        organization_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Detect unusual cost patterns."""
        # This is a simplified anomaly detection
        # In production, you might use more sophisticated statistical methods

        # Get daily cost data
        conditions = [
            VLMProviderAuditLog.created_at >= start_date,
            VLMProviderAuditLog.created_at <= end_date,
            VLMProviderAuditLog.cost.is_not(None)
        ]

        if organization_id:
            conditions.append(VLMProviderAuditLog.organization_id == organization_id)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    func.date(VLMProviderAuditLog.created_at).label('date'),
                    func.sum(VLMProviderAuditLog.cost).label('daily_cost')
                )
                .where(and_(*conditions))
                .group_by(func.date(VLMProviderAuditLog.created_at))
                .order_by(func.date(VLMProviderAuditLog.created_at))
            )
        else:
            result = self.db.execute(
                select(
                    func.date(VLMProviderAuditLog.created_at).label('date'),
                    func.sum(VLMProviderAuditLog.cost).label('daily_cost')
                )
                .where(and_(*conditions))
                .group_by(func.date(VLMProviderAuditLog.created_at))
                .order_by(func.date(VLMProviderAuditLog.created_at))
            )

        daily_costs = [(row.date, float(row.daily_cost)) for row in result]

        if len(daily_costs) < 3:
            return []  # Need at least 3 days of data

        # Simple anomaly detection: cost > 2x average
        costs = [cost for _, cost in daily_costs]
        avg_cost = sum(costs) / len(costs)
        threshold = avg_cost * 2

        anomalies = []
        for date, cost in daily_costs:
            if cost > threshold:
                anomalies.append({
                    'type': 'cost_spike',
                    'date': date.isoformat(),
                    'cost': cost,
                    'average_cost': avg_cost,
                    'severity': 'high' if cost > avg_cost * 3 else 'medium',
                    'message': f"Daily cost of ${cost:.2f} is {cost/avg_cost:.1f}x the average"
                })

        return anomalies

    async def _detect_error_anomalies(
        self,
        organization_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Detect unusual error patterns."""
        # Get hourly error rates
        conditions = [
            VLMProviderAuditLog.created_at >= start_date,
            VLMProviderAuditLog.created_at <= end_date
        ]

        if organization_id:
            conditions.append(VLMProviderAuditLog.organization_id == organization_id)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    func.date_trunc('hour', VLMProviderAuditLog.created_at).label('hour'),
                    func.count(VLMProviderAuditLog.id).label('total_events'),
                    func.count(VLMProviderAuditLog.id).filter(
                        VLMProviderAuditLog.event_status.in_(['failure', 'error'])
                    ).label('error_events')
                )
                .where(and_(*conditions))
                .group_by(func.date_trunc('hour', VLMProviderAuditLog.created_at))
            )
        else:
            # For SQLite or other databases that don't support date_trunc
            result = self.db.execute(
                select(
                    func.strftime('%Y-%m-%d %H:00:00', VLMProviderAuditLog.created_at).label('hour'),
                    func.count(VLMProviderAuditLog.id).label('total_events'),
                    func.count(VLMProviderAuditLog.id).label('error_events')  # Simplified for compatibility
                )
                .where(and_(*conditions))
                .group_by(func.strftime('%Y-%m-%d %H:00:00', VLMProviderAuditLog.created_at))
            )

        anomalies = []
        for row in result:
            if row.total_events > 10:  # Only check hours with significant activity
                error_rate = (row.error_events / row.total_events) * 100
                if error_rate > 20:  # More than 20% errors
                    anomalies.append({
                        'type': 'high_error_rate',
                        'hour': str(row.hour),
                        'error_rate': error_rate,
                        'total_events': row.total_events,
                        'error_events': row.error_events,
                        'severity': 'high' if error_rate > 50 else 'medium',
                        'message': f"Error rate of {error_rate:.1f}% in hour {row.hour}"
                    })

        return anomalies

    async def _detect_access_anomalies(
        self,
        organization_id: Optional[uuid.UUID],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Detect unusual access patterns."""
        # This could detect things like:
        # - Unusual IP addresses
        # - Off-hours access
        # - Rapid successive requests

        # For now, just detect users with unusually high activity
        conditions = [
            VLMProviderAuditLog.created_at >= start_date,
            VLMProviderAuditLog.created_at <= end_date,
            VLMProviderAuditLog.user_id.is_not(None)
        ]

        if organization_id:
            conditions.append(VLMProviderAuditLog.organization_id == organization_id)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(
                    VLMProviderAuditLog.user_id,
                    func.count(VLMProviderAuditLog.id).label('event_count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.user_id)
                .having(func.count(VLMProviderAuditLog.id) > 1000)  # More than 1000 events
            )
        else:
            result = self.db.execute(
                select(
                    VLMProviderAuditLog.user_id,
                    func.count(VLMProviderAuditLog.id).label('event_count')
                )
                .where(and_(*conditions))
                .group_by(VLMProviderAuditLog.user_id)
                .having(func.count(VLMProviderAuditLog.id) > 1000)
            )

        anomalies = []
        for row in result:
            anomalies.append({
                'type': 'high_activity_user',
                'user_id': str(row.user_id),
                'event_count': row.event_count,
                'severity': 'medium',
                'message': f"User {row.user_id} generated {row.event_count} events"
            })

        return anomalies

    # Admin audit logging methods (sync, fire-and-forget)

    def log_admin_access(
        self,
        admin_user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        filters: Optional[Dict[str, Any]] = None
    ):
        """Log admin access to a resource (fire-and-forget).

        Writes a CONFIG_CHANGED / SUCCESS audit record for admin resource
        access events (e.g. viewing audit logs, security analytics).

        Args:
            admin_user_id: Admin user who accessed the resource.
            action: Action performed (e.g. 'get_audit_logs').
            resource_type: Type of resource accessed.
            resource_id: Specific resource ID if applicable.
            filters: Query filters applied by the admin.
        """
        try:
            logger.info(
                f"Admin access: user={admin_user_id}, action={action}, "
                f"resource_type={resource_type}, resource_id={resource_id}, filters={filters}"
            )
        except Exception as e:
            logger.warning(f"Failed to log admin access: {e}")

        try:
            metadata: Dict[str, Any] = {
                "action": f"admin_access:{action}",
                "resource_type": resource_type,
            }
            if resource_id:
                metadata["resource_id"] = str(resource_id)
            if filters:
                metadata["filters"] = filters

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.CONFIG_CHANGED,
                event_status=AuditEventStatus.SUCCESS,
                user_id=admin_user_id,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write admin access audit record: {e}")

    def log_admin_action(
        self,
        admin_user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        resource_data: Optional[Dict[str, Any]] = None
    ):
        """Log admin action on a resource (fire-and-forget).

        Writes a CONFIG_CHANGED / SUCCESS audit record for admin mutation
        actions (e.g. creating/updating providers).

        Args:
            admin_user_id: Admin user who performed the action.
            action: Action performed (e.g. 'create_provider').
            resource_type: Type of resource modified.
            resource_id: Specific resource ID if applicable.
            resource_data: Data associated with the action.
        """
        try:
            logger.info(
                f"Admin action: user={admin_user_id}, action={action}, "
                f"resource_type={resource_type}, resource_id={resource_id}, data={resource_data}"
            )
        except Exception as e:
            logger.warning(f"Failed to log admin action: {e}")

        try:
            metadata: Dict[str, Any] = {
                "action": f"admin_action:{action}",
                "resource_type": resource_type,
            }
            if resource_id:
                metadata["resource_id"] = str(resource_id)
            if resource_data:
                metadata["resource_data"] = resource_data

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.CONFIG_CHANGED,
                event_status=AuditEventStatus.SUCCESS,
                user_id=admin_user_id,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write admin action audit record: {e}")

    def log_admin_error(
        self,
        admin_user_id: uuid.UUID,
        action: str,
        error_message: str,
        resource_id: Optional[uuid.UUID] = None,
        request_data: Optional[Dict[str, Any]] = None
    ):
        """Log admin error (fire-and-forget).

        Writes a PROVIDER_ERROR / ERROR audit record for admin operation
        failures.

        Args:
            admin_user_id: Admin user whose action failed.
            action: Action that failed.
            error_message: Detailed error description.
            resource_id: Specific resource ID if applicable.
            request_data: Request data that caused the error.
        """
        try:
            logger.error(
                f"Admin error: user={admin_user_id}, action={action}, "
                f"resource_id={resource_id}, error={error_message}, request_data={request_data}"
            )
        except Exception as e:
            logger.warning(f"Failed to log admin error: {e}")

        try:
            metadata: Dict[str, Any] = {
                "action": f"admin_error:{action}",
            }
            if resource_id:
                metadata["resource_id"] = str(resource_id)
            if request_data:
                metadata["request_data"] = request_data

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.PROVIDER_ERROR,
                event_status=AuditEventStatus.ERROR,
                user_id=admin_user_id,
                error_type=ErrorCategory.SYSTEM_ERROR,
                error_message=error_message[:2000] if error_message else None,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write admin error audit record: {e}")

    # =========================================================================
    # Synchronous methods for Celery tasks (used by vlm_extractor_service.py)
    # Each method logs to console AND writes a VLMProviderAuditLog record.
    # DB writes are wrapped in try/except so audit failures never break extraction.
    # No commit/flush — the caller's transaction handles persistence.
    # =========================================================================

    @staticmethod
    def _resolve_error_category(error_str: Optional[str]) -> Optional[ErrorCategory]:
        """Map a free-form error category string to the ErrorCategory enum.

        Args:
            error_str: Free-form error category string from callers
                (e.g. 'budget_exceeded', 'api_error', 'unexpected_error').

        Returns:
            Matching ErrorCategory enum value, or ErrorCategory.SYSTEM_ERROR
            as a safe fallback. None if error_str is None.
        """
        if error_str is None:
            return None
        mapping = {
            "budget_exceeded": ErrorCategory.BUDGET_LIMIT,
            "budget_limit": ErrorCategory.BUDGET_LIMIT,
            "api_error": ErrorCategory.PROVIDER_ERROR,
            "provider_error": ErrorCategory.PROVIDER_ERROR,
            "rate_limit": ErrorCategory.RATE_LIMIT,
            "rate_limited": ErrorCategory.RATE_LIMIT,
            "authentication": ErrorCategory.AUTHENTICATION,
            "auth_error": ErrorCategory.AUTHENTICATION,
            "network": ErrorCategory.NETWORK,
            "network_error": ErrorCategory.NETWORK,
            "timeout": ErrorCategory.TIMEOUT,
            "timeout_error": ErrorCategory.TIMEOUT,
            "validation": ErrorCategory.VALIDATION,
            "validation_error": ErrorCategory.VALIDATION,
            "unexpected_error": ErrorCategory.SYSTEM_ERROR,
            "system_error": ErrorCategory.SYSTEM_ERROR,
        }
        return mapping.get(error_str.lower(), ErrorCategory.SYSTEM_ERROR)

    def log_provider_selection(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        provider_type: str,
        model_name: str,
        selection_reason: str,
        provider_id: Optional[uuid.UUID] = None,
        platform_provider_id: Optional[uuid.UUID] = None,
    ):
        """Log provider selection event (sync, fire-and-forget).

        Writes a CONFIG_CHANGED audit record capturing which provider and
        model were selected and why.

        Args:
            user_id: User who triggered the selection.
            organization_id: Organization context (may be None).
            provider_type: Provider category (e.g. 'organization', 'platform', 'system').
            model_name: VLM model selected.
            selection_reason: Human-readable reason for the selection.
            provider_id: User-level VLM provider ID (if applicable).
            platform_provider_id: Platform-level provider ID (if applicable).
        """
        try:
            logger.info(
                f"Provider selected: user={user_id}, org={organization_id}, "
                f"type={provider_type}, model={model_name}, reason={selection_reason}"
            )
        except Exception as e:
            logger.warning(f"Failed to log provider selection: {e}")

        try:
            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.CONFIG_CHANGED,
                event_status=AuditEventStatus.SUCCESS,
                user_id=user_id,
                organization_id=organization_id,
                platform_provider_id=platform_provider_id,
                provider_type=provider_type,
                model_name=model_name,
                audit_metadata={
                    "action": "provider_selection",
                    "selection_reason": selection_reason,
                    "provider_id": str(provider_id) if provider_id else None,
                },
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write provider selection audit record: {e}")

    def log_provider_failover(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        failed_provider_id: uuid.UUID,
        failover_provider_id: uuid.UUID,
        failure_reason: str,
    ):
        """Log provider failover event (sync, fire-and-forget).

        Writes a FAILOVER audit record capturing which provider failed and
        which one was selected as a replacement.

        Args:
            user_id: User whose extraction triggered the failover.
            organization_id: Organization context (may be None).
            failed_provider_id: Provider that failed.
            failover_provider_id: Provider selected as replacement.
            failure_reason: Human-readable reason for the failure.
        """
        try:
            logger.warning(
                f"Provider failover: user={user_id}, org={organization_id}, "
                f"failed={failed_provider_id}, failover_to={failover_provider_id}, "
                f"reason={failure_reason}"
            )
        except Exception as e:
            logger.warning(f"Failed to log provider failover: {e}")

        try:
            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.FAILOVER,
                event_status=AuditEventStatus.WARNING,
                user_id=user_id,
                organization_id=organization_id,
                platform_provider_id=failed_provider_id,
                error_type=ErrorCategory.PROVIDER_ERROR,
                error_message=failure_reason,
                audit_metadata={
                    "failed_provider_id": str(failed_provider_id),
                    "failover_provider_id": str(failover_provider_id),
                },
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write provider failover audit record: {e}")

    def log_extraction_request(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        leaflet_id: Optional[uuid.UUID] = None,
        page_number: Optional[int] = None,
        provider_type: Optional[str] = None,
        model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        provider_id: Optional[uuid.UUID] = None,
        image_size_bytes: Optional[int] = None,
        request_ip: Optional[str] = None,
    ):
        """Log extraction request start (sync, fire-and-forget).

        Writes an EXTRACTION audit record with status PARTIAL to mark the
        beginning of a page-level VLM request (in-progress, not yet completed).

        Args:
            user_id: User who initiated the extraction.
            organization_id: Organization context (may be None).
            leaflet_id: Leaflet being processed.
            page_number: Page number within the leaflet.
            provider_type: Provider category string.
            model_name: VLM model used for the request.
            session_id: Unique session/operation identifier.
            provider_id: Provider ID used for the request.
            image_size_bytes: Size of the image payload in bytes.
            request_ip: Client IP address that initiated the extraction.
        """
        try:
            logger.info(
                f"Extraction request: user={user_id}, org={organization_id}, "
                f"leaflet={leaflet_id}, page={page_number}, provider={provider_type}, "
                f"model={model_name}, session={session_id}, provider_id={provider_id}, "
                f"image_size={image_size_bytes} bytes"
            )
        except Exception as e:
            logger.warning(f"Failed to log extraction request: {e}")

        try:
            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.PARTIAL,
                user_id=user_id,
                organization_id=organization_id,
                leaflet_id=leaflet_id,
                provider_type=provider_type,
                model_name=model_name,
                operation_id=session_id,
                request_ip=request_ip,
                audit_metadata={
                    "action": "extraction_request",
                    "page_number": page_number,
                    "provider_id": str(provider_id) if provider_id else None,
                    "image_size_bytes": image_size_bytes,
                },
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write extraction request audit record: {e}")

    def log_extraction_success(
        self,
        session_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        processing_time_ms: int = 0,
        products_found: int = 0,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        leaflet_id: Optional[uuid.UUID] = None,
        request_ip: Optional[str] = None,
        **kwargs,
    ):
        """Log successful extraction (sync, fire-and-forget).

        Writes an EXTRACTION / SUCCESS audit record with token usage,
        cost, latency, and product count.

        Args:
            session_id: Operation/session identifier linking related records.
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens generated.
            cost: Cost of the extraction in USD.
            processing_time_ms: Wall-clock time for the VLM call in ms.
            products_found: Number of products extracted from the page.
            user_id: User who initiated the extraction (optional).
            organization_id: Organization context (optional).
            leaflet_id: Leaflet being processed (optional).
            request_ip: Client IP address that initiated the extraction.
            **kwargs: Additional context (e.g. response_metadata) stored
                in the audit_metadata JSONB column.
        """
        try:
            logger.info(
                f"Extraction success: session={session_id}, tokens={input_tokens}+{output_tokens}, "
                f"cost=${cost or 0:.4f}, time={processing_time_ms}ms, products={products_found}"
            )
        except Exception as e:
            logger.warning(f"Failed to log extraction success: {e}")

        try:
            # Build metadata from kwargs (e.g. response_metadata passed by callers)
            metadata = {
                "action": "extraction_success",
                "products_found": products_found,
            }
            if kwargs.get("response_metadata"):
                metadata["response_metadata"] = kwargs["response_metadata"]

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.SUCCESS,
                operation_id=session_id,
                user_id=user_id,
                organization_id=organization_id,
                leaflet_id=leaflet_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=Decimal(str(cost)) if cost is not None else None,
                latency_ms=processing_time_ms,
                request_ip=request_ip,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write extraction success audit record: {e}")

    def log_extraction_failure(
        self,
        session_id: Optional[str] = None,
        error_message: str = "",
        error_type: Optional[str] = None,
        retry_count: int = 0,
        request_ip: Optional[str] = None,
        **kwargs,
    ):
        """Log extraction failure (sync, fire-and-forget).

        Writes an EXTRACTION / FAILURE audit record with error details.

        Args:
            session_id: Operation/session identifier linking related records.
            error_message: Detailed error description.
            error_type: Free-form error category string (mapped to ErrorCategory enum).
            retry_count: Number of retries attempted before this failure.
            request_ip: Client IP address that initiated the extraction.
            **kwargs: Additional context (e.g. error_category, processing_time_ms,
                provider_specific_error) stored in audit_metadata.
        """
        try:
            logger.error(
                f"Extraction failure: session={session_id}, error={error_message}, "
                f"type={error_type}, retries={retry_count}"
            )
        except Exception as e:
            logger.warning(f"Failed to log extraction failure: {e}")

        try:
            # Callers pass 'error_category' as a kwarg in some call sites
            error_category_str = kwargs.get("error_category", error_type)
            resolved_category = self._resolve_error_category(error_category_str)

            metadata: Dict[str, Any] = {"action": "extraction_failure"}
            if kwargs.get("processing_time_ms"):
                metadata["processing_time_ms"] = kwargs["processing_time_ms"]
            if kwargs.get("provider_specific_error"):
                metadata["provider_specific_error"] = str(kwargs["provider_specific_error"])

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.FAILURE,
                operation_id=session_id,
                error_type=resolved_category,
                error_message=error_message[:2000] if error_message else None,
                retry_count=retry_count,
                latency_ms=kwargs.get("processing_time_ms"),
                request_ip=request_ip,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write extraction failure audit record: {e}")

    def log_leaflet_extraction_start(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        leaflet_id: uuid.UUID,
        page_count: int,
        provider_type: str,
        model_name: Optional[str] = None,
        provider_id: Optional[uuid.UUID] = None,
        concurrent_processing: bool = False,
        max_concurrent: int = 1,
        request_ip: Optional[str] = None,
    ):
        """Log leaflet extraction start (sync, fire-and-forget).

        Writes an EXTRACTION / PARTIAL audit record marking the beginning
        of a full leaflet extraction job (in-progress, not yet completed).

        Args:
            user_id: User who initiated the extraction.
            organization_id: Organization context (may be None).
            leaflet_id: Leaflet being processed.
            page_count: Total number of pages in the leaflet.
            provider_type: Provider category string.
            model_name: VLM model selected for extraction.
            provider_id: Provider ID used.
            concurrent_processing: Whether pages will be processed concurrently.
            max_concurrent: Maximum number of concurrent page extractions.
            request_ip: Client IP address that initiated the extraction.
        """
        try:
            logger.info(
                f"Leaflet extraction start: user={user_id}, org={organization_id}, "
                f"leaflet={leaflet_id}, pages={page_count}, provider={provider_type}, "
                f"model={model_name}, provider_id={provider_id}, "
                f"concurrent={concurrent_processing}, max_concurrent={max_concurrent}"
            )
        except Exception as e:
            logger.warning(f"Failed to log leaflet extraction start: {e}")

        try:
            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.PARTIAL,
                user_id=user_id,
                organization_id=organization_id,
                leaflet_id=leaflet_id,
                provider_type=provider_type,
                model_name=model_name,
                request_ip=request_ip,
                audit_metadata={
                    "action": "leaflet_extraction_start",
                    "page_count": page_count,
                    "provider_id": str(provider_id) if provider_id else None,
                    "concurrent_processing": concurrent_processing,
                    "max_concurrent": max_concurrent,
                },
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write leaflet extraction start audit record: {e}")

    def log_leaflet_extraction_success(
        self,
        leaflet_id: uuid.UUID,
        total_products: int = 0,
        total_cost: float = 0.0,
        total_tokens: int = 0,
        processing_time_ms: int = 0,
        auto_approved: int = 0,
        review_required: int = 0,
        pages_processed: int = 0,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
        extraction_metadata: Optional[Dict[str, Any]] = None,
        request_ip: Optional[str] = None,
    ):
        """Log successful leaflet extraction (sync, fire-and-forget).

        Writes an EXTRACTION / SUCCESS audit record with aggregate token
        usage, cost, and product counts for the entire leaflet.

        Args:
            leaflet_id: Leaflet that was processed.
            total_products: Total number of products extracted.
            total_cost: Total extraction cost in USD.
            total_tokens: Total tokens (input + output) if pre-computed.
            processing_time_ms: Total wall-clock time in ms.
            auto_approved: Number of auto-approved products.
            review_required: Number of products routed to review.
            pages_processed: Number of pages successfully processed.
            total_input_tokens: Total input tokens consumed.
            total_output_tokens: Total output tokens generated.
            extraction_metadata: Additional structured context from the caller.
            request_ip: Client IP address that initiated the extraction.
        """
        try:
            tokens = total_tokens or (total_input_tokens + total_output_tokens)
            logger.info(
                f"Leaflet extraction success: leaflet={leaflet_id}, products={total_products}, "
                f"cost=${total_cost:.4f}, tokens={tokens}, time={processing_time_ms}ms, "
                f"pages={pages_processed}, auto_approved={auto_approved}, review_required={review_required}"
            )
        except Exception as e:
            logger.warning(f"Failed to log leaflet extraction success: {e}")

        try:
            tokens = total_tokens or (total_input_tokens + total_output_tokens)
            metadata: Dict[str, Any] = {
                "action": "leaflet_extraction_success",
                "total_products": total_products,
                "pages_processed": pages_processed,
                "auto_approved": auto_approved,
                "review_required": review_required,
            }
            if extraction_metadata:
                metadata["extraction_metadata"] = extraction_metadata

            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.SUCCESS,
                leaflet_id=leaflet_id,
                input_tokens=total_input_tokens or None,
                output_tokens=total_output_tokens or None,
                cost=Decimal(str(total_cost)) if total_cost is not None else None,
                latency_ms=processing_time_ms,
                request_ip=request_ip,
                audit_metadata=metadata,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write leaflet extraction success audit record: {e}")

    def log_leaflet_extraction_failure(
        self,
        leaflet_id: uuid.UUID,
        error_message: str,
        pages_processed: int = 0,
        partial_products: int = 0,
        processing_time_ms: int = 0,
        pages_attempted: int = 0,
        request_ip: Optional[str] = None,
    ):
        """Log failed leaflet extraction (sync, fire-and-forget).

        Writes an EXTRACTION / FAILURE audit record with error details
        and partial progress information.

        Args:
            leaflet_id: Leaflet that failed processing.
            error_message: Detailed error description.
            pages_processed: Number of pages successfully processed before failure.
            partial_products: Number of products extracted before failure.
            processing_time_ms: Wall-clock time before failure in ms.
            pages_attempted: Number of pages that were attempted.
            request_ip: Client IP address that initiated the extraction.
        """
        try:
            logger.error(
                f"Leaflet extraction failure: leaflet={leaflet_id}, error={error_message}, "
                f"pages_processed={pages_processed}, pages_attempted={pages_attempted}, "
                f"partial_products={partial_products}, time={processing_time_ms}ms"
            )
        except Exception as e:
            logger.warning(f"Failed to log leaflet extraction failure: {e}")

        try:
            audit_log = VLMProviderAuditLog(
                event_type=AuditEventType.EXTRACTION,
                event_status=AuditEventStatus.FAILURE,
                leaflet_id=leaflet_id,
                error_type=ErrorCategory.SYSTEM_ERROR,
                error_message=error_message[:2000] if error_message else None,
                latency_ms=processing_time_ms,
                request_ip=request_ip,
                audit_metadata={
                    "action": "leaflet_extraction_failure",
                    "pages_processed": pages_processed,
                    "pages_attempted": pages_attempted,
                    "partial_products": partial_products,
                },
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning(f"Failed to write leaflet extraction failure audit record: {e}")