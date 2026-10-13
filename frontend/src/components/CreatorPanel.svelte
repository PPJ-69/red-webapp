<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";

  import { apiClient, type ApiClient } from "../services/apiClient";
  import { ApiError } from "../services/errors";
  import type { Creator } from "../types/api";

  export let username: string;
  export let client: ApiClient = apiClient;

  const dispatch = createEventDispatcher<{
    search: { username: string };
    close: undefined;
  }>();

  let creator: Creator | null = null;
  let loading = false;
  let error = "";
  let controller: AbortController | undefined;

  $: if (username) void loadCreator(username);

  async function loadCreator(name: string): Promise<void> {
    controller?.abort();
    const requestController = new AbortController();
    controller = requestController;
    creator = null;
    error = "";
    loading = true;
    try {
      const result = await client.get<Creator>(
        `/api/creator/${encodeURIComponent(name)}`,
        { signal: requestController.signal },
      );
      if (!requestController.signal.aborted) creator = result;
    } catch (cause: unknown) {
      if (requestController.signal.aborted) return;
      error =
        cause instanceof ApiError && cause.category === "not_found"
          ? "This creator could not be found."
          : "Creator information could not be loaded. Please try again.";
    } finally {
      if (!requestController.signal.aborted) loading = false;
    }
  }

  onDestroy(() => controller?.abort());
</script>

<section aria-label="Creator profile" data-testid="creator-panel">
  <header>
    <h2>Creator</h2>
    <button type="button" aria-label="Close creator profile" on:click={() => dispatch("close", undefined)}>
      Close
    </button>
  </header>
  {#if loading}
    <p role="status" aria-live="polite">Loading creator…</p>
  {:else if error}
    <p role="alert">{error}</p>
    <button type="button" on:click={() => void loadCreator(username)}>Retry</button>
  {:else if creator}
    {#if creator.profileImageUrl}
      <img src={creator.profileImageUrl} alt="" loading="lazy" referrerpolicy="no-referrer" />
    {/if}
    <p>{creator.displayName ?? creator.username}</p>
    <button
      type="button"
      data-testid="creator-search"
      on:click={() => dispatch("search", { username: creator?.username ?? username })}
    >Search this creator</button>
  {/if}
</section>

<style>
  section {
    display: grid;
    gap: 0.65rem;
    padding: 1rem;
    border: 1px solid #334155;
    border-radius: 0.6rem;
    background: #0f172a;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  h2,
  p {
    margin: 0;
  }

  img {
    width: 4rem;
    height: 4rem;
    border-radius: 50%;
    object-fit: cover;
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
