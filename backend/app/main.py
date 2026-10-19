from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .api.creators import router as creators_router
from .api.health import router as health_router
from .api.media import router as media_router
from .api.search import router as search_router
from .api.stream import router as stream_router
from .api.tags import router as tags_router
from .dependencies import get_settings
from .domain.errors import register_exception_handlers
from .domain.models import canonical_model_schemas
from .observability.logging import (
    configure_logging,
    install_request_context,
    log_event,
)
from .observability.metrics import metrics
from .security.headers import install_security_headers
from .upstream.factory import create_upstream_provider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.metrics = metrics
    provider = None
    try:
        provider = await create_upstream_provider(settings)
        if provider is not None:
            app.state.upstream_provider = provider
        elif not hasattr(app.state, "upstream_provider"):
            app.state.upstream_provider = None
        yield
    finally:
        stream_service = getattr(app.state, "stream_service", None)
        if stream_service is not None:
            stream_service.hls_resources.clear()
        transport = getattr(app.state, "stream_transport", None)
        try:
            if transport is not None:
                await transport.aclose()
        finally:
            try:
                if provider is not None:
                    await provider.aclose()
                    app.state.upstream_provider = None
            finally:
                log_event(
                    "metrics_snapshot",
                    metrics=getattr(app.state, "metrics", metrics).snapshot(),
                )


configure_logging()
app = FastAPI(
    title="Stream-First Media Browser API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(search_router)
app.include_router(creators_router)
app.include_router(media_router)
app.include_router(stream_router)
app.include_router(tags_router)
register_exception_handlers(app)
install_request_context(app)
install_security_headers(app)


def _openapi_with_canonical_models() -> dict:
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.update(canonical_model_schemas())
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_canonical_models
