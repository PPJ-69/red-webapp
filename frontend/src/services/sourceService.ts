import type { MediaSource } from "../types/api";
import type { Quality } from "../types/player";
import { ApiClient, apiClient } from "./apiClient";

export class InvalidPlaybackUrlError extends Error {
  constructor() {
    super("The media source returned an invalid playback URL.");
    this.name = "InvalidPlaybackUrlError";
  }
}

export class SourceService {
  constructor(private readonly client: ApiClient = apiClient) {}

  async resolve(
    mediaId: string,
    quality: Quality,
    signal: AbortSignal,
  ): Promise<MediaSource> {
    if (!mediaId.trim()) {
      throw new TypeError("A media ID is required.");
    }
    const source = await this.client.get<MediaSource>(
      `/api/media/${encodeURIComponent(mediaId)}/source?quality=${quality}`,
      { signal },
    );
    if (!isSafePlaybackUrl(source.playbackUrl)) {
      throw new InvalidPlaybackUrlError();
    }
    return source;
  }
}

function isSafePlaybackUrl(value: string): boolean {
  if (
    value.startsWith("/") &&
    !value.startsWith("//") &&
    !value.includes("\\")
  ) {
    return true;
  }
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      url.hostname.length > 0 &&
      url.username === "" &&
      url.password === ""
    );
  } catch {
    return false;
  }
}

export const sourceService = new SourceService();
