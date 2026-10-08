import { ApiClient, apiClient } from "./apiClient";

export type TagSuggestionRequest = (
  query: string,
  signal: AbortSignal,
) => Promise<string[]>;

export interface TagSuggestOptions {
  debounceMs?: number;
  minimumLength?: number;
}

export class TagSuggestService {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private controller: AbortController | undefined;
  private pendingResolve: ((suggestions: string[]) => void) | undefined;
  private generation = 0;

  constructor(
    private readonly requester: TagSuggestionRequest,
    private readonly debounceMs = 250,
    private readonly minimumLength = 2,
  ) {
    if (!Number.isFinite(debounceMs) || debounceMs < 0) {
      throw new RangeError("The autocomplete debounce must be nonnegative.");
    }
    if (!Number.isInteger(minimumLength) || minimumLength < 1) {
      throw new RangeError("The autocomplete minimum length must be positive.");
    }
  }

  suggest(query: string): Promise<string[]> {
    this.cancelCurrent();
    const normalized = query.trim();
    if (normalized.length < this.minimumLength) return Promise.resolve([]);

    const requestGeneration = ++this.generation;
    return new Promise<string[]>((resolve, reject) => {
      this.pendingResolve = resolve;
      this.timer = setTimeout(() => {
        this.timer = undefined;
        const controller = new AbortController();
        this.controller = controller;
        void Promise.resolve()
          .then(() => this.requester(normalized, controller.signal))
          .then(
          (suggestions) => {
            const result =
              requestGeneration !== this.generation ||
              controller.signal.aborted
                ? []
                : suggestions;
            if (this.generation === requestGeneration) {
              this.pendingResolve = undefined;
              this.controller = undefined;
            }
            resolve(result);
          },
          (error: unknown) => {
            if (
              requestGeneration !== this.generation ||
              controller.signal.aborted
            ) {
              resolve([]);
              return;
            }
            this.pendingResolve = undefined;
            this.controller = undefined;
            reject(error);
          },
          );
      }, this.debounceMs);
    });
  }

  cancel(): void {
    this.cancelCurrent();
    this.generation += 1;
  }

  private cancelCurrent(): void {
    if (this.timer !== undefined) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
    this.pendingResolve?.([]);
    this.pendingResolve = undefined;
    this.controller?.abort();
    this.controller = undefined;
  }
}

function createTagSuggestionRequest(
  client: ApiClient,
): TagSuggestionRequest {
  return async (query, signal) => {
    const params = new URLSearchParams({ q: query });
    const suggestions = await client.get<unknown>(
      `/api/tags/suggest?${params.toString()}`,
      { signal },
    );
    if (
      !Array.isArray(suggestions) ||
      !suggestions.every((suggestion) => typeof suggestion === "string")
    ) {
      throw new TypeError("Tag suggestions must be an array of strings.");
    }
    return suggestions;
  };
}

export function createTagSuggestService(
  client: ApiClient = apiClient,
  options: TagSuggestOptions = {},
): TagSuggestService {
  return new TagSuggestService(
    createTagSuggestionRequest(client),
    options.debounceMs ?? 250,
    options.minimumLength ?? 2,
  );
}

export const tagSuggestService = createTagSuggestService();
