# Upstream compliance and release checklist

This checklist is a release prerequisite, not evidence that provider
permission has been granted. Keep live mode disabled and use recorded/fake
fixtures until every required review is complete.

## O6: provider terms, rate limits, and permitted use

Record a decision before any live-provider request or hosted release:

| Review item | Evidence / decision |
|---|---|
| Provider terms and applicable policies reviewed | **OPEN** |
| Permitted automated access and intended deployment use confirmed | **OPEN** |
| Rate limits and required backoff/`Retry-After` behavior recorded | **OPEN** |
| Permitted media display/relay and geographic or audience restrictions recorded | **OPEN** |
| Approved account/credential owner and secure provisioning method recorded | **OPEN** |
| Retention/logging obligations for operator and provider understood | **OPEN** |
| Reviewer, approval date, and scope recorded | **OPEN** |

Do not fill an item with an assumption or a test against a fake provider.
Attach only policy references and sanitized approval evidence; never put
credentials or signed media URLs in this document.

## Additional hosted release gates

- **O7 — Access control:** Define and implement who can use a hosted relay,
  then verify the access boundary. Current deployment packaging has no
  application access control; the per-IP stream cap is not authentication.
- **O8 — Audience gating:** Resolve the product/legal audience policy and
  implement any required gating before hosted use.
- **O1/O10 — Session scope (resolved):** V1 state is frontend RAM-only and
  backend session routes are optional future functionality (D16).
- **Provider wiring:** The opt-in RedGIFs provider construction and mounted
  token-file path are implemented. Validate them with an approved live
  integration after O6 clearance; the default Compose stack keeps the
  provider disabled.
- **Deployment smoke:** Run the actual Docker/Nginx/TLS stack and verify
  repeated Range/seek, stream closure on shutdown, and no application-created
  media or state artifacts. Local Docker/Nginx/TLS execution is still
  outstanding.

## Approval record

| Provider / intended deployment | Reviewer | Date | Decision / restrictions |
|---|---|---|---|
| Not approved for live use | — | 2026-10-19 | O6 remains open; fake/recorded test fixtures only. |
