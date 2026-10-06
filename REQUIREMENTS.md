# Stream-First Media Browser --- Requirements

## 1. Purpose

Redesign the existing media browser as a lightweight, user-friendly,
privacy-oriented web application focused on **streaming media in the
browser rather than downloading or storing media locally**.

The application should preserve the useful discovery, browsing,
playback, creator, tag, favorites, and viewed-state workflows of the
existing application while removing the local-download/library
architecture.

## 2. Core Product Requirements

The application must provide:

-   Trending/latest/top/score-based discovery.
-   Search.
-   Creator search and creator lookup.
-   Tag search and tag suggestions.
-   Paginated result browsing.
-   Grid/result-card presentation.
-   Individual media viewing.
-   Next/previous navigation where applicable.
-   Random navigation where applicable.
-   Favorites.
-   Viewed/seen state.
-   Retry and skip behavior.
-   Native browser video playback.
-   Playback speed, volume, mute, loop, and fullscreen controls.
-   Keyboard-accessible controls.
-   Temporary anonymous session state.

The application should feel like a normal modern web media browser while
remaining stream-first and privacy-oriented.

## 3. Non-Goals

The initial implementation must not include:

-   A full-file media downloader.
-   A local media library.
-   Permanent media storage.
-   Temporary MP4 files.
-   Thumbnail caching to disk.
-   SQLite media storage.
-   Persistent JSON application state.
-   OpenCV playback.
-   VLC playback.
-   Server-side transcoding.
-   Arbitrary URL proxying.
-   An open streaming proxy.
-   Browser exposure of upstream authentication tokens.
-   IndexedDB media caching.
-   Cache Storage media caching.
-   Service-worker media caching.
-   Background full-file downloading.

## 4. Technology

### Frontend

-   Svelte
-   TypeScript
-   Native HTML5 `<video>`

### Backend

-   Python
-   FastAPI
-   Async I/O

### Playback

Playback must use the browser's native media APIs. OpenCV and VLC are
not part of the new architecture.

## 5. High-Level Architecture

``` text
Browser
   |
   | HTTPS / JSON / media stream
   v
FastAPI Backend
   |
   | authenticated provider requests
   v
RedGIFs / Upstream Provider
```

The backend owns:

-   Provider authentication.
-   Provider API access.
-   Media metadata resolution.
-   Media source resolution.
-   Streaming relay.
-   Security validation.
-   SSRF protection.
-   Upstream credentials.

The frontend owns:

-   User interface.
-   Search/discovery.
-   Result navigation.
-   Player controls.
-   Temporary UI/session state.
-   Accessibility.

## 6. Provider Adapter

All RedGIFs-specific behavior must be isolated behind a provider/adaptor
layer.

The adapter should support:

-   Authentication.
-   Token refresh.
-   Trending/latest/top discovery.
-   Search.
-   Tag suggestions.
-   Creator search.
-   Creator lookup.
-   Media lookup.
-   Media source resolution.

Provider-specific details must not be scattered throughout the frontend
or generic backend code.

Normalize upstream responses into application-level models.

A normalized media model should provide, where available:

-   Stable media ID.
-   Title/description.
-   Creator.
-   Tags.
-   Dimensions.
-   Duration.
-   Thumbnail/poster.
-   Available source information.
-   Metadata required for navigation.

## 7. Authentication

The backend must own RedGIFs authentication.

The browser must never receive:

-   Bearer tokens.
-   Temporary provider tokens.
-   Provider credentials.
-   Provider authentication headers.

Authentication and refresh behavior must remain inside the provider
adapter.

Sensitive credentials must never be logged.

## 8. Streaming

Streaming is a central requirement.

### Direct Playback

If an upstream media source can safely be played directly by the browser
without exposing credentials, the application may use the direct source.

### Relay Playback

Otherwise:

``` text
Browser
   |
   v
/api/stream/{id}
   |
   v
Upstream media
```

The relay must:

-   Accept a known media ID, not an arbitrary URL.
-   Resolve the source through the provider adapter.
-   Validate the upstream destination.
-   Stream incrementally.
-   Use bounded buffers.
-   Never load the complete media into memory.
-   Never write media to disk.
-   Support HTTP Range requests.
-   Handle client disconnects/cancellation.
-   Apply connection/read timeouts.
-   Limit streaming concurrency.

