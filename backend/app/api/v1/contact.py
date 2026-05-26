"""
Contact Form API Endpoint.

This module provides a public (unauthenticated) endpoint for contact form
submissions.  It implements layered spam protection and dispatches email
sending to a background Celery task so the HTTP response is never blocked
by SMTP.

Spam protection layers (checked in order, fail-fast):
    1. Honeypot field -- silent reject if filled.
    2. Time-based validation -- silent reject if too fast (<3 s) or stale (>2 h).
    3. Redis-backed rate limiting -- 429 if per-email, per-IP, or global limits exceeded.
    4. reCAPTCHA v3 verification -- 400 if score < 0.5 (only when configured).
    5. Content validation -- silent reject for excessive URLs, script tags, or duplicates.

All "silent rejects" return 200 with the same success body so automated
bots cannot distinguish them from a genuine acceptance.

Example Usage:
    POST /api/v1/contact
    {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "message": "I'd like to learn more.",
        "website": "",
        "timestamp": 1708700000.0
    }
"""

import hashlib
import re
import time
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.config import settings
from app.schemas.contact import ContactRequest, ContactResponse
from app.utils.cache import get_redis_client

logger = structlog.get_logger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SUCCESS_RESPONSE = ContactResponse(
    success=True,
    message="Thank you, we'll be in touch.",
)

_RATE_LIMIT_TTL_SECONDS = 3600  # 1 hour

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
_SCRIPT_PATTERN = re.compile(r"<script", re.IGNORECASE)

_DEDUP_TTL_SECONDS = 86400  # 24 hours

# reCAPTCHA verification endpoint
_RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
_RECAPTCHA_MIN_SCORE = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request: Request) -> str:
    """Extract the client IP address, respecting X-Forwarded-For.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The best-guess client IP address as a string.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may contain a comma-separated list; first is the client
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _message_dedup_key(email: str, message: str) -> str:
    """Build a Redis key for duplicate message detection.

    Args:
        email: Sender email address.
        message: Raw message body.

    Returns:
        A Redis key string incorporating the SHA-256 hash of email + message.
    """
    digest = hashlib.sha256(f"{email}{message}".encode()).hexdigest()
    return f"contact:dedup:{digest}"


async def _check_rate_limits(email: str, client_ip: str) -> Optional[JSONResponse]:
    """Check per-email, per-IP, and global rate limits via Redis INCR.

    Returns a 429 JSONResponse if any limit is exceeded, or ``None`` if all
    checks pass.  If Redis is unavailable the check is skipped (fail-open).

    Args:
        email: Sender email address.
        client_ip: Client IP address.

    Returns:
        A JSONResponse with status 429 if rate limited, or None.
    """
    redis_client = get_redis_client()
    if redis_client is None:
        # Redis unavailable -- fail open
        logger.warning("Redis unavailable for contact rate limiting, allowing request")
        return None

    rate_checks = [
        (f"contact:email:{email}", settings.contact_rate_limit_per_email),
        (f"contact:ip:{client_ip}", settings.contact_rate_limit_per_ip),
        ("contact:global", settings.contact_rate_limit_global),
    ]

    try:
        for key, limit in rate_checks:
            current = await redis_client.incr(key)
            if current == 1:
                # First hit -- set TTL
                await redis_client.expire(key, _RATE_LIMIT_TTL_SECONDS)
            if current > limit:
                logger.info(
                    "Contact form rate limited",
                    key=key,
                    current=current,
                    limit=limit,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many submissions. Please try again later."
                    },
                )
    except RedisError as exc:
        logger.warning("Redis error during contact rate limit check", error=str(exc))
        # Fail open on transient Redis errors
        return None

    return None


async def _verify_recaptcha(token: str) -> bool:
    """Verify a reCAPTCHA v3 token against the Google API.

    Args:
        token: The reCAPTCHA response token from the client.

    Returns:
        True if the verification succeeds and the score meets the threshold.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                _RECAPTCHA_VERIFY_URL,
                data={
                    "secret": settings.recaptcha_secret_key,
                    "response": token,
                },
            )
            result = response.json()

        if not result.get("success", False):
            logger.info("reCAPTCHA verification failed", errors=result.get("error-codes"))
            return False

        score = result.get("score", 0.0)
        if score < _RECAPTCHA_MIN_SCORE:
            logger.info("reCAPTCHA score below threshold", score=score)
            return False

        return True

    except httpx.HTTPError as exc:
        logger.warning("reCAPTCHA HTTP request failed", error=str(exc))
        # Fail open -- if Google's API is unreachable, don't block the user
        return True
    except Exception as exc:
        logger.warning("reCAPTCHA verification error", error=str(exc))
        return True


