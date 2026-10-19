# Private deployment

> **Not approved for live use:** The base Compose stack keeps the provider
> disabled. An explicit overlay can wire the existing adapter to a mounted
> token file, but this has not been live-verified. O6 (provider terms/rate
> limits), O7 (hosted access control), and O8 (audience gating) remain release
> gates. This is private-network packaging, not approval for public or
> live-provider deployment.

The Compose stack builds the production frontend into an unprivileged Nginx
image and runs the API in a separate, non-root Python image. The API port is
only exposed to the private Compose network. Both container root filesystems
are read-only; the backend writes logs to stdout and keeps resolver state in
memory. No volume is used for media, thumbnails, or application state.

1. Copy `.env.example` to `.env`, set `UPSTREAM_ALLOWED_HOSTS` to the explicit
   provider/CDN hostnames required by the adapter, and set `TLS_CERT_PATH` and
   `TLS_KEY_PATH` to the host paths for a certificate and private key. The
   certificate must cover the hostname used by clients. Do not put private
   keys in this repository.
2. Ensure the certificate and key are readable by the unprivileged Nginx
   container user (UID 101).
3. From this directory, build and start the stack with
   `docker compose -f docker-compose.yml up --build -d`.
4. Open the application over HTTPS. Port 80 only redirects to HTTPS. The
   reverse proxy forwards `Range`/`If-Range`, disables response buffering and
   temporary-file buffering for API streams, and allows up to 610 seconds
   between proxied reads. It replaces forwarded client-IP headers with the
   socket peer address; the backend trusts only the proxy's fixed Compose IP.
5. Stop with `docker compose -f docker-compose.yml down`. Uvicorn is allowed
   20 seconds to cancel outstanding requests and release stream responses;
   Docker gives the backend 30 seconds to finish shutdown.

`UPSTREAM_ALLOWED_HOSTS` is required and must contain only approved hosts.
Review the provider's terms and rate limits before live use. If the Compose
network subnet conflicts with the host network, change the subnet and both
fixed service addresses together, including `TRUSTED_PROXY_IPS`.

For full operational checks, failure response, rollback, and remaining
deployment-validation requirements, see the [runbook](../docs/runbook.md) and
[upstream compliance checklist](../docs/upstream-compliance-checklist.md).

The default stack explicitly sets `UPSTREAM_PROVIDER=disabled`. Only after O6
approval and the required live smoke, the opt-in overlay can be combined with
the base file using
`docker compose --env-file .env -f docker-compose.yml -f docker-compose.provider.yml up --build -d`.
Set `REDGIFS_TOKEN_HOST_PATH` to a host path containing only the raw provider
token. Compose mounts it as a read-only secret; do not put the token content
in `.env`, environment variables, or the repository. The overlay does not
implement credential acquisition or refresh; on a rejected token, replace the
secret file and restart the service.

The container build installs only the pinned backend runtime dependency set;
test, browser-automation, and development packages are excluded.