## 9. Range Requests

The relay must support:

-   Requests without `Range`.
-   Single-range requests.

Valid range requests should return `206 Partial Content` where
appropriate.

Forward relevant response information when safe, including:

-   `Content-Type`
-   `Content-Length`
-   `Content-Range`
-   `Accept-Ranges`
-   `ETag`
-   `Last-Modified`

The implementation must not become a full-file downloader or cache.

## 10. Storage and Privacy

### Media

The application must not intentionally create or store media files.

No:

-   MP4 files.
-   Temporary media files.
-   Media cache directory.
-   Local media archive.
-   Server-side media library.

### Thumbnails

Thumbnails/posters may be requested for display, but the application
must not create a local thumbnail cache.

### Browser Storage

The initial application must not intentionally persist media using:

-   IndexedDB.
-   Cache Storage.
-   Service-worker media caches.
-   Application-created files.

Normal browser buffering performed by the native media element is
acceptable.

### Application State

Do not create:

-   SQLite storage.
-   Persistent JSON settings.
-   Persistent local media metadata.

Anonymous favorites/history/settings may exist in temporary in-memory
session state with TTL.

## 11. Security

### No Open Proxy

The streaming endpoint must not accept arbitrary user-supplied URLs.

Required:

``` http
GET /api/stream/{media_id}
```

Not allowed:

``` http
GET /api/stream?url=https://example.com/video.mp4
```

The backend resolves the media ID through the trusted provider adapter.

### SSRF Protection

The backend must protect against:

-   Private IP destinations.
-   Loopback destinations.
-   Link-local destinations.
-   Internal network destinations.
-   Unexpected protocols.
-   Unsafe redirects.
-   DNS rebinding where applicable.

Use an explicit upstream host allowlist where practical.

### Resource Limits

Use:

-   Connection timeouts.
-   Read timeouts.
-   Bounded buffers.
-   Streaming concurrency limits.
-   Pagination limits.
-   Request validation.

## 12. API

The backend should expose at least:

### Search

``` http
GET /api/search
```

Supports discovery/search modes, filters, and pagination.

### Media Metadata

``` http
GET /api/media/{id}
```

Returns normalized media metadata.

### Media Source

``` http
GET /api/media/{id}/source
```

Returns safe playback source information without exposing upstream
credentials.

### Media Stream

``` http
GET /api/stream/{id}
```

Provides the bounded streaming relay.

### Creator

``` http
GET /api/creator/{username}
```

Returns normalized creator information.

### Tag Suggestions

``` http
GET /api/tags/suggest?q={query}
```

Returns tag suggestions.

### Session

``` http
GET /api/session
GET /api/session/state
```

### Favorites

``` http
POST /api/session/favorites/{id}
DELETE /api/session/favorites/{id}
```

### Viewed State

``` http
POST /api/session/seen/{id}
```

Exact request/response schemas should be established in the architecture
phase.

## 13. Frontend

A suggested component structure is:

``` text
App
├── AppShell
├── Search / Discovery
│   ├── SearchBar
│   ├── FilterControls
│   ├── TagSuggestions
│   └── ResultGrid
│       └── ResultCard
├── Viewer
│   ├── MediaPlayer
│   ├── PlayerOverlay
│   ├── ThumbnailRail
│   └── InfoPanel
├── CreatorPanel
├── FavoriteButton
├── SettingsPanel
├── Toast
└── ErrorBanner
```

This structure may be refined by the architecture document without
changing product requirements.

## 14. Frontend State

Separate:

### UI State

-   Current view.
-   Search input.
-   Selected media.
-   Modal visibility.
-   Loading/error state.

### Result State

-   Current results.
-   Pagination.
-   Current result index.
-   Search/filter parameters.

### Session State

-   Favorites.
-   Viewed IDs.
-   Temporary settings.

### Player State

-   Idle.
-   Loading.
-   Ready.
-   Playing.
-   Paused.
-   Seeking.
-   Ended.
-   Error.

Avoid a single monolithic global state object.

## 15. Player

The player must support:

-   Play.
-   Pause.
-   Seek.
-   Volume.
-   Mute.
-   Playback speed.
-   Loop.
-   Fullscreen.
-   Loading indicators.
-   Error indicators.
-   Retry.
-   Next/previous navigation.

