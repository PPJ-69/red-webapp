from dataclasses import dataclass
from enum import Enum
from ipaddress import ip_network
from typing import Mapping
from urllib.parse import urlsplit


class AppEnvironment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class ConfigurationError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    app_env: AppEnvironment
    upstream_allowed_hosts: tuple[str, ...] = ()
    max_active_streams_per_ip: int = 3
    trusted_proxy_ips: tuple[str, ...] = ()
    cors_allowed_origins: tuple[str, ...] = ()

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

        return cls(
            app_env=app_env,
            upstream_allowed_hosts=upstream_allowed_hosts,
            max_active_streams_per_ip=max_active_streams_per_ip,
            trusted_proxy_ips=tuple(trusted_proxy_ips),
            cors_allowed_origins=tuple(dict.fromkeys(cors_allowed_origins)),
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
