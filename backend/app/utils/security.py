"""
Security and Authentication Module.

This module provides password hashing, JWT token generation,
and authentication utilities.

Example Usage:
    from app.utils.security import (
        hash_password,
        verify_password,
        create_access_token,
        decode_token
    )

    # Hash password
    hashed = hash_password("mypassword")

    # Verify password
    is_valid = verify_password("mypassword", hashed)

    # Create JWT token
    token = create_access_token({"sub": str(user.id)})
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis key prefix for revoked JWT IDs
REVOKED_JTI_PREFIX = "jwt:revoked:"


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Example:
        >>> hashed = hash_password("mypassword")
        >>> assert hashed != "mypassword"
    """
    return pwd_context.hash(password)


# Alias for backward compatibility
get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to check against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword")
        >>> assert verify_password("mypassword", hashed)
        >>> assert not verify_password("wrongpassword", hashed)
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token with organization context.

    Expected data fields:
        sub: User ID (required)
        org_id: Organization ID (optional, for multi-tenant context)
        role: Organization role (optional, e.g., "owner", "admin", "member")

    Args:
        data: Payload data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string

    Example:
        >>> token = create_access_token({
        ...     "sub": "user-id-123",
        ...     "org_id": "org-id-456",
        ...     "role": "admin"
        ... })
        >>> assert token.count(".") == 2  # JWT format
    """
    to_encode = data.copy()

    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "iat": _utcnow(),
        "jti": str(uuid.uuid4()),
        "type": "access",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have longer expiration than access tokens.

    Args:
        data: Payload data to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string

    Example:
        >>> token = create_refresh_token({"sub": "user-id-123"})
    """
    to_encode = data.copy()

    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(
            days=settings.refresh_token_expire_days
        )

    to_encode.update({
        "exp": expire,
        "iat": _utcnow(),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded payload if valid, None if invalid

    Example:
        >>> token = create_access_token({"sub": "123"})
        >>> payload = decode_token(token)
        >>> assert payload["sub"] == "123"
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError:
        return None


async def revoke_token(payload: Dict[str, Any]) -> bool:
    """
    Add a token's jti to the Redis blacklist for its remaining lifetime.

    Args:
        payload: Decoded JWT payload (must contain `jti` and `exp`).

    Returns:
        True if the token was registered as revoked, False if Redis
        is unavailable or the payload lacked a `jti` claim.
    """
    jti = payload.get("jti")
    if not jti:
        # Tokens issued before jti was introduced cannot be revoked
        # individually. They expire naturally.
        return False

    exp = payload.get("exp")
    if exp is None:
        ttl = settings.access_token_expire_minutes * 60
    else:
        # exp can be int (unix ts) or datetime depending on decoder
        if isinstance(exp, datetime):
            exp_ts = int(exp.timestamp())
        else:
            exp_ts = int(exp)
        now_ts = int(_utcnow().timestamp())
        ttl = max(exp_ts - now_ts, 1)

    # Import here to avoid circular import (cache -> config -> security)
    from app.utils.cache import set_cache

    return await set_cache(f"{REVOKED_JTI_PREFIX}{jti}", "1", ttl=ttl)


async def is_token_revoked(payload: Dict[str, Any]) -> bool:
    """
    Check whether a token's jti is on the revocation blacklist.

    Fail-open: if Redis is unavailable we return False rather than
    locking out every user. Token revocation is a defense-in-depth
    feature; the JWT's own expiration is still authoritative.
    """
    jti = payload.get("jti")
    if not jti:
        return False

    from app.utils.cache import get_cache

    try:
        value = await get_cache(f"{REVOKED_JTI_PREFIX}{jti}")
    except Exception as e:
        logger.warning(f"Token revocation check failed (fail-open): {e}")
        return False

    return value is not None


def generate_api_key() -> str:
    """
    Generate a secure API key.

    Returns:
        Random 32-byte hex string (64 characters)

    Example:
        >>> key = generate_api_key()
        >>> assert len(key) == 64
    """
    return secrets.token_hex(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage.

    Uses SHA-256 for API key hashing.

    Args:
        api_key: Plain API key to hash

    Returns:
        Hashed API key string (hex digest)
    """
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        plain_key: Plain API key to verify
        hashed_key: Hashed key to check against (SHA-256 hex digest)

    Returns:
        True if key matches, False otherwise
    """
    import hashlib
    import hmac
    computed_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_hash, hashed_key)


def generate_password_reset_token(user_id: Union[str, UUID]) -> str:
    """
    Generate a password reset token.

    Token expires in 1 hour.

    Args:
        user_id: User ID to encode in token

    Returns:
        JWT token for password reset
    """
    expire = _utcnow() + timedelta(hours=1)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "password_reset",
    }

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token.

    Args:
        token: Password reset token to verify

    Returns:
        User ID if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )

        if payload.get("type") != "password_reset":
            return None

        return payload.get("sub")
    except JWTError:
        return None


def generate_email_verification_token(user_id: Union[str, UUID]) -> str:
    """
    Generate an email verification token.

    Token expires in 24 hours.

    Args:
        user_id: User ID to encode in token

    Returns:
        JWT token for email verification
    """
    expire = _utcnow() + timedelta(hours=24)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "email_verification",
    }

    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def verify_email_verification_token(token: str) -> Optional[str]:
    """
    Verify an email verification token.

    Args:
        token: Email verification token to verify

    Returns:
        User ID if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )

        if payload.get("type") != "email_verification":
            return None

        return payload.get("sub")
    except JWTError:
        return None


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage using Fernet encryption.

    Args:
        api_key: Plain API key to encrypt

    Returns:
        Encrypted API key as base64 string

    Example:
        >>> encrypted = encrypt_api_key("sk-1234567890")
        >>> decrypted = decrypt_api_key(encrypted)
        >>> assert decrypted == "sk-1234567890"
    """
    from cryptography.fernet import Fernet
    import base64
    import hashlib

    # Use secret key to derive Fernet key
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    fernet = Fernet(fernet_key)

    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key from storage.

    Args:
        encrypted_key: Encrypted API key as base64 string

    Returns:
        Decrypted plain API key

    Raises:
        ValueError: If decryption fails (invalid key format)
    """
    from cryptography.fernet import Fernet, InvalidToken
    import base64
    import hashlib

    try:
        # Use secret key to derive Fernet key
        key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        fernet = Fernet(fernet_key)

        return fernet.decrypt(encrypted_key.encode()).decode()
    except (InvalidToken, ValueError) as e:
        raise ValueError(f"Failed to decrypt API key: {e}")