A failed media item must not crash the application.

The UI should allow retrying or skipping when playback fails.

## 16. Navigation

Users should be able to:

-   Open a result.
-   Return to results.
-   Move next.
-   Move previous where available.
-   Navigate randomly where supported.
-   Retry the current item.
-   Favorite/unfavorite.
-   Open creator information.
-   Explore relevant tags.

Result context should be preserved where practical.

## 17. Accessibility

Support:

-   Keyboard navigation.
-   Visible focus states.
-   Semantic controls.
-   Accessible labels.
-   Appropriate button semantics.
-   Keyboard playback controls.
-   Screen-reader-friendly states.
-   Sufficient contrast.
-   Errors that are understandable without relying only on color.

## 18. Error Handling

Normalize failures into useful application errors.

Handle:

-   Authentication failure.
-   Rate limiting.
-   Provider unavailability.
-   Invalid media IDs.
-   Provider API changes.
-   Upstream timeout.
-   Range failure.
-   Connection interruption.
-   Unsupported media.
-   Frontend/network failures.

Do not expose backend tracebacks to normal users.

Provide useful retry/skip behavior.

## 19. Sessions

Anonymous session state should be temporary.

The implementation should define:

-   Session identification.
-   In-memory session storage.
-   TTL.
-   Session-size limits.
-   Expiration cleanup.

Session state must not become a persistent local database.

Future authenticated/cloud-backed accounts are outside the initial
scope.

## 20. Configuration

Use normal environment/deployment configuration for:

-   Provider configuration.
-   Authentication configuration.
-   Timeouts.
-   Streaming concurrency.
-   Resource limits.
-   Allowed upstream hosts.
-   Session TTL.

Do not create persistent local JSON configuration as the application's
database.

## 21. Logging

Logs may contain:

-   Endpoint.
-   Request type.
-   Status.
-   Duration.
-   Provider operation.
-   Error category.

Logs must not contain:

-   Bearer tokens.
-   Authorization headers.
-   Provider credentials.
-   Sensitive signed URLs.

Do not log every streaming chunk.

## 22. Testing

### Backend

Test:

-   Provider adapter.
-   Authentication/token refresh.
-   Media normalization.
-   Media metadata endpoint.
-   Source endpoint.
-   Stream endpoint.
-   Range requests.
-   Error handling.
-   SSRF protections.
-   Host allowlist.
-   Redirect validation.
-   Session behavior.
-   TTL expiration.
-   Resource limits.

### Frontend

Test:

-   Search/discovery.
-   Result rendering.
-   Media selection.
-   Next/previous navigation.
-   Favorites.
-   Viewed state.
-   Player state transitions.
-   Retry.
-   Error states.
-   Keyboard controls.

### Integration

Test:

-   Search → result → media.
-   Media metadata → playback.
-   Direct source playback where applicable.
-   Relay playback.
-   Range requests.
-   Session state.

## 23. Release-Blocking No-Download Test

A release-blocking test must verify that normal playback does not cause
the application to create media files.

Verify:

-   No MP4 files are created.
-   No temporary media files are created.
-   No media cache directory is created.
-   No thumbnail cache is created.
-   No SQLite media database is created.
-   Backend playback streams data instead of storing it.

## 24. Performance

These are targets rather than absolute guarantees.

Aim for:

-   Fast initial rendering.
-   Small frontend overhead.
-   Progressive media playback.
-   Efficient result rendering.
-   Lazy thumbnail loading.
-   Responsive navigation.
-   Bounded backend memory.
-   No unnecessary media downloads.

The backend must never read a complete media file into memory merely to
serve it.

## 25. Repository Direction

A reasonable initial layout is:

``` text
project/
├── frontend/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── providers/
│   │   ├── streaming/
│   │   ├── sessions/
│   │   └── models/
│   └── tests/
├── docs/
├── tests/
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── PROJECT_STATE.md
└── README.md
```

The exact structure can change during architecture design if
requirements remain satisfied.

## 26. Milestones

### M0 --- Skeleton

-   Repository structure.
-   Frontend shell.
-   Backend shell.
-   Development configuration.
-   Health endpoint.
-   Frontend/backend integration.

### M1 --- Provider Integration

-   Provider abstraction.
-   RedGIFs authentication.
-   Token refresh.
-   Normalized media model.
-   Search/discovery.
-   Media lookup.

