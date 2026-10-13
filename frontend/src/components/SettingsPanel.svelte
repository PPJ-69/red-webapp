<script lang="ts">
  import { onDestroy } from "svelte";

  import { settingsStore } from "../stores/settingsStore";

  let snapshot = settingsStore.getSnapshot();

  const unsubscribe = settingsStore.subscribe((next) => {
    snapshot = next;
  });

  onDestroy(() => {
    unsubscribe();
  });
</script>

<section class="settings-panel" data-testid="settings-panel">
  <h2>Privacy</h2>
  <div class="privacy-row" data-testid="privacy-mode-row">
    <span>Privacy Mode</span>
    <span class="status" data-testid="privacy-mode-indicator" aria-live="polite">
      {snapshot.privacyModeLocked && snapshot.privacyMode ? "Locked ON" : "OFF"}
    </span>
  </div>
</section>

<style>
  .settings-panel {
    display: grid;
    gap: 0.5rem;
    padding: 1rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 0.6rem;
  }

  h2 {
    margin: 0;
    font-size: 1rem;
    color: #f8fafc;
  }

  .privacy-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    color: #cbd5e1;
  }

  .status {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: rgba(34, 197, 94, 0.14);
    border: 1px solid rgba(34, 197, 94, 0.6);
    color: #bbf7d0;
    padding: 0.2rem 0.55rem;
    font-size: 0.8rem;
  }
</style>
