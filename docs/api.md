# API reference

The canonical API contract is the generated
[`openapi.json`](openapi.json), produced by FastAPI from
`backend/app/main.py`. It is checked against the live generated schema in CI;
do not edit it by hand. To regenerate and verify:

```powershell
python -B tools/docs/openapi_reference.py
python -B tools/docs/openapi_reference.py --check
```

All paths are same-origin under `/api` except health checks. Query parameter
defaults and validation limits are defined in OpenAPI.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health/live` | Process liveness. |
| `GET` | `/health/ready` | Process readiness; makes no provider call. |
| `GET` | `/api/search` | Search or discovery with query, creator, tags, mode, order, and pagination. |
| `GET` | `/api/creator/{username}` | Look up normalized creator metadata. |
| `GET` | `/api/media/{media_id}` | Fetch normalized media metadata without resolved sources. |
| `GET` | `/api/media/{media_id}/source` | Resolve a safe playback descriptor; quality is `auto`, `hd`, or `sd`, and `supportsHls` reports native browser capability. |
| `GET` | `/api/stream/{media_id}` | Stream a media ID; accepts `Range` and optional `quality=auto|hd|sd` and `hls`. |
| `GET` | `/api/stream/{media_id}/hls/{resource_token}` | Relay an opaque short-lived VOD HLS resource handle from a rewritten playlist. |
| `GET` | `/api/tags/suggest` | Suggest tags for a query prefix. |

The stream endpoint does not accept arbitrary URL parameters. A successful
stream may return `200` or `206`; unsatisfiable ranges use `416`. Error
responses use the API's normalized envelope where applicable. Provider-backed
routes return `503 provider_unavailable` when no provider is configured. The
default deployment keeps the provider disabled; see
[architecture status](architecture.md#api-and-provider-state).

HLS resource routes accept only server-issued opaque tokens and never accept
upstream URLs. HLS is disabled by default. When enabled, unsupported live,
encrypted, and low-latency playlists are never forwarded: playback falls back
to MP4 when available, otherwise the API returns a normalized
`unsupported_media` error.

The source descriptor schema is intentionally public and excludes the
provider's internal target and required upstream headers. Canonical response
models and parameter schemas are defined in the generated OpenAPI document.
There are currently no `/api/session*` routes.
