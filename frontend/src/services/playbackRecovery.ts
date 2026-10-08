import {
  mapErrorResponse,
  mapNetworkError,
  type ApiError,
  type ClientErrorCategory,
} from "./errors";
import type { Quality } from "../types/player";

export async function inspectRelayPlaybackFailure(
  playbackUrl: string,
  signal: AbortSignal,
): Promise<ApiError | undefined> {
  if (
    !playbackUrl.startsWith("/api/stream/") ||
    playbackUrl.startsWith("//") ||
    playbackUrl.includes("\\")
  ) {
    return undefined;
  }

  let response: Response;
  try {
    response = await globalThis.fetch.bind(globalThis)(playbackUrl, {
      method: "GET",
      headers: { Range: "bytes=0-0" },
      signal,
      cache: "no-store",
    });
  } catch (error: unknown) {
    return mapNetworkError(error, signal);
  }

  if (!response.ok) return mapErrorResponse(response);
  try {
    await response.body?.cancel();
  } catch (error: unknown) {
    return mapNetworkError(error, signal);
  }
  return undefined;
}

export type PlaybackRecoveryAction =
  | "reauthorize"
  | "alternate_quality"
  | "show_rate_limit"
  | "unavailable"
  | "retry";

export interface PlaybackRecoveryDecision {
  action: PlaybackRecoveryAction;
  message: string;
  retryAfter?: number;
  alternateQuality?: Quality;
  canRetry: boolean;
  canSkip: boolean;
}

export interface RecoveryAttempts {
  reauthorized: boolean;
  alternateQuality: boolean;
}

export function playbackErrorCategory(
  mediaErrorCode: number | undefined,
): ClientErrorCategory {
  switch (mediaErrorCode) {
    case 1:
      return "request_cancelled";
    case 2:
      return "network_error";
    case 4:
      return "unsupported_media";
    default:
      return "provider_error";
  }
}

export function decidePlaybackRecovery(
  category: ClientErrorCategory,
  attempts: RecoveryAttempts,
  quality: Quality,
  retryAfter?: number,
): PlaybackRecoveryDecision {
  if (
    category === "upstream_authentication_failed" &&
    !attempts.reauthorized
  ) {
    return {
      action: "reauthorize",
      message: "Refreshing the playback source.",
      canRetry: false,
      canSkip: false,
    };
  }

  if (category === "unsupported_media" && !attempts.alternateQuality) {
    return {
      action: "alternate_quality",
      message: "Trying another video quality.",
      alternateQuality: quality === "sd" ? "hd" : "sd",
      canRetry: false,
      canSkip: false,
    };
  }

  if (category === "rate_limited" || category === "local_rate_limited") {
    return {
      action: "show_rate_limit",
      message:
        retryAfter === undefined
          ? "Playback is temporarily rate limited. Wait before retrying."
          : `Playback is rate limited. Wait ${retryAfter} ${
              retryAfter === 1 ? "second" : "seconds"
            } before retrying.`,
      retryAfter,
      canRetry: true,
      canSkip: true,
    };
  }

  if (category === "not_found" || category === "forbidden") {
    return {
      action: "unavailable",
      message: "This media is unavailable.",
      canRetry: false,
      canSkip: true,
    };
  }

  return {
    action: "retry",
    message: "Playback could not be started.",
    canRetry: true,
    canSkip: true,
  };
}
