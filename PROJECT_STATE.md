# Project State

> Checkpoint only. Chain: REQUIREMENTS.md → ARCHITECTURE.md → IMPLEMENTATION_PLAN.md → this file → code + tests.
> Milestone and chunk IDs use IMPLEMENTATION_PLAN numbering (6 milestones, 36 chunks).

## Architecture Version
- **v1.2 — quality-preserving relay path.** The relay playback URL carries only the validated quality enum so Range requests reuse the `/source` selection without accepting arbitrary URL targets (2026-10-08).
- Implementation progress: **32 of 36 chunks** (35 unconditional + 1 conditional).
- Any architecture change must be logged under *Important Architecture Decisions* and bump this version. No silent changes.

## Current Milestone
**M6: Hardening & Release**

## Current Chunk
**M6-C04: Deployment packaging and reverse proxy**
- Status: pending.
- Depends on: M3-C04, M6-C01, M6-C02, M6-C03.
- Handoff: add the minimal runtime image and reverse-proxy configuration; verify Range/seek behavior through the proxy and graceful stream shutdown.

## Completed Chunks
- **M1-C01:** Backend core, error envelope, canonical models, health. Gate O5 resolved using D10. 14 unit/integration tests pass.
- **M1-C02:** Provider interface, internal source target, fake provider, and reusable provider contract. 12 additional unit/contract tests pass; internal target excluded from API models and schemas.
- **M1-C03:** Request correlation middleware, stdout-only structured JSON logging with secret redaction, and predeclared in-process metrics registry. 12 focused observability tests pass.
- **M1-C04:** Frontend shell, cancellable typed API client, backend error mapper, generated OpenAPI types, and schema-drift check. Svelte check, 23 Vitest tests, schema tests, and production build pass.
- **M1-C05:** Live filesystem/browser-storage compliance monitors and self-check. Detects media, database, settings writes including child-process writes; detects browser storage API access and service-worker registration. Seven self-check tests pass.
- **M1-C06:** GitHub Actions CI, frontend storage-API lint, backend/frontend lockfiles, and dependency scans. Storage/lockfile gate tests pass; npm and Python dependency scans report no known vulnerabilities.
- **M2-C01:** Upstream auth manager, single-flight refresh behavior, bounded retry transport, and upstream error classification. Ten focused tests pass; token values stay out of exception text.
- **M2-C02:** RedGIFs adapter + canonical media mapper using fixture-backed payloads; provider contract suite passes and raw upstream fields remain isolated behind canonical models.
- **M2-C03:** Search/listing pipeline complete. Added query normalization, `/api/search` endpoint, provider-backed search service, and focused tests for normalization and API behavior. Targeted backend tests pass.
- **M2-C04:** Creator lookup and tag-suggestion endpoints complete. Added backend creator/tag services, API routes, and validation tests using the existing fake provider.
- **M2-C05:** Media resolver and source descriptor endpoint complete. Added source cache, resolver classification, `/api/media/{id}/source`, and integration/unit coverage.
- **M3-C01:** Relay security guardrails complete. Added `UPSTREAM_ALLOWED_HOSTS`, strict HTTPS/private-range validation, and a focused validation unit suite that rejects allowlist violations and localhost/private targets.
- **M3-C02:** Pure Range parsing and downstream response semantics complete. Added named tests for closed/open/suffix ranges, malformed and multi-range handling, upstream 200/206/416 behavior, safe response headers, and unknown/known object sizes.
- **M3-C03:** Added a loopback-only Range-capable fake CDN, a 272-byte AVI fixture, bounded synthetic responses, status/latency/disconnect/auth/signature/header/range faults, connection counters, a shared test context manager, and fake-provider CDN targeting.
- **M3-C04:** Added the ID-based range relay, bounded async HTTP transport, timeout/error handling, close-on-cancel behavior, source-resolution caching/invalidation, quality-preserving relay descriptors, and connect-time pinning to validated public IPs. The relay allowlist is strictly fail-closed when blank.
- **M3-C05:** Added per-IP active-stream caps before source resolution, trusted-proxy-aware client IP derivation, local 429 error envelopes, slot release on completion/failure/cancellation, and request/bytes/first-byte/active/upstream-error metrics. Updated frontend error typing and mapping for `local_rate_limited`.
- **M3-C06:** Added the development-only native-video page, test-only loopback CDN API, browser E2E for play/pause/seeking/failure retry/item switching, runtime browser/filesystem compliance assertions, and a 128 MiB concurrent/cancelled relay RSS test. The page is excluded from production output.
- **M4-C01:** Added typed player states/events, strict transition validation, native-media-event mapping, an in-memory Svelte-compatible player store, restoration of play/pause intent across seeking and buffering, and RETRY/SKIP/NEXT/LOOP actions.
- **M4-C02:** Added typed source resolution with safe playback URL validation, cancellable native MediaPlayer source lifecycle, loading/buffering overlays, the temporary player shell, and Chromium E2E using the fake provider/CDN. The client binds browser `fetch` correctly; stale `emptied` events during item switches no longer reset the new source.
- **M4-C03:** Added a typed playback-recovery decision table, quality/auth retry limits, item-level unavailable/rate-limit/error states, Retry/Skip/Open actions, and error-envelope diagnosis for failed relay playback via a one-byte Range request. Added one-shot expired-signature fake-CDN behavior for browser coverage; forbidden sources remain terminal with no retry or bypass.
- **M4-C04:** Added accessible native playback controls, keyboard shortcut routing with focus-aware typing suppression, keyboard help, and emitted player intent events. Fullscreen covers the player section so controls remain available while fullscreen. Queue and favorite behavior remain unwired.
- **M4-C05:** Added array-backed in-memory queue navigation with seen-aware random selection and one-item source-descriptor prefetch. Ended playback honors loop/autoplay/bounds; close restores the opener and scroll position.
- **M5-C01:** Added a typed query parser with creator/tag chips and mode normalization, shared frontend/backend vectors, and an in-memory search context with deduplication, cancellation, sequential pagination, and failure-safe retention.
- **M5-C02:** Added accessible search filters and tag suggestions with a 250 ms debounce, minimum length, cancellation, and surfaced errors; search parameters are covered through the fake-provider browser flow.
- **M5-C03:** Added the responsive ResultGrid/ResultCard display layer with lazy thumbnails, duration/creator metadata, a current-item indicator, and a single-flight IntersectionObserver sentinel. Invalid items are filtered before render so a single bad payload cannot block the grid, and the grid emits only display-level open events without wiring player/favorite/seen behavior. Targeted grid/context tests pass.
- **M5-C04:** Added the `Store` abstraction, RAM-only session and settings stores, and a `SettingsPanel` privacy indicator that keeps Privacy Mode locked ON. No browser storage or persistence is used; targeted store tests pass.
- **M5-C05:** Wired favorites into result cards/player keyboard controls, seen state to native playback start, random navigation to the session seen set, and recent/saved search flows. Added on-demand Favorites metadata hydration and canonical `GET /api/media/{id}` without source descriptors; state remains frontend RAM-only. Backend suite, frontend checks, and session-feature browser coverage pass.
- **M5-C06:** Integrated discovery-backed playback, previous/next/random, creator and tag exploration, favorites/settings navigation, and user-facing errors. Closing restores scroll and focus; Escape/G returns to results. The fake-provider browse/play browser flow passes.
- **M5-C07:** Completed accessibility and responsive work: semantic landmarks/results states, labelled native modal with keyboard focus, visible focus, reduced motion, and constrained-width layouts. Added keyboard, mobile/infinite-scroll, accessibility, and browser-restart privacy checks. All 15 browser E2E tests pass.
- **M6-C01:** Added CSP and browser security headers to backend responses and Vite-served documents, plus exact-origin CORS allowlisting via `CORS_ALLOWED_ORIGINS` (empty defaults to same-origin; no wildcard or credentials). Added hostile-metadata browser coverage and API/stream/CORS integration tests.
- **M6-C02:** Added structured stdout metrics snapshots on graceful shutdown, updated the direct-vs-relay gauge as the direct share of uncached source resolutions, and verified canary-free logs for upstream 401/403/429, timeout, disconnect, and malformed-item failures. Metrics remain unlabeled; `browser_player_errors` remains excluded under G4.
- **M6-C03:** Added repeatable fake-provider/CDN latency checks, expanded the relay memory/cancellation scenario to sixteen concurrent cancelled streams, made the source-cache TTL configurable with a 60-second default, and verified production JS size plus viewport-driven thumbnail requests in Chromium. Local p95/memory/bundle targets pass; live-provider capacity and signed-URL lifetime remain unverified under O6.

