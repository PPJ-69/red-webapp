from dataclasses import dataclass
from enum import Enum
import math
from ipaddress import ip_network
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


DEFAULT_SOURCE_CACHE_TTL_SECONDS = 60.0


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class UpstreamProviderMode(str, Enum):
    DISABLED = "disabled"
    REDGIFS = "redgifs"


class ConfigurationError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    app_env: AppEnvironment
    upstream_provider: UpstreamProviderMode = UpstreamProviderMode.DISABLED
    redgifs_token_file: Path | None = None
    upstream_allowed_hosts: tuple[str, ...] = ()
    max_active_streams_per_ip: int = 3
    trusted_proxy_ips: tuple[str, ...] = ()
    cors_allowed_origins: tuple[str, ...] = ()
    source_cache_ttl_seconds: float = DEFAULT_SOURCE_CACHE_TTL_SECONDS
    enable_hls: bool = False

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str] | None = None
    ) -> "Settings":
        if environ is None:
            import os

            environ = os.environ

        value = environ.get("APP_ENV", "").strip().lower()
        if not value:
            raise ConfigurationError("APP_ENV must be set.")

        try:
            app_env = AppEnvironment(value)
        except ValueError as exc:
            allowed = ", ".join(environment.value for environment in AppEnvironment)
            raise ConfigurationError(
                f"APP_ENV must be one of: {allowed}."
            ) from exc

        raw_provider = environ.get("UPSTREAM_PROVIDER", "disabled").strip().lower()
        try:
            upstream_provider = UpstreamProviderMode(raw_provider)
        except ValueError as exc:
            allowed = ", ".join(provider.value for provider in UpstreamProviderMode)
            raise ConfigurationError(
                f"UPSTREAM_PROVIDER must be one of: {allowed}."
            ) from exc

        raw_token_file = environ.get("REDGIFS_TOKEN_FILE", "").strip()
        if upstream_provider is UpstreamProviderMode.REDGIFS and not raw_token_file:
            raise ConfigurationError(
                "REDGIFS_TOKEN_FILE must point to a mounted provider token file "
                "when UPSTREAM_PROVIDER=redgifs."
            )
        if upstream_provider is UpstreamProviderMode.DISABLED and raw_token_file:
            raise ConfigurationError(
                "REDGIFS_TOKEN_FILE requires UPSTREAM_PROVIDER=redgifs."
            )
        redgifs_token_file = Path(raw_token_file) if raw_token_file else None

        raw_hosts = environ.get("UPSTREAM_ALLOWED_HOSTS", "")
        upstream_allowed_hosts = tuple(
            host.strip().lower()
            for host in raw_hosts.split(",")
            if host.strip()
        )
        raw_stream_limit = environ.get("MAX_ACTIVE_STREAMS_PER_IP", "3").strip()
        try:
            max_active_streams_per_ip = int(raw_stream_limit)
        except ValueError as exc:
            raise ConfigurationError(
                "MAX_ACTIVE_STREAMS_PER_IP must be a positive integer."
            ) from exc
        if max_active_streams_per_ip < 1:
            raise ConfigurationError(
                "MAX_ACTIVE_STREAMS_PER_IP must be a positive integer."
            )

        raw_source_cache_ttl = environ.get(
            "SOURCE_CACHE_TTL_SECONDS",
            str(DEFAULT_SOURCE_CACHE_TTL_SECONDS),
        ).strip()
        try:
            source_cache_ttl_seconds = float(raw_source_cache_ttl)
        except ValueError as exc:
            raise ConfigurationError(
                "SOURCE_CACHE_TTL_SECONDS must be a positive number."
            ) from exc
        if not math.isfinite(source_cache_ttl_seconds) or source_cache_ttl_seconds <= 0:
            raise ConfigurationError(
                "SOURCE_CACHE_TTL_SECONDS must be a positive number."
            )

        raw_trusted_proxies = environ.get("TRUSTED_PROXY_IPS", "")
        trusted_proxy_ips: list[str] = []
        for proxy in raw_trusted_proxies.split(","):
            proxy = proxy.strip()
            if not proxy:
                continue
            try:
                trusted_proxy_ips.append(str(ip_network(proxy, strict=False)))
            except ValueError as exc:
                raise ConfigurationError(
                    "TRUSTED_PROXY_IPS must contain valid IP addresses or CIDRs."
                ) from exc

        cors_allowed_origins: list[str] = []
        for origin in environ.get("CORS_ALLOWED_ORIGINS", "").split(","):
            origin = origin.strip()
            if not origin:
                continue
            try:
                cors_allowed_origins.append(_normalize_origin(origin))
            except ValueError as exc:
                raise ConfigurationError(
                    "CORS_ALLOWED_ORIGINS must contain explicit HTTP(S) origins "
                    "without paths, credentials, queries, or wildcards."
                ) from exc

        raw_enable_hls = environ.get("ENABLE_HLS", "false").strip().lower()
        if raw_enable_hls not in {"true", "false", "1", "0", "yes", "no"}:
            raise ConfigurationError(
                "ENABLE_HLS must be a boolean value."
            )
        enable_hls = raw_enable_hls in {"true", "1", "yes"}

        return cls(
            app_env=app_env,
            upstream_provider=upstream_provider,
            redgifs_token_file=redgifs_token_file,
            upstream_allowed_hosts=upstream_allowed_hosts,
            max_active_streams_per_ip=max_active_streams_per_ip,
            trusted_proxy_ips=tuple(trusted_proxy_ips),
            cors_allowed_origins=tuple(dict.fromkeys(cors_allowed_origins)),
            source_cache_ttl_seconds=source_cache_ttl_seconds,
            enable_hls=enable_hls,
        )


def _normalize_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "*" in origin
    ):
        raise ValueError("Invalid origin.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid origin port.") from exc

    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    if port is not None and not (
        parsed.scheme == "http" and port == 80
        or parsed.scheme == "https" and port == 443
    ):
        hostname = f"{hostname}:{port}"
    return f"{parsed.scheme}://{hostname}"
