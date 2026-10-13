import { describe, expect, it } from "vitest";

import { ResultsPlaybackQueue } from "../../src/services/resultsQueue";

const items = [
  { id: "one", title: "One" },
  { id: "two", title: "Two" },
  { id: "three", title: "Three" },
];

describe("results playback queue", () => {
  it("starts empty and follows appended and replaced search results", () => {
    const queue = new ResultsPlaybackQueue(() => 0);

    expect(queue.items).toEqual([]);
    expect(queue.hasNext).toBe(false);
    expect(() => queue.current).toThrow(RangeError);

    queue.replaceItems(items.slice(0, 2));
    queue.select("one");
    queue.replaceItems(items);
    expect(queue.current.id).toBe("one");
    expect(queue.next()?.id).toBe("two");
    expect(queue.nextItem?.id).toBe("three");

    queue.select("three");
    queue.replaceItems([items[0], items[2]]);
    expect(queue.current.id).toBe("three");
    expect(queue.currentIndex).toBe(1);
    expect(queue.next()).toBeUndefined();
  });

  it("clears a selection removed by a new search and emits queue selections", () => {
    const queue = new ResultsPlaybackQueue(() => 0);
    const changes: string[] = [];
    queue.replaceItems(items);
    queue.subscribe(({ id }) => changes.push(id));

    queue.select("two");
    queue.replaceItems([items[0]]);

    expect(changes).toEqual(["two"]);
    expect(queue.currentOrUndefined).toBeUndefined();
    expect(queue.hasPrevious).toBe(false);
    expect(queue.canRandom).toBe(false);
  });

  it("uses the current seen set for random navigation", () => {
    const seen = new Set(["two"]);
    const queue = new ResultsPlaybackQueue(() => 0.99, () => seen);
    queue.replaceItems(items);
    queue.select("one");

    expect(queue.random().id).toBe("three");
    seen.add("three");
    expect(queue.random().id).toBe("two");
  });

  it("rejects duplicate IDs and random values outside the unit interval", () => {
    const queue = new ResultsPlaybackQueue(() => 1);
    expect(() => queue.replaceItems([items[0], items[0]])).toThrow(TypeError);
    queue.replaceItems(items);
    queue.select("one");
    expect(() => queue.random()).toThrow(RangeError);
  });
});
