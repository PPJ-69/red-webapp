<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { SearchOrder } from "../types/search";
  import { sessionStore } from "../stores/sessionStore";

  const dispatch = createEventDispatcher<{
    select: { query: string; order: SearchOrder | null };
  }>();
</script>

{#if $sessionStore.savedSearches.length > 0}
  <section aria-label="Saved searches" data-testid="saved-searches">
    <h2>Saved searches</h2>
    <ul>
      {#each $sessionStore.savedSearches as saved (saved.id)}
        <li>
          <button
            type="button"
            data-testid="saved-search"
            on:click={() =>
              dispatch("select", { query: saved.query, order: saved.order })}
          >
            {saved.query}{saved.order ? ` · ${saved.order}` : ""}
          </button>
          <button
            type="button"
            aria-label={`Remove saved search ${saved.query}`}
            on:click={() => sessionStore.removeSavedSearch(saved.id)}
          >Remove</button>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  section {
    display: grid;
    gap: 0.4rem;
  }

  h2 {
    margin: 0;
    font-size: 1rem;
  }

  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: 0.25rem;
  }

  button {
    min-height: 2.25rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.35rem 0.6rem;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
