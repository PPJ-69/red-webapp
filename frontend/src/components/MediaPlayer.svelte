<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";

  import {
    createPlayerStore,
    IllegalPlayerTransitionError,
    playerEventForMediaEvent,
  } from "../stores/playerStore";
  import type {
    NativeMediaEventName,
    PlayerEvent,
    PlayerState,
    Quality,
  } from "../types/player";
  import { sourceService } from "../services/sourceService";

  export let itemId: string;
  export let autoplay = false;
  export let muted = false;
  export let loop = false;
  export let volume = 1;
  export let speed = 1;
  export let quality: Quality = "auto";

  const dispatch = createEventDispatcher<{
    playerEvent: { event: PlayerEvent; state: PlayerState };
  }>();
  const playerStore = createPlayerStore();
  let video: HTMLVideoElement;
  let mounted = false;
  let activeController: AbortController | undefined;
  let activeRequest = 0;
  let ignoreEmptiedUntilLoadStarts = false;
  let sourceError = "";
  $: snapshot = $playerStore;

  $: if (video) {
    video.volume = volume;
    video.playbackRate = speed;
  }

  $: if (mounted) {
    void resolveAndLoad(itemId, quality);
  }

  function apply(event: PlayerEvent): void {
    playerStore.dispatch(event);
    dispatch("playerEvent", { event, state: playerStore.getSnapshot().state });
  }

  function handleMediaEvent(event: Event): void {
    const eventName = event.type as NativeMediaEventName;
    if (eventName === "loadstart") ignoreEmptiedUntilLoadStarts = false;
    if (
      eventName === "emptied" &&
      (ignoreEmptiedUntilLoadStarts || !video.currentSrc)
    ) {
      return;
    }
    try {
      playerStore.dispatchMediaEvent(eventName);
    } catch (error) {
      if (!(error instanceof IllegalPlayerTransitionError)) throw error;
      return;
    }
    const playerEvent = playerEventForMediaEvent(eventName);
    if (playerEvent === null) return;
    dispatch("playerEvent", {
      event: playerEvent,
      state: playerStore.getSnapshot().state,
    });
  }

  async function resolveAndLoad(
    requestedItemId: string,
    requestedQuality: Quality,
  ): Promise<void> {
    const requestId = ++activeRequest;
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    sourceError = "";
    ignoreEmptiedUntilLoadStarts = true;
    video.pause();
    video.removeAttribute("src");
    video.load();
    apply({ type: "RESET" });
    apply({ type: "OPEN" });

    try {
      const source = await sourceService.resolve(
        requestedItemId,
        requestedQuality,
        controller.signal,
      );
      if (requestId !== activeRequest || controller.signal.aborted) return;
      apply({ type: "SOURCE_RESOLVED" });
      video.src = source.playbackUrl;
      video.load();
      if (autoplay) {
        void video.play().catch(() => {
          // Autoplay can be denied by browser policy; native media events remain authoritative.
        });
      }
    } catch (error) {
      if (requestId !== activeRequest || controller.signal.aborted) return;
      sourceError =
        error instanceof Error
          ? error.message
          : "The media source could not be loaded.";
      apply({ type: "ERROR" });
    }
  }

  onMount(() => {
    mounted = true;
    return () => {
      mounted = false;
      activeRequest += 1;
      activeController?.abort();
      video.pause();
      ignoreEmptiedUntilLoadStarts = true;
      video.removeAttribute("src");
      video.load();
      apply({ type: "RESET" });
    };
  });
</script>

<section class="player" aria-label="Media player">
  <video
    bind:this={video}
    data-testid="media-player"
    autoplay={autoplay}
    muted={muted}
    loop={loop}
    preload="metadata"
    playsinline
    on:loadstart={handleMediaEvent}
    on:loadedmetadata={handleMediaEvent}
    on:playing={handleMediaEvent}
    on:pause={handleMediaEvent}
    on:seeking={handleMediaEvent}
    on:seeked={handleMediaEvent}
    on:waiting={handleMediaEvent}
    on:stalled={handleMediaEvent}
    on:canplay={handleMediaEvent}
    on:ended={handleMediaEvent}
    on:error={handleMediaEvent}
    on:emptied={handleMediaEvent}
  ></video>
  {#if snapshot.state === "RESOLVING" || snapshot.state === "LOADING"}
    <p class="player-overlay" data-testid="loading" role="status" aria-live="polite">
      Loading…
    </p>
  {:else if snapshot.state === "BUFFERING"}
    <p class="player-overlay" data-testid="buffering" role="status" aria-live="polite">
      Buffering…
    </p>
  {:else if snapshot.state === "ERROR"}
    <p class="player-overlay error" data-testid="player-error" role="alert">
      {sourceError || "Playback could not be started."}
    </p>
  {/if}
</section>

<style>
  .player {
    position: relative;
    width: 100%;
    background: #000;
  }

  video {
    display: block;
    width: 100%;
    max-height: 75vh;
    background: #000;
  }

  .player-overlay {
    position: absolute;
    inset: auto 1rem 1rem;
    margin: 0;
    padding: 0.75rem 1rem;
    border-radius: 0.375rem;
    background: rgb(0 0 0 / 75%);
    color: #fff;
    text-align: center;
  }

  .error {
    color: #fecaca;
  }
</style>
