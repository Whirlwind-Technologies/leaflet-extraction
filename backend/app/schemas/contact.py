"""
Contact Form Pydantic Schemas.

This module defines request and response schemas for the public contact
form endpoint.

Example Usage:
    from app.schemas.contact import ContactRequest, ContactResponse

    request = ContactRequest(
        name="Jane Doe",
        email="jane@example.com",
        message="I'd like to learn more about the platform.",
    )
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ContactRequest(BaseModel):
    """
    Schema for incoming contact form submissions.

    Attributes:
        name: Sender's full name (required, max 100 chars).
        email: Sender's email address (required, valid email).
        message: Contact message body (required, max 2000 chars).
        website: Honeypot field -- must be empty for legitimate submissions.
        timestamp: Unix epoch seconds when the form was rendered on the
                   client side. Used for time-based spam detection.
        recaptcha_token: Optional reCAPTCHA v3 token for bot verification.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Sender's full name",
    )
    email: EmailStr = Field(
        ...,
        description="Sender's email address",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Contact message body",
    )
    website: Optional[str] = Field(
        default=None,
        description="Honeypot field (should be empty for real users)",
    )
    timestamp: Optional[float] = Field(
        default=None,
        description="Unix epoch seconds when the form was rendered",
    )
    recaptcha_token: Optional[str] = Field(
        default=None,
        description="reCAPTCHA v3 token for bot verification",
    )


class ContactResponse(BaseModel):
    """
    Schema for contact form submission response.

    Always returns a success-like structure so bots cannot distinguish
    a real acceptance from a silent rejection.

    Attributes:
        success: Indicates whether the submission was accepted.
        message: Human-readable acknowledgement message.
    """

    success: bool = Field(
        default=True,
        description="Always true in the response body",
    )
    message: str = Field(
        default="Thank you, we'll be in touch.",
        description="Acknowledgement message",
    )
