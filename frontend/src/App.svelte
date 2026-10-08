<script lang="ts">
  import MediaPlayer from "./components/MediaPlayer.svelte";
  import type { PlayerEvent, PlayerState, Quality } from "./types/player";

  let itemId = "sample-media";
  let playerState: PlayerState = "IDLE";
  const quality: Quality = "auto";

  function handlePlayerEvent(
    event: CustomEvent<{ event: PlayerEvent; state: PlayerState }>,
  ): void {
    playerState = event.detail.state;
  }
</script>

<svelte:head>
  <meta name="description" content="A native media player backed by a stream relay." />
</svelte:head>

<main>
  <h1>Stream-First Media Browser</h1>
  <label for="item">Test media</label>
  <select id="item" bind:value={itemId} data-testid="media-select">
    <option value="sample-media">Sample media</option>
    <option value="sample-media-two">Second sample</option>
  </select>
  <MediaPlayer
    {itemId}
    autoplay={false}
    muted={true}
    loop={false}
    volume={1}
    speed={1}
    {quality}
    on:playerEvent={handlePlayerEvent}
  />
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
