# Project State

> Checkpoint only. Chain: REQUIREMENTS.md → ARCHITECTURE.md → IMPLEMENTATION_PLAN.md → this file → code + tests.
> Milestone and chunk IDs use IMPLEMENTATION_PLAN numbering (6 milestones, 36 chunks).

## Architecture Version
- **v1.2 — quality-preserving relay path.** The relay playback URL carries only the validated quality enum so Range requests reuse the `/source` selection without accepting arbitrary URL targets (2026-10-08).
- Implementation progress: **13 of 36 chunks** (35 unconditional + 1 conditional).
- Any architecture change must be logged under *Important Architecture Decisions* and bump this version. No silent changes.

## Current Milestone
**M3: Streaming Relay (POC Gate)**

## Current Chunk
**M3-C05: Stream concurrency limits and relay metrics**
- Status: pending.
- Depends on: M3-C04, M1-C03.
- Handoff: implement per-IP stream caps and relay metric updates; do not add those limits to the relay transport itself.

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

## Upcoming Chunks
**M1:** Complete. The configured CI stages pass locally; a GitHub-hosted workflow run remains pending.

- **M2 Adapter & Resolution:** C01 auth + transport · C02 media lookup/mapper · C03 search · C04 creator + tags · C05 resolver + `/source`
- **M3 Relay (POC gate):** C01 SSRF guardrails · C02 Range semantics · C03 fake CDN · C04 stream relay · C05 concurrency limits (current) · C06 POC page + gate
- **M4 Player:** C01 state machine · C02 MediaPlayer + E2E rig · C03 failure recovery · C04 controls/keyboard · C05 overlay/queue/prefetch
- **M5 Discovery & Session:** C01 query parser/search store · C02 SearchBar · C03 grid/infinite scroll · C04 RAM stores · C05 favorites/seen/history · C06 app integration · C07 a11y/E2E · C08 backend sessions *(conditional)*
- **M6 Hardening & Release:** C01 headers/CORS/CSP · C02 log-leak audit · C03 load tuning · C04 deploy/proxy · C05 full no-download compliance run · C06 docs/runbook

Hard gates: **M3-C06** must pass before any M4-C02 or full UI work. **M6-C05** blocks release.

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

## Known Issues
No implementation defects are currently known. Remaining document-level issues:
1. **Section references don't match.** ARCHITECTURE and PLAN cite requirement sections up to roughly §70 (e.g. the POC gate, error taxonomy, session TTL values, metric names). The uploaded REQUIREMENTS.md has 29 sections and doesn't contain those items. Confirm which document is the source of truth.
2. **Session conflict.** REQUIREMENTS lists `/api/session*` endpoints (§12) and expired-session cleanup (§19, §27). ARCHITECTURE (O1) and the PLAN default to frontend-only state with backend sessions conditional (M5-C08). Needs explicit resolution before M5.
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
- Highest-priority tests:
  - M3-C06 POC gate (play/pause/seek/retry/next; zero media files; flat relay memory; upstream closes on cancel).
  - M6-C05 full no-download scenario (**release-blocking**).
- Planned suites: backend unit/integration/contract (recorded fixtures, live opt-in), fake provider + fake CDN, frontend unit/component, browser E2E (from M4-C02), schema-drift check, storage-API lint.

## Open Decisions
O5 is resolved; other gates remain open and use their listed defaults until resolved.

| Gate | Question | Blocks | Default |
|---|---|---|---|
| O5 | `playbackUrl` naming; stream relay-only; quality carried on `/source` | Resolved in M1-C01 and completed by M3-C04 | Adopt D10 |
| O6 | Upstream terms, rate limits, permitted use | Live use in M2-C02, M3-C06 live smoke, any hosted release | Recorded fixtures only |
| O3 / O4 | Direct-vs-relay privacy trade-off; HLS in v1 | M2-C05, M3-C04 | Conservative classifier (relay default); MP4 only |
| O1 / O10 | Backend sessions in v1? Privacy Mode behavior | M5-C04, M5-C08 | Frontend-only; Privacy Mode locked ON (see Known Issue 2) |
| O12 | Browser support matrix | M4-C02 E2E | Latest evergreen desktop + mobile |
| G1 | Local rate-limit error category | M3-C05 | Add `LOCAL_RATE_LIMITED` |
| G2 | Multi-range `Range` header | M3-C02 | Treat as no Range |
| G3 | Definition of "seen" | M5-C05 | Mark when playback begins |
| G4 | Reporting path for `browser_player_errors` | M6-C02 | Not implemented |
| O11 / O13 | Cache/session/limit values; metrics exposure | M6-C02, M6-C03 | From load tests; stdout only |
| O7 / O8 | Hosted access control; audience gating | Hosted release | Private/trusted network only |

Also open, defaults in ARCHITECTURE: O2 (multi-worker sessions), O9 (deep-linkable URLs).

## Last Handoff
- **Date:** 2026-10-08
- **Done:** Completed M3-C04: media-ID relay endpoint with a validated quality selector, safe Range forwarding, bounded streaming, and upstream cleanup on disconnect.
- **Next:** Implement M3-C05 stream concurrency limits and relay metrics; the relay currently has no concurrency cap.
- **Watch:** Known Issues 1 and 2 before M5. Do a live upstream spike only after O6 is cleared.
- **On each chunk completion:** move it to *Completed Chunks* with test status, advance *Current Chunk*, and log any decision changes.