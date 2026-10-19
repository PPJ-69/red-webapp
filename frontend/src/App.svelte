<script lang="ts">
  import { onMount, tick } from "svelte";

  import CreatorPanel from "./components/CreatorPanel.svelte";
  import FavoritesPanel from "./components/FavoritesPanel.svelte";
  import Header from "./components/Header.svelte";
  import InfoPanel from "./components/InfoPanel.svelte";
  import MediaPlayer from "./components/MediaPlayer.svelte";
  import PlayerOverlay from "./components/PlayerOverlay.svelte";
  import ResultGrid from "./components/ResultGrid.svelte";
  import SearchBar from "./components/SearchBar.svelte";
  import SettingsPanel from "./components/SettingsPanel.svelte";
  import ThumbnailRail from "./components/ThumbnailRail.svelte";
  import ToastErrorBanner from "./components/ToastErrorBanner.svelte";
  import type { AppPanel } from "./types/navigation";
  import { sourceService } from "./services/sourceService";
  import { PlaybackPrefetcher } from "./services/prefetch";
  import { ResultsPlaybackQueue } from "./services/resultsQueue";
  import { searchContextStore } from "./stores/searchContextStore";
  import { sessionStore } from "./stores/sessionStore";
  import type { MediaItem, MediaSource } from "./types/api";
  import type { PlayerEvent, PlayerState, Quality } from "./types/player";

  const resultsQueue = new ResultsPlaybackQueue<MediaItem>(
    Math.random,
    () => sessionStore.getSnapshot().seen,
  );
  const prefetcher = new PlaybackPrefetcher<MediaSource>();
  let searchBar: SearchBar;
  let playerState: PlayerState = "IDLE";
  let playerOpen = false;
  let activePanel: AppPanel = "discovery";
  let hasPrevious = false;
  let hasNext = false;
  let canRandom = false;
  let autoplay = false;
  let playerOpener: HTMLButtonElement;
  let resultOpener: HTMLButtonElement | undefined;
  let savedScrollPosition = 0;
  let prefetchAnnouncement = "";
  let searchAnnouncement = "";
  let searchError: unknown = null;
  let displayedResults: MediaItem[] = [];
  let resultsHaveMore = false;
  let loadingInitialResults = false;
  let loadingMoreResults = false;
  let currentItem: MediaItem | undefined;
  let currentItemId: string | null = null;
  let creatorUsername = "";
  let muted = true;
  let loop = false;
  let volume = 1;
  let speed = 1;
  const quality: Quality = "auto";
  let lastSearch: {
    rawQuery: string;
    order: "trending" | "latest" | "top" | "score";
    limit: number;
  } | null = null;

  function updateQueue(item: MediaItem): void {
    currentItem = item;
    currentItemId = item.id;
    updateQueueCapabilities();
    prefetchAnnouncement = "";
    primeNextSource();
  }

  function updateQueueCapabilities(): void {
    hasPrevious = resultsQueue.hasPrevious;
    hasNext = resultsQueue.hasNext;
    canRandom = resultsQueue.canRandom;
  }

  function refreshQueue(items: readonly MediaItem[]): void {
    resultsQueue.replaceItems(items);
    currentItem = resultsQueue.currentOrUndefined;
    currentItemId = currentItem?.id ?? null;
    updateQueueCapabilities();
    if (currentItem === undefined) {
      playerOpen = false;
      prefetcher.cancel();
    } else {
      primeNextSource();
    }
  }

  function primeNextSource(): void {
    if (!playerOpen || resultsQueue.currentOrUndefined === undefined) return;
    void prefetcher
      .prepareNext(resultsQueue, (nextId, signal) =>
        sourceService.resolve(nextId, quality, signal),
      )
      .then(() => undefined)
      .catch(() => {
        prefetchAnnouncement =
          "The next source was not prepared; it will resolve when selected.";
      });
  }

  function moveNext(): void {
    resultsQueue.next();
  }

  function movePrevious(): void {
    resultsQueue.previous();
  }

  function moveRandom(): void {
    resultsQueue.random();
  }

  async function closePlayer(): Promise<void> {
    playerOpen = false;
    prefetcher.cancel();
    await tick();
    window.scrollTo(0, savedScrollPosition);
    resultOpener?.focus();
  }

  async function reopenPlayer(): Promise<void> {
    if (currentItem === undefined) return;
    resultOpener = playerOpener;
    playerOpen = true;
    await tick();
    window.scrollTo(0, savedScrollPosition);
    primeNextSource();
  }

  function openItem(
    event: CustomEvent<{
      item: MediaItem;
      index: number;
      opener: HTMLButtonElement;
    }>,
  ): void {
    resultOpener = event.detail.opener;
    savedScrollPosition = window.scrollY;
    resultsQueue.select(event.detail.item.id);
    playerOpen = true;
    primeNextSource();
  }

  async function performSearch(
    request: {
      rawQuery: string;
      order: "trending" | "latest" | "top" | "score";
      limit: number;
    },
  ): Promise<void> {
    lastSearch = request;
    activePanel = "discovery";
    playerOpen = false;
    prefetcher.cancel();
    searchError = null;
    searchAnnouncement = "Searching…";
    const succeeded = await searchContextStore.search(request.rawQuery, {
      order: request.order,
      limit: request.limit,
    });
    const result = searchContextStore.getSnapshot();
    if (succeeded) {
      searchAnnouncement = `${result.itemsById.size} results loaded.`;
    } else if (result.error !== null) {
      searchAnnouncement = "";
      searchError = result.error;
    }
  }

  function submitSearch(
    event: CustomEvent<{
      rawQuery: string;
      order: "trending" | "latest" | "top" | "score";
      limit: number;
    }>,
  ): Promise<void> {
    return performSearch(event.detail);
  }

  function loadNextPage(): void {
    if (!searchContextStore.getSnapshot().hasMore) return;
    void searchContextStore.loadNextPage().then((succeeded) => {
      const result = searchContextStore.getSnapshot();
      if (succeeded) {
        searchAnnouncement = `${result.itemsById.size} results loaded.`;
      } else if (result.error !== null) {
        searchError = result.error;
      }
    });
  }

  function setPanel(panel: AppPanel): void {
    activePanel = panel;
    if (panel !== "discovery") {
      playerOpen = false;
      prefetcher.cancel();
    }
  }

  function handleWindowKeydown(event: KeyboardEvent): void {
    if (
      !playerOpen ||
      (event.key !== "g" && event.key !== "G") ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.target instanceof Element &&
        event.target.closest(
          "input, textarea, select, [contenteditable]:not([contenteditable='false'])",
        )
    ) {
      return;
    }
    event.preventDefault();
    void closePlayer();
  }

  function retrySearch(): void {
    if (lastSearch === null) return;
    void performSearch(lastSearch);
  }

  onMount(() => {
    const unsubscribeQueue = resultsQueue.subscribe(updateQueue);
    const unsubscribeSearch = searchContextStore.subscribe((snapshot) => {
      displayedResults = [...snapshot.itemsById.values()];
      resultsHaveMore = snapshot.hasMore;
      loadingInitialResults = snapshot.loadingInitial;
      loadingMoreResults = snapshot.loadingMore;
      refreshQueue(displayedResults);
    });
    window.addEventListener("keydown", handleWindowKeydown);
    return () => {
      unsubscribeQueue();
      unsubscribeSearch();
      window.removeEventListener("keydown", handleWindowKeydown);
      prefetcher.cancel();
      searchContextStore.discard();
    };
  });
