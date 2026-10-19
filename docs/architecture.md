# Architecture and implementation status

## Runtime boundaries

The production package described by `deploy/docker-compose.yml` has two
services:

- **Browser/Nginx:** serves the built Svelte frontend, terminates externally
  provisioned TLS, and proxies `/api/` to the backend. It forwards Range
  headers without response or temporary-file buffering.
- **FastAPI backend:** owns the provider boundary, source resolution, ID-based
  stream relay, upstream-target validation, per-IP stream concurrency limit,
  error normalization, and process-local metrics. It runs as a non-root user
  with a read-only root filesystem and ephemeral `/tmp`.

The API relay accepts a media ID and the `auto|hd|sd` quality selector; it
does not accept arbitrary upstream URLs. It validates HTTPS destinations
against `UPSTREAM_ALLOWED_HOSTS`, uses bounded async streaming, supports
single byte ranges, and returns `Cache-Control: no-store`. Provider
authentication and internal source targets must remain server-side.

When `ENABLE_HLS=true`, the source resolver selects a VOD HLS source only
when the browser reports native HLS support. Same-origin playlist rewriting
issues short-lived opaque resource handles for nested playlists, media
segments, and initialization maps. Each referenced upstream URL is retained
server-side and validated when fetched; privileged headers are not forwarded
across origins. Live/event, encrypted, low-latency, and other unsupported
URI-bearing playlist features are never forwarded; playback falls back to
MP4 when available and returns `unsupported_media` when it is not.

The browser owns search and player UI state, favorites, seen IDs, history, and
settings in RAM. State is lost on reload. Privacy Mode is locked ON. No
backend session API or browser persistence layer is currently implemented.

## API and provider state

The API routes currently implemented are listed in [the API reference](api.md)
and machine-readable [OpenAPI document](openapi.json). Provider construction is
disabled by default. Setting `UPSTREAM_PROVIDER=redgifs` and mounting a raw
token file through `REDGIFS_TOKEN_FILE` wires the existing RedGIFs adapter into
application state at startup; startup reads the token locally and makes no
provider request. The explicit deployment overlay is
`deploy/docker-compose.provider.yml`. This wiring has not been validated
against the live provider and does not resolve O6. Do not mistake a healthy
process or successful image build for a usable live-provider deployment.

V1 temporary session state lives only in frontend RAM and is lost on page
reload. Backend `/api/session*` endpoints are optional future functionality,
not part of the v1 API or architecture (D16). No backend session routes are
implemented.

## Security and operational boundaries

- CORS is same-origin by default. Configured origins must be explicit HTTP(S)
  origins; credentials and wildcards are not enabled.
- CSP and browser security headers are applied to API and production-served
  documents.
- Nginx is the sole trusted forwarded-IP peer in the provided Compose network.
- Active stream concurrency is capped per client IP; there is no general API
  rate limiter or hosted access-control layer.
- Metrics are process-local and emitted as a structured stdout snapshot at
  graceful shutdown. They are not served from a metrics endpoint or stored by
  the application.
- TLS certificate and key files are mounted read-only from paths outside the
  image. They must not be committed or included in build context.

The [runbook](runbook.md) covers startup checks, failure response, and
rollback. The [privacy statement](privacy.md) explains what the no-download
checks do and do not prove. Live upstream use is gated by O6; hosted/public
release is blocked by O6/O7/O8.
