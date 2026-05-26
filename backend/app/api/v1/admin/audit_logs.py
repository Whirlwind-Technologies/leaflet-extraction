"""
Admin API endpoints for Audit Log Retrieval and Analysis.

These endpoints provide comprehensive access to VLM audit logs for compliance,
security monitoring, and operational analytics. Designed for SOC2, GDPR,
and other regulatory compliance requirements.

Features:
- Advanced filtering and search capabilities
- Compliance reporting (CSV, JSON export)
- Anomaly detection and security analysis
- User activity tracking
- Provider usage auditing
- Data retention management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import csv
import io
import json
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text

from app.api.deps import get_db, get_current_superuser
from app.models.user import User
from app.models.organization import Organization
from app.models.vlm_audit_log import (
    VLMProviderAuditLog,
    AuditEventType,
    AuditEventStatus,
    ErrorCategory
)
from app.models.platform_vlm_provider import PlatformVLMProvider
from app.services.vlm_audit_service import VLMAuditService
from app.schemas.platform_vlm import (
    AuditLogFilter,
    AuditLogResponse,
    AuditLogListResponse
)

router = APIRouter()


@router.get("")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    user_ids: Optional[List[UUID]] = Query(None, description="Filter by user IDs"),
    organization_ids: Optional[List[UUID]] = Query(None, description="Filter by organization IDs"),
    event_types: Optional[List[AuditEventType]] = Query(None, description="Filter by event types"),
    event_status: Optional[AuditEventStatus] = Query(None, description="Filter by event status"),
    error_categories: Optional[List[ErrorCategory]] = Query(None, description="Filter by error categories"),
    provider_ids: Optional[List[UUID]] = Query(None, description="Filter by provider IDs"),
    session_ids: Optional[List[str]] = Query(None, description="Filter by session IDs"),
    date_from: Optional[datetime] = Query(None, description="Start date for filtering"),
    date_to: Optional[datetime] = Query(None, description="End date for filtering"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    search_text: Optional[str] = Query(None, description="Search in error messages and metadata"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    order_by: str = Query("created_at", description="Order by field"),
    order_dir: str = Query("desc", description="Order direction (asc, desc)"),
) -> Dict[str, Any]:
    """
    Retrieve audit logs with comprehensive filtering capabilities.

    Provides access to detailed audit trail for compliance and security monitoring.
    """
    audit_service = VLMAuditService(db)

    try:
        # Build query with filters
        query = select(VLMProviderAuditLog)

        if user_ids:
            query = query.where(VLMProviderAuditLog.user_id.in_(user_ids))
        if organization_ids:
            query = query.where(VLMProviderAuditLog.organization_id.in_(organization_ids))
        if event_types:
            query = query.where(VLMProviderAuditLog.event_type.in_(event_types))
        if event_status:
            query = query.where(VLMProviderAuditLog.event_status == event_status)
        if error_categories:
            query = query.where(VLMProviderAuditLog.error_type.in_(error_categories))
        if provider_ids:
            query = query.where(VLMProviderAuditLog.platform_provider_id.in_(provider_ids))
        if session_ids:
            query = query.where(VLMProviderAuditLog.session_id.in_(session_ids))
        if date_from:
            query = query.where(VLMProviderAuditLog.created_at >= date_from)
        if date_to:
            query = query.where(VLMProviderAuditLog.created_at <= date_to)
        if ip_address:
            query = query.where(VLMProviderAuditLog.request_ip == ip_address)

        # Text search in error messages and metadata
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.where(
                VLMProviderAuditLog.error_message.ilike(search_pattern) |
                func.cast(VLMProviderAuditLog.audit_metadata, text('text')).ilike(search_pattern)
            )

        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply ordering
        order_column = getattr(VLMProviderAuditLog, order_by, VLMProviderAuditLog.created_at)
        if order_dir == "desc":
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(order_column)

        # Apply pagination
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        logs = result.scalars().all()

        # Log admin access to audit logs
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="get_audit_logs",
            resource_type="audit_logs",
            filters={
                "user_ids": [str(id) for id in user_ids] if user_ids else None,
                "organization_ids": [str(id) for id in organization_ids] if organization_ids else None,
                "event_types": [et.value for et in event_types] if event_types else None,
                "event_status": event_status.value if event_status else None,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "search_text": search_text,
                "limit": limit,
            }
        )

        # Build response items
        # Note: Response keys are kept stable for frontend compatibility,
        # but we read from the correct model attribute names.
        items = []
        for log in logs:
            items.append({
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "organization_id": str(log.organization_id) if log.organization_id else None,
                "event_type": log.event_type.value if log.event_type else None,
                "event_status": log.event_status.value if log.event_status else None,
                "session_id": log.session_id,
                "provider_type": log.provider_type,
                "provider_id": str(log.platform_provider_id) if log.platform_provider_id else None,
                "platform_provider_id": str(log.platform_provider_id) if log.platform_provider_id else None,
                "model_name": log.model_name,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost": float(log.cost) if log.cost else None,
                "processing_time_ms": log.latency_ms,
                "ip_address": str(log.request_ip) if log.request_ip else None,
                "user_agent": log.user_agent,
                "error_category": log.error_type.value if log.error_type else None,
                "error_message": log.error_message,
                "request_metadata": log.audit_metadata,
                "response_metadata": None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
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
            action="get_audit_logs",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit logs: {str(e)}"
        )


@router.get("/analytics/security")
async def get_security_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    days: int = Query(7, ge=1, le=90, description="Number of days for security analysis"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
) -> Dict[str, Any]:
    """
    Get security analytics from audit logs.

    Identifies suspicious patterns, failed authentications, anomalies,
    and potential security issues.
    """
    audit_service = VLMAuditService(db)

    try:
        date_from = datetime.utcnow() - timedelta(days=days)

        # Build base query
        query = select(VLMProviderAuditLog).where(
            VLMProviderAuditLog.created_at >= date_from
        )
        if organization_id:
            query = query.where(VLMProviderAuditLog.organization_id == organization_id)

        result = await db.execute(query)
        logs = result.scalars().all()

        analytics = {
            "analysis_period_days": days,
            "total_events": len(logs),
            "security_summary": {},
            "anomalies": [],
            "failed_operations": {},
            "unusual_patterns": {},
            "ip_analysis": {},
            "user_activity": {},
            "error_patterns": {},
        }

        # Basic security metrics
        failed_events = [log for log in logs if log.event_status == AuditEventStatus.FAILURE]
        error_events = [log for log in logs if log.event_status == AuditEventStatus.ERROR]
        successful_events = [log for log in logs if log.event_status == AuditEventStatus.SUCCESS]

        analytics["security_summary"] = {
            "total_events": len(logs),
            "failed_events": len(failed_events),
            "error_events": len(error_events),
            "successful_events": len(successful_events),
            "failure_rate": (len(failed_events) / len(logs) * 100) if logs else 0,
            "error_rate": (len(error_events) / len(logs) * 100) if logs else 0,
        }

        # Analyze IP addresses
        ip_stats = {}
        for log in logs:
            if log.request_ip:
                if log.request_ip not in ip_stats:
                    ip_stats[log.request_ip] = {
                        "total_requests": 0,
                        "failed_requests": 0,
                        "error_requests": 0,
                        "users": set(),
                        "event_types": set(),
                    }

                ip_stats[log.request_ip]["total_requests"] += 1
                if log.event_status == AuditEventStatus.FAILURE:
                    ip_stats[log.request_ip]["failed_requests"] += 1
                elif log.event_status == AuditEventStatus.ERROR:
                    ip_stats[log.request_ip]["error_requests"] += 1

                if log.user_id:
                    ip_stats[log.request_ip]["users"].add(log.user_id)
                ip_stats[log.request_ip]["event_types"].add(log.event_type.value)

        # Convert sets to counts and find suspicious IPs
        suspicious_ips = []
        for ip, stats in ip_stats.items():
            stats["unique_users"] = len(stats["users"])
            stats["unique_event_types"] = len(stats["event_types"])
            stats["failure_rate"] = (stats["failed_requests"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0

            # Flag suspicious patterns
            if stats["failure_rate"] > 50 and stats["total_requests"] > 10:
                suspicious_ips.append({
                    "ip_address": ip,
                    "reason": "High failure rate",
                    "failure_rate": stats["failure_rate"],
                    "total_requests": stats["total_requests"]
                })
            elif stats["unique_users"] > 10:  # Same IP used by many users
                suspicious_ips.append({
                    "ip_address": ip,
                    "reason": "Multiple users from same IP",
                    "unique_users": stats["unique_users"],
                    "total_requests": stats["total_requests"]
                })

            del stats["users"]  # Remove sets from response
            del stats["event_types"]

        analytics["ip_analysis"] = {
            "unique_ips": len(ip_stats),
            "suspicious_ips": suspicious_ips,
            "top_ips_by_requests": sorted(
                [{"ip": ip, **stats} for ip, stats in ip_stats.items()],
                key=lambda x: x["total_requests"],
                reverse=True
            )[:10]
        }

        # Analyze user activity patterns
        user_stats = {}
        for log in logs:
            if log.user_id:
                user_id = str(log.user_id)
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        "total_requests": 0,
                        "failed_requests": 0,
                        "unique_ips": set(),
                        "event_types": set(),
                        "first_activity": log.created_at,
                        "last_activity": log.created_at,
                    }

                user_stats[user_id]["total_requests"] += 1
                if log.event_status in [AuditEventStatus.FAILURE, AuditEventStatus.ERROR]:
                    user_stats[user_id]["failed_requests"] += 1

                if log.request_ip:
                    user_stats[user_id]["unique_ips"].add(log.request_ip)
                user_stats[user_id]["event_types"].add(log.event_type.value)

                # Track activity timespan
                if log.created_at < user_stats[user_id]["first_activity"]:
                    user_stats[user_id]["first_activity"] = log.created_at
                if log.created_at > user_stats[user_id]["last_activity"]:
                    user_stats[user_id]["last_activity"] = log.created_at

        # Find suspicious user patterns
        suspicious_users = []
        for user_id, stats in user_stats.items():
            stats["unique_ip_count"] = len(stats["unique_ips"])
            stats["unique_event_types"] = len(stats["event_types"])
            stats["failure_rate"] = (stats["failed_requests"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0

            # Flag suspicious patterns
            if stats["unique_ip_count"] > 5:  # User from many different IPs
                suspicious_users.append({
                    "user_id": user_id,
                    "reason": "Multiple IP addresses",
                    "unique_ips": stats["unique_ip_count"],
                    "total_requests": stats["total_requests"]
                })
            elif stats["failure_rate"] > 30 and stats["total_requests"] > 5:
                suspicious_users.append({
                    "user_id": user_id,
                    "reason": "High failure rate",
                    "failure_rate": stats["failure_rate"],
                    "total_requests": stats["total_requests"]
                })

            del stats["unique_ips"]  # Remove sets
            del stats["event_types"]
            stats["first_activity"] = stats["first_activity"].isoformat()
            stats["last_activity"] = stats["last_activity"].isoformat()

        analytics["user_activity"] = {
            "unique_users": len(user_stats),
            "suspicious_users": suspicious_users,
            "most_active_users": sorted(
                [{"user_id": uid, **stats} for uid, stats in user_stats.items()],
                key=lambda x: x["total_requests"],
                reverse=True
            )[:10]
        }

        # Analyze error patterns
        error_patterns = {}
        for log in failed_events + error_events:
            if log.error_message:
                # Group similar errors
                error_key = log.error_message[:100]  # First 100 chars
                if error_key not in error_patterns:
                    error_patterns[error_key] = {
                        "count": 0,
                        "first_seen": log.created_at,
                        "last_seen": log.created_at,
                        "affected_users": set(),
                        "affected_ips": set(),
                        "error_category": log.error_type.value if log.error_type else "unknown",
                    }

                error_patterns[error_key]["count"] += 1
                if log.user_id:
                    error_patterns[error_key]["affected_users"].add(log.user_id)
                if log.request_ip:
                    error_patterns[error_key]["affected_ips"].add(log.request_ip)

                if log.created_at < error_patterns[error_key]["first_seen"]:
                    error_patterns[error_key]["first_seen"] = log.created_at
                if log.created_at > error_patterns[error_key]["last_seen"]:
                    error_patterns[error_key]["last_seen"] = log.created_at

        # Convert to serializable format
        error_list = []
        for error_msg, stats in error_patterns.items():
            error_list.append({
                "error_message": error_msg,
                "count": stats["count"],
                "first_seen": stats["first_seen"].isoformat(),
                "last_seen": stats["last_seen"].isoformat(),
                "affected_users": len(stats["affected_users"]),
                "affected_ips": len(stats["affected_ips"]),
                "error_category": stats["error_category"],
            })

        analytics["error_patterns"] = {
            "unique_error_types": len(error_patterns),
            "most_common_errors": sorted(error_list, key=lambda x: x["count"], reverse=True)[:10]
        }

        # Identify anomalies
        anomalies = []

        # Time-based anomalies (unusual activity hours)
        hourly_activity = {}
        for log in logs:
            hour = log.created_at.hour
            hourly_activity[hour] = hourly_activity.get(hour, 0) + 1

        if hourly_activity:
            avg_hourly = sum(hourly_activity.values()) / len(hourly_activity)
            for hour, count in hourly_activity.items():
                if count > avg_hourly * 3:  # More than 3x average
                    anomalies.append({
                        "type": "unusual_activity_hour",
                        "description": f"Unusual activity spike at hour {hour}:00",
                        "value": count,
                        "normal_range": f"~{avg_hourly:.1f}",
                        "severity": "medium"
                    })

        # Rate-based anomalies
        if len(logs) > 100:  # Only analyze if sufficient data
            # Check for request bursts (many requests in short time)
            time_windows = {}
            for log in logs:
                window = log.created_at.replace(minute=0, second=0, microsecond=0)  # Hour window
                time_windows[window] = time_windows.get(window, 0) + 1

            if time_windows:
                avg_requests_per_hour = sum(time_windows.values()) / len(time_windows)
                for window, count in time_windows.items():
                    if count > avg_requests_per_hour * 4:  # 4x normal rate
                        anomalies.append({
                            "type": "request_burst",
                            "description": f"Request burst detected at {window.strftime('%Y-%m-%d %H:%M')}",
                            "value": count,
                            "normal_range": f"~{avg_requests_per_hour:.1f}",
                            "severity": "high"
                        })

        analytics["anomalies"] = anomalies

        # Log security analytics access
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="get_security_analytics",
            resource_type="audit_logs_security",
            filters={
                "days": days,
                "organization_id": str(organization_id) if organization_id else None,
            }
        )

        analytics["generated_at"] = datetime.utcnow().isoformat()
        return analytics

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="get_security_analytics",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate security analytics: {str(e)}"
        )


@router.post("/compliance-export")
async def compliance_export_with_url(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    export_request: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Export compliance report and return a download URL.

    This endpoint returns a data URL for the exported file, suitable for
    browser-based downloads triggered by JavaScript.
    """
    import base64
    from datetime import timezone
    from pydantic import BaseModel

    audit_service = VLMAuditService(db)

    if export_request is None:
        export_request = {}

    format_type = export_request.get("format", "json")
    start_date_str = export_request.get("start_date")
    end_date_str = export_request.get("end_date")
    organization_id_str = export_request.get("organization_id")

    # Parse dates
    if end_date_str:
        try:
            if len(end_date_str) == 10:
                date_to = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            else:
                date_to = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            date_to = datetime.now(timezone.utc)
    else:
        date_to = datetime.now(timezone.utc)

    if start_date_str:
        try:
            if len(start_date_str) == 10:
                date_from = datetime.strptime(start_date_str, "%Y-%m-%d")
            else:
                date_from = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        except ValueError:
            date_from = date_to - timedelta(days=30)
    else:
        date_from = date_to - timedelta(days=30)

    organization_id = UUID(organization_id_str) if organization_id_str else None

    try:
        # Build query for audit logs
        query = select(VLMProviderAuditLog).where(
            and_(
                VLMProviderAuditLog.created_at >= date_from,
                VLMProviderAuditLog.created_at <= date_to
            )
        )

        if organization_id:
            query = query.where(VLMProviderAuditLog.organization_id == organization_id)

        result = await db.execute(query.order_by(desc(VLMProviderAuditLog.created_at)))
        logs = result.scalars().all()

        # Build export data
        if format_type == "json":
            export_data = {
                "report_type": "compliance_audit",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                },
                "total_records": len(logs),
                "audit_logs": []
            }

            for log in logs:
                export_data["audit_logs"].append({
                    "id": str(log.id),
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "user_id": str(log.user_id) if log.user_id else None,
                    "organization_id": str(log.organization_id) if log.organization_id else None,
                    "event_type": log.event_type.value if log.event_type else None,
                    "event_status": log.event_status.value if log.event_status else None,
                    "ip_address": str(log.request_ip) if log.request_ip else None,
                    "provider_type": log.provider_type,
                    "model_name": log.model_name,
                    "input_tokens": log.input_tokens,
                    "output_tokens": log.output_tokens,
                    "cost": float(log.cost) if log.cost else None,
                    "processing_time_ms": log.latency_ms,
                    "error_category": log.error_type.value if log.error_type else None,
                    "error_message": log.error_message,
                })

            content = json.dumps(export_data, indent=2)
            content_type = "application/json"
            extension = "json"
        else:
            # CSV format
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Timestamp', 'User ID', 'Organization ID', 'Event Type', 'Event Status',
                'IP Address', 'Provider Type', 'Model Name', 'Input Tokens', 'Output Tokens',
                'Cost', 'Processing Time (ms)', 'Error Category', 'Error Message'
            ])

            for log in logs:
                writer.writerow([
                    log.created_at.isoformat() if log.created_at else "",
                    str(log.user_id) if log.user_id else "",
                    str(log.organization_id) if log.organization_id else "",
                    log.event_type.value if log.event_type else "",
                    log.event_status.value if log.event_status else "",
                    log.request_ip or "",
                    log.provider_type or "",
                    log.model_name or "",
                    log.input_tokens or "",
                    log.output_tokens or "",
                    float(log.cost) if log.cost else "",
                    log.latency_ms or "",
                    log.error_type.value if log.error_type else "",
                    log.error_message or "",
                ])

            content = output.getvalue()
            content_type = "text/csv"
            extension = "csv"

        # Create a data URL for download
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        download_url = f"data:{content_type};base64,{encoded_content}"

        # Log export
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="export_compliance_report",
            resource_type="audit_logs",
            resource_data={
                "format": format_type,
                "record_count": len(logs),
                "date_range": f"{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}",
            }
        )

        return {
            "download_url": download_url,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "filename": f"audit-logs-{date_from.strftime('%Y%m%d')}-{date_to.strftime('%Y%m%d')}.{extension}",
            "record_count": len(logs),
        }

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="export_compliance_report",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export compliance report: {str(e)}"
        )


