import { describe, expect, it, vi } from "vitest";

import { hydrateFavoriteMetadata } from "../../src/services/favoriteMetadata";
import type { MediaItem } from "../../src/types/api";

const item = (id: string): MediaItem => ({ id, title: `Title ${id}` });

describe("favorite metadata hydration", () => {
  it("hydrates only unique requested IDs and rejects mismatched metadata", async () => {
    const loadMedia = vi.fn(async (id: string) => item(id));

    const result = await hydrateFavoriteMetadata(
      ["one", "one", "two"],
      loadMedia,
      new AbortController().signal,
    );

    expect(loadMedia.mock.calls.map(([id]) => id)).toEqual(["one", "two"]);
    expect(result.items).toEqual([item("one"), item("two")]);
    expect(result.errors.size).toBe(0);
  });

  it("surfaces failed and malformed metadata per favorite", async () => {
    const loadMedia = vi.fn(async (id: string) => {
      if (id === "bad") return item("wrong");
      throw new Error("Provider unavailable.");
    });

    const result = await hydrateFavoriteMetadata(
      ["bad", "offline"],
      loadMedia,
      new AbortController().signal,
    );

    expect(result.items).toEqual([]);
    expect(result.errors.get("bad")).toContain("mismatched metadata");
    expect(result.errors.get("offline")).toBe("Provider unavailable.");
  });
});
