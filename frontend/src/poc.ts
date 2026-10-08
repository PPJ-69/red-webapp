import "./poc.css";

const mediaIds = [
  "sample-media",
  "sample-media-two",
  "sample-media-failure",
] as const;
type MediaId = (typeof mediaIds)[number];

const mediaSelect = element<HTMLSelectElement>("media");
const player = element<HTMLVideoElement>("player");
const status = element<HTMLParagraphElement>("status");
const sourceKind = element<HTMLParagraphElement>("source-kind");

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`Missing POC element: ${id}`);
  return found as T;
}

function setStatus(value: string): void {
  status.textContent = value;
}

async function setFault(fault: "clear" | "server_error"): Promise<void> {
  const response = await fetch(`/__poc/fault?fault=${fault}`, { method: "POST" });
  if (!response.ok) throw new Error("Could not update the local fake CDN fault.");
}

async function loadSelected(autoplay = false): Promise<void> {
  const mediaId = mediaSelect.value as MediaId;
  setStatus("Resolving source…");
  try {
    const response = await fetch(
      `/api/media/${encodeURIComponent(mediaId)}/source?quality=auto`,
    );
    if (!response.ok) throw new Error(`Source resolution failed (${response.status}).`);
    const source: { playbackUrl: string; kind?: string | null } = await response.json();
    player.pause();
    player.src = source.playbackUrl;
    player.load();
    sourceKind.textContent = `Source: ${source.kind ?? "unknown"}; ${source.playbackUrl}`;
    setStatus("Source loaded");
    if (autoplay) await player.play();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Source resolution failed.");
  }
}

element<HTMLButtonElement>("load").addEventListener("click", () => {
  void loadSelected();
});
element<HTMLButtonElement>("play").addEventListener("click", () => {
  void player.play().catch(() => setStatus("Playback could not start."));
});
element<HTMLButtonElement>("pause").addEventListener("click", () => player.pause());
element<HTMLButtonElement>("seek-back").addEventListener("click", () => {
  player.currentTime = Math.max(0, player.currentTime - 2);
});
element<HTMLButtonElement>("seek-forward").addEventListener("click", () => {
  if (Number.isFinite(player.duration)) {
    player.currentTime = Math.min(player.duration, player.currentTime + 2);
  }
});
element<HTMLButtonElement>("inject-failure").addEventListener("click", async () => {
  try {
    mediaSelect.value = "sample-media-failure";
    await setFault("server_error");
    await loadSelected();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Could not inject fault.");
  }
});
element<HTMLButtonElement>("retry").addEventListener("click", async () => {
  try {
    await setFault("clear");
    await loadSelected();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Retry failed.");
  }
});
element<HTMLButtonElement>("next").addEventListener("click", () => {
  const index = mediaIds.indexOf(mediaSelect.value as MediaId);
  mediaSelect.value = mediaIds[(index + 1) % mediaIds.length];
  void loadSelected();
});
element<HTMLButtonElement>("stop").addEventListener("click", () => {
  player.pause();
  player.removeAttribute("src");
  player.load();
  setStatus("Stopped");
});

player.addEventListener("playing", () => setStatus("Playing"));
player.addEventListener("pause", () => setStatus("Paused"));
player.addEventListener("waiting", () => setStatus("Buffering"));
player.addEventListener("error", () => {
  setStatus(`Playback failed${player.error ? ` (${player.error.code})` : ""}.`);
});
