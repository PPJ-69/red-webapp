<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let currentTime = 0;
  export let duration = 0;
  export let playing = false;
  export let volume = 1;
  export let muted = false;
  export let speed = 1;
  export let loop = false;

  const dispatch = createEventDispatcher<{
    playPause: void;
    seek: number;
    volume: number;
    mute: void;
    speed: number;
    loop: void;
    fullscreen: void;
    help: void;
  }>();

  const speeds = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];

  function formatTime(seconds: number): string {
    if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
    const wholeSeconds = Math.floor(seconds);
    const minutes = Math.floor(wholeSeconds / 60);
    return `${minutes}:${String(wholeSeconds % 60).padStart(2, "0")}`;
  }
</script>

<div
  class="player-controls"
  data-testid="player-controls"
  role="group"
  aria-label="Playback controls"
>
  <div class="timeline">
    <label for="seek">Playback position</label>
    <input
      id="seek"
      data-testid="seek"
      type="range"
      min="0"
      max={duration > 0 ? duration : 0}
      step="0.1"
      value={Math.min(currentTime, duration || 0)}
      disabled={!Number.isFinite(duration) || duration <= 0}
      aria-valuetext={`${formatTime(currentTime)} of ${formatTime(duration)}`}
      on:input={(event) =>
        dispatch("seek", Number((event.currentTarget as HTMLInputElement).value))}
    />
    <output for="seek">{formatTime(currentTime)} / {formatTime(duration)}</output>
  </div>

  <div class="actions">
    <button
      type="button"
      data-testid="play-pause"
      aria-label={playing ? "Pause" : "Play"}
      on:click={() => dispatch("playPause", undefined)}
    >{playing ? "Pause" : "Play"}</button>

    <button
      type="button"
      data-testid="mute"
      aria-label={muted || volume === 0 ? "Unmute" : "Mute"}
      aria-pressed={muted}
      on:click={() => dispatch("mute", undefined)}
    >{muted || volume === 0 ? "Unmute" : "Mute"}</button>

    <label for="volume">Volume</label>
    <input
      id="volume"
      data-testid="volume"
      type="range"
      min="0"
      max="1"
      step="0.05"
      value={volume}
      aria-valuetext={`${Math.round(volume * 100)} percent`}
      on:input={(event) =>
        dispatch("volume", Number((event.currentTarget as HTMLInputElement).value))}
    />

    <label for="speed">Playback speed</label>
    <select
      id="speed"
      data-testid="speed"
      value={speed}
      on:change={(event) =>
        dispatch("speed", Number((event.currentTarget as HTMLSelectElement).value))}
    >
      {#each speeds as rate}
        <option value={rate}>{rate}×</option>
      {/each}
    </select>

    <button
      type="button"
      data-testid="loop"
      aria-label={loop ? "Disable loop" : "Enable loop"}
      aria-pressed={loop}
      on:click={() => dispatch("loop", undefined)}
    >Loop</button>

    <button
      type="button"
      data-testid="fullscreen"
      aria-label="Toggle fullscreen"
      on:click={() => dispatch("fullscreen", undefined)}
    >Fullscreen</button>

    <button
      type="button"
      data-testid="keyboard-help"
      aria-label="Show keyboard shortcuts"
      on:click={() => dispatch("help", undefined)}
    >Shortcuts</button>
  </div>
</div>

<style>
  .player-controls {
    display: grid;
    gap: 0.75rem;
    padding: 0.85rem;
    background: #111827;
    color: #f8fafc;
  }

  .timeline {
    display: grid;
    grid-template-columns: auto minmax(5rem, 1fr) auto;
    align-items: center;
    gap: 0.75rem;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
  }

  button,
  select {
    min-height: 2.5rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    font: inherit;
    padding: 0.4rem 0.7rem;
  }

  button {
    cursor: pointer;
  }

  input[type="range"] {
    accent-color: #38bdf8;
  }

  button:focus-visible,
  select:focus-visible,
  input:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }

  @media (max-width: 36rem) {
    .timeline {
      grid-template-columns: 1fr auto;
    }

    .timeline label {
      grid-column: 1 / -1;
    }

    .actions {
      gap: 0.45rem;
    }
  }
</style>
