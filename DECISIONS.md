# M1-C01 Contracts

- **C01-D1 — Runtime configuration:** `APP_ENV` is the required environment-only setting for the backend core. Accepted values are `development`, `test`, and `production`; startup fails when it is absent or invalid. Later chunks add their own configuration only when required.
- **C01-D2 — Canonical models:** API model attributes serialize with camelCase aliases. `MediaItem` requires `id` and `title`; remaining descriptive metadata is optional or an empty collection when absent. `MediaSource` exposes `playbackUrl` and optional `mimeType`; extra fields are forbidden so internal source targets cannot leak through serialization.
- **C01-D3 — Error envelope:** Categories use stable snake_case values with this HTTP mapping: `invalid_request`/`invalid_media_id` 400, `unauthorized` 401, `forbidden` 403, `not_found` 404, `unsupported_media` 415, `range_not_satisfiable` 416, `rate_limited`/`local_rate_limited` 429, `upstream_authentication_failed`/`provider_error`/`connection_interrupted` 502, `provider_unavailable` 503, `upstream_timeout` 504, and `internal_error` 500. Envelopes contain `category`, `message`, `correlationId`, and optional `retryAfter` seconds.
- **C01-D4 — Health and schema:** Both health endpoints return `{"status":"ok"}` without contacting an upstream. FastAPI-generated OpenAPI explicitly includes canonical schemas that are not yet used by non-health routes.

# M1-C03 Observability Contracts

- **C03-D1 — Request correlation:** Generate a fresh UUID for every request; do not trust a caller-supplied correlation ID. Store it in request/context-local state and return it as `X-Correlation-ID` and, for errors, as `correlationId`.
- **C03-D2 — Log output and redaction:** Emit structured JSON to stdout only. Log route templates rather than raw URLs, never request headers or bodies, and redact authorization/bearer values, cookies, session fields, credentials, and sensitive signed-URL query parameters.
- **C03-D3 — Initial metric registry:** Predeclare the stream metrics named by the implementation plan (`stream_requests_total`, `stream_bytes_forwarded_total`, `stream_active_connections`, `stream_first_byte_ms`, `stream_upstream_errors_total`) plus `direct_vs_relay_ratio`, referenced by the resolver plan. The registry is in-process, has no label dimensions, and stores histogram count/sum/maximum only. `browser_player_errors` remains excluded under G4.

# M1-C04 Frontend API Contracts

- **C04-D1 — API transport:** Frontend requests use origin-relative paths, with per-request `AbortSignal` cancellation; absolute and protocol-relative URLs are rejected. The client does not contain provider-specific hosts or credentials.
- **C04-D2 — Frontend errors:** Backend error categories pass through unchanged when the shared envelope is valid. `network_error`, `malformed_response`, and `request_cancelled` describe client-side failures; malformed envelope/JSON data is not silently treated as a backend category.
- **C04-D3 — Type source:** Canonical TypeScript API models are generated from the backend OpenAPI model schemas and checked for exact drift. No new API endpoints are introduced in this chunk.

# M2-C01 Upstream Auth & Transport Contracts

- **C01-D1 — Token lifetime and refresh:** Upstream auth tokens are held in memory only, with a TTL and refresh leeway; refreshes are serialized so concurrent callers share a single in-flight refresh.
- **C01-D2 — Failure classification:** Upstream outcomes map to stable application categories without leaking provider credentials or raw auth headers into exception text. A 401 triggers a single refresh attempt before the request is retried; 400/404/416 are terminal assertions, while 429/5xx paths are retried with bounded exponential backoff and `Retry-After` when present.
- **C01-D3 — Transport boundary:** The upstream transport owns connect/read timeout controls and handles provider connectivity, timeout, and retry behavior; it never exposes raw upstream auth values to the browser or logs.

# M2-C02 RedGIFs Mapping Contracts

