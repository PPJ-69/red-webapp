<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import type { SearchOrder } from "../types/search";

  export let order: SearchOrder = "trending";
  export let limit = 20;

  const dispatch = createEventDispatcher<{
    change: { order: SearchOrder; limit: number };
  }>();

  const orders: ReadonlyArray<{ value: SearchOrder; label: string }> = [
    { value: "trending", label: "Trending" },
    { value: "latest", label: "Latest" },
    { value: "top", label: "Top" },
    { value: "score", label: "Score" },
  ];

  function emitChange(): void {
    dispatch("change", { order, limit });
  }

  function updateLimit(event: Event): void {
    const value = Number((event.currentTarget as HTMLInputElement).value);
    if (Number.isInteger(value) && value >= 1 && value <= 100) {
      limit = value;
      emitChange();
    }
  }
</script>

<div class="search-filters" role="group" aria-label="Search filters">
  <label for="search-order">Order</label>
  <select
    id="search-order"
    data-testid="search-order"
    bind:value={order}
    on:change={emitChange}
  >
    {#each orders as option}
      <option value={option.value}>{option.label}</option>
    {/each}
  </select>

  <label for="search-limit">Results per page</label>
  <input
    id="search-limit"
    data-testid="search-limit"
    type="number"
    min="1"
    max="100"
    step="1"
    value={limit}
    on:change={updateLimit}
  />
</div>

<style>
  .search-filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  label {
    color: #cbd5e1;
  }

  select,
  input {
    min-height: 2.5rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    font: inherit;
    padding: 0.4rem 0.65rem;
  }

  select:focus-visible,
  input:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
