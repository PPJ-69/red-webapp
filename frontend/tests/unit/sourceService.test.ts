import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../src/services/apiClient";
import {
  InvalidPlaybackUrlError,
  SourceService,
} from "../../src/services/sourceService";

const credentialUrl = new URL("https://cdn.example/media.mp4");
credentialUrl.username = "test-user";
credentialUrl.password = "test-password";

describe("SourceService", () => {
  it("resolves an encoded media ID and validated quality with cancellation", async () => {
    const controller = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          playbackUrl: "/api/stream/id%2Fpart?quality=hd",
          kind: "relay",
        }),
        { status: 200 },
      ),
    );
    const service = new SourceService(new ApiClient({ fetcher }));

    await expect(
      service.resolve("id/part", "hd", controller.signal),
    ).resolves.toMatchObject({
      playbackUrl: "/api/stream/id%2Fpart?quality=hd",
      kind: "relay",
    });
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/media/id%2Fpart/source?quality=hd",
    );
    expect(fetcher.mock.calls[0][1]?.signal).toBe(controller.signal);
  });

  it.each([
    "https://cdn.example/media.mp4",
    "/api/stream/media?quality=auto",
  ])("accepts safe playback URL %s", async (playbackUrl) => {
    const service = new SourceService(
      new ApiClient({
        fetcher: vi.fn<typeof fetch>().mockResolvedValue(
          new Response(JSON.stringify({ playbackUrl }), { status: 200 }),
        ),
      }),
    );

    await expect(
      service.resolve("media", "auto", new AbortController().signal),
    ).resolves.toMatchObject({ playbackUrl });
  });

  it.each([
    "http://cdn.example/media.mp4",
    "//cdn.example/media.mp4",
    "/\\cdn.example/media.mp4",
    "javascript:alert(1)",
    credentialUrl.href,
  ])("rejects unsafe playback URL %s", async (playbackUrl) => {
    const service = new SourceService(
      new ApiClient({
        fetcher: vi.fn<typeof fetch>().mockResolvedValue(
          new Response(JSON.stringify({ playbackUrl }), { status: 200 }),
        ),
      }),
    );

    await expect(
      service.resolve("media", "auto", new AbortController().signal),
    ).rejects.toBeInstanceOf(InvalidPlaybackUrlError);
  });
});
