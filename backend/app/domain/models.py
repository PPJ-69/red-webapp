from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import ErrorCategory


def _to_camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class Creator(ApiModel):
    id: str
    username: str
    display_name: str | None = None
    profile_image_url: str | None = None


class MediaSource(ApiModel):
    playback_url: str
    mime_type: str | None = None


class MediaItem(ApiModel):
    id: str
    title: str
    description: str | None = None
    creator: Creator | None = None
    tags: list[str] = Field(default_factory=list)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration: float | None = Field(default=None, ge=0)
    thumbnail_url: str | None = None
    poster_url: str | None = None
    sources: list[MediaSource] = Field(default_factory=list)


class SearchResult(ApiModel):
    items: list[MediaItem]
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    has_more: bool
    total: int | None = Field(default=None, ge=0)


class SearchQuery(ApiModel):
    mode: str = "search"
    query: str | None = None
    tags: list[str] = Field(default_factory=list)
    order: str | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class ErrorEnvelope(ApiModel):
    category: ErrorCategory
    message: str
    correlation_id: str
    retry_after: int | None = Field(default=None, ge=0)


class HealthStatus(ApiModel):
    status: str


def canonical_model_schemas() -> dict[str, dict[str, Any]]:
    models = (Creator, MediaSource, MediaItem, SearchResult, SearchQuery, ErrorEnvelope)
    schemas: dict[str, dict[str, Any]] = {}
    for model in models:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions = schema.pop("$defs", {})
        schemas.update(definitions)
        schemas[model.__name__] = schema
    return schemas
