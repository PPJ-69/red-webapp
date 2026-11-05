# Stream-First Media Browser

A Svelte/TypeScript frontend and FastAPI service for discovering and streaming
media in a browser. The approved design uses native browser playback, an
ID-based bounded relay, and temporary in-memory UI state rather than a
downloaded media library.

## Project status

This repository is at M6-C06, documentation and operational runbook. The
browser no-download gate passes locally and runs as a release-blocking CI
check. This does not make the current production package ready for live use:

- Provider construction is opt-in and disabled in the default Compose stack.
  The explicit provider Compose overlay enables the existing adapter, which
  obtains a short-lived API token from RedGIFs automatically. No live provider
  request or deployment smoke has been verified.
- Upstream terms, rate limits, and permitted use (O6) have not been cleared.
- Hosted access control and audience gating (O7/O8) are not implemented.
- V1 session state is held in frontend RAM and lost on reload. Backend
  session endpoints are optional future functionality, not a v1 requirement
  (D16).
- VOD HLS is opt-in and requires browser-native HLS support. Live/event,
  encrypted, and low-latency playlists are rejected; MP4 remains the fallback
  (D17).
- A real Docker/Nginx/TLS smoke has not been run in the local environment.

Do not use live provider credentials or deploy to the public internet until the
release gates in [the upstream checklist](docs/upstream-compliance-checklist.md)
and [the runbook](docs/runbook.md) are cleared.

## Run the app locally

Local development can browse live RedGIFs content. The frontend opens on the
trending feed and proxies API requests to the local backend. The test-only POC
with a fake provider remains available for offline playback and browser tests.

### 1) Prerequisites

Install:

- Python 3.12+
- Node.js 22.12+
- npm
- Git

On Windows, use PowerShell for the commands below.

### 2) Get the repository

```powershell
git clone https://github.com/PPJ-69/red-webapp.git
cd red-webapp
```

### 3) Install dependencies

Backend dependencies:

```powershell
python -m pip install -r backend/requirements.lock
```

Frontend dependencies:

```powershell
npm.cmd --prefix frontend ci
```

### 4) Start the local API with RedGIFs

Open a terminal in the repository root and run:

```powershell
$env:APP_ENV = "development"
$env:UPSTREAM_PROVIDER = "redgifs"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The backend obtains a short-lived RedGIFs API token from its temporary
authentication endpoint; no provider token needs to be supplied or stored.
Starting the app and browsing sends requests to RedGIFs. Follow the provider's
terms and rate limits; this local setup does not approve public deployment or
bypass the release gates listed below.

Confirm the API is responding:

```powershell
curl.exe http://127.0.0.1:8000/health/ready
```

### 5) Start the frontend

Open a second terminal in the repository root and run:

```powershell
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000` by default, so
the browser can reach the live backend without extra environment variables.

### 6) Open the app

Browse to:

```text
http://127.0.0.1:5173
```

The trending grid should load on open. Search text, `#tags`, and `@creators`
use the live provider.

### Offline POC

To run the isolated fake-provider POC instead, start it with
`python -m backend.tests.run_poc` on port 8001 and set
`$env:POC_API_ORIGIN = "http://127.0.0.1:8001"` before starting Vite. This is
for offline playback and browser testing, not live browsing.

### 7) Stop the app

Stop both commands with `Ctrl+C` in their respective terminals.

### 8) Production/private deployment

This repository also includes a private Compose deployment for a trusted network, but it is not approved for public or live-provider deployment. See:

- [deploy/README.md](deploy/README.md)
- [docs/runbook.md](docs/runbook.md)
- [docs/upstream-compliance-checklist.md](docs/upstream-compliance-checklist.md)

Do not enable live provider use until O6/O7/O8 are cleared.

## Repository map

- `frontend/`: Svelte application, browser tests, and generated frontend types.
- `backend/app/`: FastAPI API, provider boundary, resolver, relay, security, and
  observability.
- `backend/tests/`: provider fakes, relay fixtures, and backend test suites.
- `tests/compliance/`: release-blocking no-download scenario and harness checks.
- `docs/`: architecture summary, API reference, privacy statement, operational
  runbook, and release checklists.
- `deploy/`: production Dockerfiles, Compose topology, Nginx configuration,
  and private-deployment instructions.

## Development and verification

Use Python 3.12+ and Node.js 22.12+ with npm. From the repository root:

```powershell
python -m pip install -r backend/requirements.lock
npm.cmd --prefix frontend ci
$env:APP_ENV = "test"
python -B -m unittest discover -s backend/tests -t . -v
python -B -m unittest tests.documentation.test_docs -v
python -B -m unittest tests.compliance.test_harness_selfcheck -v
```

Frontend verification:

```powershell
npm.cmd --prefix frontend run check
npm.cmd --prefix frontend run test:unit
npm.cmd --prefix frontend run check:schema
npm.cmd --prefix frontend run build
```

The complete CI workflow also installs Chromium and runs the browser E2E and
release-blocking no-download scenario. The API's generated OpenAPI document is
committed at [`docs/openapi.json`](docs/openapi.json); regenerate it with
`python -B tools/docs/openapi_reference.py` and check it with
`python -B tools/docs/openapi_reference.py --check`.

## Documentation

- [Architecture and implemented boundaries](docs/architecture.md)
- [API reference](docs/api.md) and [generated OpenAPI](docs/openapi.json)
- [Privacy statement and limitations](docs/privacy.md)
- [Operational runbook](docs/runbook.md)
- [Upstream compliance and release checklist](docs/upstream-compliance-checklist.md)
- [Security review evidence](docs/security-review.md)
- [Private deployment instructions](deploy/README.md)
