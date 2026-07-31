"""SSRF guard for outbound HTTP requests.

Distribution download URLs come from third-party publishers via the I14Y API.
Before fetching them, we must ensure they resolve to a *public* IP address so
that an attacker who controls a distribution URL cannot pivot into internal
services (cloud metadata endpoints, RFC1918 hosts, loopback, etc.).

This is a stdlib-only port of the equivalent helper in the sibling swagger2dcat
service so mcp-i14y remains self-contained (no shared package).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_safe_public_url(url: str) -> tuple[bool, str]:
    """Return (True, "ok") if the URL resolves to a public IP address.

    Refuses:
    - non-http(s) schemes
    - missing hostname / literal "localhost"
    - hostnames that fail DNS resolution
    - resolved IPs that are private, loopback, link-local, multicast, reserved
      or unspecified
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "invalid URL"

    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported scheme"

    hostname = parsed.hostname
    if not hostname:
        return False, "missing hostname"

    lowered = hostname.lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        return False, "localhost is not allowed"

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, "hostname resolution failed"

    if not infos:
        return False, "hostname resolution failed"

    for info in infos:
        ip_str = info[4][0]
        try:
            ip_addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, "invalid resolved IP"

        if (
            ip_addr.is_private
            or ip_addr.is_loopback
            or ip_addr.is_link_local
            or ip_addr.is_multicast
            or ip_addr.is_reserved
            or ip_addr.is_unspecified
        ):
            return False, f"resolved to non-public IP {ip_str}"

    return True, "ok"
