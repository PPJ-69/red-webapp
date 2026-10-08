export type SearchChip =
  | { type: "tag"; value: string }
  | { type: "creator"; value: string };

export interface ParsedSearchQuery {
  query: string | null;
  tags: string[];
  creators: string[];
  queryCreators: string[];
  explicitCreator: string | null;
  mode: string;
  page: number;
  limit: number;
  chips: SearchChip[];
}

export interface QueryParserOptions {
  tags?: readonly string[];
  creator?: string | null;
  mode?: string | null;
  page?: number | string | null;
  limit?: number | string | null;
}

const TOKEN_TRIM_CHARACTERS = /^[ "'`\[\](){}<>,;:]+|[ "'`\[\](){}<>,;:]+$/g;

function coerceInteger(value: number | string | null | undefined, fallback: number): number {
  if (value === null || value === undefined || typeof value === "boolean") {
    return fallback;
  }
  if (typeof value === "string" && !/^[+-]?\d+$/.test(value.trim())) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
}

function cleanToken(value: string): string {
  return value.replace(TOKEN_TRIM_CHARACTERS, "");
}

function tagName(value: string): string {
  return cleanToken(value).replace(/^#+/, "").trim();
}

function creatorName(value: string): string {
  const candidate = cleanToken(value);
  const lowered = candidate.toLowerCase();
  if (lowered.startsWith("@")) return cleanToken(candidate.slice(1));
  if (lowered.startsWith("user:")) return cleanToken(candidate.slice(5));
  if (lowered.startsWith("creator:")) return cleanToken(candidate.slice(8));
  return candidate;
}

function addUnique(values: string[], value: string): void {
  if (value && !values.includes(value)) values.push(value);
}

export function parseSearchQuery(
  rawQuery: string | null | undefined,
  options: QueryParserOptions = {},
): ParsedSearchQuery {
  const queryText = rawQuery ?? "";
  const textParts: string[] = [];
  const tags: string[] = [];
  const queryCreators: string[] = [];

  for (const piece of queryText.split(/\s+/u).flatMap((part) => part.split(","))) {
    const token = cleanToken(piece);
    if (!token) continue;
    const lowered = token.toLowerCase();
    if (token.startsWith("#")) {
      addUnique(tags, tagName(token));
    } else if (
      lowered.startsWith("@") ||
      lowered.startsWith("user:") ||
      lowered.startsWith("creator:")
    ) {
      addUnique(queryCreators, creatorName(token));
    } else {
      textParts.push(token);
    }
  }

  for (const tag of options.tags ?? []) {
    addUnique(tags, tagName(String(tag)));
  }
  const explicitCreator = options.creator
    ? creatorName(options.creator) || null
    : null;
  const creators = [...queryCreators];
  if (explicitCreator) addUnique(creators, explicitCreator);

  const query = textParts.join(" ");
  const mode =
    options.mode ??
    (query || tags.length > 0 || queryText || options.creator
      ? "search"
      : "trending");
  const page = Math.max(1, coerceInteger(options.page, 1));
  const limit = Math.max(1, Math.min(100, coerceInteger(options.limit, 20)));
  const chips: SearchChip[] = [
    ...creators.map((value) => ({ type: "creator" as const, value })),
    ...tags.map((value) => ({ type: "tag" as const, value })),
  ];

  return {
    query: query || null,
    tags,
    creators,
    queryCreators,
    explicitCreator,
    mode,
    page,
    limit,
    chips,
  };
}

export function queryForApi(query: ParsedSearchQuery): string | undefined {
  const parts = [
    ...(query.query === null ? [] : [query.query]),
    ...query.creators.map((creator) => `@${creator}`),
  ];
  return parts.length > 0 ? parts.join(" ") : undefined;
}

export function queryTextForApi(
  query: ParsedSearchQuery,
): string | undefined {
  const parts = [
    ...(query.query === null ? [] : [query.query]),
    ...query.queryCreators.map((creator) => `@${creator}`),
  ];
  return parts.length > 0 ? parts.join(" ") : undefined;
}