- **C02-D1 — Canonical mapping boundary:** The RedGIFs adapter converts upstream JSON to canonical backend models only; raw upstream fields such as provider-specific payload keys, signed URLs, or auth headers are never exposed to application code or browser responses.
- **C02-D2 — Recorded provider contract:** The adapter must satisfy the reusable `ProviderContract` for authentication, media lookup, creator lookup, search, tag suggestions, and source resolution using fixture-backed payloads, so the live dependency remains isolated until O6 is cleared.
- **C02-D3 — Tolerant normalization:** Missing optional metadata is dropped to null/empty values, and malformed records are skipped rather than crashing the whole result set; the adapter raises provider-level application errors only for actual upstream faults or unsupported responses.

# M3-C01 Relay Security Contracts

- **C01-D1 — Fail-closed upstream validation:** Relay targets must be HTTPS, host allowlisted via `UPSTREAM_ALLOWED_HOSTS`, and resolve only to public, non-private addresses. Localhost, loopback, private, link-local, multicast, unspecified, and reserved IPs are rejected before any fetch occurs.
- **C01-D2 — Redirect handling:** Redirects are not followed by default for upstream relay targets; future stream code must explicitly opt into redirect handling only when the target remains allowlisted and safe.
- **C01-D3 — Configured allowlist:** The setting defaults to an empty list, so an unset or blank allowlist fails closed rather than allowing untrusted upstream hosts.

# M3-C04 Relay Contracts

- **C04-D1 — Stream variant:** The relay accepts only the validated `quality=auto|hd|sd` enum in addition to the media ID path and Range header. The resolver returns `/api/stream/{id}?quality=...` for relay-bound sources so all seek requests resolve the selected variant; arbitrary URLs remain unsupported.
- **C04-D2 — Re-resolution:** A relay open retries source resolution once after an upstream 401 or an explicit expired-signature 403. A plain 403 is terminal and is not bypassed. Internal resolved targets share the resolver's short-lived RAM cache with source descriptors and are invalidated before the retry.
- **C04-D3 — Relay transport:** The HTTP client does not follow redirects, validates HTTPS targets against the explicit allowlist before opening, pins each connection to the public DNS addresses validated for that target, uses bounded raw chunks and independent connect/header/idle/total timeouts, and closes upstream responses on completion or downstream cancellation, including termination before the first body chunk. Stream responses default to `Cache-Control: no-store`.

# M3-C02 Range Semantics Contracts

- **C02-D1 — Single-range behavior:** Closed, open-ended, and suffix byte ranges are accepted. Multi-range headers are treated as no Range per G2; malformed or unsatisfiable ranges produce 416 when the object size is known, with `Content-Range: bytes */<size>`. If size is unknown, the upstream response semantics are retained.
- **C02-D2 — Downstream response headers:** Only `Content-Type`, `Content-Length`, `Content-Range`, `Accept-Ranges`, `ETag`, `Last-Modified`, and `Cache-Control` are eligible for forwarding. Header names are normalized; malformed values are omitted; a 200 response that ignored Range must not retain `Content-Range`. If upstream omits `Cache-Control`, the downstream default is `no-store`.

# M3-C05 Stream Limits & Metrics Contracts

- **C05-D1 — Per-client stream slots:** Enforce `MAX_ACTIVE_STREAMS_PER_IP` in the relay API before source resolution or upstream opening. Its initial configurable default is 3 pending load-based tuning in M6-C03. A slot remains held until the downstream response completes or is cancelled, and local cap failures use `local_rate_limited` with HTTP 429 and `Retry-After: 1`.
- **C05-D2 — Proxy trust:** Use `X-Forwarded-For` only when the immediate peer matches `TRUSTED_PROXY_IPS`; walk the chain from the trusted peer and select the nearest untrusted address. Invalid chains fall back to the socket peer.
- **C05-D3 — Relay metric updates:** Increment request and upstream-error counters at route/open and body-failure boundaries; count yielded body bytes, observe time to first nonempty body chunk, and maintain the active-connection gauge with acquired stream slots. Metrics remain process-local and unlabeled.

