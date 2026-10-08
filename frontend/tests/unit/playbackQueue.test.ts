import { describe, expect, it } from "vitest";

import { ArrayPlaybackQueue } from "../../src/services/playbackQueue";

const items = [
  { id: "one", title: "One" },
  { id: "two", title: "Two" },
  { id: "three", title: "Three" },
];

describe("array playback queue", () => {
  it("tracks current, next, previous, and emits only when selection changes", () => {
    const queue = new ArrayPlaybackQueue(items, "two");
    const changes: string[] = [];
    queue.subscribe(({ id }) => changes.push(id));

    expect(queue.current).toEqual(items[1]);
    expect(queue.hasPrevious).toBe(true);
    expect(queue.hasNext).toBe(true);
    expect(queue.nextItem).toEqual(items[2]);
    expect(queue.next()).toEqual(items[2]);
    expect(queue.previous()).toEqual(items[1]);
    expect(queue.select("two")).toEqual(items[1]);
    expect(changes).toEqual(["three", "two"]);
  });

  it("keeps navigation within the array bounds", () => {
    const queue = new ArrayPlaybackQueue(items, "one");

    expect(queue.previous()).toBeUndefined();
    queue.select("three");
    expect(queue.next()).toBeUndefined();
    expect(queue.current.id).toBe("three");
  });

  it("chooses unseen items first and excludes the current item", () => {
    const randomValues = [0, 0.99];
    const queue = new ArrayPlaybackQueue(
      items,
      "one",
      () => randomValues.shift() ?? 0,
      ["two"],
    );

    expect(queue.random().id).toBe("three");
    expect(queue.random().id).toBe("two");
  });

  it("falls back to any other item once all items have been seen", () => {
    const queue = new ArrayPlaybackQueue(items, "two", () => 0.99, [
      "one",
      "two",
      "three",
    ]);

    expect(queue.random().id).toBe("three");
  });

  it("rejects empty, duplicate, and unknown queue entries", () => {
    expect(() => new ArrayPlaybackQueue([], "one")).toThrow(TypeError);
    expect(
      () =>
        new ArrayPlaybackQueue(
          [
            { id: "same", title: "First" },
            { id: "same", title: "Second" },
          ],
          "same",
        ),
    ).toThrow(TypeError);
    expect(() => new ArrayPlaybackQueue(items, "missing")).toThrow(RangeError);
  });
});
