import { describe, expect, it } from "vitest";

import { createSessionStore } from "../../src/stores/sessionStore";

describe("session store", () => {
  it("keeps favorites and seen IDs in RAM without duplicating entries", () => {
    const store = createSessionStore();

    store.toggleFavorite("alpha");
    store.toggleFavorite("alpha");
    store.markSeen("alpha");
    store.markSeen("alpha");

    expect(store.getSnapshot().favorites).toEqual([]);
    expect(store.getSnapshot().seen).toEqual(["alpha"]);
    expect(store.hasSeen("alpha")).toBe(true);
    expect(store.isFavorite("alpha")).toBe(false);
  });

  it("tracks search history and saved searches without persisting to browser storage", () => {
    const store = createSessionStore();

    store.addSearchHistory("#cats");
    store.addSearchHistory("#cats");
    store.saveSearch("#cats", "trending");
    store.saveSearch("#cats", "latest");

    expect(store.getSnapshot().searchHistory).toEqual(["#cats"]);
    expect(store.getSnapshot().savedSearches).toHaveLength(1);
    expect(store.getSnapshot().savedSearches[0]?.query).toBe("#cats");
    expect(store.getSnapshot().savedSearches[0]?.order).toBe("latest");
  });

  it("keeps saved search identifiers unique and bounds in-memory history", () => {
    const store = createSessionStore();
    const now = Date.now;
    Date.now = () => 123;
    try {
      store.saveSearch("first", "top");
      store.saveSearch("second", "score");
    } finally {
      Date.now = now;
    }
    for (let index = 0; index < 27; index += 1) {
      store.addSearchHistory(`query-${index}`);
    }

    const snapshot = store.getSnapshot();
    expect(snapshot.savedSearches[0]?.id).not.toBe(snapshot.savedSearches[1]?.id);
    expect(snapshot.searchHistory).toHaveLength(25);
    expect(snapshot.searchHistory[0]).toBe("query-26");
  });

  it("removes saved searches and rejects unsupported ordering values", () => {
    const store = createSessionStore();
    store.saveSearch("cats", "arbitrary");
    const saved = store.getSnapshot().savedSearches[0];
    expect(saved?.order).toBeNull();
    if (saved) store.removeSavedSearch(saved.id);
    expect(store.getSnapshot().savedSearches).toEqual([]);
  });

  it("resets the session state without touching browser storage APIs", () => {
    const store = createSessionStore();
    store.toggleFavorite("beta");
    store.markSeen("beta");
    store.addSearchHistory("beta");

    store.reset();

    expect(store.getSnapshot()).toMatchObject({
      favorites: [],
      seen: [],
      searchHistory: [],
      savedSearches: [],
      privacyMode: true,
      privacyModeLocked: true,
    });
  });
});
