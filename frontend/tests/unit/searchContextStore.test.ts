import { describe, expect, it, vi } from "vitest";

import {
  createSearchContextStore,
  type SearchRequestHandler,
} from "../../src/stores/searchContextStore";
import type { MediaItem, SearchResult } from "../../src/types/api";

function item(id: string, title = id): MediaItem {
  return { id, title };
}

function result(
  items: MediaItem[],
  page: number,
  hasMore: boolean,
): SearchResult {
  return { items, page, limit: 2, hasMore };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("search context store", () => {
  it("replaces prior results after search and deduplicates each page by ID", async () => {
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockResolvedValueOnce(result([item("one"), item("two")], 1, true))
      .mockResolvedValueOnce(
        result([item("two", "duplicate"), item("three")], 2, false),
      )
      .mockResolvedValueOnce(result([item("new")], 1, false));
    const store = createSearchContextStore(searcher);

    await expect(store.search("cats", { limit: 2 })).resolves.toBe(true);
    await expect(store.loadNextPage()).resolves.toBe(true);
    expect([...store.getSnapshot().itemsById.keys()]).toEqual([
      "one",
      "two",
      "three",
    ]);
    expect(store.getSnapshot().itemsById.get("two")?.title).toBe("two");
    expect(store.getSnapshot().loadedPages).toEqual([1, 2]);

    await expect(store.search("#funny")).resolves.toBe(true);
    expect([...store.getSnapshot().itemsById.keys()]).toEqual(["new"]);
    expect(store.getSnapshot().loadedPages).toEqual([1]);
    expect(searcher.mock.calls[2][0]).toMatchObject({
      query: { tags: ["funny"], mode: "search" },
      page: 1,
      limit: 20,
    });
  });

  it("allows only one next-page request at a time", async () => {
    const nextPage = deferred<SearchResult>();
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockResolvedValueOnce(result([item("one")], 1, true))
      .mockImplementationOnce(() => nextPage.promise);
    const store = createSearchContextStore(searcher);

    await store.search("cats");
    const firstRequest = store.loadNextPage();
    await expect(store.loadNextPage()).resolves.toBe(false);
    expect(searcher).toHaveBeenCalledTimes(2);

    nextPage.resolve(result([item("two")], 2, false));
    await expect(firstRequest).resolves.toBe(true);
    expect(store.getSnapshot().loadedPages).toEqual([1, 2]);
  });

  it("retains loaded items when a pagination request fails", async () => {
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockResolvedValueOnce(result([item("one")], 1, true))
      .mockRejectedValueOnce(new Error("temporary failure"));
    const store = createSearchContextStore(searcher);

    await store.search("cats");
    await expect(store.loadNextPage()).resolves.toBe(false);

    expect([...store.getSnapshot().itemsById.keys()]).toEqual(["one"]);
    expect(store.getSnapshot().loadedPages).toEqual([1]);
    expect(store.getSnapshot().hasMore).toBe(true);
    expect(store.getSnapshot().error).toBeInstanceOf(Error);
    expect(store.getSnapshot().loadingMore).toBe(false);
  });

  it("aborts superseded searches and ignores stale responses", async () => {
    const oldSearch = deferred<SearchResult>();
    let oldSignal: AbortSignal | undefined;
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockImplementationOnce((_request, signal) => {
        oldSignal = signal;
        return oldSearch.promise;
      })
      .mockResolvedValueOnce(result([item("current")], 1, false));
    const store = createSearchContextStore(searcher);

    const staleRequest = store.search("old");
    await expect(store.search("new")).resolves.toBe(true);
    expect(oldSignal?.aborted).toBe(true);
    oldSearch.resolve(result([item("stale")], 1, false));
    await expect(staleRequest).resolves.toBe(false);

    expect([...store.getSnapshot().itemsById.keys()]).toEqual(["current"]);
    expect(store.getSnapshot().query?.query).toBe("new");
  });

  it("aborts an in-flight next page when a new query supersedes it", async () => {
    const pendingPage = deferred<SearchResult>();
    let pageSignal: AbortSignal | undefined;
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockResolvedValueOnce(result([item("old")], 1, true))
      .mockImplementationOnce((_request, signal) => {
        pageSignal = signal;
        return pendingPage.promise;
      })
      .mockResolvedValueOnce(result([item("new")], 1, false));
    const store = createSearchContextStore(searcher);

    await store.search("old");
    const stalePage = store.loadNextPage();
    await store.search("new");
    expect(pageSignal?.aborted).toBe(true);
    pendingPage.resolve(result([item("stale")], 2, false));
    await expect(stalePage).resolves.toBe(false);

    expect([...store.getSnapshot().itemsById.keys()]).toEqual(["new"]);
  });

  it("leaves existing items intact on a failed replacement search", async () => {
    const searcher = vi
      .fn<SearchRequestHandler>()
      .mockResolvedValueOnce(result([item("one")], 1, true))
      .mockRejectedValueOnce(new Error("offline"));
    const store = createSearchContextStore(searcher);

    await store.search("first");
    await expect(store.search("second")).resolves.toBe(false);

    expect([...store.getSnapshot().itemsById.keys()]).toEqual(["one"]);
    expect(store.getSnapshot().error).toBeInstanceOf(Error);
    expect(store.getSnapshot().hasMore).toBe(false);
  });

  it("discards items and cancels active requests", async () => {
    const pending = deferred<SearchResult>();
    let signal: AbortSignal | undefined;
    const store = createSearchContextStore((_request, requestSignal) => {
      signal = requestSignal;
      return pending.promise;
    });

    const request = store.search("cats");
    store.discard();
    pending.resolve(result([item("stale")], 1, false));

    await expect(request).resolves.toBe(false);
    expect(signal?.aborted).toBe(true);
    expect(store.getSnapshot().itemsById.size).toBe(0);
    expect(store.getSnapshot().query).toBeNull();
  });
});
