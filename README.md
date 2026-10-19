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
  The explicit provider Compose overlay reads a mounted token file and wires
  the existing adapter, but no live provider request or deployment smoke has
  been verified.
- Upstream terms, rate limits, and permitted use (O6) have not been cleared.
- Hosted access control and audience gating (O7/O8) are not implemented.
- Backend session endpoints in `REQUIREMENTS.md` conflict with the approved
  frontend-only RAM state default (O1/O10); do not claim full requirements
  compliance.
- A real Docker/Nginx/TLS smoke has not been run in the local environment.

Do not use live provider credentials or deploy to the public internet until the
release gates in [the upstream checklist](docs/upstream-compliance-checklist.md)
and [the runbook](docs/runbook.md) are cleared.

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
