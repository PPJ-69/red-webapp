import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../src/services/apiClient";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ApiClient", () => {
  it("passes each request's signal through to fetch", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const client = new ApiClient({ fetcher });

    await client.get<{ status: string }>("/health/live", {
      signal: controller.signal,
    });

    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/health/live");
    expect(options?.signal).toBe(controller.signal);
  });

  it("reports an aborted request as cancelled", async () => {
    const controller = new AbortController();
    controller.abort();
    const client = new ApiClient({
      fetcher: vi.fn<typeof fetch>(),
    });

    await expect(
      client.get("/health/live", { signal: controller.signal }),
    ).rejects.toMatchObject({ category: "request_cancelled" });
  });

  it("maps cancellation during an active fetch", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockImplementation(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted.", "AbortError")),
            { once: true },
          );
        }),
    );
    const client = new ApiClient({ fetcher });
    const request = client.get("/health/live", { signal: controller.signal });

    controller.abort();

    await expect(request).rejects.toMatchObject({
      category: "request_cancelled",
    });
  });

  it("maps errors and malformed successful responses", async () => {
    const errorClient = new ApiClient({
      fetcher: vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            category: "not_found",
            message: "Missing.",
            correlationId: "request-1",
          }),
          { status: 404 },
        ),
      ),
    });
    const malformedClient = new ApiClient({
      fetcher: vi.fn<typeof fetch>().mockResolvedValue(
        new Response("invalid-json", { status: 200 }),
      ),
    });

    await expect(errorClient.get("/api/media/missing")).rejects.toMatchObject({
      category: "not_found",
      correlationId: "request-1",
    });
    await expect(malformedClient.get("/health/live")).rejects.toMatchObject({
      category: "malformed_response",
    });
  });

  it("uses same-origin paths and rejects absolute URLs", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const client = new ApiClient({ baseUrl: "/backend/", fetcher });

    await client.get("/health/live");

    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/backend/health/live");
    expect(options?.method).toBe("GET");
    await expect(client.get("https://example.invalid/api")).rejects.toThrow(
      "origin-relative",
    );
    await expect(client.get("//example.invalid/api")).rejects.toThrow(
      "origin-relative",
    );
  });

  it("sends JSON request bodies", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const client = new ApiClient({ fetcher });

    await client.post("/api/example", { value: 1 });

    const [url, options] = fetcher.mock.calls[0];
    const headers = new Headers(options?.headers);
    expect(url).toBe("/api/example");
    expect(options?.method).toBe("POST");
    expect(options?.body).toBe(JSON.stringify({ value: 1 }));
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Accept")).toBe("application/json");
  });
});
