# M6-C05 Security and Privacy Release Gate

**Review date:** 2026-10-19  
**Scope:** Repository controls and automated tests for SSRF, credential/log
exposure, relay concurrency, CORS/CSP, metadata XSS, resource exhaustion, and
no-download behavior. This is an implementation-gate review, not a third-party
penetration test.

## Checklist

| Control | Result | Evidence and scope |
|---|---|---|
| SSRF / open relay | PASS | `backend/app/security/validation.py` fails closed on non-HTTPS, non-allowlisted, credential-bearing, and private/reserved destinations. `backend/tests/unit/test_upstream_target_validation.py` exercises allowlist, DNS, localhost, private IP, and scheme rejection. The stream API accepts only a media ID and validated quality, not arbitrary URLs. |
| Provider credential and signed-URL leakage | PASS | `backend/app/observability/logging.py` redacts authorization, cookies, signed URL values, and session fields. `backend/tests/security/test_log_leak_scenarios.py` checks canaries across 401/403/429, timeout, disconnect, and malformed provider data; it also verifies metrics contain no labels. |
| Relay resource limits | PASS, scoped | `MAX_ACTIVE_STREAMS_PER_IP` gates streams before upstream resolution and releases slots on completion, failure, or cancellation. `backend/tests/unit/test_limits.py` and `backend/tests/integration/test_stream_limits.py` cover client-IP trust and slot behavior. `backend/tests/performance/test_relay_memory.py` verifies bounded memory with a 128 MiB relay plus 16 cancelled streams. This is a per-IP concurrency limit, not a general API request-rate limiter. |
| CORS and browser policy | PASS | `backend/tests/integration/test_security_headers.py` verifies exact-origin allow/deny, method/header preflight restrictions, and CSP/security headers on API and stream responses. Empty CORS configuration remains same-origin-only. |
| Metadata XSS | PASS, scoped | `frontend/tests/e2e/xss_metadata_spec.py` renders hostile title, description, tag, and creator metadata as inert text under CSP and verifies no injected handler executes. |
| No-download and browser persistence | PASS, automated gate | `tests/compliance/test_full_scenario.py` runs 10 unique searches, plays and seeks 100 distinct in-memory WebM items, scrolls 320 thumbnails, toggles a favorite, saves a search, checks browser storage/cookies, restarts the browser, and compares recursive media/database/settings scans while monitoring filesystem writes. The fixture remains in browser memory and API responses are intercepted locally. CI runs this test as a release-blocking stage. |
| Production provider wiring | IMPLEMENTED, NOT LIVE-VERIFIED | `UPSTREAM_PROVIDER=redgifs` constructs the existing adapter from a mounted token file at startup. The base Compose stack remains disabled, and startup makes no provider call. Live terms, credentials, and API behavior remain unverified under O6. |

## Release limitations

- O6 remains unresolved: the live provider's terms, rate limits, and permitted
  use have not been cleared. The full scenario uses only intercepted browser
  responses, the test API, and fake CDN fixtures; it is not live-provider
  evidence.
- O7/O8 remain unresolved: hosted access control and audience gating are not
  implemented. This review does not approve public or untrusted-network
  deployment.
- O1/O10 are resolved: v1 state is frontend RAM-only and is lost on reload;
  backend session endpoints are optional future functionality (D16).
- Provider wiring is implemented but remains opt-in and has not been tested
  against the live service. The base Compose stack leaves it disabled; this
  does not resolve O6 or establish live-provider readiness.
- Docker/Nginx execution is not available in the local verification
  environment. M6-C04 verifies proxy configuration and loopback Range behavior,
  but a real container/TLS smoke remains a deployment prerequisite.

## Full-scenario run record

The local Chromium run on 2026-10-19 completed 10 unique searches, played 100
distinct media IDs, observed 200 completed seeks and 100 ranged stream
requests, and fetched 320 unique thumbnails while scrolling. It reported zero
browser storage API accesses, zero cookies, zero filesystem-monitor violations,
and no new media, thumbnail, database, or settings artifacts across the
monitored project, temporary, and existing application-data roots. Media bytes
were generated and retained in browser memory; API responses were intercepted
in the test browser.

**Gate decision:** The automated, repository-scoped checks above pass where
marked. The release is **not approved for live-provider operation** until O6
is cleared and the opt-in wiring is validated against an approved live
integration. Hosted/public release additionally remains blocked on O7/O8. No
live provider credentials or media were used for this review.