@router.get("/export/compliance")
async def export_compliance_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    format: str = Query("json", description="Export format: json, csv"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    compliance_type: str = Query("general", description="Compliance type: general, soc2, gdpr, hipaa"),
) -> StreamingResponse:
    """
    Export compliance report in various formats.

    Generates compliance-ready audit reports suitable for regulatory requirements.
    """
    audit_service = VLMAuditService(db)

    try:
        # Set default date range if not specified
        if not date_to:
            date_to = datetime.utcnow()
        if not date_from:
            date_from = date_to - timedelta(days=90)  # Default 90 days for compliance

        # Generate compliance report
        report_data = audit_service.generate_compliance_report(
            date_from=date_from,
            date_to=date_to,
            organization_id=organization_id,
            compliance_type=compliance_type
        )

        # Log compliance export
        audit_service.log_admin_action(
            admin_user_id=current_user.id,
            action="export_compliance_report",
            resource_type="audit_compliance",
            resource_data={
                "format": format,
                "compliance_type": compliance_type,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "organization_id": str(organization_id) if organization_id else None,
            }
        )

        # Generate filename
        filename_date = date_from.strftime("%Y%m%d") + "_" + date_to.strftime("%Y%m%d")
        org_suffix = f"_org_{organization_id}" if organization_id else "_all_orgs"
        filename = f"compliance_report_{compliance_type}_{filename_date}{org_suffix}"

        if format.lower() == "csv":
            # Generate CSV format
            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers based on compliance type
            if compliance_type == "soc2":
                headers = [
                    'Timestamp', 'User ID', 'Organization ID', 'Event Type', 'Event Status',
                    'IP Address', 'Session ID', 'Provider Type', 'Input Tokens', 'Output Tokens',
                    'Cost', 'Processing Time (ms)', 'Error Type', 'Error Message'
                ]
            elif compliance_type == "gdpr":
                headers = [
                    'Timestamp', 'Data Subject (User ID)', 'Organization', 'Processing Activity',
                    'Legal Basis', 'Data Categories', 'Recipients', 'Retention Period',
                    'Cross Border Transfer', 'IP Address', 'Session ID'
                ]
            else:  # general
                headers = [
                    'Timestamp', 'User ID', 'Organization ID', 'Event Type', 'Event Status',
                    'IP Address', 'Platform Provider ID', 'Model Name', 'Cost', 'Error Message'
                ]

            writer.writerow(headers)

            # Write data rows
            for log_entry in report_data.get("audit_logs", []):
                if compliance_type == "soc2":
                    row = [
                        log_entry.get("created_at", ""),
                        log_entry.get("user_id", ""),
                        log_entry.get("organization_id", ""),
                        log_entry.get("event_type", ""),
                        log_entry.get("event_status", ""),
                        log_entry.get("request_ip", ""),
                        log_entry.get("session_id", ""),
                        log_entry.get("provider_type", ""),
                        log_entry.get("input_tokens", ""),
                        log_entry.get("output_tokens", ""),
                        log_entry.get("cost", ""),
                        log_entry.get("latency_ms", ""),
                        log_entry.get("error_type", ""),
                        log_entry.get("error_message", ""),
                    ]
                elif compliance_type == "gdpr":
                    row = [
                        log_entry.get("created_at", ""),
                        log_entry.get("user_id", ""),
                        log_entry.get("organization_id", ""),
                        "VLM Processing",  # Processing activity
                        "Legitimate Interest",  # Legal basis (would be configurable)
                        "Usage Data, Technical Data",  # Data categories
                        log_entry.get("provider_type", ""),  # Recipients
                        "As per retention policy",  # Retention period
                        "Yes" if log_entry.get("provider_type") != "local" else "No",  # Cross border
                        log_entry.get("request_ip", ""),
                        log_entry.get("session_id", ""),
                    ]
                else:  # general
                    row = [
                        log_entry.get("created_at", ""),
                        log_entry.get("user_id", ""),
                        log_entry.get("organization_id", ""),
                        log_entry.get("event_type", ""),
                        log_entry.get("event_status", ""),
                        log_entry.get("request_ip", ""),
                        log_entry.get("platform_provider_id", ""),
                        log_entry.get("model_name", ""),
                        log_entry.get("cost", ""),
                        log_entry.get("error_message", ""),
                    ]
                writer.writerow(row)

            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}.csv"}
            )

        else:  # JSON format
            json_output = json.dumps(report_data, indent=2, default=str)
            return StreamingResponse(
                io.BytesIO(json_output.encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}.json"}
            )

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="export_compliance_report",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export compliance report: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_old_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    retention_days: int = Query(90, ge=30, le=365, description="Retention period in days"),
    dry_run: bool = Query(True, description="Perform dry run without actual deletion"),
    organization_id: Optional[UUID] = Query(None, description="Cleanup specific organization only"),
) -> Dict[str, Any]:
    """
    Cleanup old audit logs based on retention policy.

    Allows super admins to manage audit log storage by removing old records
    while maintaining compliance requirements.
    """
    audit_service = VLMAuditService(db)

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Build cleanup query
        query = select(VLMProviderAuditLog).where(
            VLMProviderAuditLog.created_at < cutoff_date
        )
        if organization_id:
            query = query.where(VLMProviderAuditLog.organization_id == organization_id)

        result = await db.execute(query)
        logs_to_cleanup = result.scalars().all()

        cleanup_stats = {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "total_logs_found": len(logs_to_cleanup),
            "dry_run": dry_run,
            "organization_id": str(organization_id) if organization_id else None,
            "breakdown": {},
            "estimated_space_freed": 0,
        }

        # Analyze logs by event type and status
        breakdown = {}
        total_size_estimate = 0

        for log in logs_to_cleanup:
            event_type = log.event_type.value
            if event_type not in breakdown:
                breakdown[event_type] = {
                    "count": 0,
                    "success": 0,
                    "failed": 0,
                    "error": 0,
                }

            breakdown[event_type]["count"] += 1
            status_key = log.event_status.value.lower()
            if status_key in breakdown[event_type]:
                breakdown[event_type][status_key] += 1
            elif status_key == "failure":
                breakdown[event_type]["failed"] += 1

            # Estimate size (rough calculation)
            size_estimate = len(str(log.error_message) or "") + len(str(log.audit_metadata) or "")
            total_size_estimate += size_estimate

        cleanup_stats["breakdown"] = breakdown
        cleanup_stats["estimated_space_freed"] = total_size_estimate  # bytes

        if not dry_run:
            # Perform actual cleanup
            deleted_count = 0
            for log in logs_to_cleanup:
                await db.delete(log)
                deleted_count += 1

            await db.commit()
            cleanup_stats["actually_deleted"] = deleted_count
            cleanup_stats["cleanup_completed_at"] = datetime.utcnow().isoformat()

            # Log cleanup action
            audit_service.log_admin_action(
                admin_user_id=current_user.id,
                action="cleanup_audit_logs",
                resource_type="audit_logs",
                resource_data={
                    "retention_days": retention_days,
                    "deleted_count": deleted_count,
                    "organization_id": str(organization_id) if organization_id else None,
                    "cutoff_date": cutoff_date.isoformat(),
                }
            )
        else:
            # Log dry run
            audit_service.log_admin_access(
                admin_user_id=current_user.id,
                action="audit_log_cleanup_dry_run",
                resource_type="audit_logs",
                filters={
                    "retention_days": retention_days,
                    "logs_to_cleanup": len(logs_to_cleanup),
                    "organization_id": str(organization_id) if organization_id else None,
                }
            )

        return cleanup_stats

    except Exception as e:
        if not dry_run:
            await db.rollback()

        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="cleanup_audit_logs",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup audit logs: {str(e)}"
        )


