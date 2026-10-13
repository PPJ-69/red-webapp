<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { MediaItem } from "../types/api";
  import { formatDuration } from "../utils/resultGrid";
  import { sessionStore } from "../stores/sessionStore";
  import FavoriteButton from "./FavoriteButton.svelte";

  export let item: MediaItem;
  export let index = 0;
  export let current = false;

  const dispatch = createEventDispatcher<{
    "open-item": { item: MediaItem; index: number };
  }>();

  const fallbackImage =
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="#0f172a"/><text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" fill="#cbd5e1" font-size="32" font-family="sans-serif">No image</text></svg>',
    );

  function openItem(): void {
    dispatch("open-item", { item, index });
  }

  $: seen = $sessionStore.seen.includes(item.id);
</script>

<article class:current data-testid="result-card" aria-current={current ? "true" : undefined}>
  <button type="button" class="card-button" on:click={openItem}>
    <img
      loading="lazy"
      alt={item.title}
      src={item.thumbnailUrl ?? item.posterUrl ?? fallbackImage}
      referrerpolicy="no-referrer"
    />
    <div class="thumbnail-meta">
      <span class="duration">{formatDuration(item.duration ?? null)}</span>
      {#if current}
        <span class="current-pill">Current item</span>
      {/if}
    </div>
  </button>

  <div class="details">
    <div class="title-row">
      <h3>{item.title}</h3>
      <div class="action-slot">
        {#if seen}
          <span class="state-indicator" data-testid={`seen-${item.id}`}>
            <span aria-hidden="true">✓</span> Seen
          </span>
        {/if}
        <FavoriteButton mediaId={item.id} />
        <slot name="seen" />
        <slot name="favorite" />
      </div>
    </div>

    <p class="creator">{item.creator?.username ?? "Unknown creator"}</p>
    {#if item.description}
      <p class="description">{item.description}</p>
    {/if}
  </div>
</article>

<style>
  article {
    display: grid;
    gap: 0.75rem;
    padding: 0.65rem;
    border: 1px solid #334155;
    border-radius: 0.8rem;
    background: #0f172a;
    min-height: 100%;
  }

  article.current {
    border-color: #38bdf8;
    box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.4);
  }

  .card-button {
    position: relative;
    border: 0;
    padding: 0;
    background: transparent;
    border-radius: 0.75rem;
    overflow: hidden;
    cursor: pointer;
  }

  img {
    display: block;
    width: 100%;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    background: #111827;
  }

  .thumbnail-meta {
    position: absolute;
    inset: auto 0 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.35rem 0.5rem;
    background: linear-gradient(180deg, transparent, rgba(15, 23, 42, 0.9));
  }

  .duration,
  .current-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.85);
    color: #e2e8f0;
    padding: 0.2rem 0.45rem;
    font-size: 0.75rem;
    line-height: 1.2;
  }

  .details {
    display: grid;
    gap: 0.35rem;
  }

  .title-row {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    align-items: start;
  }

  h3 {
    margin: 0;
    font-size: 1rem;
    line-height: 1.3;
    color: #f8fafc;
  }

  .action-slot {
    display: flex;
    gap: 0.25rem;
    align-items: center;
  }

  .creator,
  .description {
    margin: 0;
    color: #cbd5e1;
  }

  .state-indicator {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    min-height: 2rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    padding: 0.25rem 0.5rem;
    color: #e2e8f0;
    font-size: 0.85rem;
  }

  .description {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
