from fastapi import Request

from .config import Settings
from .domain.enums import ErrorCategory
from .domain.errors import ApplicationError
from .observability.metrics import metrics
from .security.limits import StreamLimiter
from .services.media_resolver import MediaResolver
from .services.stream_service import StreamService
from .upstream.provider import UpstreamMediaProvider


def get_settings() -> Settings:
    return Settings.from_environment()


def get_upstream_provider(request: Request) -> UpstreamMediaProvider:
    provider = getattr(request.app.state, "upstream_provider", None)
    if provider is None:
        raise ApplicationError(
            ErrorCategory.PROVIDER_UNAVAILABLE,
            "The upstream provider is disabled.",
        )
    return provider


def get_media_resolver(request: Request) -> MediaResolver:
    resolver = getattr(request.app.state, "media_resolver", None)
    if resolver is None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        resolver = MediaResolver(
            get_upstream_provider(request),
            ttl_seconds=settings.source_cache_ttl_seconds,
            metrics_registry=getattr(request.app.state, "metrics", metrics),
        )
        request.app.state.media_resolver = resolver
    return resolver


def get_stream_service(request: Request) -> StreamService:
    from .upstream.stream_transport import StreamTransport

    service = getattr(request.app.state, "stream_service", None)
    if service is not None:
        return service

    resolver = get_media_resolver(request)
    settings = getattr(request.app.state, "settings", None) or get_settings()
    transport = getattr(request.app.state, "stream_transport", None)
    if transport is None:
        transport = StreamTransport(allowed_hosts=settings.upstream_allowed_hosts)
        request.app.state.stream_transport = transport

    service = StreamService(resolver, transport)
    request.app.state.stream_service = service
    return service


def get_stream_limiter(request: Request) -> StreamLimiter:
    limiter = getattr(request.app.state, "stream_limiter", None)
    if limiter is not None:
        return limiter

    settings = getattr(request.app.state, "settings", None) or get_settings()
    registry = getattr(request.app.state, "metrics", metrics)
    limiter = StreamLimiter(settings.max_active_streams_per_ip, registry)
    request.app.state.stream_limiter = limiter
    return limiter
