import { writable, type Readable } from "svelte/store";

import type { MediaItem, SearchResult } from "../types/api";
import { ApiClient, apiClient } from "../services/apiClient";
import {
  parseSearchQuery,
  queryTextForApi,
  type ParsedSearchQuery,
  type QueryParserOptions,
} from "../utils/queryParser";

export interface SearchRequest {
  query: ParsedSearchQuery;
  order: string | null;
  page: number;
  limit: number;
}

export type SearchRequestHandler = (
  request: SearchRequest,
  signal: AbortSignal,
) => Promise<SearchResult>;

export interface SearchContextSnapshot {
  query: ParsedSearchQuery | null;
  order: string | null;
  loadedPages: readonly number[];
  itemsById: ReadonlyMap<string, MediaItem>;
  hasMore: boolean;
  loadingInitial: boolean;
  loadingMore: boolean;
  error: unknown | null;
}

export interface SearchContextStore extends Readable<SearchContextSnapshot> {
  getSnapshot(): SearchContextSnapshot;
  search(
    rawQuery: string | null | undefined,
    options?: QueryParserOptions & { order?: string | null },
  ): Promise<boolean>;
  loadNextPage(): Promise<boolean>;
  discard(): void;
}

const INITIAL_SNAPSHOT: SearchContextSnapshot = {
  query: null,
  order: null,
  loadedPages: [],
  itemsById: new Map(),
  hasMore: false,
  loadingInitial: false,
  loadingMore: false,
  error: null,
};

function mergeItems(
  currentItems: ReadonlyMap<string, MediaItem>,
  newItems: readonly MediaItem[],
): ReadonlyMap<string, MediaItem> {
  const merged = new Map(currentItems);
  for (const item of newItems) {
    if (!merged.has(item.id)) merged.set(item.id, item);
  }
  return merged;
}

export function createSearchRequestHandler(
  client: ApiClient = apiClient,
): SearchRequestHandler {
  return async (request, signal) => {
    const params = new URLSearchParams();
    const query = queryTextForApi(request.query);
    if (query !== undefined) params.set("q", query);
    for (const tag of request.query.tags) params.append("tags", tag);
    if (request.query.explicitCreator !== null) {
      params.set("creator", request.query.explicitCreator);
    }
    params.set("mode", request.query.mode);
    if (request.order !== null) params.set("order", request.order);
    params.set("page", String(request.page));
    params.set("limit", String(request.limit));
    return client.get<SearchResult>(`/api/search?${params.toString()}`, {
      signal,
    });
  };
}

export function createSearchContextStore(
  searcher: SearchRequestHandler = createSearchRequestHandler(apiClient),
): SearchContextStore {
  const store = writable<SearchContextSnapshot>(INITIAL_SNAPSHOT);
  let snapshot = INITIAL_SNAPSHOT;
  let activeController: AbortController | undefined;
  let generation = 0;

  function update(next: SearchContextSnapshot): void {
    snapshot = next;
    store.set(next);
  }

  function mergeResult(
    result: SearchResult,
    replace: boolean,
  ): ReadonlyMap<string, MediaItem> {
    return mergeItems(replace ? new Map() : snapshot.itemsById, result.items);
  }

  async function search(
    rawQuery: string | null | undefined,
    options: QueryParserOptions & { order?: string | null } = {},
  ): Promise<boolean> {
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    const requestGeneration = ++generation;
    const query = parseSearchQuery(rawQuery, options);
    const order = options.order ?? null;
    update({
      ...snapshot,
      query,
      order,
      hasMore: false,
      loadingInitial: true,
      loadingMore: false,
      error: null,
    });

    try {
      const result = await searcher(
        { query, order, page: 1, limit: query.limit },
        controller.signal,
      );
      if (requestGeneration !== generation || controller.signal.aborted) {
        return false;
      }
      update({
        query,
        order,
        loadedPages: [result.page],
        itemsById: mergeResult(result, true),
        hasMore: result.hasMore,
        loadingInitial: false,
        loadingMore: false,
        error: null,
      });
      return true;
    } catch (error) {
      if (requestGeneration !== generation || controller.signal.aborted) {
        return false;
      }
      update({
        ...snapshot,
        loadingInitial: false,
        loadingMore: false,
        error,
      });
      return false;
    }
  }

  async function loadNextPage(): Promise<boolean> {
    if (
      snapshot.query === null ||
      !snapshot.hasMore ||
      snapshot.loadingInitial ||
      snapshot.loadingMore
    ) {
      return false;
    }
    const controller = activeController;
    if (!controller || controller.signal.aborted) return false;

    const requestGeneration = generation;
    const query = snapshot.query;
    const order = snapshot.order;
    const page = (snapshot.loadedPages.at(-1) ?? 0) + 1;
    update({ ...snapshot, loadingMore: true, error: null });

    try {
      const result = await searcher(
        { query, order, page, limit: query.limit },
        controller.signal,
      );
      if (requestGeneration !== generation || controller.signal.aborted) {
        return false;
      }
      update({
        ...snapshot,
        loadedPages: [...snapshot.loadedPages, result.page],
        itemsById: mergeResult(result, false),
        hasMore: result.hasMore,
        loadingMore: false,
        error: null,
      });
      return true;
    } catch (error) {
      if (requestGeneration !== generation || controller.signal.aborted) {
        return false;
      }
      update({ ...snapshot, loadingMore: false, error });
      return false;
    }
  }

  function discard(): void {
    activeController?.abort();
    activeController = undefined;
    generation += 1;
    update(INITIAL_SNAPSHOT);
  }

  return {
    subscribe: store.subscribe,
    getSnapshot: () => snapshot,
    search,
    loadNextPage,
    discard,
  };
}

export const searchContextStore = createSearchContextStore();
