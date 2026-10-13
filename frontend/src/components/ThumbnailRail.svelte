<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { MediaItem } from "../types/api";

  export let items: readonly MediaItem[] = [];
  export let currentItemId: string;

  const dispatch = createEventDispatcher<{ select: { id: string } }>();
</script>

{#if items.length > 1}
  <nav class="thumbnail-rail" aria-label="Items in these results" data-testid="thumbnail-rail">
    {#each items as item (item.id)}
      <button
        type="button"
        aria-current={item.id === currentItemId ? "true" : undefined}
        aria-label={`Play ${item.title}`}
        data-testid={`thumbnail-${item.id}`}
        on:click={() => dispatch("select", { id: item.id })}
      >
        {#if item.thumbnailUrl ?? item.posterUrl}
          <img
            src={item.thumbnailUrl ?? item.posterUrl ?? undefined}
            alt=""
            loading="lazy"
            referrerpolicy="no-referrer"
          />
        {/if}
        <span>{item.title}</span>
      </button>
    {/each}
  </nav>
{/if}

<style>
  .thumbnail-rail {
    display: flex;
    gap: 0.6rem;
    overflow-x: auto;
    padding: 0.25rem 0;
  }

  button {
    display: grid;
    flex: 0 0 9rem;
    gap: 0.35rem;
    border: 1px solid #475569;
    border-radius: 0.5rem;
    background: #0f172a;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.4rem;
    text-align: left;
  }

  button[aria-current="true"] {
    border-width: 2px;
  }

  img {
    width: 100%;
    aspect-ratio: 16 / 9;
    object-fit: cover;
  }

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
