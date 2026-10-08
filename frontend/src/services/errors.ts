import type { ErrorCategory, ErrorEnvelope } from "../types/api";

export type ClientErrorCategory =
  | ErrorCategory
  | "network_error"
  | "malformed_response"
  | "request_cancelled";

const BACKEND_ERROR_CATEGORIES: ReadonlySet<string> = new Set([
  "invalid_request",
  "invalid_media_id",
  "unauthorized",
  "forbidden",
  "not_found",
  "rate_limited",
  "local_rate_limited",
  "upstream_authentication_failed",
  "provider_unavailable",
  "provider_error",
  "upstream_timeout",
  "range_not_satisfiable",
  "connection_interrupted",
  "unsupported_media",
  "internal_error",
]);

export class ApiError extends Error {
  readonly category: ClientErrorCategory;
  readonly status: number | undefined;
  readonly retryAfter: number | undefined;
  readonly correlationId: string | undefined;

  constructor(
    category: ClientErrorCategory,
    message: string,
    options: {
      status?: number;
      retryAfter?: number;
      correlationId?: string;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.category = category;
    this.status = options.status;
    this.retryAfter = options.retryAfter;
    this.correlationId = options.correlationId;
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const envelope = value as Record<string, unknown>;
  return (
    typeof envelope.category === "string" &&
    BACKEND_ERROR_CATEGORIES.has(envelope.category) &&
    typeof envelope.message === "string" &&
    typeof envelope.correlationId === "string" &&
    (envelope.retryAfter === undefined ||
      envelope.retryAfter === null ||
      (typeof envelope.retryAfter === "number" &&
        Number.isInteger(envelope.retryAfter) &&
        envelope.retryAfter >= 0))
  );
}

export async function mapErrorResponse(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new ApiError(
      "malformed_response",
      "The server returned an invalid error response.",
      { status: response.status },
    );
  }

  if (!isErrorEnvelope(payload)) {
    return new ApiError(
      "malformed_response",
      "The server returned an invalid error response.",
      { status: response.status },
    );
  }

  return new ApiError(payload.category, payload.message, {
    status: response.status,
    retryAfter: payload.retryAfter ?? undefined,
    correlationId: payload.correlationId,
  });
}

export function mapNetworkError(error: unknown, signal?: AbortSignal): ApiError {
  if (
    signal?.aborted ||
    (typeof error === "object" &&
      error !== null &&
      "name" in error &&
      error.name === "AbortError")
  ) {
    return new ApiError("request_cancelled", "The request was cancelled.");
  }
  return new ApiError("network_error", "The server could not be reached.");
}
