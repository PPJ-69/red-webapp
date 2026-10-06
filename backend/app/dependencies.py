from fastapi import Request

from .config import Settings
from .upstream.provider import UpstreamMediaProvider


def get_settings() -> Settings:
    return Settings.from_environment()


def get_upstream_provider(request: Request) -> UpstreamMediaProvider:
    provider = getattr(request.app.state, "upstream_provider", None)
    if provider is None:
        raise RuntimeError("No upstream media provider has been configured.")
    return provider
