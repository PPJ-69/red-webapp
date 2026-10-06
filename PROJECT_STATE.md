# Project State

> Checkpoint only. Chain: REQUIREMENTS.md → ARCHITECTURE.md → IMPLEMENTATION_PLAN.md → this file → code + tests.
> Milestone and chunk IDs use IMPLEMENTATION_PLAN numbering (6 milestones, 36 chunks).

## Architecture Version
- **v1 baseline.** ARCHITECTURE.md carries no version tag; this is the first checkpoint (2026-10-02).
- Implementation progress: **0 of 36 chunks** (35 unconditional + 1 conditional).
- Any architecture change must be logged under *Important Architecture Decisions* and bump this version. No silent changes.

## Current Milestone
**M1: Foundations & Compliance Harness**
Exit gate: CI green; the harness catches a deliberate violation and reports zero writes on an idle app.

## Current Chunk
**M1-C01: Backend core, error envelope, canonical models, health**
- Status: not started. Gate **O5** applies (default: adopt D10 unless told otherwise).
- Delivers: env-only config validated at startup; one error envelope (category, message, correlation ID, optional retry-after); canonical models (`MediaItem`, `MediaSource` with `playbackUrl`, `Creator`, `SearchResult`, `SearchQuery`); `GET /health/live` and `/health/ready` (no upstream calls); generated OpenAPI.
- Depends on: nothing. Out of scope: upstream calls, sessions, rate limits, any non-health endpoint.

## Completed Chunks
None.

## Upcoming Chunks
**M1 (next):** C02 provider interface + fake provider · C03 redacting logging/metrics · C04 frontend typed API client · C05 no-persistence compliance harness (high risk, build early) · C06 CI/lockfiles/storage-API lint. C02–C05 can run in parallel after C01.

- **M2 Adapter & Resolution:** C01 auth + transport · C02 media lookup/mapper · C03 search · C04 creator + tags · C05 resolver + `/source`
- **M3 Relay (POC gate):** C01 SSRF guardrails · C02 Range semantics · C03 fake CDN · C04 stream relay (highest risk) · C05 concurrency limits · C06 POC page + gate
- **M4 Player:** C01 state machine · C02 MediaPlayer + E2E rig · C03 failure recovery · C04 controls/keyboard · C05 overlay/queue/prefetch
- **M5 Discovery & Session:** C01 query parser/search store · C02 SearchBar · C03 grid/infinite scroll · C04 RAM stores · C05 favorites/seen/history · C06 app integration · C07 a11y/E2E · C08 backend sessions *(conditional)*
- **M6 Hardening & Release:** C01 headers/CORS/CSP · C02 log-leak audit · C03 load tuning · C04 deploy/proxy · C05 full no-download compliance run · C06 docs/runbook

Hard gates: **M3-C06** must pass before any M4-C02 or full UI work. **M6-C05** blocks release.

## Important Architecture Decisions
- **Stream, don't store.** No DB, media or thumbnail cache, or persisted app state. RAM-only, TTL-bound.
- Backend owns provider auth. Tokens and signed upstream details never reach the browser or logs.
- Provider interface + RedGIFs adapter isolate all upstream shapes (D2, D3).
- Media Resolver is the reliability boundary. `/api/media/{id}/source` is the only place direct-vs-relay is communicated (`playbackUrl`). `/api/stream/{id}` is relay-only, ID-only, no URL parameter, no redirect (D10).
- Relay: bounded chunks, single Range, 200/206/416, upstream aborted on client disconnect, host allowlist + private-IP rejection, concurrency caps. Basic security pulled forward into M3 (D5, D14).
- Short-TTL RAM source cache in the resolver (D9).
- MP4-first; HLS behind a flag and deferred (D11). Kill switches: `ENABLE_DIRECT_MEDIA`, `ENABLE_HLS`.
- Native `<video>`; player store derives state from video events (D1).
- Frontend is authoritative for favorites/seen/history in v1, behind a `Store` interface; no browser storage APIs (D7, D8).
- POC-first ordering; compliance harness runs in CI from M1.
- Same-origin deployment by default (D12).

## Known Issues
No code exists yet, so no defects. Document-level issues to resolve:
1. **Section references don't match.** ARCHITECTURE and PLAN cite requirement sections up to roughly §70 (e.g. the POC gate, error taxonomy, session TTL values, metric names). The uploaded REQUIREMENTS.md has 29 sections and doesn't contain those items. Confirm which document is the source of truth.
2. **Session conflict.** REQUIREMENTS lists `/api/session*` endpoints (§12) and expired-session cleanup (§19, §27). ARCHITECTURE (O1) and the PLAN default to frontend-only state with backend sessions conditional (M5-C08). Needs explicit resolution before M5.
3. **Repo layout differs.** REQUIREMENTS §25 (`api/providers/streaming/sessions/models`) vs PLAN (`domain/upstream/services/security/observability`). REQUIREMENTS allows changes; confirm the PLAN layout.
4. **Milestone numbering differs** across docs (REQUIREMENTS M0–M8, ARCHITECTURE M1–M7, PLAN M1–M6). Use PLAN numbering.

## Tests
- Written / passing: none.
- Highest-priority tests:
  - M1-C05 harness self-check (detects a deliberate media/DB/settings file; zero writes on idle boot).
  - M3-C06 POC gate (play/pause/seek/retry/next; zero media files; flat relay memory; upstream closes on cancel).
  - M6-C05 full no-download scenario (**release-blocking**).
- Planned suites: backend unit/integration/contract (recorded fixtures, live opt-in), fake provider + fake CDN, frontend unit/component, browser E2E (from M4-C02), schema-drift check, storage-API lint.

## Open Decisions
None resolved yet. Defaults apply if unresolved.

| Gate | Question | Blocks | Default |
|---|---|---|---|
| O5 | `playbackUrl` naming; stream relay-only; quality carried on `/source` | M1-C01 | Adopt D10 |
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
- **Date:** 2026-10-02
- **Done:** Reviewed REQUIREMENTS, ARCHITECTURE, IMPLEMENTATION_PLAN and created this checkpoint. No code, scaffolding, or tests exist.
- **Next:** Confirm the O5 default (or change it), then start M1-C01. Build M1-C05 (harness) early.
- **Watch:** Known Issues 1 and 2 before M5. Do a live upstream spike only after O6 is cleared.
- **On each chunk completion:** move it to *Completed Chunks* with test status, advance *Current Chunk*, and log any decision changes.