## Upcoming Chunks
**M1:** Complete. The configured CI stages pass locally; a GitHub-hosted workflow run remains pending.

- **M2 Adapter & Resolution:** C01 auth + transport · C02 media lookup/mapper · C03 search · C04 creator + tags · C05 resolver + `/source`
- **M3 Relay (POC gate):** C01 SSRF guardrails · C02 Range semantics · C03 fake CDN · C04 stream relay · C05 concurrency limits · C06 POC page + gate
- **M4 Player:** Complete — C01 state machine · C02 MediaPlayer + E2E rig · C03 failure recovery · C04 controls/keyboard · C05 overlay/queue/prefetch
- **M5 Discovery & Session:** C01 query parser/search store · C02 SearchBar · C03 grid/infinite scroll · C04 RAM stores (done) · C05 favorites/seen/history (done) · C06 app integration (done) · C07 a11y/E2E (done) · C08 backend sessions *(conditional; pending O1/O10)*
- **M6 Hardening & Release:** C01 headers/CORS/CSP (done) · C02 log-leak audit (done) · C03 load tuning (done) · C04 deploy/proxy · C05 full no-download compliance run · C06 docs/runbook

Hard gates: the M3-C06 live-provider smoke remains gated on O6; M4-C02 used only the fake provider/CDN. **M6-C05** blocks release.

