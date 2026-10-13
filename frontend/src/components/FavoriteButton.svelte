<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { sessionStore } from "../stores/sessionStore";

  export let mediaId: string;

  const dispatch = createEventDispatcher<{ change: { mediaId: string; favorite: boolean } }>();

  $: favorite = $sessionStore.favorites.includes(mediaId);

  function toggle(): void {
    sessionStore.toggleFavorite(mediaId);
    dispatch("change", { mediaId, favorite: sessionStore.isFavorite(mediaId) });
  }
</script>

<button
  type="button"
  class="favorite"
  data-testid={`favorite-${mediaId}`}
  aria-label={favorite ? "Remove from favorites" : "Add to favorites"}
  aria-pressed={favorite}
  on:click={toggle}
>
  <span aria-hidden="true">{favorite ? "★" : "☆"}</span>
  <span>{favorite ? "Favorited" : "Favorite"}</span>
</button>

<style>
  .favorite {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.25rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.35rem 0.6rem;
  }

  .favorite:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
