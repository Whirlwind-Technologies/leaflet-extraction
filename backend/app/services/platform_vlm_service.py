"""
Platform VLM Provider Service Module.

This service manages platform-level VLM providers with intelligent failover,
budget monitoring, and usage tracking across organizations.

Example Usage:
    from app.services.platform_vlm_service import PlatformVLMProviderService

    service = PlatformVLMProviderService(db_session)
    provider = await service.get_active_provider(organization_id)
    await service.record_usage(provider.id, organization_id, usage_data)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal

from sqlalchemy import select, update, and_, or_, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_vlm_provider import PlatformVLMProvider, PlatformVLMProviderType
from app.models.organization_usage import OrganizationVLMUsage
from app.models.vlm_audit_log import VLMProviderAuditLog, AuditEventType, AuditEventStatus, ErrorCategory
from app.models.budget_alert import BudgetAlert, AlertType, AlertPeriod
from app.models.organization import Organization
from app.core.extraction.multi_provider_client import (
    VLMClientError,
    APIError,
    BudgetExceededError,
    InsufficientCreditsError,
    ProviderNotSupportedError
)

logger = logging.getLogger(__name__)


class ProviderFailoverError(Exception):
    """Raised when all providers have failed or are unavailable."""
    pass


class PlatformVLMProviderService:
    """
    Service for managing platform VLM providers with failover and monitoring.

    This service handles:
    - Provider selection based on priority and availability
    - Automatic failover when providers fail or exceed budgets
    - Usage tracking per organization
    - Budget monitoring and alerts
    - Audit logging for compliance
    """

    def __init__(self, db_session: Session):
        """
        Initialize the platform VLM provider service.

        Args:
            db_session: Database session (sync or async)
        """
        self.db = db_session
        self._provider_cache = {}
        self._cache_ttl = 300  # 5 minutes

    async def get_active_provider(
        self,
        organization_id: uuid.UUID,
        required_provider_type: Optional[PlatformVLMProviderType] = None
    ) -> PlatformVLMProvider:
        """
        Get the best available platform provider for an organization.

        Uses priority-based selection with smart failover logic:
        1. Try default provider first
        2. If budget exhausted or failed, try next priority provider
        3. Respect provider type requirements if specified

        Args:
            organization_id: Organization needing a provider
            required_provider_type: Specific provider type required (optional)

        Returns:
            PlatformVLMProvider: Active provider ready for use

        Raises:
            ProviderFailoverError: If no providers are available
        """
        cache_key = f"active_provider:{organization_id}:{required_provider_type}"

        # Check cache first
        if cache_key in self._provider_cache:
            cached_data = self._provider_cache[cache_key]
            if datetime.now(timezone.utc) - cached_data['timestamp'] < timedelta(seconds=self._cache_ttl):
                provider = cached_data['provider']
                if await self._is_provider_available(provider):
                    return provider

        # Get available providers ordered by priority
        providers = await self._get_available_providers(required_provider_type)

        if not providers:
            error_msg = "No active platform providers configured"
            if required_provider_type:
                error_msg += f" for type {required_provider_type.value}"

            await self._log_audit_event(
                event_type=AuditEventType.PROVIDER_ERROR,
                event_status=AuditEventStatus.ERROR,
                organization_id=organization_id,
                error_type=ErrorCategory.SYSTEM_ERROR,
                error_message=error_msg
            )
            raise ProviderFailoverError(error_msg)

        # Try providers in priority order
        for provider in providers:
            try:
                if await self._is_provider_available(provider):
                    # Cache the successful provider
                    self._provider_cache[cache_key] = {
                        'provider': provider,
                        'timestamp': datetime.now(timezone.utc)
                    }

                    logger.info(
                        f"Selected provider {provider.name} (priority {provider.priority}) "
                        f"for organization {organization_id}"
                    )
                    return provider

            except Exception as e:
                logger.warning(f"Provider {provider.name} failed availability check: {e}")
                await self._log_provider_failure(provider, organization_id, str(e))
                continue

        # All providers failed
        await self._log_audit_event(
            event_type=AuditEventType.FAILOVER,
            event_status=AuditEventStatus.FAILURE,
            organization_id=organization_id,
            error_type=ErrorCategory.SYSTEM_ERROR,
            error_message="All platform providers failed or unavailable"
        )
        raise ProviderFailoverError("All platform providers failed or unavailable")

    async def record_usage(
        self,
        provider_id: uuid.UUID,
        organization_id: uuid.UUID,
        usage_data: Dict[str, Any]
    ) -> OrganizationVLMUsage:
        """
        Record VLM usage for a platform provider and organization.

        Args:
            provider_id: Platform provider that was used
            organization_id: Organization that used the provider
            usage_data: Usage metrics
                - request_count: Number of requests
                - input_tokens: Input tokens consumed
                - output_tokens: Output tokens generated
                - cost: Cost in USD
                - leaflet_count: Number of leaflets processed
                - page_count: Number of pages processed
                - product_count: Number of products extracted
                - confidence_score: Average confidence score

        Returns:
            OrganizationVLMUsage: Updated or created usage record
        """
        now = datetime.now(timezone.utc)
        usage_date = now.date()
        usage_hour = now.hour

        # Get or create usage record
        usage_record = await self._get_or_create_usage_record(
            organization_id, provider_id, usage_date, usage_hour
        )

        # Update the record
        usage_record.add_usage(
            request_count=usage_data.get('request_count', 1),
            input_tokens=usage_data.get('input_tokens', 0),
            output_tokens=usage_data.get('output_tokens', 0),
            cost=usage_data.get('cost', 0.0),
            leaflet_count=usage_data.get('leaflet_count', 0),
            page_count=usage_data.get('page_count', 0),
            product_count=usage_data.get('product_count', 0),
            confidence_score=usage_data.get('confidence_score')
        )

        # Update platform provider usage
        await self._update_provider_usage(provider_id, usage_data)

        # Check budget thresholds
        await self._check_budget_thresholds(provider_id, organization_id)

        # Commit the transaction
        if hasattr(self.db, 'commit'):
            self.db.commit()
        else:
            await self.db.commit()

        logger.debug(
            f"Recorded usage: provider={provider_id}, org={organization_id}, "
            f"cost=${usage_data.get('cost', 0):.4f}, tokens={usage_data.get('input_tokens', 0)}+{usage_data.get('output_tokens', 0)}"
        )

        return usage_record

    async def trigger_failover(
        self,
        failed_provider_id: uuid.UUID,
        organization_id: uuid.UUID,
        failure_reason: str,
        error_category: ErrorCategory = ErrorCategory.PROVIDER_ERROR
    ) -> Optional[PlatformVLMProvider]:
        """
        Trigger failover to next available provider.

        Args:
            failed_provider_id: Provider that failed
            organization_id: Organization context
            failure_reason: Reason for failover
            error_category: Category of error that triggered failover

        Returns:
            PlatformVLMProvider: Next available provider, or None if none available
        """
        # Log the failover event
        await self._log_audit_event(
            event_type=AuditEventType.FAILOVER,
            event_status=AuditEventStatus.WARNING,
            platform_provider_id=failed_provider_id,
            organization_id=organization_id,
            error_type=error_category,
            error_message=f"Failover triggered: {failure_reason}"
        )

        # Clear cache for this organization
        cache_pattern = f"active_provider:{organization_id}"
        keys_to_remove = [key for key in self._provider_cache.keys() if key.startswith(cache_pattern)]
        for key in keys_to_remove:
            del self._provider_cache[key]

        # Get failed provider to determine type constraints
        failed_provider = await self._get_provider_by_id(failed_provider_id)
        required_type = None

        # If the failure is budget-related, we can try different provider types
        # If it's an API error, we might want to stick to the same type
        if error_category not in [ErrorCategory.BUDGET_LIMIT, ErrorCategory.RATE_LIMIT]:
            if failed_provider:
                required_type = failed_provider.provider_type

        try:
            # Get next available provider (excluding the failed one)
            next_provider = await self._get_next_provider(failed_provider_id, required_type)

            if next_provider:
                logger.info(
                    f"Failover successful: {failed_provider.name if failed_provider else 'unknown'} "
                    f"-> {next_provider.name} for organization {organization_id}"
                )

                # Log successful failover
                await self._log_audit_event(
                    event_type=AuditEventType.FAILOVER,
                    event_status=AuditEventStatus.SUCCESS,
                    platform_provider_id=next_provider.id,
                    organization_id=organization_id,
                    metadata={
                        'failed_provider_id': str(failed_provider_id),
                        'failover_reason': failure_reason
                    }
                )

                return next_provider
            else:
                logger.error(f"Failover failed: no alternative providers available for organization {organization_id}")

                # Log failed failover
                await self._log_audit_event(
                    event_type=AuditEventType.FAILOVER,
                    event_status=AuditEventStatus.FAILURE,
                    platform_provider_id=failed_provider_id,
                    organization_id=organization_id,
                    error_type=ErrorCategory.SYSTEM_ERROR,
                    error_message="No alternative providers available for failover"
                )

                return None

        except Exception as e:
            logger.exception(f"Error during failover for organization {organization_id}: {e}")

            await self._log_audit_event(
                event_type=AuditEventType.FAILOVER,
                event_status=AuditEventStatus.ERROR,
                platform_provider_id=failed_provider_id,
                organization_id=organization_id,
                error_type=ErrorCategory.SYSTEM_ERROR,
                error_message=f"Failover error: {str(e)}"
            )

            return None

    async def get_usage_summary(
        self,
        organization_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get usage summary for an organization within a date range.

        Args:
            organization_id: Organization to summarize
            start_date: Start of date range
            end_date: End of date range

        Returns:
            dict: Usage summary with costs, tokens, and metrics
        """
        if hasattr(self.db, 'execute'):
            # Async session
            result = await self.db.execute(
                select(
                    func.sum(OrganizationVLMUsage.request_count).label('total_requests'),
                    func.sum(OrganizationVLMUsage.input_tokens).label('total_input_tokens'),
                    func.sum(OrganizationVLMUsage.output_tokens).label('total_output_tokens'),
                    func.sum(OrganizationVLMUsage.total_cost).label('total_cost'),
                    func.sum(OrganizationVLMUsage.leaflet_count).label('total_leaflets'),
                    func.sum(OrganizationVLMUsage.page_count).label('total_pages'),
                    func.sum(OrganizationVLMUsage.product_count).label('total_products'),
                    func.avg(OrganizationVLMUsage.average_confidence).label('avg_confidence')
                )
                .where(
                    and_(
                        OrganizationVLMUsage.organization_id == organization_id,
                        OrganizationVLMUsage.usage_date >= start_date.date(),
                        OrganizationVLMUsage.usage_date <= end_date.date()
                    )
                )
            )
        else:
            # Sync session
            result = self.db.execute(
                select(
                    func.sum(OrganizationVLMUsage.request_count).label('total_requests'),
                    func.sum(OrganizationVLMUsage.input_tokens).label('total_input_tokens'),
                    func.sum(OrganizationVLMUsage.output_tokens).label('total_output_tokens'),
                    func.sum(OrganizationVLMUsage.total_cost).label('total_cost'),
                    func.sum(OrganizationVLMUsage.leaflet_count).label('total_leaflets'),
                    func.sum(OrganizationVLMUsage.page_count).label('total_pages'),
                    func.sum(OrganizationVLMUsage.product_count).label('total_products'),
                    func.avg(OrganizationVLMUsage.average_confidence).label('avg_confidence')
                )
                .where(
                    and_(
                        OrganizationVLMUsage.organization_id == organization_id,
                        OrganizationVLMUsage.usage_date >= start_date.date(),
                        OrganizationVLMUsage.usage_date <= end_date.date()
                    )
                )
            )

        row = result.first()

        return {
            'total_requests': row.total_requests or 0,
            'total_input_tokens': row.total_input_tokens or 0,
            'total_output_tokens': row.total_output_tokens or 0,
            'total_tokens': (row.total_input_tokens or 0) + (row.total_output_tokens or 0),
            'total_cost': float(row.total_cost or 0),
            'total_leaflets': row.total_leaflets or 0,
            'total_pages': row.total_pages or 0,
            'total_products': row.total_products or 0,
            'average_confidence': float(row.avg_confidence or 0),
            'cost_per_request': float(row.total_cost or 0) / max(row.total_requests or 1, 1),
            'cost_per_leaflet': float(row.total_cost or 0) / max(row.total_leaflets or 1, 1),
            'products_per_leaflet': (row.total_products or 0) / max(row.total_leaflets or 1, 1),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }

    # Private helper methods

    async def _get_available_providers(
        self,
        required_provider_type: Optional[PlatformVLMProviderType] = None
    ) -> List[PlatformVLMProvider]:
        """Get available providers ordered by priority."""
        query = (
            select(PlatformVLMProvider)
            .where(PlatformVLMProvider.is_active == True)
            .order_by(
                PlatformVLMProvider.priority.asc(),
                PlatformVLMProvider.is_default.desc(),
                PlatformVLMProvider.created_at.desc()
            )
        )

        if required_provider_type:
            query = query.where(PlatformVLMProvider.provider_type == required_provider_type)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        return result.scalars().all()

    async def _is_provider_available(self, provider: PlatformVLMProvider) -> bool:
        """Check if a provider is available for use."""
        if not provider.is_active:
            return False

        # Check all budget constraints
        if not provider.check_budget():
            return False

        return True

    async def _get_next_provider(
        self,
        exclude_provider_id: uuid.UUID,
        required_provider_type: Optional[PlatformVLMProviderType] = None
    ) -> Optional[PlatformVLMProvider]:
        """Get next available provider excluding the specified one."""
        query = (
            select(PlatformVLMProvider)
            .where(
                and_(
                    PlatformVLMProvider.is_active == True,
                    PlatformVLMProvider.id != exclude_provider_id
                )
            )
            .order_by(
                PlatformVLMProvider.priority.asc(),
                PlatformVLMProvider.is_default.desc(),
                PlatformVLMProvider.created_at.desc()
            )
        )

        if required_provider_type:
            query = query.where(PlatformVLMProvider.provider_type == required_provider_type)

        if hasattr(self.db, 'execute'):
            result = await self.db.execute(query)
        else:
            result = self.db.execute(query)

        providers = result.scalars().all()

        for provider in providers:
            if await self._is_provider_available(provider):
                return provider

        return None

    async def _get_provider_by_id(self, provider_id: uuid.UUID) -> Optional[PlatformVLMProvider]:
        """Get provider by ID."""
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
            )
        else:
            result = self.db.execute(
                select(PlatformVLMProvider).where(PlatformVLMProvider.id == provider_id)
            )
        return result.scalar_one_or_none()

    async def _get_or_create_usage_record(
        self,
        organization_id: uuid.UUID,
        provider_id: uuid.UUID,
        usage_date,
        usage_hour: int
    ) -> OrganizationVLMUsage:
        """Get or create usage record for the specified parameters."""
        if hasattr(self.db, 'execute'):
            result = await self.db.execute(
                select(OrganizationVLMUsage).where(
                    and_(
                        OrganizationVLMUsage.organization_id == organization_id,
                        OrganizationVLMUsage.platform_provider_id == provider_id,
                        OrganizationVLMUsage.usage_date == usage_date,
                        OrganizationVLMUsage.usage_hour == usage_hour
                    )
                )
            )
        else:
            result = self.db.execute(
                select(OrganizationVLMUsage).where(
                    and_(
                        OrganizationVLMUsage.organization_id == organization_id,
                        OrganizationVLMUsage.platform_provider_id == provider_id,
                        OrganizationVLMUsage.usage_date == usage_date,
                        OrganizationVLMUsage.usage_hour == usage_hour
                    )
                )
            )

        usage_record = result.scalar_one_or_none()

        if not usage_record:
            usage_record = OrganizationVLMUsage(
                organization_id=organization_id,
                platform_provider_id=provider_id,
                usage_date=usage_date,
                usage_hour=usage_hour
            )
            self.db.add(usage_record)

        return usage_record

    async def _update_provider_usage(self, provider_id: uuid.UUID, usage_data: Dict[str, Any]):
        """Update platform provider usage statistics."""
        if hasattr(self.db, 'execute'):
            await self.db.execute(
                update(PlatformVLMProvider)
                .where(PlatformVLMProvider.id == provider_id)
                .values(
                    total_requests=PlatformVLMProvider.total_requests + usage_data.get('request_count', 1),
                    total_input_tokens=PlatformVLMProvider.total_input_tokens + usage_data.get('input_tokens', 0),
                    total_output_tokens=PlatformVLMProvider.total_output_tokens + usage_data.get('output_tokens', 0),
                    total_spent=PlatformVLMProvider.total_spent + usage_data.get('cost', 0.0),
                    current_month_spent=PlatformVLMProvider.current_month_spent + usage_data.get('cost', 0.0),
                    current_day_spent=PlatformVLMProvider.current_day_spent + usage_data.get('cost', 0.0),
                    current_hour_requests=PlatformVLMProvider.current_hour_requests + usage_data.get('request_count', 1),
                    last_used_at=datetime.now(timezone.utc)
                )
            )
        else:
            self.db.execute(
                update(PlatformVLMProvider)
                .where(PlatformVLMProvider.id == provider_id)
                .values(
                    total_requests=PlatformVLMProvider.total_requests + usage_data.get('request_count', 1),
                    total_input_tokens=PlatformVLMProvider.total_input_tokens + usage_data.get('input_tokens', 0),
                    total_output_tokens=PlatformVLMProvider.total_output_tokens + usage_data.get('output_tokens', 0),
                    total_spent=PlatformVLMProvider.total_spent + usage_data.get('cost', 0.0),
                    current_month_spent=PlatformVLMProvider.current_month_spent + usage_data.get('cost', 0.0),
                    current_day_spent=PlatformVLMProvider.current_day_spent + usage_data.get('cost', 0.0),
                    current_hour_requests=PlatformVLMProvider.current_hour_requests + usage_data.get('request_count', 1),
                    last_used_at=datetime.now(timezone.utc)
                )
            )

    async def _check_budget_thresholds(self, provider_id: uuid.UUID, organization_id: uuid.UUID):
        """Check if budget thresholds have been exceeded and trigger alerts."""
        # This will be implemented when we create the BudgetMonitoringService
        pass

    async def _log_audit_event(
        self,
        event_type: AuditEventType,
        event_status: AuditEventStatus,
        platform_provider_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        leaflet_id: Optional[uuid.UUID] = None,
        error_type: Optional[ErrorCategory] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log audit event."""
        audit_log = VLMProviderAuditLog(
            event_type=event_type,
            event_status=event_status,
            platform_provider_id=platform_provider_id,
            organization_id=organization_id,
            user_id=user_id,
            leaflet_id=leaflet_id,
            error_type=error_type,
            error_message=error_message,
            metadata=metadata or {}
        )
        self.db.add(audit_log)

    async def _log_provider_failure(
        self,
        provider: PlatformVLMProvider,
        organization_id: uuid.UUID,
        error_message: str
    ):
        """Log provider failure event."""
        await self._log_audit_event(
            event_type=AuditEventType.PROVIDER_ERROR,
            event_status=AuditEventStatus.FAILURE,
            platform_provider_id=provider.id,
            organization_id=organization_id,
            error_type=ErrorCategory.PROVIDER_ERROR,
            error_message=error_message,
            metadata={
                'provider_name': provider.name,
                'provider_type': provider.provider_type.value,
                'provider_priority': provider.priority
            }
        )

    # =========================================================================
    # Synchronous methods for Celery tasks (which use sync database sessions)
    # =========================================================================

    def get_best_provider(
        self,
        organization_id: Optional[uuid.UUID] = None,
        exclude_failed: bool = False
    ) -> Optional[PlatformVLMProvider]:
        """
        Get the best available platform provider (synchronous version).

        Used by Celery tasks which have sync database sessions.

        Args:
            organization_id: Optional organization context
            exclude_failed: Whether to exclude recently failed providers

        Returns:
            PlatformVLMProvider or None if no providers available
        """
        query = (
            select(PlatformVLMProvider)
            .where(PlatformVLMProvider.is_active == True)
            .order_by(
                PlatformVLMProvider.priority.asc(),
                PlatformVLMProvider.is_default.desc(),
                PlatformVLMProvider.created_at.desc()
            )
        )

        result = self.db.execute(query)
        providers = result.scalars().all()

        for provider in providers:
            if self._is_provider_available_sync(provider):
                logger.info(
                    f"Selected platform provider: {provider.name} "
                    f"(priority {provider.priority})"
                )
                return provider

        logger.warning("No platform providers available")
        return None

    def _is_provider_available_sync(self, provider: PlatformVLMProvider) -> bool:
        """Check if a provider is available (sync version)."""
        if not provider.is_active:
            return False
        if not provider.check_budget():
            return False
        return True

    def mark_provider_failed(self, provider_id: uuid.UUID, error_message: str):
        """
        Mark a provider as temporarily failed (synchronous version).

        This can be used to temporarily skip a provider during failover.

        Args:
            provider_id: Provider that failed
            error_message: Reason for failure
        """
        logger.warning(f"Provider {provider_id} marked as failed: {error_message}")
        # For now, just log the failure. In a more advanced implementation,
        # we could track failed providers in Redis with TTL for temporary exclusion.

    def record_usage(
        self,
        provider_id: uuid.UUID,
        organization_id: uuid.UUID,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        request_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record VLM usage for a platform provider (synchronous version).

        Args:
            provider_id: Platform provider that was used
            organization_id: Organization that used the provider
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost in USD
            request_metadata: Optional metadata about the request
        """
        try:
            # Update provider usage
            self.db.execute(
                update(PlatformVLMProvider)
                .where(PlatformVLMProvider.id == provider_id)
                .values(
                    total_requests=PlatformVLMProvider.total_requests + 1,
                    total_input_tokens=PlatformVLMProvider.total_input_tokens + input_tokens,
                    total_output_tokens=PlatformVLMProvider.total_output_tokens + output_tokens,
                    total_spent=PlatformVLMProvider.total_spent + cost,
                    current_month_spent=PlatformVLMProvider.current_month_spent + cost,
                    current_day_spent=PlatformVLMProvider.current_day_spent + cost,
                    current_hour_requests=PlatformVLMProvider.current_hour_requests + 1,
                    last_used_at=datetime.now(timezone.utc)
                )
            )

            self.db.commit()

            logger.debug(
                f"Recorded usage: provider={provider_id}, org={organization_id}, "
                f"tokens={input_tokens}+{output_tokens}, cost=${cost:.4f}"
            )

        except Exception as e:
            logger.error(f"Failed to record usage: {e}")
            self.db.rollback()

    async def restore_provider_from_backup(
        self,
        backup_id: uuid.UUID,
        restore_reason: str,
        restored_by: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Restore a platform provider configuration from backup.

        Args:
            backup_id: ID of the backup to restore from
            restore_reason: Reason for the restore
            restored_by: User ID performing the restore

        Returns:
            dict: Result containing restored_provider_id and message

        Raises:
            ValueError: If backup not found or cannot be restored
        """
        from app.models.vlm_provider_backup import VLMProviderBackup, BackupStatus

        # Get the backup
        query = select(VLMProviderBackup).where(VLMProviderBackup.id == backup_id)
        result = await self.db.execute(query)
        backup = result.scalar_one_or_none()

        if not backup:
            raise ValueError(f"Backup {backup_id} not found")

        if not backup.is_restorable:
            raise ValueError(f"Backup {backup_id} is not restorable (status: {backup.status.value})")

        # Restore the configuration
        try:
            config = backup.restore_config()
        except Exception as e:
            raise ValueError(f"Failed to decrypt backup configuration: {str(e)}")

        # Find or create the provider
        provider = None
        if backup.platform_provider_id:
            # Try to find the original provider
            provider_query = select(PlatformVLMProvider).where(
                PlatformVLMProvider.id == backup.platform_provider_id
            )
            provider_result = await self.db.execute(provider_query)
            provider = provider_result.scalar_one_or_none()

        if provider:
            # Update existing provider with backup config
            provider.name = config.get("name", provider.name)
            provider.api_endpoint = config.get("api_endpoint", provider.api_endpoint)
            provider.model_name = config.get("model_name", provider.model_name)
            provider.max_tokens = config.get("max_tokens", provider.max_tokens)
            provider.temperature = config.get("temperature", provider.temperature)
            provider.config = config.get("config", provider.config)
            provider.priority = config.get("priority", provider.priority)
            provider.is_active = config.get("is_active", provider.is_active)
            provider.max_requests_per_hour = config.get("max_requests_per_hour", provider.max_requests_per_hour)

            if config.get("monthly_budget"):
                provider.monthly_budget = config.get("monthly_budget")
            if config.get("daily_budget"):
                provider.daily_budget = config.get("daily_budget")

            message = f"Provider '{provider.name}' configuration restored from backup"
        else:
            # Provider was deleted - can't restore without creating new one
            raise ValueError(
                f"Original provider was deleted. Cannot restore backup to deleted provider. "
                f"Consider creating a new provider manually."
            )

        # Mark backup as restored
        backup.mark_restored(restored_by)

        await self.db.commit()

        logger.info(
            f"Provider {provider.id} restored from backup {backup_id} "
            f"by user {restored_by}. Reason: {restore_reason}"
        )

        return {
            "restored_provider_id": str(provider.id),
            "message": message
        }