<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { AppPanel } from "../types/navigation";

  export let active: AppPanel = "discovery";

  const dispatch = createEventDispatcher<{ navigate: { panel: AppPanel } }>();
  const links: { panel: AppPanel; label: string }[] = [
    { panel: "discovery", label: "Discover" },
    { panel: "favorites", label: "Favorites" },
    { panel: "settings", label: "Settings" },
  ];
</script>

<nav aria-label="Main navigation" data-testid="main-navigation">
  {#each links as item}
    <button
      type="button"
      data-testid={`navigate-${item.panel}`}
      aria-current={active === item.panel ? "page" : undefined}
      on:click={() => dispatch("navigate", { panel: item.panel })}
    >{item.label}</button>
  {/each}
</nav>

<style>
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  button {
    min-height: 2.5rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.4rem 0.7rem;
  }

  button[aria-current="page"] {
    border-width: 2px;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
