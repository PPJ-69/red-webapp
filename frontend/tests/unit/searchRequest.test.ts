import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../src/services/apiClient";
import {
  createSearchRequestHandler,
  type SearchRequest,
} from "../../src/stores/searchContextStore";
import { parseSearchQuery } from "../../src/utils/queryParser";

describe("search request serialization", () => {
  it("sends normalized text, repeated tags, filters, and pagination", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          page: 2,
          limit: 10,
          hasMore: false,
        }),
        { status: 200 },
      ),
    );
    const controller = new AbortController();
    const searcher = createSearchRequestHandler(
      new ApiClient({ fetcher }),
    );
    const request: SearchRequest = {
      query: parseSearchQuery("cats #funny #cute @alice", { limit: 10 }),
      order: "score",
      page: 2,
      limit: 10,
    };

    await searcher(request, controller.signal);

    const [url, init] = fetcher.mock.calls[0];
    const params = new URL(String(url), "https://app.invalid").searchParams;
    expect(String(url)).toMatch(/^\/api\/search\?/);
    expect(params.get("q")).toBe("cats @alice");
    expect(params.getAll("tags")).toEqual(["funny", "cute"]);
    expect(params.get("mode")).toBe("search");
    expect(params.get("order")).toBe("score");
    expect(params.get("page")).toBe("2");
    expect(params.get("limit")).toBe("10");
    expect(init?.signal).toBe(controller.signal);
  });

  it("keeps an explicit creator separate from tokenized search text", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], page: 1, limit: 20, hasMore: false }),
        { status: 200 },
      ),
    );
    const searcher = createSearchRequestHandler(new ApiClient({ fetcher }));
    const query = parseSearchQuery("cats", { creator: "Alice Smith" });

    await searcher(
      { query, order: null, page: 1, limit: query.limit },
      new AbortController().signal,
    );

    const [url] = fetcher.mock.calls[0];
    const params = new URL(String(url), "https://app.invalid").searchParams;
    expect(params.get("q")).toBe("cats");
    expect(params.get("creator")).toBe("Alice Smith");
  });
});
