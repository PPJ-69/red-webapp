<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { Creator, MediaItem } from "../types/api";

  export let item: MediaItem;

  const dispatch = createEventDispatcher<{
    creator: { creator: Creator };
    tag: { tag: string };
  }>();

  function openCreator(): void {
    if (item.creator) dispatch("creator", { creator: item.creator });
  }
</script>

<section aria-label="Media information" data-testid="media-info">
  <h3>Media details</h3>
  {#if item.description}
    <p>{item.description}</p>
  {/if}
  <dl>
    {#if item.duration !== null && item.duration !== undefined}
      <div>
        <dt>Duration</dt>
        <dd>{Math.floor(item.duration / 60)}:{String(Math.floor(item.duration % 60)).padStart(2, "0")}</dd>
      </div>
    {/if}
    {#if item.width && item.height}
      <div>
        <dt>Dimensions</dt>
        <dd>{item.width} × {item.height}</dd>
      </div>
    {/if}
    {#if item.creator}
      <div>
        <dt>Creator</dt>
        <dd>
          <button
            type="button"
            data-testid="creator-link"
            on:click={openCreator}
          >{item.creator.displayName ?? item.creator.username}</button>
        </dd>
      </div>
    {/if}
  </dl>
  {#if item.tags && item.tags.length > 0}
    <ul aria-label="Media tags">
      {#each item.tags as tag (tag)}
        <li>
          <button
            type="button"
            data-testid={`tag-${tag}`}
            on:click={() => dispatch("tag", { tag })}
          >#{tag}</button>
        </li>
      {/each}
    </ul>
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

  h3,
  p {
    margin: 0;
  }

  p {
    color: #cbd5e1;
  }

  dl,
  dl div {
    display: grid;
    gap: 0.35rem;
  }

  dl {
    margin: 0;
  }

  dt {
    color: #94a3b8;
    font-size: 0.85rem;
  }

  dd {
    margin: 0;
  }

  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  button {
    min-height: 2.25rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.3rem 0.55rem;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
