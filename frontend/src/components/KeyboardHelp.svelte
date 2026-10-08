<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let open = false;

  const dispatch = createEventDispatcher<{ close: void }>();
  let dialog: HTMLDialogElement;

  $: if (dialog && open && !dialog.open) dialog.showModal();
  $: if (dialog && !open && dialog.open) dialog.close();

  function close(): void {
    dispatch("close", undefined);
  }
</script>

<dialog
  bind:this={dialog}
  data-testid="keyboard-help-dialog"
  aria-labelledby="keyboard-help-title"
  on:cancel|preventDefault={close}
  on:close={() => {
    if (open) close();
  }}
>
  <div class="dialog-content">
    <h2 id="keyboard-help-title">Keyboard shortcuts</h2>
    <dl>
      <dt><kbd>Space</kbd></dt><dd>Play or pause</dd>
      <dt><kbd>←</kbd> / <kbd>→</kbd></dt><dd>Seek backward or forward 5 seconds</dd>
      <dt><kbd>↑</kbd> / <kbd>↓</kbd></dt><dd>Increase or decrease volume</dd>
      <dt><kbd>M</kbd></dt><dd>Toggle mute</dd>
      <dt><kbd>L</kbd></dt><dd>Toggle loop</dd>
      <dt><kbd>F</kbd></dt><dd>Toggle fullscreen</dd>
      <dt><kbd>?</kbd></dt><dd>Show shortcuts</dd>
      <dt><kbd>N</kbd> / <kbd>P</kbd></dt><dd>Next or previous intent</dd>
      <dt><kbd>R</kbd></dt><dd>Retry intent</dd>
      <dt><kbd>V</kbd></dt><dd>Favorite intent</dd>
      <dt><kbd>Esc</kbd></dt><dd>Close intent</dd>
    </dl>
    <button type="button" data-testid="close-keyboard-help" on:click={close}>
      Close
    </button>
  </div>
</dialog>

<style>
  dialog {
    width: min(32rem, calc(100vw - 2rem));
    max-height: min(85vh, 42rem);
    border: 1px solid #64748b;
    border-radius: 0.65rem;
    background: #111827;
    color: #f8fafc;
    padding: 0;
  }

  dialog::backdrop {
    background: rgb(0 0 0 / 72%);
  }

  .dialog-content {
    display: grid;
    gap: 1rem;
    padding: 1.25rem;
  }

  h2 {
    margin: 0;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.65rem 1rem;
    margin: 0;
  }

  dd {
    margin: 0;
  }

  kbd {
    border: 1px solid #64748b;
    border-radius: 0.25rem;
    background: #1f2937;
    padding: 0.1rem 0.35rem;
  }

  button {
    justify-self: end;
    border: 1px solid #94a3b8;
    border-radius: 0.375rem;
    background: #1f2937;
    color: inherit;
    cursor: pointer;
    font: inherit;
    padding: 0.5rem 0.8rem;
  }

  button:focus-visible {
    outline: 3px solid #38bdf8;
    outline-offset: 2px;
  }
</style>
