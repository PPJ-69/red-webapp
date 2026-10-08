import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../src/services/apiClient";
import {
  createTagSuggestService,
  TagSuggestService,
} from "../../src/services/tagSuggest";

afterEach(() => {
  vi.useRealTimers();
});

describe("tag suggestions", () => {
  it("waits for debounce and enforces the minimum query length", async () => {
    vi.useFakeTimers();
    const requester = vi.fn(async () => ["funny"]);
    const service = new TagSuggestService(requester, 250, 2);

    await expect(service.suggest(" f ")).resolves.toEqual([]);
    expect(requester).not.toHaveBeenCalled();

    const pending = service.suggest("fu");
    await vi.advanceTimersByTimeAsync(249);
    expect(requester).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await expect(pending).resolves.toEqual(["funny"]);
    expect(requester).toHaveBeenCalledWith(
      "fu",
      expect.any(AbortSignal),
    );
  });

  it("cancels a pending debounce when a newer query arrives", async () => {
    vi.useFakeTimers();
    const requester = vi.fn(async (query: string) => [`${query}-tag`]);
    const service = new TagSuggestService(requester, 200, 2);

    const stale = service.suggest("ca");
    const latest = service.suggest("cat");
    await expect(stale).resolves.toEqual([]);
    await vi.advanceTimersByTimeAsync(200);

    await expect(latest).resolves.toEqual(["cat-tag"]);
    expect(requester).toHaveBeenCalledTimes(1);
    expect(requester).toHaveBeenCalledWith("cat", expect.any(AbortSignal));
  });

  it("aborts active work and ignores a late stale response", async () => {
    vi.useFakeTimers();
    let resolveStale: ((tags: string[]) => void) | undefined;
    let staleSignal: AbortSignal | undefined;
    const requester = vi
      .fn<(query: string, signal: AbortSignal) => Promise<string[]>>()
      .mockImplementationOnce((_query, signal) => {
        staleSignal = signal;
        return new Promise((resolve) => {
          resolveStale = resolve;
        });
      })
      .mockResolvedValueOnce(["new"]);
    const service = new TagSuggestService(requester, 100, 2);

    const stale = service.suggest("old");
    await vi.advanceTimersByTimeAsync(100);
    const latest = service.suggest("new");
    expect(staleSignal?.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(100);

    await expect(stale).resolves.toEqual([]);
    await expect(latest).resolves.toEqual(["new"]);
    resolveStale?.(["stale"]);
    await Promise.resolve();
    expect(staleSignal?.aborted).toBe(true);
  });

  it("encodes query text and rejects malformed API payloads", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify(["funny cats"])))
      .mockResolvedValueOnce(new Response(JSON.stringify({ tags: [] })));
    const client = new ApiClient({ fetcher });
    const service = createTagSuggestService(client, {
      debounceMs: 0,
      minimumLength: 1,
    });

    const suggestions = service.suggest("funny cats");
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    await expect(suggestions).resolves.toEqual(["funny cats"]);
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe("/api/tags/suggest?q=funny+cats");
    expect(options?.signal).toBeInstanceOf(AbortSignal);

    const malformed = service.suggest("other");
    const malformedAssertion = expect(malformed).rejects.toThrow(
      "Tag suggestions must be an array of strings.",
    );
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    await malformedAssertion;
  });

  it("propagates API failures instead of presenting empty suggestions", async () => {
    const service = new TagSuggestService(
      async () => {
        throw new Error("backend unavailable");
      },
      0,
      2,
    );
    const pending = service.suggest("cat");
    await expect(pending).rejects.toThrow("backend unavailable");
  });
});
