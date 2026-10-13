import { describe, expect, it } from "vitest";

import {
  formatDuration,
  sanitizeMediaItems,
  shouldLoadMore,
} from "../../src/utils/resultGrid";

describe("result grid utils", () => {
  it("formats durations for hours and minutes", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(3661)).toBe("01:01:01");
    expect(formatDuration(Number.NaN)).toBe("—");
  });

  it("filters out invalid items without breaking the grid", () => {
    const items = [
      { id: "ok", title: "Valid item", duration: 42 },
      { id: "bad" },
      null,
      undefined,
      { id: "also-ok", title: "Another" },
    ];

    expect(sanitizeMediaItems(items)).toEqual([
      { id: "ok", title: "Valid item", duration: 42 },
      { id: "also-ok", title: "Another" },
    ]);
  });

  it("allows loading only when there is more data and the grid is idle", () => {
    expect(shouldLoadMore({ hasMore: true, loading: false })).toBe(true);
    expect(shouldLoadMore({ hasMore: true, loading: true })).toBe(false);
    expect(shouldLoadMore({ hasMore: false, loading: false })).toBe(false);
  });
});
