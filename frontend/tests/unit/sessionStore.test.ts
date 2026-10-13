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
