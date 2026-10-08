from __future__ import annotations

import ipaddress
import socket
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidatedUpstreamTarget:
    url: str
    hostname: str
    addresses: tuple[str, ...]


def _normalize_allowed_hosts(allowed_hosts: Sequence[str] | None) -> set[str]:
    if not allowed_hosts:
        return set()
    hosts: set[str] = set()
    for raw in allowed_hosts:
        value = raw.strip().lower()
        if value:
            hosts.add(value.lstrip("."))
    return hosts


def _resolve_host_ips(hostname: str) -> set[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return set()
    ips: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_value = sockaddr[0]
        if ip_value:
            ips.add(ip_value)
    return ips


def validate_upstream_target(
    target_url: str,
    *,
    allowed_hosts: Sequence[str] | None = None,
) -> str:
    return resolve_validated_upstream_target(
        target_url, allowed_hosts=allowed_hosts
    ).url


def resolve_validated_upstream_target(
    target_url: str,
    *,
    allowed_hosts: Sequence[str] | None = None,
) -> ValidatedUpstreamTarget:
    parsed = urlparse(target_url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Upstream target must use HTTPS.")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("Upstream target must not include credentials or a fragment.")

    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("Upstream target must include a valid hostname.")

    normalized_allowed_hosts = _normalize_allowed_hosts(allowed_hosts)
    host_name = hostname.lower().lstrip(".")
    if host_name not in normalized_allowed_hosts:
        raise ValueError("Upstream target host is not allowlisted.")

    resolved_ips = _resolve_host_ips(hostname)
    if not resolved_ips:
        raise ValueError("Upstream target hostname could not be resolved.")

    for ip_text in resolved_ips:
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            raise ValueError("Upstream target resolved to an invalid address.")
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            raise ValueError("Upstream target resolves to a prohibited network address.")

    if host_name in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Upstream target host is not permitted.")

    return ValidatedUpstreamTarget(
        url=target_url,
        hostname=host_name,
        addresses=tuple(sorted(resolved_ips)),
    )
