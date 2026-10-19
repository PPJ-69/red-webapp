# M3 Streaming POC Gate Checklist

The POC page is served by Vite at `/poc.html` and is deliberately excluded from
the production build. Its API is a test-only app backed by the loopback fake
CDN; it is not part of `backend.app.main` and must never be deployed.

## Automated fake-upstream gate

Run from the repository root:

```powershell
$env:APP_ENV = "test"
.\.venv\Scripts\python.exe -m unittest frontend.tests.e2e.poc_spec
.\.venv\Scripts\python.exe -m unittest backend.tests.performance.test_relay_memory
npm.cmd --prefix frontend run build
if (Test-Path frontend\dist\poc.html) { throw "The POC page leaked into production output." }
```

The browser test creates a short WebM clip in browser memory, streams it through
the local API and fake CDN, then verifies native play, pause, forward/backward
seek, injected-upstream-failure retry, next-item switching, and disconnect
cleanup. Browser storage instrumentation is installed before playback. The
filesystem monitor observes the repository for the entire test. The memory
test relays a 128 MiB synthetic object alongside sixteen concurrent streams
that are cancelled after their first chunks; it asserts a working-set increase
under 48 MiB and that all fake-CDN connections close. The original three-stream
recorded run peaked at 1.9 MiB above baseline; the M6-C03 run is recorded below.

The automated test harness needs the checked-in Python environment and its
Playwright Chromium browser. It starts and stops its own test API, CDN, and Vite
server.

## Local manual smoke

For interactive inspection with the same fake upstream:

1. Start the test-only API app and fake CDN with
   `.\.venv\Scripts\python.exe -m backend.tests.run_poc`.
2. In another terminal start Vite with
   `$env:POC_API_ORIGIN = "http://127.0.0.1:8001"; npm.cmd --prefix frontend run dev`.
3. Open `http://127.0.0.1:5173/poc.html`; play, pause, seek in both directions,
   inject a server error and retry, switch items, then stop and disconnect.
4. Confirm `/__poc/stats` returns zero active CDN and relay connections after
   stopping. While playing, run
   `.\.venv\Scripts\python.exe tools\compliance\browser_storage_check\check_browser_storage.py http://127.0.0.1:5173/poc.html --duration 20`
   and confirm it reports no violations.
5. Observe RSS during the large synthetic relay and confirm the memory test
   remains below its threshold. No media fixture is written to disk.

## Live-provider and direct-vs-relay notes

- **O6 blocks live-provider smoke:** upstream terms and permitted use have not
  been cleared. Do not use production provider credentials or live media for
  this gate. Record the operator, date, provider, and results here only after
  O6 is resolved and an approved live smoke is run.
- **O3 remains open:** the POC adapter supplies provider-auth headers, so the
  resolver classifies both test items as relay-required. This confirms the
  relay path only; it does not establish whether direct playback is preferable.
  Record any approved direct-vs-relay comparison here after O3 is resolved.
- A reverse-proxy seek/long-stream smoke is deferred to M6-C04; the Vite proxy
  used by the automated POC is only the local test proxy.

### Run record

| Date | Environment / upstream | Result | Notes |
|---|---|---|---|
| 2026-10-08 | Local loopback fake CDN | Browser E2E passed; 128 MiB RSS increase 1.9 MiB (<48 MiB); all CDN connections closed | Live-provider smoke blocked by O6; direct-vs-relay decision open under O3. |

## M6-C03 load, latency, and frontend measurements

Reproduce backend checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.performance.test_service_latency
.\.venv\Scripts\python.exe -m unittest backend.tests.performance.test_relay_memory
```

The latency scenario uses the fake provider for 100 sequential search and
uncached source-resolution samples, then the loopback fake CDN for 30 relay
first-byte samples. It excludes upstream outages and does not contact the live
provider. The memory scenario streams the deterministic 128 MiB object while
sixteen other CDN streams are held at their first chunks and then cancelled.
It measures process working-set increase and waits for every CDN connection to
close.

The frontend bundle and browser check can be reproduced with the checked-in
Playwright Node runtime:

```powershell
Set-Location frontend
& ..\.venv\Lib\site-packages\playwright\driver\node.exe node_modules\vite\bin\vite.js build
Set-Location ..
$env:PATH = (Resolve-Path .venv\Lib\site-packages\playwright\driver).Path + ';' + $env:PATH
.\.venv\Scripts\python.exe -m unittest frontend.tests.e2e.browse_play_flow_spec.BrowsePlayFlowBrowserTests.test_result_grid_thumbnails_load_as_the_viewport_approaches
```

The bundle check records Vite's gzip size for the production entry JavaScript.
The browser scenario renders 100 cards, confirms every thumbnail uses native
`loading="lazy"`, counts requests before scrolling, then scrolls to card 90 and
confirms its image request begins.

### M6-C03 run record

| Date | Environment / workload | Result | Decision / limitation |
|---|---|---|---|
| 2026-10-19 | Local Python test process, fake provider; 100 searches and 100 uncached resolutions | Search p95 0.03 ms (<1.5 s); source-resolution p95 0.04 ms (<1.0 s) | Synthetic provider only; does not model live upstream latency or rate limits. |
| 2026-10-19 | Loopback fake CDN; 30 sequential full relay opens | First-byte p95 8.94 ms (<1.5 s); all sampled connections closed | Synthetic loopback excludes WAN/provider outages. |
| 2026-10-19 | 128 MiB synthetic relay plus 16 concurrent streams cancelled after first chunk | RSS increase 4.0 MiB (<48 MiB); all CDN connections closed | Retain per-IP cap at 3: local memory passes, but O6 prevents evidence-based increases against actual provider capacity/rate limits. |
| 2026-10-19 | Vite production build, Chromium, 100 result thumbnails | Initial JavaScript 110.17 kB raw / 38.39 kB gzip (<250 kB); 39/100 thumbnails requested before scrolling; card 90 loaded after scrolling | Native lazy loading keeps offscreen image requests viewport-driven. |

The source-cache default is now 60 seconds and can be tuned with
`SOURCE_CACHE_TTL_SECONDS`. This shortens the previous five-minute stale-source
window; the fake-provider uncached-resolution p95 remains below target. The
provider's actual signed-URL lifetime is unverified while O6 remains open, so
the default remains configurable and must be revisited before live use. A
backend session cap is not applicable: backend sessions remain unimplemented
pending O1/O10; do not add a limit without resolving that scope gate.
