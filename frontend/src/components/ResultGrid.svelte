<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";

  import type { MediaItem } from "../types/api";
  import { sanitizeMediaItems, shouldLoadMore } from "../utils/resultGrid";
  import ResultCard from "./ResultCard.svelte";

  export let items: readonly MediaItem[] = [];
  export let currentItemId: string | null = null;
  export let loading = false;
  export let hasMore = false;
  export let sentinelText = "Loading more results…";

  const dispatch = createEventDispatcher<{
    "open-item": {
      item: MediaItem;
      index: number;
      opener: HTMLButtonElement;
    };
    load: undefined;
  }>();

  let sentinel: HTMLDivElement | null = null;
  let observer: IntersectionObserver | undefined;

  $: filteredItems = sanitizeMediaItems(items);

  function handleOpen(
    event: CustomEvent<{
      item: MediaItem;
      index: number;
      opener: HTMLButtonElement;
    }>,
  ): void {
    dispatch("open-item", event.detail);
  }

  function handleLoad(): void {
    if (!shouldLoadMore({ hasMore, loading })) return;
    dispatch("load");
  }

  function cleanupObserver(): void {
    observer?.disconnect();
    observer = undefined;
  }

  $: {
    cleanupObserver();

    if (typeof IntersectionObserver !== "undefined" && sentinel && shouldLoadMore({ hasMore, loading })) {
      observer = new IntersectionObserver(
        (entries) => {
          const entry = entries[0];
          if (entry?.isIntersecting) handleLoad();
        },
        { rootMargin: "200px" },
      );
      observer.observe(sentinel);
    }
  }

  onDestroy(() => {
    cleanupObserver();
  });
</script>

{#if filteredItems.length === 0 && !loading}
  <p class="empty" data-testid="result-grid-empty">No results yet.</p>
{:else}
  <div
    class="grid"
    data-testid="result-grid"
    role="region"
    aria-label="Search results"
    aria-busy={loading}
  >
    {#each filteredItems as item, index (item.id)}
      <ResultCard
        {item}
        {index}
        current={currentItemId === item.id}
        on:open-item={handleOpen}
      >
        <svelte:fragment slot="seen"><slot name="seen" /></svelte:fragment>
        <svelte:fragment slot="favorite"><slot name="favorite" /></svelte:fragment>
      </ResultCard>
    {/each}
  </div>
{/if}

{#if hasMore || loading}
  <div bind:this={sentinel} class="sentinel" data-testid="result-grid-sentinel" aria-live="polite">
    {loading ? sentinelText : "Scroll for more results"}
  </div>
{/if}

<style>
  .grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .empty {
    color: #cbd5e1;
  }

  .sentinel {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 2.5rem;
    color: #cbd5e1;
    border: 1px dashed #475569;
    border-radius: 0.6rem;
    margin-top: 1rem;
  }
</style>
