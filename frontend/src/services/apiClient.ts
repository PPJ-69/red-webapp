import { ApiError, mapErrorResponse, mapNetworkError } from "./errors";

export interface RequestOptions {
  signal?: AbortSignal;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(options: { baseUrl?: string; fetcher?: typeof fetch } = {}) {
    this.baseUrl = (options.baseUrl ?? "").replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? globalThis.fetch.bind(globalThis);
  }

  async get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(path, { method: "GET", signal: options.signal });
  }

  async post<T>(
    path: string,
    body: unknown,
    options: RequestOptions = {},
  ): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: options.signal,
    });
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!path.startsWith("/") || path.startsWith("//")) {
      throw new TypeError("API paths must be origin-relative.");
    }

    if (init.signal?.aborted) {
      throw mapNetworkError(init.signal.reason, init.signal);
    }

    let response: Response;
    try {
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        ...init,
        headers,
      });
    } catch (error: unknown) {
      throw mapNetworkError(error, init.signal ?? undefined);
    }

    if (!response.ok) {
      throw await mapErrorResponse(response);
    }

    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError(
        "malformed_response",
        "The server returned invalid JSON.",
        { status: response.status },
      );
    }
  }
}

export const apiClient = new ApiClient();