async def _is_duplicate_message(email: str, message: str) -> bool:
    """Check if an identical message was submitted within the last 24 hours.

    Args:
        email: Sender email address.
        message: Raw message body.

    Returns:
        True if the exact same email+message combination was already submitted.
    """
    redis_client = get_redis_client()
    if redis_client is None:
        return False

    key = _message_dedup_key(email, message)
    try:
        exists = await redis_client.exists(key)
        if exists:
            return True
        # Mark this combination for the dedup window
        await redis_client.setex(key, _DEDUP_TTL_SECONDS, "1")
        return False
    except RedisError as exc:
        logger.warning("Redis error during dedup check", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    description=(
        "Public endpoint for contact form submissions.  No authentication "
        "required.  Implements layered spam protection including honeypot, "
        "time-based validation, rate limiting, optional reCAPTCHA v3, and "
        "content analysis."
    ),
)
async def submit_contact_form(
    payload: ContactRequest,
    request: Request,
) -> ContactResponse:
    """Submit a contact form message.

    Runs the submission through multiple spam protection layers before
    dispatching notification and confirmation emails via a Celery task.

    Args:
        payload: Validated contact form data.
        request: The raw FastAPI request (used for IP extraction).

    Returns:
        ContactResponse with a generic success message.
    """
    client_ip = _get_client_ip(request)

    # -----------------------------------------------------------------
    # Layer 1: Honeypot field
    # -----------------------------------------------------------------
    if payload.website:
        logger.info("Contact form honeypot triggered", client_ip=client_ip)
        return _SUCCESS_RESPONSE

    # -----------------------------------------------------------------
    # Layer 2: Time-based validation
    # -----------------------------------------------------------------
    if payload.timestamp is None:
        logger.info("Contact form missing timestamp", client_ip=client_ip)
        return _SUCCESS_RESPONSE

    now = time.time()
    elapsed = now - payload.timestamp

    if elapsed < settings.contact_min_submit_time:
        logger.info(
            "Contact form submitted too fast",
            elapsed_seconds=round(elapsed, 2),
            client_ip=client_ip,
        )
        return _SUCCESS_RESPONSE

    max_age_seconds = 7200  # 2 hours
    if elapsed > max_age_seconds:
        logger.info(
            "Contact form timestamp too old",
            elapsed_seconds=round(elapsed, 2),
            client_ip=client_ip,
        )
        return _SUCCESS_RESPONSE

    # -----------------------------------------------------------------
    # Layer 3: Rate limiting (Redis-backed)
    # -----------------------------------------------------------------
    rate_limit_response = await _check_rate_limits(payload.email, client_ip)
    if rate_limit_response is not None:
        return rate_limit_response

    # -----------------------------------------------------------------
    # Layer 4: reCAPTCHA v3 verification (optional)
    # -----------------------------------------------------------------
    if settings.recaptcha_secret_key:
        if payload.recaptcha_token:
            is_valid = await _verify_recaptcha(payload.recaptcha_token)
            if not is_valid:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Verification failed. Please try again."},
                )
        else:
            # reCAPTCHA is configured but no token was provided -- treat as
            # suspicious but don't block (could be an API client).
            logger.info(
                "Contact form missing reCAPTCHA token while reCAPTCHA is configured",
                client_ip=client_ip,
                email=payload.email,
            )

    # -----------------------------------------------------------------
    # Layer 5: Content validation
    # -----------------------------------------------------------------
    # 5a. Excessive URLs
    url_count = len(_URL_PATTERN.findall(payload.message))
    if url_count > 3:
        logger.info(
            "Contact form excessive URLs",
            url_count=url_count,
            client_ip=client_ip,
        )
        return _SUCCESS_RESPONSE

    # 5b. Script tags
    if _SCRIPT_PATTERN.search(payload.message):
        logger.info("Contact form script tag detected", client_ip=client_ip)
        return _SUCCESS_RESPONSE

    # 5c. Duplicate message (same email + message within 24h)
    if await _is_duplicate_message(payload.email, payload.message):
        logger.info(
            "Contact form duplicate submission",
            email=payload.email,
            client_ip=client_ip,
        )
        return _SUCCESS_RESPONSE

    # -----------------------------------------------------------------
    # All checks passed -- dispatch emails via Celery
    # -----------------------------------------------------------------
    from app.workers.tasks import send_contact_emails_task

    send_contact_emails_task.delay(
        name=payload.name,
        email=payload.email,
        message=payload.message,
    )

    logger.info(
        "Contact form accepted",
        email=payload.email,
        client_ip=client_ip,
    )

    return _SUCCESS_RESPONSE
