<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { QueueItem } from "../services/playbackQueue";

  export let item: QueueItem;
  export let hasPrevious = false;
  export let hasNext = false;
  export let canRandom = false;

  const dispatch = createEventDispatcher<{
    previous: void;
    next: void;
    random: void;
    close: { scrollPosition: number };
  }>();

  function close(): void {
    dispatch("close", { scrollPosition: window.scrollY });
  }
</script>

<section class="player-overlay" data-testid="player-overlay" aria-label="Media viewer">
  <header>
    <h2>{item.title}</h2>
    <nav aria-label="Media navigation">
      <button
        type="button"
        data-testid="previous-item"
        aria-label="Previous item"
        disabled={!hasPrevious}
        on:click={() => dispatch("previous", undefined)}
      >Previous</button>
      <button
        type="button"
        data-testid="next-item"
        aria-label="Next item"
        disabled={!hasNext}
        on:click={() => dispatch("next", undefined)}
      >Next</button>
      <button
        type="button"
        data-testid="random-item"
        aria-label="Random item"
        disabled={!canRandom}
        on:click={() => dispatch("random", undefined)}
      >Random</button>
      <button type="button" data-testid="close-player" on:click={close}>
        Close
      </button>
    </nav>
  </header>
  <slot />
</section>

<style>
  .player-overlay {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
  }

  header,
  nav {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.65rem;
  }

  header {
    justify-content: space-between;
  }

  h2 {
    margin: 0;
    font-size: 1.15rem;
  }

  button {
    min-height: 2.5rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.4rem 0.7rem;
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
