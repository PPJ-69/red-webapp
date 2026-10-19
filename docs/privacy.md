# Privacy and storage statement

The application **does not intentionally persist media or application data on
the local machine**. This is a statement about application behavior, not a
guarantee that the browser, operating system, network, hosting platform, or
upstream provider never retains data.

## What the application is designed to do

- Stream media through native browser playback instead of creating a
  downloadable media library.
- Keep favorites, seen IDs, search history, saved searches, player state, and
  settings in frontend memory only. Reloading the page clears that state.
- Avoid application use of localStorage, sessionStorage, IndexedDB, Cache
  Storage, service-worker media caches, SQLite, or persistent JSON settings.
- Keep provider credentials and internal source targets on the backend and
  redact sensitive values from application logs.
- Avoid intentional media and thumbnail files or caches. Normal browser media
  buffering is outside the application's filesystem-storage guarantee.

## Important limits

- Browser-native buffering, browser caches, browser history, crash reports,
  operating-system behavior, endpoint monitoring, and network equipment are
  outside this application-level guarantee.
- When a source is classified as direct, the browser contacts that media host;
  the host may receive the user's network address. Images are also requested
  by the browser from their metadata URLs. Referrer policy is set to
  `no-referrer`, but this does not conceal the network address.
- Backend stdout logs and container/runtime logs may be retained by whoever
  operates the deployment. Metrics are process-local and logged at graceful
  shutdown. Do not treat deployment logs as ephemeral unless the operator has
  verified their logging policy.
- V1 favorites, viewed IDs, history, and temporary settings live in frontend
  RAM and are lost on page reload. Backend session endpoints are optional
  future functionality (D16).
- The full no-download scenario uses intercepted responses and in-memory
  browser-generated media. It proves the tested local scenario, not all
  browsers, operating systems, or deployment environments.

See the [security review](security-review.md) for test evidence and the
[upstream checklist](upstream-compliance-checklist.md) for release gates.