### M2 --- Streaming Proof of Concept

-   `/api/media/{id}`.
-   `/api/media/{id}/source`.
-   `/api/stream/{id}`.
-   Upstream streaming.
-   Range forwarding.
-   Bounded buffering.
-   SSRF protection.
-   Stream tests.
-   Proof that playback creates no media files.

### M3 --- Browser Player

-   Native `<video>`.
-   Playback controls.
-   Seek.
-   Volume/mute.
-   Speed.
-   Loop.
-   Fullscreen.
-   Loading/error states.
-   Retry.
-   Next/previous.

### M4 --- Discovery UI

-   Search.
-   Trending.
-   Latest.
-   Top/score.
-   Tags.
-   Suggestions.
-   Creator search.
-   Result grid.
-   Pagination.
-   Navigation.

### M5 --- Session Features

-   Favorites.
-   Viewed state.
-   Temporary settings.
-   Session expiration.
-   Cleanup.

### M6 --- Security Hardening

-   SSRF protection.
-   Host allowlist.
-   Redirect validation.
-   Credential protection.
-   Resource limits.
-   Security tests.
-   Error normalization.

### M7 --- Performance and UX

-   Lazy loading.
-   Thumbnail optimization.
-   Efficient result rendering.
-   Player polish.
-   Keyboard/accessibility improvements.
-   Loading/error polish.

### M8 --- Release Validation

Verify:

-   Core workflows.
-   Streaming.
-   Range requests.
-   Error handling.
-   Security.
-   Accessibility.
-   Performance targets.
-   No-download compliance.
-   No unintended persistent storage.

## 27. Acceptance Criteria

The initial release must satisfy all of the following:

### Functionality

-   Users can discover media.
-   Users can search.
-   Users can browse results.
-   Users can open media.
-   Users can play media in the browser.
-   Users can seek.
-   Users can control volume/mute.
-   Users can change playback speed.
-   Users can loop.
-   Users can use fullscreen.
-   Users can retry failed playback.
-   Users can move between results.
-   Users can favorite media.
-   Users can track viewed state within the temporary session.

### Streaming

-   Media streams without application-created media files.
-   Range requests work.
-   Large media is not fully buffered by the backend.
-   Streaming is asynchronous.
-   Browser playback works through the relay.

### Security

-   Stream endpoint does not accept arbitrary URLs.
-   Provider credentials never reach the browser.
-   Upstream destinations are validated.
-   Redirects are validated.
-   Sensitive credentials are not logged.

### Storage

-   No local media library.
-   No temporary MP4 files.
-   No thumbnail cache.
-   No SQLite media database.
-   No persistent media cache.

### Reliability

-   One failed media item does not crash the application.
-   Provider failures produce usable error states.
-   Streaming failures can be retried.
-   Expired sessions are cleaned up.

## 28. Core Engineering Principles

1.  **Stream, don't store.**
2.  **Keep provider authentication on the backend.**
3.  **Use media IDs instead of arbitrary URLs.**
4.  **Keep provider-specific behavior behind an adapter.**
5.  **Use native browser playback.**
6.  **Prefer the smallest implementation that satisfies the
    requirements.**
7.  **Avoid speculative abstractions.**
8.  **Do not silently change architecture.**
9.  **Test privacy/storage guarantees as well as functionality.**
10. **Treat no-download behavior as release-blocking.**
11. **Keep anonymous session state temporary.**
12. **Make security boundaries explicit.**
13. **Implement incrementally.**
14. **Preserve useful existing functionality while simplifying the
    architecture.**

## 29. Source of Truth

This file is the **product requirements source of truth**.

The architecture document must translate these requirements into
technical decisions.

The implementation plan must translate the approved architecture into
incremental chunks.

The project state must describe what has actually been implemented.

The intended chain is:

``` text
REQUIREMENTS.md
      |
      v
ARCHITECTURE.md
      |
      v
IMPLEMENTATION_PLAN.md
      |
      v
PROJECT_STATE.md
      |
      v
Code + Tests
```

If architecture or implementation conflicts with a requirement:

1.  Identify the conflict.
2.  Do not silently ignore the requirement.
3.  Do not silently change the architecture.
4.  Record the conflict.
5.  Resolve it explicitly before proceeding.