## Important Architecture Decisions
- **Stream, don't store.** No DB, media or thumbnail cache, or persisted app state. RAM-only, TTL-bound.
- Backend owns provider auth. Tokens and signed upstream details never reach the browser or logs.
- Provider interface + RedGIFs adapter isolate all upstream shapes (D2, D3).
- Media Resolver is the reliability boundary. `/api/media/{id}/source` is the only place direct-vs-relay is communicated (`playbackUrl`). `/api/stream/{id}` is relay-only, accepts only a validated quality enum (never an upstream URL), and does not redirect (D10).
- Relay: bounded chunks, single Range, 200/206/416, upstream aborted on client disconnect, host allowlist + private-IP rejection with DNS address pinning, concurrency caps. Basic security pulled forward into M3 (D5, D14).
- Short-TTL RAM source cache in the resolver (D9).
- MP4-first; HLS behind a flag and deferred (D11). Kill switches: `ENABLE_DIRECT_MEDIA`, `ENABLE_HLS`.
- Native `<video>`; player store derives state from video events (D1).
- Frontend is authoritative for favorites/seen/history in v1, behind a `Store` interface; no browser storage APIs (D7, D8).
- POC-first ordering; compliance harness runs in CI from M1.
- Same-origin deployment by default (D12).
- Browser documents and backend responses receive restrictive CSP/security headers; CORS remains same-origin unless exact origins are explicitly configured. Development-only Vite CSP permits eval for test tooling; production headers remain strict.
- Resolver source descriptors and internal targets use a configurable 60-second default TTL (`SOURCE_CACHE_TTL_SECONDS`); per-IP relay concurrency remains three pending live-provider capacity evidence.
- Metrics remain process-local, unlabeled, and stdout-only; `metrics_snapshot` logs the complete snapshot at graceful shutdown. `direct_vs_relay_ratio` reports the direct fraction of successful uncached source classifications; G4's `browser_player_errors` remains excluded.

## Known Issues
No implementation defects remain from the completed-chunk audit. Outstanding document/source-of-truth issues:
1. **Requirement references drift.** ARCHITECTURE and PLAN cite sections through roughly 70 (including error taxonomy, session TTLs, and metrics), while REQUIREMENTS.md has 29 sections. The documented acceptance criteria cannot be traced reliably to the current requirements.
2. **Session scope conflicts with product requirements.** REQUIREMENTS.md calls for `/api/session*` endpoints and session identification/TTL/cleanup. The approved plan makes the backend service conditional (M5-C08) and defaults to frontend-only state. Current code follows the plan default, so it does not implement the session API/cleanup described by REQUIREMENTS. O1/O10 must be explicitly resolved before claiming full requirements compliance; do not add M5-C08 without that decision.
3. **Repo layout differs.** REQUIREMENTS §25 (`api/providers/streaming/sessions/models`) vs PLAN (`domain/upstream/services/security/observability`). REQUIREMENTS allows changes; confirm the PLAN layout.
4. **Milestone numbering differs** across docs (REQUIREMENTS M0–M8, ARCHITECTURE M1–M7, PLAN M1–M6). Use PLAN numbering.


