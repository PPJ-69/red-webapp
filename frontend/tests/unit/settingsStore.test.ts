import { describe, expect, it } from "vitest";

import { createSettingsStore } from "../../src/stores/settingsStore";

describe("settings store", () => {
  it("keeps privacy mode locked on and clamps playback settings", () => {
    const store = createSettingsStore();

    store.setVolume(2);
    store.setSpeed(20);
    store.setLoop(true);
    store.setQuality("hd");
    store.setPrivacyMode(false);

    expect(store.getSnapshot()).toMatchObject({
      volume: 1,
      speed: 4,
      loop: true,
      quality: "hd",
      privacyMode: true,
      privacyModeLocked: true,
    });
  });

  it("validates values and lets subscribers observe updates", () => {
    const store = createSettingsStore();
    const observed: Array<{ volume: number; quality: string }> = [];
    const unsubscribe = store.subscribe((snapshot) => {
      observed.push({ volume: snapshot.volume, quality: snapshot.quality });
    });

    store.setVolume(0.4);
    store.setQuality("sd");
    unsubscribe();

    expect(observed).toEqual([
      { volume: 1, quality: "auto" },
      { volume: 0.4, quality: "auto" },
      { volume: 0.4, quality: "sd" },
    ]);
  });
});
