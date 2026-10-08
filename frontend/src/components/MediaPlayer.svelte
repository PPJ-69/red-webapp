<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";

  import {
    createPlayerStore,
    IllegalPlayerTransitionError,
    playerEventForMediaEvent,
  } from "../stores/playerStore";
  import { ApiError, type ClientErrorCategory } from "../services/errors";
  import ErrorState from "./ErrorState.svelte";
  import KeyboardHelp from "./KeyboardHelp.svelte";
  import PlayerControls from "./PlayerControls.svelte";
  import {
    installKeyboardController,
    type KeyboardAction,
  } from "../services/keyboardController";
  import {
    decidePlaybackRecovery,
    inspectRelayPlaybackFailure,
    playbackErrorCategory,
    type PlaybackRecoveryDecision,
    type RecoveryAttempts,
  } from "../services/playbackRecovery";
  import type {
    NativeMediaEventName,
    PlayerEvent,
    PlayerState,
    Quality,
  } from "../types/player";
  import type { MediaSource } from "../types/api";
  import { sourceService } from "../services/sourceService";

  export let itemId: string;
  export let autoplay = false;
  export let muted = false;
  export let loop = false;
  export let volume = 1;
  export let speed = 1;
  export let quality: Quality = "auto";
  export let openUrl: string | undefined = undefined;
  export let hasNext = false;
  export let takePrefetchedSource: (id: string) => MediaSource | undefined = () =>
    undefined;

  const dispatch = createEventDispatcher<{
    playerEvent: { event: PlayerEvent; state: PlayerState };
    skip: undefined;
    next: undefined;
    previous: undefined;
    retry: undefined;
    toggleFavorite: undefined;
    close: undefined;
    help: undefined;
  }>();
  const playerStore = createPlayerStore();
  let video: HTMLVideoElement;
  let mounted = false;
  let activeController: AbortController | undefined;
  let activeRequest = 0;
  let diagnosedRequest = -1;
  let ignoreEmptiedUntilLoadStarts = false;
  let recoveryAttempts: RecoveryAttempts = {
    reauthorized: false,
    alternateQuality: false,
  };
  let activeQuality: Quality = quality;
  let recoveryDecision: PlaybackRecoveryDecision | undefined;
  let currentTime = 0;
  let duration = 0;
  let showKeyboardHelp = false;
  let controlAnnouncement = "";
  $: snapshot = $playerStore;
  $: isPlaying =
    snapshot.state === "PLAYING" ||
    (snapshot.state === "BUFFERING" && snapshot.resumeState === "PLAYING") ||
    (snapshot.state === "SEEKING" && snapshot.resumeState === "PLAYING");

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
    if (
      eventName === "timeupdate" ||
      eventName === "durationchange" ||
      eventName === "loadedmetadata"
    ) {
      currentTime = video.currentTime;
      duration = Number.isFinite(video.duration) ? video.duration : 0;
    }
    if (eventName === "error") {
      if (ignoreEmptiedUntilLoadStarts || !video.currentSrc) return;
      void handlePlaybackError();
      return;
    }
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
    if (eventName === "ended" && !loop) {
      if (autoplay && hasNext) {
        dispatch("next", undefined);
      }
    }
  }

  async function resolveAndLoad(
    requestedItemId: string,
    requestedQuality: Quality,
    attempts: RecoveryAttempts = { reauthorized: false, alternateQuality: false },
    isManualRetry = false,
  ): Promise<void> {
    const requestId = ++activeRequest;
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    activeQuality = requestedQuality;
    recoveryAttempts = attempts;
    recoveryDecision = undefined;
    ignoreEmptiedUntilLoadStarts = true;
    video.pause();
    video.removeAttribute("src");
    video.load();
    if (isManualRetry && playerStore.getSnapshot().state === "ERROR") {
      apply({ type: "RETRY" });
    } else {
      apply({ type: "RESET" });
      apply({ type: "OPEN" });
    }

    try {
      const preparedSource = isManualRetry
        ? undefined
        : takePrefetchedSource(requestedItemId);
      const source =
        preparedSource ??
        (await sourceService.resolve(
          requestedItemId,
          requestedQuality,
          controller.signal,
        ));
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
      handleRecoveryError(
        error instanceof ApiError ? error.category : "provider_error",
        error instanceof ApiError ? error.retryAfter : undefined,
        requestedItemId,
        requestedQuality,
        attempts,
      );
    }
  }

  async function handlePlaybackError(): Promise<void> {
    const requestId = activeRequest;
    if (diagnosedRequest === requestId) return;
    diagnosedRequest = requestId;
    const signal = activeController?.signal ?? new AbortController().signal;
    const mediaError = video.error;
    const relayError = await inspectRelayPlaybackFailure(
      video.getAttribute("src") ?? "",
      signal,
    );
    if (requestId !== activeRequest || signal.aborted) return;
    const category =
      relayError?.category ?? playbackErrorCategory(mediaError?.code);
    handleRecoveryError(
      category,
      relayError?.retryAfter,
      itemId,
      activeQuality,
      recoveryAttempts,
    );
  }

  function handleRecoveryError(
    category: ClientErrorCategory,
    retryAfter: number | undefined,
    requestedItemId: string,
    requestedQuality: Quality,
    attempts: RecoveryAttempts,
  ): void {
    const decision = decidePlaybackRecovery(
      category,
      attempts,
      requestedQuality,
      retryAfter,
    );
    if (decision.action === "reauthorize") {
      void resolveAndLoad(requestedItemId, requestedQuality, {
        ...attempts,
        reauthorized: true,
      });
      return;
    }
    if (
      decision.action === "alternate_quality" &&
      decision.alternateQuality !== undefined
    ) {
      void resolveAndLoad(
        requestedItemId,
        decision.alternateQuality,
        { ...attempts, alternateQuality: true },
      );
      return;
    }
    recoveryDecision = decision;
    if (playerStore.getSnapshot().state !== "ERROR") {
      apply({ type: "ERROR" });
    }
  }

  function retry(): void {
    void resolveAndLoad(
      itemId,
      quality,
      { reauthorized: false, alternateQuality: false },
      true,
    );
  }

  function togglePlayback(): void {
    if (video.paused) {
      void video.play().catch(() => void handlePlaybackError());
    } else {
      video.pause();
    }
  }

  function seekTo(time: number): void {
    if (!Number.isFinite(duration) || duration <= 0) return;
    video.currentTime = Math.max(0, Math.min(duration, time));
  }

  function adjustVolume(nextVolume: number): void {
    volume = Math.max(0, Math.min(1, nextVolume));
    video.volume = volume;
    if (volume > 0 && muted) {
      muted = false;
      video.muted = false;
    }
  }

  function toggleMute(): void {
    muted = !muted;
    video.muted = muted;
  }

  function setSpeed(nextSpeed: number): void {
    speed = Math.max(0.25, Math.min(4, nextSpeed));
    video.playbackRate = speed;
  }

  function toggleLoop(): void {
    loop = !loop;
    video.loop = loop;
  }

  function openKeyboardHelp(): void {
    showKeyboardHelp = true;
    dispatch("help", undefined);
  }

  async function toggleFullscreen(): Promise<void> {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        const player = video.closest(".player");
        if (!player) {
          controlAnnouncement = "Fullscreen is not available in this browser.";
          return;
        }
        await player.requestFullscreen();
      }
      controlAnnouncement = document.fullscreenElement
        ? "Fullscreen enabled."
        : "Fullscreen disabled.";
    } catch {
      controlAnnouncement = "Fullscreen is not available in this browser.";
    }
  }

  function handleKeyboardAction(action: KeyboardAction): void {
    switch (action) {
      case "toggle-play":
        togglePlayback();
        break;
      case "seek-backward":
        seekTo(video.currentTime - 5);
        break;
      case "seek-forward":
        seekTo(video.currentTime + 5);
        break;
      case "volume-up":
        adjustVolume(volume + 0.05);
        break;
      case "volume-down":
        adjustVolume(volume - 0.05);
        break;
      case "toggle-mute":
        toggleMute();
        break;
      case "toggle-loop":
        toggleLoop();
        break;
      case "toggle-fullscreen":
        void toggleFullscreen();
        break;
      case "toggle-help":
        openKeyboardHelp();
        break;
      case "next":
        dispatch("next", undefined);
        break;
      case "previous":
        dispatch("previous", undefined);
        break;
      case "retry":
        dispatch("retry", undefined);
        if (snapshot.state === "ERROR") retry();
        break;
      case "toggle-favorite":
        dispatch("toggleFavorite", undefined);
        break;
      case "close":
        showKeyboardHelp = false;
        dispatch("close", undefined);
        break;
    }
  }

  function skip(): void {
    activeRequest += 1;
    activeController?.abort();
    video.pause();
    ignoreEmptiedUntilLoadStarts = true;
    video.removeAttribute("src");
    video.load();
    apply({ type: "SKIP" });
    dispatch("skip", undefined);
  }

  function open(): void {
    if (!isSafeWebUrl(openUrl)) return;
    window.open(openUrl, "_blank", "noopener,noreferrer");
  }

  function isSafeWebUrl(value: string | undefined): value is string {
    if (value === undefined) return false;
    try {
      const url = new URL(value);
      return (
        url.protocol === "https:" &&
        url.hostname.length > 0 &&
        url.username === "" &&
        url.password === ""
      );
    } catch {
      return false;
    }
  }

  onMount(() => {
    mounted = true;
    const removeKeyboardController = installKeyboardController(
      window,
      handleKeyboardAction,
    );
    return () => {
      removeKeyboardController();
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
    on:timeupdate={handleMediaEvent}
    on:durationchange={handleMediaEvent}
    on:ended={handleMediaEvent}
    on:error={handleMediaEvent}
    on:emptied={handleMediaEvent}
  ></video>
  <PlayerControls
    {currentTime}
    {duration}
    playing={isPlaying}
    {volume}
    {muted}
    {speed}
    {loop}
    on:playPause={togglePlayback}
    on:seek={(event) => seekTo(event.detail)}
    on:volume={(event) => adjustVolume(event.detail)}
    on:mute={toggleMute}
    on:speed={(event) => setSpeed(event.detail)}
    on:loop={toggleLoop}
    on:fullscreen={() => void toggleFullscreen()}
    on:help={openKeyboardHelp}
  />
  <KeyboardHelp
    open={showKeyboardHelp}
    on:close={() => (showKeyboardHelp = false)}
  />
  <p class="control-announcement" aria-live="polite">{controlAnnouncement}</p>
  {#if snapshot.state === "RESOLVING" || snapshot.state === "LOADING"}
    <p class="player-overlay" data-testid="loading" role="status" aria-live="polite">
      Loading…
    </p>
  {:else if snapshot.state === "BUFFERING"}
    <p class="player-overlay" data-testid="buffering" role="status" aria-live="polite">
      Buffering…
    </p>
  {/if}
  {#if snapshot.state === "ERROR" && recoveryDecision}
    <ErrorState
      decision={recoveryDecision}
      {openUrl}
      on:retry={retry}
      on:skip={skip}
      on:open={open}
    />
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

  .control-announcement {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      scroll-behavior: auto !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }

</style>