@router.get("/analytics/usage-patterns")
async def get_usage_pattern_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
    days: int = Query(30, ge=7, le=90, description="Analysis period in days"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
) -> Dict[str, Any]:
    """
    Analyze VLM usage patterns from audit logs.

    Provides insights into usage trends, peak hours, popular models,
    and operational patterns for capacity planning.
    """
    audit_service = VLMAuditService(db)

    try:
        date_from = datetime.utcnow() - timedelta(days=days)

        # Get usage analytics
        analytics_data = audit_service.analyze_usage_patterns(
            date_from=date_from,
            organization_id=organization_id,
            include_trends=True,
            include_predictions=True
        )

        # Log analytics access
        audit_service.log_admin_access(
            admin_user_id=current_user.id,
            action="get_usage_pattern_analytics",
            resource_type="audit_analytics",
            filters={
                "days": days,
                "organization_id": str(organization_id) if organization_id else None,
            }
        )

        return {
            "analysis_period_days": days,
            "organization_id": str(organization_id) if organization_id else None,
            "generated_at": datetime.utcnow().isoformat(),
            **analytics_data
        }

    except Exception as e:
        audit_service.log_admin_error(
            admin_user_id=current_user.id,
            action="get_usage_pattern_analytics",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate usage pattern analytics: {str(e)}"
        )