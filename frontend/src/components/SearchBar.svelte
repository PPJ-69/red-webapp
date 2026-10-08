<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import {
    parseSearchQuery,
    type ParsedSearchQuery,
  } from "../utils/queryParser";
  import SearchFilters from "./SearchFilters.svelte";
  import type { SearchOrder } from "../types/search";
  import {
    tagSuggestService,
    type TagSuggestService,
  } from "../services/tagSuggest";

  export let suggestionsService: TagSuggestService = tagSuggestService;
  export let order: SearchOrder = "trending";
  export let limit = 20;

  const dispatch = createEventDispatcher<{
    submit: {
      rawQuery: string;
      parsed: ParsedSearchQuery;
      order: SearchOrder;
      limit: number;
    };
  }>();

  let rawQuery = "";
  let suggestions: string[] = [];
  let activeSuggestion = -1;
  let suggestionError = "";
  let requestId = 0;
  let input: HTMLInputElement;

  $: parsed = parseSearchQuery(rawQuery);

  function partialTag(value: string): string {
    const token = value.trim().split(/\s+/u).at(-1) ?? "";
    return token.startsWith("#") ? token.slice(1) : token;
  }

  async function updateSuggestions(): Promise<void> {
    const currentRequest = ++requestId;
    const partial = partialTag(rawQuery);
    suggestions = [];
    activeSuggestion = -1;
    suggestionError = "";
    try {
      const results = await suggestionsService.suggest(partial);
      if (currentRequest === requestId) suggestions = results;
    } catch {
      if (currentRequest === requestId) {
        suggestionError = "Tag suggestions are temporarily unavailable.";
      }
    }
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    suggestionsService.cancel();
    suggestions = [];
    dispatch("submit", {
      rawQuery,
      parsed: parseSearchQuery(rawQuery),
      order,
      limit,
    });
  }

  function chooseSuggestion(value: string): void {
    const pieces = rawQuery.trimEnd().split(/\s+/u);
    pieces.pop();
    rawQuery = `${pieces.length > 0 ? `${pieces.join(" ")} ` : ""}#${value} `;
    suggestionsService.cancel();
    suggestions = [];
    input?.focus();
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeSuggestion = (activeSuggestion + 1) % suggestions.length;
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeSuggestion =
        activeSuggestion <= 0 ? suggestions.length - 1 : activeSuggestion - 1;
    } else if (event.key === "Enter" && activeSuggestion >= 0) {
      event.preventDefault();
      chooseSuggestion(suggestions[activeSuggestion]);
    } else if (event.key === "Escape") {
      suggestionsService.cancel();
      suggestions = [];
    }
  }

  onDestroy(() => {
    requestId += 1;
    suggestionsService.cancel();
  });
</script>

<form class="search-bar" data-testid="search-form" on:submit={submit}>
  <div class="query-field">
    <label for="search-query">Search media</label>
    <div class="query-entry">
      <input
        bind:this={input}
        id="search-query"
        data-testid="search-query"
        type="search"
        autocomplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={suggestions.length > 0}
        aria-controls="tag-suggestions"
        aria-activedescendant={activeSuggestion >= 0
          ? `tag-option-${activeSuggestion}`
          : undefined}
        aria-describedby="query-guidance"
        placeholder="Search text, #tags, or @creators"
        bind:value={rawQuery}
        on:input={updateSuggestions}
        on:keydown={handleKeydown}
      />
      <button type="submit" data-testid="search-submit">Search</button>
    </div>
    <span id="query-guidance" class="guidance">
      Use #tag and @creator tokens to filter results.
    </span>
    {#if suggestions.length > 0}
      <ul
        id="tag-suggestions"
        class="suggestions"
        role="listbox"
        aria-label="Tag suggestions"
        data-testid="tag-suggestions"
      >
        {#each suggestions as suggestion, index}
          <li role="presentation">
            <button
              id={`tag-option-${index}`}
              type="button"
              role="option"
              aria-selected={activeSuggestion === index}
              data-testid="tag-suggestion"
              on:mousedown|preventDefault
              on:click={() => chooseSuggestion(suggestion)}
            >#{suggestion}</button>
          </li>
        {/each}
      </ul>
    {/if}
    {#if suggestionError}
      <p role="status" class="suggestion-error">{suggestionError}</p>
    {/if}
  </div>

  <SearchFilters
    bind:order
    bind:limit
    on:change={(event) => {
      order = event.detail.order;
      limit = event.detail.limit;
    }}
  />

  {#if parsed.chips.length > 0}
    <ul class="query-chips" aria-label="Parsed search filters" data-testid="query-chips">
      {#each parsed.chips as chip}
        <li data-chip-type={chip.type}>
          <span>{chip.type === "tag" ? "#" : "@"}{chip.value}</span>
        </li>
      {/each}
    </ul>
  {/if}
</form>

<style>
  .search-bar {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid #334155;
    border-radius: 0.6rem;
    background: #0f172a;
  }

  .query-field {
    position: relative;
    display: grid;
    gap: 0.4rem;
  }

  label,
  .guidance {
    color: #cbd5e1;
  }

  .query-entry {
    display: flex;
    gap: 0.5rem;
  }

  input,
  button {
    min-height: 2.7rem;
    border: 1px solid #64748b;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    font: inherit;
    padding: 0.45rem 0.7rem;
  }

  input {
    min-width: 0;
    flex: 1;
  }

  button {
    cursor: pointer;
  }

  input:focus-visible,
  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }

  .suggestions,
  .query-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .suggestions {
    position: absolute;
    z-index: 1;
    inset: calc(100% - 1rem) 0 auto;
    padding: 0.5rem;
    border: 1px solid #475569;
    border-radius: 0.4rem;
    background: #111827;
  }

  .suggestions button {
    min-height: 2rem;
  }

  .query-chips li {
    border: 1px solid #475569;
    border-radius: 999px;
    background: #1e293b;
    padding: 0.25rem 0.65rem;
  }

  .suggestion-error {
    margin: 0;
    color: #fecaca;
  }

  @media (max-width: 36rem) {
    .query-entry {
      flex-direction: column;
    }

    .suggestions {
      inset: calc(100% - 3rem) 0 auto;
    }
  }
</style>