</script>

<svelte:head>
  <meta name="description" content="A native media player backed by a stream relay." />
</svelte:head>

<div class="app-shell">
  <Header active={activePanel} on:navigate={(event) => setPanel(event.detail.panel)} />
  <main>
    <ToastErrorBanner
      error={searchError}
      on:dismiss={() => (searchError = null)}
      on:retry={retrySearch}
    />

    {#if activePanel === "discovery"}
      <SearchBar bind:this={searchBar} on:submit={submitSearch} />
      <p data-testid="search-status" role="status" aria-live="polite">
        {searchAnnouncement}
      </p>
      {#if displayedResults.length > 0 || loadingInitialResults || loadingMoreResults}
        <ResultGrid
          items={displayedResults}
          {currentItemId}
          loading={loadingMoreResults}
          hasMore={resultsHaveMore}
          on:open-item={openItem}
          on:load={loadNextPage}
        />
      {:else if !loadingInitialResults}
        <p data-testid="discovery-empty">Search for media to start browsing.</p>
      {/if}
      {#if currentItem && !playerOpen}
        <button
          type="button"
          class="open-player"
          data-testid="open-player"
          bind:this={playerOpener}
          aria-expanded="false"
          on:click={reopenPlayer}
        >Open selected item</button>
      {/if}
    {:else if activePanel === "favorites"}
      <FavoritesPanel open={true} />
    {:else}
      <SettingsPanel />
    {/if}

    {#if playerOpen && currentItem}
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
          itemId={currentItem.id}
          {autoplay}
          {hasNext}
          bind:muted
          bind:loop
          bind:volume
          bind:speed
          {quality}
          takePrefetchedSource={(id) => prefetcher.take(id)}
          on:playerEvent={(event) => (playerState = event.detail.state)}
          on:next={moveNext}
          on:previous={movePrevious}
          on:skip={moveNext}
          on:close={closePlayer}
        />
        <ThumbnailRail
          items={resultsQueue.items}
          currentItemId={currentItem.id}
          on:select={(event) => resultsQueue.select(event.detail.id)}
        />
        <InfoPanel
          item={currentItem}
          on:creator={(event) => (creatorUsername = event.detail.creator.username)}
          on:tag={(event) => {
            activePanel = "discovery";
            searchBar.searchTag(event.detail.tag);
          }}
        />
        {#if creatorUsername}
          <CreatorPanel
            username={creatorUsername}
            on:search={(event) => {
              creatorUsername = "";
              activePanel = "discovery";
              searchBar.searchCreator(event.detail.username);
            }}
            on:close={() => (creatorUsername = "")}
          />
        {/if}
      </PlayerOverlay>
    {/if}

    <p data-testid="prefetch-status" role="status" aria-live="polite">
      {prefetchAnnouncement}
    </p>
    <p data-testid="player-state" role="status" aria-live="polite">{playerState}</p>
    <label class="autoplay-setting">
      <input type="checkbox" bind:checked={autoplay} data-testid="autoplay-setting" />
      Play next automatically
    </label>
  </main>
</div>

<style>
  .app-shell {
    display: grid;
    gap: 1rem;
    box-sizing: border-box;
    width: min(100%, 74.5rem);
    margin: 2rem auto;
    padding: 0 1.25rem;
  }

  main {
    display: grid;
    gap: 1rem;
    min-width: 0;
  }

  .autoplay-setting {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #cbd5e1;
  }

  .open-player {
    justify-self: start;
    min-height: 2.5rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.4rem 0.7rem;
  }

  .open-player:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
