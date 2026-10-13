<script lang="ts">
  import { onDestroy } from "svelte";

  import { ApiClient, apiClient } from "../services/apiClient";
  import {
    hydrateFavoriteMetadata,
    type FavoriteMetadataLoader,
  } from "../services/favoriteMetadata";
  import type { MediaItem } from "../types/api";
  import { sessionStore } from "../stores/sessionStore";
  import FavoriteButton from "./FavoriteButton.svelte";

  export let open = false;
  export let client: ApiClient = apiClient;
  export let loadMedia: FavoriteMetadataLoader = (id, signal) =>
    client.get<MediaItem>(`/api/media/${encodeURIComponent(id)}`, { signal });

  let snapshot = sessionStore.getSnapshot();
  let mediaItems: MediaItem[] = [];
  let errors = new Map<string, string>();
  let loading = false;
  let lastFavoriteKey = "";
  let generation = 0;
  let controller: AbortController | undefined;

  $: if (open) {
    const favoriteIds = [...snapshot.favorites];
    const key = favoriteIds.join("\u0000");
    if (key !== lastFavoriteKey) {
      lastFavoriteKey = key;
      void loadFavorites(favoriteIds);
    }
  } else {
    lastFavoriteKey = "";
    cancelLoad();
  }

  function cancelLoad(): void {
    generation += 1;
    controller?.abort();
    controller = undefined;
    loading = false;
  }

  async function loadFavorites(ids: readonly string[]): Promise<void> {
    cancelLoad();
    const requestGeneration = generation;
    const requestController = new AbortController();
    controller = requestController;
    mediaItems = [];
    errors = new Map();
    if (ids.length === 0) return;

    loading = true;
    const result = await hydrateFavoriteMetadata(
      ids,
      loadMedia,
      requestController.signal,
    );
    if (
      requestGeneration !== generation ||
      requestController.signal.aborted
    ) {
      return;
    }
    mediaItems = result.items;
    errors = result.errors;
    loading = false;
  }

  const unsubscribe = sessionStore.subscribe((value) => {
    snapshot = value;
  });

  onDestroy(() => {
    unsubscribe();
    cancelLoad();
  });
</script>

{#if open}
  <section aria-label="Favorites" data-testid="favorites-panel">
    <h2>Favorites</h2>
    {#if loading}
      <p role="status" aria-live="polite">Loading favorites…</p>
    {:else if snapshot.favorites.length === 0}
      <p>No favorites yet.</p>
    {:else}
      <ul>
        {#each snapshot.favorites as id (id)}
          {@const item = mediaItems.find((favorite) => favorite.id === id)}
          <li data-testid={`favorite-entry-${id}`}>
            {#if item}
              <div class="media-details">
                {#if item.thumbnailUrl ?? item.posterUrl}
                  <img
                    src={item.thumbnailUrl ?? item.posterUrl ?? undefined}
                    alt=""
                    loading="lazy"
                    referrerpolicy="no-referrer"
                  />
                {/if}
                <span>{item.title}</span>
              </div>
            {:else if errors.has(id)}
              <p role="alert">Could not load this favorite: {errors.get(id)}</p>
            {:else}
              <p>Favorite details are unavailable.</p>
            {/if}
            <FavoriteButton mediaId={id} />
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}

<style>
  section {
    display: grid;
    gap: 0.65rem;
    padding: 1rem;
    border: 1px solid #334155;
    border-radius: 0.6rem;
    background: #0f172a;
  }

  h2,
  p {
    margin: 0;
  }

  ul {
    display: grid;
    gap: 0.6rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .media-details {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  img {
    width: 4rem;
    aspect-ratio: 16 / 9;
    object-fit: cover;
  }
</style>
