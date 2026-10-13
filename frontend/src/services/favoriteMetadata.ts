import type { MediaItem } from "../types/api";

export type FavoriteMetadataLoader = (
  id: string,
  signal: AbortSignal,
) => Promise<MediaItem>;

export interface FavoriteMetadataResult {
  items: MediaItem[];
  errors: Map<string, string>;
}

function isMediaItemForId(value: unknown, id: string): value is MediaItem {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return item.id === id && typeof item.title === "string";
}

export async function hydrateFavoriteMetadata(
  ids: readonly string[],
  loadMedia: FavoriteMetadataLoader,
  signal: AbortSignal,
): Promise<FavoriteMetadataResult> {
  const uniqueIds = [...new Set(ids)];
  const responses = await Promise.all(
    uniqueIds.map(async (id) => {
      try {
        const item = await loadMedia(id, signal);
        if (!isMediaItemForId(item, id)) {
          throw new TypeError("The media endpoint returned mismatched metadata.");
        }
        return { id, item, error: null };
      } catch (error: unknown) {
        return {
          id,
          item: null,
          error:
            error instanceof Error
              ? error.message
              : "The media metadata request failed.",
        };
      }
    }),
  );

  return {
    items: responses.flatMap(({ item }) => (item === null ? [] : [item])),
    errors: new Map(
      responses.flatMap(({ id, error }) =>
        error === null ? [] : [[id, error] as const],
      ),
    ),
  };
}
