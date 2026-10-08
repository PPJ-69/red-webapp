import { describe, expect, it } from "vitest";

import { PlaybackPrefetcher } from "../../src/services/prefetch";
import { ArrayPlaybackQueue } from "../../src/services/playbackQueue";

const items = [
  { id: "one", title: "One" },
  { id: "two", title: "Two" },
  { id: "three", title: "Three" },
];

describe("playback prefetch policy", () => {
  it("resolves only the immediate next source and consumes it once", async () => {
    const queue = new ArrayPlaybackQueue(items, "one");
    const prefetcher = new PlaybackPrefetcher<string>();
    const resolved: string[] = [];

    await expect(
      prefetcher.prepareNext(queue, async (id) => {
        resolved.push(id);
        return `source:${id}`;
      }),
    ).resolves.toBe(true);

    expect(resolved).toEqual(["two"]);
    expect(prefetcher.take("two")).toBe("source:two");
    expect(prefetcher.take("two")).toBeUndefined();
    expect(prefetcher.take("three")).toBeUndefined();
  });

  it("does not resolve a source when there is no next item", async () => {
    const queue = new ArrayPlaybackQueue(items, "three");
    const prefetcher = new PlaybackPrefetcher<string>();
    const resolved: string[] = [];

    await expect(
      prefetcher.prepareNext(queue, async (id) => {
        resolved.push(id);
        return id;
      }),
    ).resolves.toBe(false);
    expect(resolved).toEqual([]);
  });

  it("drops prepared sources once they are no longer current or next", async () => {
    const queue = new ArrayPlaybackQueue(items, "one");
    const prefetcher = new PlaybackPrefetcher<string>();
    await prefetcher.prepareNext(queue, async (id) => `source:${id}`);

    queue.select("three");
    await prefetcher.prepareNext(queue, async (id) => `source:${id}`);

    expect(prefetcher.take("two")).toBeUndefined();
  });

  it("cancels stale work and never caches its result", async () => {
    const queue = new ArrayPlaybackQueue(items, "one");
    const prefetcher = new PlaybackPrefetcher<string>();
    let resolveSource: ((source: string) => void) | undefined;
    let aborted = false;
    const preparing = prefetcher.prepareNext(queue, (_id, signal) => {
      signal.addEventListener("abort", () => (aborted = true));
      return new Promise((resolve) => {
        resolveSource = resolve;
      });
    });

    prefetcher.cancel();
    resolveSource?.("stale-source");

    await expect(preparing).resolves.toBe(false);
    expect(aborted).toBe(true);
    expect(prefetcher.take("two")).toBeUndefined();
  });
});
