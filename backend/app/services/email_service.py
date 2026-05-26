"""
Email Service Module.

This module handles all email sending operations for the platform,
including business registration notifications, invitation emails,
and deletion request notifications.

Example Usage:
    from app.services.email_service import email_service

    # Send registration notification
    await email_service.send_registration_notification(
        organization=org,
        owner=user,
        super_admins=admin_list
    )

    # Send invitation
    await email_service.send_invitation(
        invitation=invitation,
        organization=org,
        invited_by=admin_user
    )
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.deletion_request import DeletionRequest
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails using SMTP.

    This service handles all email notifications for the platform,
    including registration approvals, invitations, and admin notifications.
    """

    def __init__(self):
        """Initialize the email service with Jinja2 template engine."""
        # Set up Jinja2 template environment
        template_dir = Path(__file__).parent.parent / "templates" / "email"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    async def _send_email(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Send an email using SMTP.

        Args:
            to_email: Recipient email address.
            to_name: Recipient name.
            subject: Email subject.
            html_body: HTML email body.
            text_body: Plain text email body (optional).
            reply_to: Reply-To email address (optional). When set, replies
                to this email will be directed to this address instead of
                the sender (From) address.

        Returns:
            True if email was sent successfully.

        Raises:
            Exception: If email sending fails.
        """
        if not settings.smtp_enabled:
            logger.info(
                f"Email sending disabled. Would send to {to_email}: {subject}"
            )
            logger.debug(f"Email body:\n{html_body}")
            return False

        try:
            logger.info(f"Sending email to {to_email}: {subject}")

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email

            # Set Reply-To header so replies go to the desired address
            if reply_to:
                msg["Reply-To"] = reply_to

            # Attach text and HTML parts
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Connect to SMTP server
            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

            # Authenticate if credentials provided
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)

            # Send email
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            raise

    async def send_registration_received(
        self,
        organization: Organization,
        owner: User,
    ) -> None:
        """
        Notify applicant that registration was received and is pending approval.

        Works for both personal and business registrations.

        Args:
            organization: The newly registered organization.
            owner: The user who submitted the registration.
        """
        template = self.jinja_env.get_template("registration_received.html")

        html_body = template.render(
            owner_name=owner.full_name or owner.email,
            organization_name=organization.name,
            business_name=organization.business_name,  # None for personal orgs
            support_email=settings.support_email,
        )

        await self._send_email(
            to_email=owner.email,
            to_name=owner.full_name,
            subject=f"Registration Received: {organization.name}",
            html_body=html_body,
        )

    async def send_registration_notification(
        self,
        organization: Organization,
        owner: User,
        super_admins: List[User],
    ) -> None:
        """
        Notify super admins of a new user registration (personal or business).

        Args:
            organization: The newly registered organization.
            owner: The user who submitted the registration.
            super_admins: List of super admin users to notify.
        """
        template = self.jinja_env.get_template("registration_notification.html")

        # Determine appropriate subject based on organization type
        org_type_label = "Business" if organization.organization_type.value == "business" else "User"
        subject = f"New {org_type_label} Registration: {organization.name}"

        for admin in super_admins:
            html_body = template.render(
                admin_name=admin.full_name or admin.email,
                organization_name=organization.name,
                business_name=organization.business_name,
                business_email=organization.business_email,
                business_phone=organization.business_phone,
                owner_name=owner.full_name or owner.email,
                owner_email=owner.email,
                registration_id=str(organization.id),
                admin_url=f"{settings.frontend_url}/admin/users",
            )

            try:
                await self._send_email(
                    to_email=admin.email,
                    to_name=admin.full_name,
                    subject=subject,
                    html_body=html_body,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send registration notification to {admin.email}: {e}"
                )

    async def send_registration_alert_to_support(
        self,
        organization: Organization,
        owner: User,
        support_email: str,
    ) -> None:
        """
        Send a registration alert to the support email address.

        This supplements the superuser notifications by also alerting the
        shared support inbox (e.g. info@leafxtract.com) so that non-admin
        staff are aware of new sign-ups.

        Args:
            organization: The newly registered organization.
            owner: The user who submitted the registration.
            support_email: The support email address to notify.
        """
        template = self.jinja_env.get_template("registration_notification.html")

        org_type_label = (
            "Business"
            if organization.organization_type.value == "business"
            else "User"
        )
        subject = f"New {org_type_label} Registration: {organization.name}"

        html_body = template.render(
            admin_name="Support Team",
            organization_name=organization.name,
            business_name=organization.business_name,
            business_email=organization.business_email,
            business_phone=organization.business_phone,
            owner_name=owner.full_name or owner.email,
            owner_email=owner.email,
            registration_id=str(organization.id),
            admin_url=f"{settings.frontend_url}/admin/users",
        )

        await self._send_email(
            to_email=support_email,
            to_name="Support Team",
            subject=subject,
            html_body=html_body,
        )

    async def send_registration_approved(
        self,
        organization: Organization,
        owner: User,
        approved_by: User,
    ) -> None:
        """
        Notify business owner that their registration was approved.

        Args:
            organization: The approved organization
            owner: The business owner
            approved_by: The super admin who approved the registration
        """
        template = self.jinja_env.get_template("registration_approved.html")

        html_body = template.render(
            owner_name=owner.full_name,
            organization_name=organization.name,
            approved_by_name=approved_by.full_name or approved_by.email,
            login_url=f"{settings.frontend_url}/login",
            dashboard_url=f"{settings.frontend_url}/dashboard",
        )

        await self._send_email(
            to_email=owner.email,
            to_name=owner.full_name,
            subject=f"Registration Approved: {organization.name}",
            html_body=html_body,
        )

    async def send_registration_rejected(
        self,
        organization: Organization,
        owner: User,
        rejection_reason: str,
    ) -> None:
        """
        Notify business owner that their registration was rejected.

        Args:
            organization: The rejected organization
            owner: The business owner
            rejection_reason: Reason for rejection
        """
        template = self.jinja_env.get_template("registration_rejected.html")

        html_body = template.render(
            owner_name=owner.full_name,
            organization_name=organization.name,
            rejection_reason=rejection_reason,
            support_email=settings.support_email,
        )

        await self._send_email(
            to_email=owner.email,
            to_name=owner.full_name,
            subject=f"Registration Update: {organization.name}",
            html_body=html_body,
        )

    async def send_invitation(
        self,
        invitation: OrganizationInvitation,
        organization: Organization,
        invited_by: User,
    ) -> bool:
        """
        Send organization invitation email.

        Args:
            invitation: The invitation record.
            organization: The organization the user is invited to.
            invited_by: The user who sent the invitation.

        Returns:
            True if email was sent successfully, False if sending is
            disabled or the send operation failed.
        """
        from datetime import datetime as dt

        template = self.jinja_env.get_template("invitation.html")

        invitation_url = f"{settings.frontend_url}/invitations/{invitation.token}"

        html_body = template.render(
            organization_name=organization.name,
            invited_by_name=invited_by.full_name or invited_by.email,
            role=invitation.role.value,
            invitation_url=invitation_url,
            expires_at=invitation.expires_at.strftime("%B %d, %Y"),
            current_year=dt.now().year,
        )

        result = await self._send_email(
            to_email=invitation.email,
            to_name=None,
            subject=f"You've been invited to join {organization.name}",
            html_body=html_body,
        )
        return result

    async def send_deletion_request_notification(
        self,
        deletion_request: DeletionRequest,
        organization: Organization,
        requested_by: User,
        super_admins: List[User],
    ) -> None:
        """
        Notify super admins of organization deletion request.

        Args:
            deletion_request: The deletion request
            organization: The organization to be deleted
            requested_by: The user who requested deletion
            super_admins: List of super admin users to notify
        """
        template = self.jinja_env.get_template("deletion_request_notification.html")

        for admin in super_admins:
            html_body = template.render(
                admin_name=admin.full_name or admin.email,
                organization_name=organization.name,
                requested_by_name=requested_by.full_name or requested_by.email,
                requested_by_email=requested_by.email,
                reason=deletion_request.reason or "No reason provided",
                request_id=str(deletion_request.id),
                admin_url=f"{settings.frontend_url}/admin/deletion-requests",
            )

            try:
                await self._send_email(
                    to_email=admin.email,
                    to_name=admin.full_name,
                    subject=f"Organization Deletion Request: {organization.name}",
                    html_body=html_body,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send deletion request notification to {admin.email}: {e}"
                )

    async def send_deletion_approved(
        self,
        organization_name: str,
        owner_email: str,
        owner_name: Optional[str],
    ) -> None:
        """
        Notify organization owner that deletion was approved.

        Args:
            organization_name: Name of the deleted organization
            owner_email: Email of the organization owner
            owner_name: Name of the organization owner
        """
        template = self.jinja_env.get_template("deletion_approved.html")

        html_body = template.render(
            owner_name=owner_name or owner_email,
            organization_name=organization_name,
            support_email=settings.support_email,
        )

        await self._send_email(
            to_email=owner_email,
            to_name=owner_name,
            subject=f"Organization Deleted: {organization_name}",
            html_body=html_body,
        )

    async def send_password_reset(
        self,
        user: User,
        reset_token: str,
    ) -> None:
        """
        Send password reset email to user.

        Args:
            user: User requesting password reset
            reset_token: Reset token for password reset link

        Raises:
            Exception: If email sending fails
        """
        from datetime import datetime

        reset_url = f"{settings.frontend_url}/reset-password/{reset_token}"

        template = self.jinja_env.get_template("password_reset.html")
        html_body = template.render(
            user_name=user.full_name or "User",
            reset_url=reset_url,
            current_year=datetime.now().year,
        )

        await self._send_email(
            to_email=user.email,
            to_name=user.full_name or user.email,
            subject="Reset Your Password - LEAFXTRACT",
            html_body=html_body,
        )


# Global email service instance
email_service = EmailService()
