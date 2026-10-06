from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .enums import ErrorCategory
from .models import ErrorEnvelope


ERROR_STATUS_CODES: Mapping[ErrorCategory, int] = {
    ErrorCategory.INVALID_REQUEST: 400,
    ErrorCategory.INVALID_MEDIA_ID: 400,
    ErrorCategory.UNAUTHORIZED: 401,
    ErrorCategory.FORBIDDEN: 403,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.RATE_LIMITED: 429,
    ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED: 502,
    ErrorCategory.PROVIDER_UNAVAILABLE: 503,
    ErrorCategory.PROVIDER_ERROR: 502,
    ErrorCategory.UPSTREAM_TIMEOUT: 504,
    ErrorCategory.RANGE_NOT_SATISFIABLE: 416,
    ErrorCategory.CONNECTION_INTERRUPTED: 502,
    ErrorCategory.UNSUPPORTED_MEDIA: 415,
    ErrorCategory.INTERNAL_ERROR: 500,
}

_HTTP_STATUS_CATEGORIES = {
    400: ErrorCategory.INVALID_REQUEST,
    401: ErrorCategory.UNAUTHORIZED,
    403: ErrorCategory.FORBIDDEN,
    404: ErrorCategory.NOT_FOUND,
    416: ErrorCategory.RANGE_NOT_SATISFIABLE,
    429: ErrorCategory.RATE_LIMITED,
}


class ApplicationError(Exception):
    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.retry_after = retry_after


def _envelope_response(
    request: Request,
    category: ErrorCategory,
    message: str,
    status_code: int,
    retry_after: int | None = None,
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid4())
    request.state.error_category = category.value
    envelope = ErrorEnvelope(
        category=category,
        message=message,
        correlation_id=correlation_id,
        retry_after=retry_after,
    )
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", by_alias=True, exclude_none=True),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        return _envelope_response(
            request,
            exc.category,
            exc.message,
            ERROR_STATUS_CODES[exc.category],
            exc.retry_after,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return _envelope_response(
            request,
            ErrorCategory.INVALID_REQUEST,
            "Request validation failed.",
            ERROR_STATUS_CODES[ErrorCategory.INVALID_REQUEST],
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        category = _HTTP_STATUS_CATEGORIES.get(
            exc.status_code, ErrorCategory.INTERNAL_ERROR
        )
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _envelope_response(
            request, category, message, exc.status_code
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, _exc: Exception
    ) -> JSONResponse:
        return _envelope_response(
            request,
            ErrorCategory.INTERNAL_ERROR,
            "An unexpected error occurred.",
            ERROR_STATUS_CODES[ErrorCategory.INTERNAL_ERROR],
        )