## Tests
- **M1-C01:** 14 unit and integration tests passing, including startup configuration validation, canonical model contracts, full error-category mapping, health routes, OpenAPI schemas, and no-write startup check.
- **M1-C03:** 12 tests pass for canary redaction, correlation in logs/error responses, stdout-only logging, and metric registry operations. Full backend suite: 38 tests passing.
- **M1-C04:** OpenAPI-to-TypeScript drift check and deliberate-model-mutation test pass (2 tests); Svelte check passes; 23 Vitest tests pass; production build succeeds.
- **M1-C05:** Seven compliance tests pass: media/database/settings writes, child-process writes, committed-fixture exclusion, app-data root discovery, zero artifacts during idle backend boot, browser storage API access, and service-worker registration.
- **M1-C06:** Frontend type-check, 23 Vitest tests, storage-API lint and fixture test, lockfile freshness/mutation tests, schema-drift checks, and production build pass. All 38 backend tests and seven compliance tests pass; idle filesystem scenario reports zero writes; browser monitor self-check passes. `npm audit` and `pip-audit` report no known vulnerabilities.
- **M3-C02:** 17 focused range-semantics tests pass. The pure module performs no network I/O or endpoint wiring.
- **M3-C03:** 13 focused fake-CDN/provider tests pass; the full backend suite passes (104 tests). Fault coverage includes all injected statuses and non-status behaviors, byte ranges, synthetic streaming, and client disconnect counter cleanup.
- **M3-C04:** Full backend suite passes (134 tests). Relay integration covers full/ranged/repeated-seek/416, upstream errors and redirects, signature refresh, auth-header isolation, large-stream cancellation (including before iteration), total/idle timeouts, DNS pinning, target rejection, quality propagation, and the no-full-buffer guard.
- **M3-C05:** Full backend suite passes (144 tests); focused concurrency, trusted-proxy, slot-cleanup, configuration, and metric assertions pass. Frontend type-check, error-mapping unit test, and schema-drift check pass for the added error category.
- **M3-C06:** Browser E2E passes using the generated in-memory WebM fixture; verifies play, pause, forward/backward seek, injected upstream failure and retry, next item, zero browser-storage/filesystem violations, and closed relay/CDN connections. Full backend suite passes (145 tests). The 128 MiB synthetic relay peaks at 1.9 MiB RSS growth against a 48 MiB limit while three concurrent streams are cancelled. Production build omits `poc.html`; live smoke remains blocked by O6.
- **M4-C01:** All 70 frontend unit tests pass, including valid/invalid state-event combinations, startup/seek/stall/end/error sequences, play/pause restoration, loop/retry/skip/next actions, subscriber updates, and a static no-clock/no-polling guard. Svelte type-check passes.
- **M4-C02:** All 78 frontend unit tests pass, including source URL validation, ID encoding, quality propagation, and abort-signal forwarding. Svelte type-check and production build pass. Chromium E2E passes for metadata load, native play, buffering/canplay transitions, item switching, and upstream connection cleanup using only the fake provider/CDN.
- **M4-C03:** All 91 frontend unit tests pass, including recovery decisions, bounded auth/quality retries, relay-only error diagnosis, and timing messages. Svelte type-check and production build pass. Five Chromium E2E cases pass for source re-resolution, fake-CDN expired-signature recovery, 404 unavailable/no-retry, 429 timing/manual retry, and skip behavior. Full backend suite passes (145 tests).
- **M4-C04:** All 118 frontend unit tests pass, including the selected keyboard map, modifier/repeat handling, and typing-focus suppression including contenteditable variants. Svelte type-check, production build, storage policy check, and Chromium E2E pass for mute, volume, speed, loop, fullscreen, keyboard seek, shortcut-help dialog, and accessible control names. Existing lifecycle and recovery browser suites also pass.
- **M4-C05:** Added an array-backed in-memory queue with previous/next/random, seen-aware selection and change notifications; a player overlay with navigation/close; and one-item source-descriptor prefetch that never requests non-current media bytes. Skip and keyboard navigation now use the queue; ended behavior honors loop/autoplay/queue bounds, and close restores scroll position and opener focus. All 127 frontend unit tests pass; type-check, build, storage policy check, and all seven fake-provider lifecycle/recovery/controls/navigation Chromium tests pass.
- **M5-C01:** Added a typed query parser with creator/tag chips and mode normalization, shared fixtures checked against the backend normalizer, and an in-memory search context with page loading, deduplication, cancellation/supersession, and failure-safe retention of loaded items. Frontend type-check, all 143 frontend unit tests, production build, storage policy check, the backend suite, and shared-vector parity tests pass.
- **M5-C02:** Added accessible SearchBar and SearchFilters components, normalized chip previews, trending/latest/top/score ordering, 1–100 page size, and tag suggestions with a 250 ms debounce, two-character minimum, active-request cancellation, and surfaced errors. Wired search submissions through the M5-C01 context; tests verify serialized query parameters and that typing does not trigger player shortcuts. All 148 frontend unit tests, type-check, production build, storage policy check, and the fake-provider browser search test pass.
- **M5-C03:** Added the responsive ResultGrid/ResultCard display layer with lazy thumbnails, duration/creator metadata, a current-item indicator, and a single-flight IntersectionObserver sentinel. Invalid items are filtered before render so a single bad payload cannot block the grid, and the grid emits only display-level open events without wiring player/favorite/seen behavior. Frontend Svelte check and the targeted grid/search-context tests pass.
- **Completed-chunk audit (2026-10-19):** Backend suite passes (148 tests); frontend Svelte check has 0 warnings/errors, 164 Vitest tests pass, storage/lock/schema checks pass, and production build succeeds. All 15 browser E2E tests pass. All 7 compliance harness tests and browser-monitor self-check pass; idle backend boot reports zero writes. Audit fixes restored disabled CI suites, reintroduced mobile/infinite-scroll coverage, wired search pagination into the UI, fixed POC failure-fixture metadata, and removed redundant dialog/autofocus warnings.
- **M6-C01:** Full backend suite passes (153 tests), including explicit CORS origin/method/header allow/deny coverage and security-header assertions on API/stream responses. All 164 frontend unit tests, Svelte check, and production build pass. All 16 Chromium E2E tests pass, including hostile metadata rendering and static-document header assertions; production preview serves the strict CSP without `unsafe-eval`.
- **M6-C02:** Full backend CI suite passes (160 tests). Added canary leak scenarios for upstream 401/403/429, stream timeout and disconnect, and malformed provider data; verifies credentials, signed URL query values, cookies, and session contents appear neither in logs nor metric labels. Verified the shutdown JSON metrics snapshot and direct/relay ratio calculations.
- **M6-C03:** Full backend suite passes (164 tests), including 100-sample fake-provider search/source-resolution benchmarks, 30 loopback relay first-byte samples, and the 128 MiB relay with 16 concurrent cancelled streams (4.0 MiB RSS growth, <48 MiB). Chromium confirms 39/100 lazy thumbnails requested before scrolling and loads card 90 when scrolled into view. Vite production entry JavaScript is 38.39 kB gzip (<250 kB). Source-cache TTL is configurable, default 60 seconds; per-IP cap remains 3 pending live-provider capacity evidence. Backend sessions remain N/A under O1/O10.
- Outstanding gates:
  - M3-C06 approved live-provider smoke after O6 is resolved; fake-provider implementation and E2E are complete.
  - M6-C05 full no-download scenario (**release-blocking**).
