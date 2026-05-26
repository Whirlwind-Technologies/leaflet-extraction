"""
Admin Deletion Request Management Endpoints.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_superuser, get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.deletion_request import DeletionRequest, DeletionRequestStatus
from app.schemas.organization import (
    DeletionRequestResponse,
    DeletionRequestReview,
)
from app.utils.exceptions import NotFoundError, ValidationException

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=List[DeletionRequestResponse],
    summary="List deletion requests",
    description="Get all deletion requests (super admin only).",
)
async def list_deletion_requests(
    status_filter: Optional[str] = Query(
        default="pending",
        description="Filter by status (pending, approved, rejected, all)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> List[DeletionRequestResponse]:
    """List deletion requests for admin review."""
    query = select(DeletionRequest)

    if status_filter and status_filter.lower() != "all":
        status_enum = DeletionRequestStatus(status_filter.lower())
        query = query.where(DeletionRequest.status == status_enum)

    offset = (page - 1) * page_size
    query = query.order_by(DeletionRequest.created_at.desc())
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    responses = []
    for req in requests:
        # Get organization name if applicable
        org_name = None
        if req.organization_id:
            result = await db.execute(
                select(Organization).where(Organization.id == req.organization_id)
            )
            org = result.scalar_one_or_none()
            if org:
                org_name = org.name

        # Get user email if applicable
        user_email = None
        if req.user_id:
            result = await db.execute(
                select(User).where(User.id == req.user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user_email = user.email

        # Get requester
        requester_name = "Unknown"
        if req.requested_by_user_id:
            result = await db.execute(
                select(User).where(User.id == req.requested_by_user_id)
            )
            requester = result.scalar_one_or_none()
            if requester:
                requester_name = requester.full_name or requester.email

        # Get reviewer
        reviewer_name = None
        if req.reviewed_by_user_id:
            result = await db.execute(
                select(User).where(User.id == req.reviewed_by_user_id)
            )
            reviewer = result.scalar_one_or_none()
            if reviewer:
                reviewer_name = reviewer.full_name or reviewer.email

        responses.append(
            DeletionRequestResponse(
                id=req.id,
                request_type=req.request_type.value,
                organization_name=org_name,
                user_email=user_email,
                status=req.status.value,
                reason=req.reason,
                requested_by=requester_name,
                reviewed_by=reviewer_name,
                reviewed_at=req.reviewed_at,
                review_notes=req.review_notes,
                created_at=req.created_at,
                updated_at=req.updated_at,
            )
        )

    return responses


@router.post(
    "/{request_id}/approve",
    summary="Approve deletion request",
    description="Approve and execute a deletion request (super admin only).",
)
async def approve_deletion_request(
    request_id: UUID,
    review: DeletionRequestReview,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve and execute deletion request.

    WARNING: This will permanently delete the organization or user and all associated data.
    """
    result = await db.execute(
        select(DeletionRequest).where(DeletionRequest.id == request_id)
    )
    del_request = result.scalar_one_or_none()

    if not del_request:
        raise NotFoundError("Deletion request", str(request_id))

    if del_request.status != DeletionRequestStatus.PENDING:
        raise ValidationException("Can only approve pending requests")

    # Mark as approved
    del_request.status = DeletionRequestStatus.APPROVED
    del_request.reviewed_by_user_id = current_user.id
    del_request.reviewed_at = datetime.utcnow()
    del_request.review_notes = review.review_notes

    # Execute deletion
    if del_request.request_type.value == "organization":
        if del_request.organization_id:
            result = await db.execute(
                select(Organization).where(
                    Organization.id == del_request.organization_id
                )
            )
            org = result.scalar_one_or_none()
            if org:
                org_name = org.name
                await db.delete(org)
                logger.warning(
                    f"Admin {current_user.email} deleted organization {org_name} "
                    f"(ID: {del_request.organization_id})"
                )
    elif del_request.request_type.value == "user":
        if del_request.user_id:
            result = await db.execute(
                select(User).where(User.id == del_request.user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user_email = user.email
                await db.delete(user)
                logger.warning(
                    f"Admin {current_user.email} deleted user {user_email} "
                    f"(ID: {del_request.user_id})"
                )

    await db.commit()

    return {
        "message": "Deletion request approved and executed",
        "request_id": str(del_request.id),
        "request_type": del_request.request_type.value,
    }


@router.post(
    "/{request_id}/reject",
    summary="Reject deletion request",
    description="Reject a deletion request (super admin only).",
)
async def reject_deletion_request(
    request_id: UUID,
    review: DeletionRequestReview,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Reject a deletion request."""
    result = await db.execute(
        select(DeletionRequest).where(DeletionRequest.id == request_id)
    )
    del_request = result.scalar_one_or_none()

    if not del_request:
        raise NotFoundError("Deletion request", str(request_id))

    if del_request.status != DeletionRequestStatus.PENDING:
        raise ValidationException("Can only reject pending requests")

    del_request.status = DeletionRequestStatus.REJECTED
    del_request.reviewed_by_user_id = current_user.id
    del_request.reviewed_at = datetime.utcnow()
    del_request.review_notes = review.review_notes

    await db.commit()

    logger.info(
        f"Admin {current_user.email} rejected deletion request {request_id}"
    )

    return {
        "message": "Deletion request rejected",
        "request_id": str(del_request.id),
        "request_type": del_request.request_type.value,
        "review_notes": del_request.review_notes,
    }
