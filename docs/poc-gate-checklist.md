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
test relays a 128 MiB synthetic object alongside three concurrent streams that
are cancelled after their first chunks; it asserts a working-set increase under
48 MiB and that all fake-CDN connections close. The recorded run peaked at
1.9 MiB above baseline.

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
