import type { MediaItem } from "../types/api";

export function formatDuration(duration: number | null | undefined): string {
  if (typeof duration !== "number" || Number.isNaN(duration) || duration < 0) {
    return "—";
  }

  const totalSeconds = Math.max(0, Math.floor(duration));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
  }

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function isRenderableMediaItem(value: unknown): value is MediaItem {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const item = value as Partial<MediaItem>;
  return typeof item.id === "string" && item.id.length > 0 && typeof item.title === "string" && item.title.length > 0;
}

export function sanitizeMediaItems(items: readonly unknown[]): MediaItem[] {
  return items.filter(isRenderableMediaItem);
}
