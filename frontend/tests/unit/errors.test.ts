import { describe, expect, it } from "vitest";

import { ApiError, mapErrorResponse, mapNetworkError } from "../../src/services/errors";

const categories = [
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
] as const;

describe("API errors", () => {
  it.each(categories)("maps the %s backend category", async (category) => {
    const error = await mapErrorResponse(
      new Response(
        JSON.stringify({
          category,
          message: "Request failed.",
          correlationId: "request-1",
          retryAfter:
            category === "rate_limited" || category === "local_rate_limited"
              ? 30
              : undefined,
        }),
        {
          status:
            category === "rate_limited" || category === "local_rate_limited"
              ? 429
              : 400,
        },
      ),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error.category).toBe(category);
    expect(error.correlationId).toBe("request-1");
    if (category === "rate_limited" || category === "local_rate_limited") {
      expect(error.retryAfter).toBe(30);
    }
  });

  it("maps invalid JSON and malformed envelopes", async () => {
    const invalidJson = await mapErrorResponse(
      new Response("not-json", { status: 502 }),
    );
    const invalidEnvelope = await mapErrorResponse(
      new Response(JSON.stringify({ message: "missing required fields" }), {
        status: 502,
      }),
    );

    expect(invalidJson.category).toBe("malformed_response");
    expect(invalidEnvelope.category).toBe("malformed_response");
  });

  it("maps network failures without leaking transport details", () => {
    const error = mapNetworkError(new Error("token=private"));

    expect(error.category).toBe("network_error");
    expect(error.message).not.toContain("private");
  });

  it("distinguishes cancellation from network failure", () => {
    const controller = new AbortController();
    controller.abort();

    expect(mapNetworkError(controller.signal.reason, controller.signal).category).toBe(
      "request_cancelled",
    );
  });
});
