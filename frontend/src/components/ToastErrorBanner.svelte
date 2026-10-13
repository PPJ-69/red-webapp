<script lang="ts">
  import { createEventDispatcher } from "svelte";

  import { ApiError } from "../services/errors";

  export let error: unknown = null;

  const dispatch = createEventDispatcher<{ dismiss: undefined; retry: undefined }>();

  function messageFor(value: unknown): string {
    if (!(value instanceof ApiError)) {
      return "Something went wrong. Please try again.";
    }
    switch (value.category) {
      case "network_error":
        return "The server could not be reached. Check your connection and retry.";
      case "request_cancelled":
        return "This request was cancelled.";
      case "malformed_response":
        return "The server returned an invalid response.";
      case "not_found":
      case "invalid_media_id":
        return "This media item could not be found.";
      case "unsupported_media":
        return "This media format is not supported.";
      case "rate_limited":
      case "local_rate_limited":
        return value.retryAfter === undefined
          ? "Too many requests. Please wait and try again."
          : `Too many requests. Try again in ${value.retryAfter} seconds.`;
      case "upstream_timeout":
        return "The provider took too long to respond. Please retry.";
      case "provider_unavailable":
        return "The provider is temporarily unavailable. Please retry.";
      case "upstream_authentication_failed":
      case "provider_error":
      case "connection_interrupted":
        return "The provider could not complete the request. Please retry.";
      case "invalid_request":
        return "The request could not be understood.";
      case "unauthorized":
        return "This request is not authorized.";
      case "forbidden":
        return "This request is not allowed.";
      case "range_not_satisfiable":
        return "The requested media range is unavailable.";
      case "internal_error":
        return "An unexpected server error occurred. Please retry.";
    }
  }
</script>

{#if error}
  <div class="error-banner" role="alert" data-testid="error-banner">
    <span>{messageFor(error)}</span>
    <button type="button" data-testid="retry-error" on:click={() => dispatch("retry", undefined)}>
      Retry
    </button>
    <button type="button" aria-label="Dismiss error" on:click={() => dispatch("dismiss", undefined)}>
      Dismiss
    </button>
  </div>
{/if}

<style>
  .error-banner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.65rem;
    padding: 0.75rem 1rem;
    border: 1px solid #fca5a5;
    border-radius: 0.5rem;
    background: #450a0a;
    color: #fee2e2;
  }

  span {
    flex: 1;
  }

  button {
    min-height: 2.25rem;
    border: 1px solid currentColor;
    border-radius: 0.375rem;
    background: transparent;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.35rem 0.6rem;
  }

  button:focus-visible {
    outline: 3px solid #fff;
    outline-offset: 2px;
  }
</style>