- Planned suites: backend unit/integration/contract (recorded fixtures, live opt-in), fake provider + fake CDN, frontend unit/component, browser E2E (lifecycle, recovery, controls, navigation, search), schema-drift check, storage-API lint.

## Open Decisions
O5 is resolved; other gates remain open and use their listed defaults until resolved.

| Gate | Question | Blocks | Default |
|---|---|---|---|
| O5 | `playbackUrl` naming; stream relay-only; quality carried on `/source` | Resolved in M1-C01 and completed by M3-C04 | Adopt D10 |
| O6 | Upstream terms, rate limits, permitted use | Live use in M2-C02, M3-C06 live smoke, any hosted release | Recorded fixtures only |
| O3 / O4 | Direct-vs-relay privacy trade-off; HLS in v1 | M2-C05, M3-C04 | Conservative classifier (relay default); MP4 only |
| O1 / O10 | Backend sessions in v1? Privacy Mode behavior | M5-C04, M5-C08 | Frontend-only; Privacy Mode locked ON (see Known Issue 2) |
| O12 | Browser support matrix | M4-C02 E2E | Latest evergreen desktop + mobile |
| G2 | Multi-range `Range` header | M3-C02 | Treat as no Range |
| G3 | Definition of "seen" | M5-C05 | Mark when playback begins |
| G4 | Reporting path for `browser_player_errors` | M6-C02 | Not implemented |
| O11 / O13 | Cache/session/limit values; metrics exposure | M6-C02, M6-C03 | Local cache/stream values recorded; backend session cap pending O1/O10; metrics stdout-only |
| O7 / O8 | Hosted access control; audience gating | Hosted release | Private/trusted network only |

Also open, defaults in ARCHITECTURE: O2 (multi-worker sessions), O9 (deep-linkable URLs).

## Last Handoff
- **Date:** 2026-10-19
- **Done:** Completed M6-C03 load, memory, and limit tuning; the full backend suite passes (164 tests).
- **Next:** M6-C04 deployment packaging and reverse-proxy behavior. Resolve the REQUIREMENTS/PLAN session-scope conflict before claiming full product-requirement compliance; M5-C08 remains conditional on O1/O10.
- **Watch:** Live-provider use remains gated by O6. Preserve RAM-only metadata and no-browser-storage behavior unless O1/O10 is explicitly resolved.
- **On each chunk completion:** move it to *Completed Chunks* with test status, advance *Current Chunk*, and log any decision changes.
