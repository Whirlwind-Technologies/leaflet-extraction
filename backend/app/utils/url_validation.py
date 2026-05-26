"""
URL Validation Utilities.

This module provides helper functions for validating webhook URLs,
including SSRF (Server-Side Request Forgery) prevention by blocking
requests to private and internal IP addresses.

Example Usage:
    from app.utils.url_validation import validate_webhook_url

    # Raises ValidationException if URL points to private IP
    validate_webhook_url("https://example.com/webhook")

    # Blocked:
    validate_webhook_url("http://127.0.0.1/hook")  # -> raises
    validate_webhook_url("http://192.168.1.1/hook")  # -> raises
"""

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

from app.config import settings
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

# Private and reserved IP ranges that must be blocked for SSRF prevention.
# These ranges cover loopback, link-local, RFC 1918 private, and
# the metadata service address used by cloud providers.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 Class A private
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 Class B private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 Class C private
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

# Hostnames that are always blocked regardless of what they resolve to.
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
    "metadata.google.internal",
})

# Error message returned to clients.
SSRF_ERROR_MESSAGE = (
    "Webhook URL must not point to a private or internal IP address"
)


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address string falls within a blocked private/reserved range.

    Args:
        ip_str: IPv4 or IPv6 address string (e.g., "192.168.1.1").

    Returns:
        True if the IP is within any blocked network range, False otherwise.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        # If we cannot parse it, treat as private (fail-closed).
        return True

    for network in _BLOCKED_NETWORKS:
        if addr in network:
            return True

    return False


def is_private_url(url: str) -> bool:
    """Determine if a URL resolves to a private or internal IP address.

    This function performs DNS resolution to check the actual IP that
    the hostname points to. It blocks:
      - Known private hostnames (localhost, 0.0.0.0, etc.)
      - Hostnames that resolve to private/reserved IP ranges
      - URLs with IP address literals in private ranges
      - Non-HTTP(S) schemes

    Args:
        url: The full URL to check (e.g., "https://example.com/webhook").

    Returns:
        True if the URL is private/internal and should be blocked.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return True

    # Only allow HTTP and HTTPS schemes.
    if parsed.scheme not in ("http", "https"):
        return True

    hostname = parsed.hostname
    if not hostname:
        return True

    # Normalize hostname to lowercase for comparison.
    hostname_lower = hostname.lower().rstrip(".")

    # Check against known blocked hostnames.
    if hostname_lower in _BLOCKED_HOSTNAMES:
        return True

    # Check if hostname is already an IP literal.
    try:
        addr = ipaddress.ip_address(hostname_lower)
        return is_private_ip(str(addr))
    except ValueError:
        pass  # Not an IP literal; resolve via DNS below.

    # Resolve hostname to IP address(es) and check each one.
    try:
        addr_infos = socket.getaddrinfo(
            hostname_lower, parsed.port or 443, proto=socket.IPPROTO_TCP
        )
    except (socket.gaierror, OSError) as exc:
        logger.warning(
            "DNS resolution failed for webhook URL hostname",
            extra={"hostname": hostname_lower, "error": str(exc)},
        )
        # If DNS resolution fails, we cannot verify -- fail closed.
        return True

    for addr_info in addr_infos:
        ip_str = addr_info[4][0]
        if is_private_ip(ip_str):
            return True

    return False


def validate_webhook_url(url: str, field_name: str = "url") -> None:
    """Validate a webhook URL, raising an exception if it is unsafe.

    Checks that the URL uses HTTP(S) and does not point to a
    private/internal IP address. Respects the
    ``WEBHOOK_ALLOW_PRIVATE_IPS`` setting which can be enabled in
    development environments.

    Args:
        url: The webhook URL to validate.
        field_name: Name of the field for the error message context.

    Raises:
        ValidationException: If the URL points to a private/internal IP
            and ``WEBHOOK_ALLOW_PRIVATE_IPS`` is False.
    """
    # In development mode with the flag enabled, skip the check.
    if settings.webhook_allow_private_ips:
        logger.debug(
            "Skipping SSRF check for webhook URL (WEBHOOK_ALLOW_PRIVATE_IPS=True)",
            extra={"url": url},
        )
        return

    if is_private_url(url):
        logger.warning(
            "Blocked webhook URL pointing to private/internal IP",
            extra={"url": url},
        )
        raise ValidationException(
            errors=[{"field": field_name, "message": SSRF_ERROR_MESSAGE}],
            message=SSRF_ERROR_MESSAGE,
        )
