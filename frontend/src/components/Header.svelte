<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import type { AppPanel } from "../types/navigation";
  import Navigation from "./Navigation.svelte";

  export let active: AppPanel = "discovery";

  const dispatch = createEventDispatcher<{ navigate: { panel: AppPanel } }>();
</script>

<header class="app-header">
  <h1>Stream-First Media Browser</h1>
  <Navigation
    {active}
    on:navigate={(event) => dispatch("navigate", event.detail)}
  />
</header>

<style>
  .app-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  h1 {
    margin: 0;
    font-size: clamp(2rem, 6vw, 3.5rem);
    line-height: 1.1;
  }
</style>
