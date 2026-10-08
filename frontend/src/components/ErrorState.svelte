<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { PlaybackRecoveryDecision } from "../services/playbackRecovery";

  export let decision: PlaybackRecoveryDecision;
  export let openUrl: string | undefined = undefined;

  const dispatch = createEventDispatcher<{
    retry: void;
    skip: void;
    open: void;
  }>();

  $: safeOpenUrl = getSafeOpenUrl(openUrl);

  function getSafeOpenUrl(value: string | undefined): string | undefined {
    if (value === undefined) return undefined;
    try {
      const url = new URL(value);
      return url.protocol === "https:" &&
        url.hostname.length > 0 &&
        url.username === "" &&
        url.password === ""
        ? url.href
        : undefined;
    } catch {
      return undefined;
    }
  }
</script>

<section class="error-state" data-testid="player-error" role="alert">
  <h2>{decision.action === "unavailable" ? "Unavailable" : "Playback error"}</h2>
  <p>{decision.message}</p>
  <div class="actions">
    {#if decision.canRetry}
      <button type="button" data-testid="retry" on:click={() => dispatch("retry")}>
        Retry
      </button>
    {/if}
    {#if decision.canSkip}
      <button type="button" data-testid="skip" on:click={() => dispatch("skip")}>
        Skip
      </button>
    {/if}
    {#if safeOpenUrl}
      <button type="button" data-testid="open" on:click={() => dispatch("open")}>
        Open on RedGIFs
      </button>
    {/if}
  </div>
</section>

<style>
  .error-state {
    position: absolute;
    inset: 1rem;
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: 0.375rem;
    background: rgb(0 0 0 / 88%);
    color: #fff;
    text-align: center;
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 1.25rem;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
  }

  button {
    border: 1px solid #94a3b8;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.5rem 0.8rem;
  }
</style>
