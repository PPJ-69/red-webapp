// Generated from backend OpenAPI canonical schemas by scripts/check_schema_drift.py.

export type Creator = {
  id: string;
  username: string;
  displayName?: string | null;
  profileImageUrl?: string | null;
};

export type ErrorCategory = "invalid_request" | "invalid_media_id" | "unauthorized" | "forbidden" | "not_found" | "rate_limited" | "upstream_authentication_failed" | "provider_unavailable" | "provider_error" | "upstream_timeout" | "range_not_satisfiable" | "connection_interrupted" | "unsupported_media" | "internal_error";

export type ErrorEnvelope = {
  category: ErrorCategory;
  message: string;
  correlationId: string;
  retryAfter?: number | null;
};

export type MediaItem = {
  id: string;
  title: string;
  description?: string | null;
  creator?: Creator | null;
  tags?: string[];
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  thumbnailUrl?: string | null;
  posterUrl?: string | null;
  sources?: MediaSource[];
};

export type MediaSource = {
  playbackUrl: string;
  mimeType?: string | null;
  kind?: string | null;
  requiresRelay?: boolean | null;
  expiresAt?: unknown | null;
};

export type SearchQuery = {
  mode?: string;
  query?: string | null;
  tags?: string[];
  order?: string | null;
  page?: number;
  limit?: number;
};

export type SearchResult = {
  items: MediaItem[];
  page: number;
  limit: number;
  hasMore: boolean;
  total?: number | null;
};