# M3-C06 Streaming POC Contracts

- **C06-D1 — Development-only fixture path:** The native-video proof page is a Vite development entry explicitly excluded from production Rollup inputs. Its test API and fixture-upload/fault controls live only under `backend.tests`, use a port-scoped loopback fake CDN, and are not registered in the production application.
- **C06-D2 — Gate evidence:** Browser playback is exercised with a WebM clip generated and kept in browser memory. The relay memory test uses deterministic synthetic bytes; compliance monitors cover the browser session and repository while playback is running. Live provider use remains gated by O6.

# M4-C03 Playback Recovery Contracts

- **C03-D1 — Relay error diagnosis:** Native media errors do not expose the relay's structured error envelope. For a relay playback URL only, the player may make one diagnostic `Range: bytes=0-0` request after a native media error, read a non-success error envelope, and immediately cancel any successful response body. Direct playback URLs are never probed; no endpoint or upstream URL contract changes.
- **C03-D2 — Bounded recovery:** Re-resolve once for upstream authentication expiry and try one alternate quality for unsupported media. Plain forbidden and not-found errors are terminal Unavailable states with no retry or bypass; rate limits display `Retry-After` when the API response is available and only retry after explicit user action.
- **C03-D3 — Player actions:** Retry restarts source resolution; Skip releases the current media and emits an intent without navigating the queue; Open is shown only for a credential-free HTTPS URL. Queue navigation remains in M4-C05.

# M4-C04 Player Controls Contracts

- **C04-D1 — Keyboard map:** Space toggles play/pause; Left/Right seek by 5 seconds; Up/Down adjust volume by 0.05; M toggles mute; L toggles loop; F toggles fullscreen; ? opens shortcut help; N/P/R/V/Escape emit next/previous/retry/favorite/close intents. F is fullscreen and V is favorite. M4-C05 wires next/previous to the queue; favorite remains intent-only.
- **C04-D2 — Focus and playback authority:** Player shortcuts do not override text-entry or interactive control targets, except Escape remains available to close. The native video element remains authoritative for playback and the controls act on its media properties/events.

# M4-C05 Queue and Prefetch Contracts

- **C05-D1 — Queue navigation:** The queue is array-backed and RAM-only. Random navigation prefers unseen items, excludes the current item when alternatives exist, and falls back to any other item when all alternatives have been seen.
- **C05-D2 — Bounded prefetch:** Metadata stays with queue entries. The current item's source is resolved by the player; only the immediate next item's source descriptor may be resolved ahead and reused once. No non-current media stream is requested, and prepared descriptors for items no longer current/next are discarded.
- **C05-D3 — End and close behavior:** Native looping remains controlled by the video element. Ended playback advances only when autoplay is enabled and a next item exists; otherwise the player remains ended. Closing reports the current scroll position and returns focus to the opener.

# M5-C01 Search Context Contracts

- **C01-D1 — Query parity:** The frontend parser follows the backend token normalization contract; shared JSON vectors are exercised by both frontend and backend tests. Creator tokens embedded in query text are normalized into `q`; an explicit creator filter uses the existing `creator` parameter, while tags remain repeated `tags` parameters.
- **C01-D2 — Search lifecycle:** Search metadata and item maps are held in RAM only. A new query aborts and supersedes the previous request; page requests are sequential and deduplicate items by ID. Failed or superseded requests do not replace already loaded items.

# M5-C02 Search Controls Contracts

- **C02-D1 — Search filters:** Search order is limited to trending/latest/top/score; page size accepts integers 1–100 and defaults to 20.
- **C02-D2 — Tag suggestions:** Autocomplete starts at two characters after a 250 ms debounce. New input aborts and supersedes older work; malformed API responses and non-cancellation failures are surfaced to the user.