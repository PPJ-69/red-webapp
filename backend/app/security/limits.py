from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from threading import Lock

from starlette.requests import Request

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.observability.metrics import MetricsRegistry

IPAddress = IPv4Address | IPv6Address


def _parse_ip(value: str) -> IPAddress | None:
    try:
        return ip_address(value.strip())
    except ValueError:
        return None


def client_ip_for_request(
    request: Request, trusted_proxy_ips: tuple[str, ...] = ()
) -> str:
    peer_host = request.client.host if request.client is not None else None
    peer = _parse_ip(peer_host or "")
    if peer is None:
        return peer_host or "unknown"

    trusted_networks = tuple(
        ip_network(network, strict=False) for network in trusted_proxy_ips
    )

    def is_trusted(address: IPAddress) -> bool:
        return any(
            address.version == network.version and address in network
            for network in trusted_networks
        )

    if not is_trusted(peer):
        return peer.compressed

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer.compressed

    chain = [_parse_ip(part) for part in forwarded.split(",")]
    if not chain or any(address is None for address in chain):
        return peer.compressed

    addresses = [address for address in chain if address is not None]
    current = peer
    for address in reversed(addresses):
        if not is_trusted(current):
            return current.compressed
        current = address
    return current.compressed


class StreamLease:
    def __init__(self, limiter: StreamLimiter, client_ip: str) -> None:
        self._limiter = limiter
        self._client_ip = client_ip
        self._released = False
        self._lock = Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        self._limiter._release(self._client_ip)


class StreamLimiter:
    def __init__(
        self,
        max_active_streams_per_ip: int,
        metrics: MetricsRegistry,
    ) -> None:
        if max_active_streams_per_ip < 1:
            raise ValueError("The per-IP stream limit must be positive.")
        self._limit = max_active_streams_per_ip
        self._metrics = metrics
        self._active_by_ip: dict[str, int] = {}
        self._active_total = 0
        self._lock = Lock()

    def acquire(self, client_ip: str) -> StreamLease:
        with self._lock:
            active = self._active_by_ip.get(client_ip, 0)
            if active >= self._limit:
                raise ApplicationError(
                    ErrorCategory.LOCAL_RATE_LIMITED,
                    "This client has reached the concurrent stream limit.",
                    retry_after=1,
                )
            self._active_by_ip[client_ip] = active + 1
            self._active_total += 1
            self._metrics.set_gauge("stream_active_connections", self._active_total)
        return StreamLease(self, client_ip)

    def _release(self, client_ip: str) -> None:
        with self._lock:
            active = self._active_by_ip.get(client_ip, 0)
            if active <= 0:
                raise RuntimeError("Cannot release a stream slot that is not active.")
            if active == 1:
                del self._active_by_ip[client_ip]
            else:
                self._active_by_ip[client_ip] = active - 1
            self._active_total -= 1
            self._metrics.set_gauge("stream_active_connections", self._active_total)
