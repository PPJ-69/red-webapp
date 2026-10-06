from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .api.health import router as health_router
from .dependencies import get_settings
from .domain.errors import register_exception_handlers
from .domain.models import canonical_model_schemas


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = get_settings()
    yield


app = FastAPI(
    title="Stream-First Media Browser API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health_router)
register_exception_handlers(app)


def _openapi_with_canonical_models() -> dict:
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.update(canonical_model_schemas())
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_canonical_models
