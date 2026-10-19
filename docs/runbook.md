# Operational runbook

## Scope and release status

Use the Compose deployment only on a private, trusted network. O6 (provider
terms/rate limits), O7 (hosted access control), and O8 (audience gating) remain
release gates. Provider wiring is opt-in and disabled in the base Compose
stack; the explicit provider overlay reads a mounted token file and constructs
the existing adapter, but has not been validated against the live provider. A
healthy container only proves process health, not provider readiness. Do not
deploy publicly or enable live credentials until the
[upstream checklist](upstream-compliance-checklist.md) is approved and the
live integration is verified.

## Start and verify

From a clean deployment checkout, provision TLS files outside the repository
and create `deploy/.env` from `deploy/.env.example`. Set
`UPSTREAM_ALLOWED_HOSTS` only to approved provider/CDN hostnames, and set
`TLS_CERT_PATH` and `TLS_KEY_PATH` to readable host file paths. Do not display
or copy private key contents into logs or tickets.

From the repository root:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config --quiet
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up --build -d
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

The web service is published on ports 80 and 443. Port 80 redirects to HTTPS.
Check the externally visible certificate and web response using the configured
hostname:

```powershell
curl.exe -I https://<configured-hostname>/
```

Confirm the backend container reports healthy with `docker compose ps`. For
API readiness from inside the private network, use the existing health route:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health/ready', timeout=2).read().decode())"
```

This health check does not contact or validate the upstream provider. Do not
use live API requests as a smoke test until O6 and provider wiring are cleared.

## Diagnose incidents

Inspect bounded recent logs without dumping environment values or credentials:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail 200 backend web
docker stats --no-stream
```

Correlation IDs and normalized error categories are useful for support.
Application logs are redacted, but operators must still protect container
logs and never paste credentials, authorization headers, or signed URLs into
incident records. Metrics are process-local; `metrics_snapshot` is emitted to
backend stdout on graceful shutdown, not continuously served or persisted by
the application.

### Provider authentication failures

An `upstream_authentication_failed` or repeated provider error means the
provider request path is failing; it is not fixed by retrying indefinitely.
Check only the deployment's approved secret/configuration mechanism and
sanitized error category. The provider overlay reads a raw bearer token from a
mounted secret file; do not put token contents in `.env`. A `401` refresh
rereads that file once. Replace the mounted secret and restart the service if
the provider rejects the credential; disable live use and escalate if failures
continue.

### Rate limiting

- `local_rate_limited` is the local per-IP active-stream cap. Reduce parallel
  playback and retry after the supplied `Retry-After`; do not raise the cap
  based only on synthetic tests.
- `rate_limited` is an upstream/provider response. Honor `Retry-After`, reduce
  request volume, and stop live use if repeated. Do not bypass provider limits.

Provider capacity and terms have not been established (O6).

### Relay memory growth

Use `docker stats --no-stream` to compare backend memory over time and inspect
whether active playback is ending normally. The relay is designed for bounded
chunked streaming and cancellation cleanup; it is not a promise of constant
total process memory under arbitrary concurrency. If memory grows
continuously, restrict access/stop new playback, capture timestamps and
sanitized logs, then reproduce with the fake-CDN memory test before
restarting. Do not collect provider media or credentials as a diagnostic
artifact.

### Bandwidth saturation

The provided stack has a per-IP active-stream limit, not an aggregate
bandwidth quota or hosted access control. Check host and network utilization.
If saturated, reduce or stop playback and restrict the private network
audience. Do not expose the relay publicly or increase stream limits as a
mitigation; O6/O7/O8 must be resolved first.

### Provider format or schema changes

Stop live use when provider responses become malformed or playback begins
failing systematically. Preserve sanitized error categories and correlation
IDs, then update recorded fixtures and adapter contract tests only through the
provider review process. Do not commit live credentials, signed URLs, or
unapproved media samples. Re-run backend, browser, and no-download gates
before redeployment.

## Shutdown and rollback

Stop normally so Uvicorn can cancel requests, close upstream responses, and
emit its shutdown metrics snapshot:

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

For rollback, use a clean deployment checkout at the last reviewed commit;
do not alter a developer worktree or attempt to recover by adding data
volumes. Rebuild and start the previously reviewed revision with the same
externally managed TLS files and approved environment:

```powershell
git switch --detach <previous-reviewed-commit>
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up --build -d
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
```

If the previous revision cannot be identified or validated, stop the stack
instead of deploying an unreviewed image. The Compose stack mounts TLS files
only; it does not mount media or application-state volumes.

## Deployment validation still required

A successful local test run does not replace the deployment smoke. Before any
release, build and run the actual containers with an approved provider
configuration; verify TLS, health, repeated Range/seek behavior, unbuffered
streaming, graceful stream closure, and absence of application-created
artifacts. Docker/Nginx/TLS execution remains unverified locally, and live
provider verification is blocked until O6 is resolved and the opt-in wiring
has been validated.
