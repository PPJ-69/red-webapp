import { describe, expect, it, vi } from "vitest";

import {
  decidePlaybackRecovery,
  inspectRelayPlaybackFailure,
  playbackErrorCategory,
} from "../../src/services/playbackRecovery";

const noAttempts = { reauthorized: false, alternateQuality: false };

describe("playback recovery decisions", () => {
  it("reads relay error envelopes with one byte-range diagnostic request", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          category: "forbidden",
          message: "Denied.",
          correlationId: "request-1",
        }),
        { status: 403 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    try {
      await expect(
        inspectRelayPlaybackFailure(
          "/api/stream/item?quality=hd",
          controller.signal,
        ),
      ).resolves.toMatchObject({ category: "forbidden" });
      expect(fetcher).toHaveBeenCalledWith(
        "/api/stream/item?quality=hd",
        expect.objectContaining({
          headers: { Range: "bytes=0-0" },
          signal: controller.signal,
          cache: "no-store",
        }),
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("does not probe direct playback URLs", async () => {
    const fetcher = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetcher);
    try {
      await expect(
        inspectRelayPlaybackFailure(
          "https://cdn.example/video.mp4",
          new AbortController().signal,
        ),
      ).resolves.toBeUndefined();
      expect(fetcher).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it.each([
    [1, "request_cancelled"],
    [2, "network_error"],
    [4, "unsupported_media"],
    [undefined, "provider_error"],
  ] as const)("classifies native media error %s", (code, expected) => {
    expect(playbackErrorCategory(code)).toBe(expected);
  });

  it("refreshes authentication only once", () => {
    expect(
      decidePlaybackRecovery(
        "upstream_authentication_failed",
        noAttempts,
        "auto",
      ),
    ).toMatchObject({ action: "reauthorize", canRetry: false });
    expect(
      decidePlaybackRecovery(
        "upstream_authentication_failed",
        { ...noAttempts, reauthorized: true },
        "auto",
      ),
    ).toMatchObject({ action: "retry", canRetry: true });
  });

  it("tries an alternate quality only once", () => {
    expect(
      decidePlaybackRecovery("unsupported_media", noAttempts, "auto"),
    ).toMatchObject({ action: "alternate_quality", alternateQuality: "sd" });
    expect(
      decidePlaybackRecovery("unsupported_media", noAttempts, "sd"),
    ).toMatchObject({ action: "alternate_quality", alternateQuality: "hd" });
    expect(
      decidePlaybackRecovery(
        "unsupported_media",
        { ...noAttempts, alternateQuality: true },
        "auto",
      ),
    ).toMatchObject({ action: "retry", canRetry: true });
  });

  it.each(["rate_limited", "local_rate_limited"] as const)(
    "surfaces retry timing for %s",
    (category) => {
      expect(
        decidePlaybackRecovery(category, noAttempts, "auto", 12),
      ).toMatchObject({
        action: "show_rate_limit",
        retryAfter: 12,
        message: "Playback is rate limited. Wait 12 seconds before retrying.",
        canRetry: true,
      });
    },
  );

  it.each(["not_found", "forbidden"] as const)(
    "does not retry or bypass %s",
    (category) => {
      expect(
        decidePlaybackRecovery(category, noAttempts, "auto"),
      ).toMatchObject({
        action: "unavailable",
        message: "This media is unavailable.",
        canRetry: false,
        canSkip: true,
      });
    },
  );

  it("provides manual retry for other failures", () => {
    expect(
      decidePlaybackRecovery("network_error", noAttempts, "auto"),
    ).toMatchObject({ action: "retry", canRetry: true, canSkip: true });
  });
});
