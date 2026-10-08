from enum import Enum


class ErrorCategory(str, Enum):
    INVALID_REQUEST = "invalid_request"
    INVALID_MEDIA_ID = "invalid_media_id"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    LOCAL_RATE_LIMITED = "local_rate_limited"
    UPSTREAM_AUTHENTICATION_FAILED = "upstream_authentication_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    RANGE_NOT_SATISFIABLE = "range_not_satisfiable"
    CONNECTION_INTERRUPTED = "connection_interrupted"
    UNSUPPORTED_MEDIA = "unsupported_media"
    INTERNAL_ERROR = "internal_error"
