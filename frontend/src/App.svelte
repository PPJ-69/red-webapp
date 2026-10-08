<script lang="ts">
  import { onMount, tick } from "svelte";

  import MediaPlayer from "./components/MediaPlayer.svelte";
  import PlayerOverlay from "./components/PlayerOverlay.svelte";
  import SearchBar from "./components/SearchBar.svelte";
  import { ArrayPlaybackQueue } from "./services/playbackQueue";
  import { PlaybackPrefetcher } from "./services/prefetch";
  import { searchContextStore } from "./stores/searchContextStore";
  import { sourceService } from "./services/sourceService";
  import type { MediaSource } from "./types/api";
  import type { QueueItem } from "./services/playbackQueue";
  import type { PlayerEvent, PlayerState, Quality } from "./types/player";

  const playbackQueue = new ArrayPlaybackQueue<QueueItem>(
    [
      { id: "sample-media", title: "Sample media" },
      { id: "sample-media-two", title: "Second sample" },
    ],
    "sample-media",
  );
  const prefetcher = new PlaybackPrefetcher<MediaSource>();
  let itemId = playbackQueue.current.id;
  let currentItem = playbackQueue.current;
  let playerState: PlayerState = "IDLE";
  let hasPrevious = playbackQueue.hasPrevious;
  let hasNext = playbackQueue.hasNext;
  let canRandom = playbackQueue.canRandom;
  let playerOpen = true;
  let autoplay = false;
  let playerOpener: HTMLButtonElement;
  let savedScrollPosition = 0;
  let prefetchAnnouncement = "";
  let searchAnnouncement = "";
  let searchError = "";
  let muted = true;
  let loop = false;
  let volume = 1;
  let speed = 1;
  const quality: Quality = "auto";

  function updateQueue(item: QueueItem): void {
    currentItem = item;
    itemId = item.id;
    hasPrevious = playbackQueue.hasPrevious;
    hasNext = playbackQueue.hasNext;
    canRandom = playbackQueue.canRandom;
    prefetchAnnouncement = "";
    primeNextSource();
  }

  function primeNextSource(): void {
    void prefetcher
      .prepareNext(playbackQueue, (nextId, signal) =>
        sourceService.resolve(nextId, quality, signal),
      )
      .then(() => undefined)
      .catch(() => {
        prefetchAnnouncement =
          "The next source was not prepared; it will resolve when selected.";
      });
  }

  function moveNext(): void {
    playbackQueue.next();
  }

  function movePrevious(): void {
    playbackQueue.previous();
  }

  function moveRandom(): void {
    playbackQueue.random();
  }

  async function closePlayer(
    event?: CustomEvent<unknown>,
  ): Promise<void> {
    const detail = event?.detail;
    savedScrollPosition =
      typeof detail === "object" &&
      detail !== null &&
      "scrollPosition" in detail &&
      typeof detail.scrollPosition === "number"
        ? detail.scrollPosition
        : window.scrollY;
    playerOpen = false;
    prefetcher.cancel();
    await tick();
    window.scrollTo(0, savedScrollPosition);
    playerOpener?.focus();
  }

  async function openPlayer(): Promise<void> {
    playerOpen = true;
    await tick();
    window.scrollTo(0, savedScrollPosition);
    primeNextSource();
  }

  function handlePlayerEvent(
    event: CustomEvent<{ event: PlayerEvent; state: PlayerState }>,
  ): void {
    playerState = event.detail.state;
  }

  async function submitSearch(
    event: CustomEvent<{
      rawQuery: string;
      order: "trending" | "latest" | "top" | "score";
      limit: number;
    }>,
  ): Promise<void> {
    searchError = "";
    searchAnnouncement = "Searching…";
    const succeeded = await searchContextStore.search(event.detail.rawQuery, {
      order: event.detail.order,
      limit: event.detail.limit,
    });
    const result = searchContextStore.getSnapshot();
    if (succeeded) {
      searchAnnouncement = `${result.itemsById.size} results loaded.`;
    } else if (result.error !== null) {
      searchAnnouncement = "";
      searchError = "Search could not be completed. Please try again.";
    }
  }

  onMount(() => {
    const unsubscribe = playbackQueue.subscribe(updateQueue);
    updateQueue(playbackQueue.current);
    return () => {
      unsubscribe();
      prefetcher.cancel();
      searchContextStore.discard();
    };
  });
</script>

<svelte:head>
  <meta name="description" content="A native media player backed by a stream relay." />
</svelte:head>

<main>
  <h1>Stream-First Media Browser</h1>
  <SearchBar on:submit={submitSearch} />
  <p data-testid="search-status" role="status" aria-live="polite">
    {searchAnnouncement}
  </p>
  {#if searchError}
    <p data-testid="search-error" role="alert">{searchError}</p>
  {/if}
  <label for="item">Test media</label>
  <select
    id="item"
    bind:value={itemId}
    data-testid="media-select"
    on:change={() => playbackQueue.select(itemId)}
  >
    {#each playbackQueue.items as queueItem}
      <option value={queueItem.id}>{queueItem.title}</option>
    {/each}
  </select>
  <label class="autoplay-setting">
    <input type="checkbox" bind:checked={autoplay} data-testid="autoplay-setting" />
    Play next automatically
  </label>
  <button
    type="button"
    data-testid="open-player"
    bind:this={playerOpener}
    aria-expanded={playerOpen}
    disabled={playerOpen}
    on:click={openPlayer}
  >Open player</button>
  {#if playerOpen}
    <PlayerOverlay
      item={currentItem}
      {hasPrevious}
      {hasNext}
      {canRandom}
      on:previous={movePrevious}
      on:next={moveNext}
      on:random={moveRandom}
      on:close={closePlayer}
    >
      <MediaPlayer
        {itemId}
        {autoplay}
        {hasNext}
        bind:muted
        bind:loop
        bind:volume
        bind:speed
        {quality}
        takePrefetchedSource={(id) => prefetcher.take(id)}
        on:playerEvent={handlePlayerEvent}
        on:next={moveNext}
        on:previous={movePrevious}
        on:skip={moveNext}
        on:close={closePlayer}
      />
    </PlayerOverlay>
  {/if}
  <p data-testid="prefetch-status" role="status" aria-live="polite">
    {prefetchAnnouncement}
  </p>
  <p data-testid="player-state" aria-live="polite">{playerState}</p>
</main>

<style>
  main {
    display: grid;
    gap: 1rem;
    margin: 2rem auto;
    max-width: 58rem;
    padding: 0 1.25rem;
  }

  h1 {
    font-size: clamp(2rem, 6vw, 3.5rem);
    line-height: 1.1;
  }

  label {
    color: #cbd5e1;
  }

  .autoplay-setting {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  select {
    justify-self: start;
    border: 1px solid #475569;
    border-radius: 0.4rem;
    background: #1f2937;
    color: inherit;
    font: inherit;
    padding: 0.55rem 0.8rem;
  }

  [data-testid="player-state"] {
    color: #cbd5e1;
  }
</style>
