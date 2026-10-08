import { describe, expect, it } from "vitest";
import vectors from "../../../shared/fixtures/query_vectors.json";

import {
  parseSearchQuery,
  queryForApi,
} from "../../src/utils/queryParser";

interface QueryVector {
  name: string;
  input: {
    query?: string;
    tags?: string[];
    creator?: string;
    mode?: string;
    page?: number;
    limit?: number;
  };
  expected: {
    query: string | null;
    tags: string[];
    mode: string;
    page: number;
    limit: number;
  };
}

describe("search query parser", () => {
  it.each(vectors as QueryVector[])(
    "matches backend normalization: $name",
    ({ input, expected }) => {
      const parsed = parseSearchQuery(input.query, input);

      expect({
        query: queryForApi(parsed) ?? null,
        tags: parsed.tags,
        mode: parsed.mode,
        page: parsed.page,
        limit: parsed.limit,
      }).toEqual(expected);
    },
  );

  it("emits normalized creator and tag chips", () => {
    const parsed = parseSearchQuery("cats #funny @Alice");

    expect(parsed.chips).toEqual([
      { type: "creator", value: "Alice" },
      { type: "tag", value: "funny" },
    ]);
  });
});
