import { createMemoryStore, type Store } from "./storeInterface";

export type PlaybackQuality = "auto" | "hd" | "sd";

export type SettingsSnapshot = {
  volume: number;
  speed: number;
  loop: boolean;
  quality: PlaybackQuality;
  privacyMode: boolean;
  privacyModeLocked: boolean;
};

export const INITIAL_SETTINGS_SNAPSHOT: SettingsSnapshot = Object.freeze({
  volume: 1,
  speed: 1,
  loop: false,
  quality: "auto",
  privacyMode: true,
  privacyModeLocked: true,
});

export interface SettingsStore extends Store<SettingsSnapshot> {
  setVolume(value: number): void;
  setSpeed(value: number): void;
  setLoop(value: boolean): void;
  setQuality(value: PlaybackQuality): void;
  setPrivacyMode(value: boolean): void;
  reset(): void;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function createSettingsStore(
  initialSnapshot: Partial<SettingsSnapshot> = {},
): SettingsStore {
  const base: SettingsSnapshot = {
    ...INITIAL_SETTINGS_SNAPSHOT,
    ...initialSnapshot,
  };

  const store = createMemoryStore(base);

  function updateSnapshot(mutator: (snapshot: SettingsSnapshot) => SettingsSnapshot): void {
    store.set(mutator(store.getSnapshot()));
  }

  return {
    subscribe: store.subscribe,
    getSnapshot: store.getSnapshot,
    set: store.set,
    update: store.update,
    reset: () => store.set({ ...INITIAL_SETTINGS_SNAPSHOT }),
    setVolume(value: number): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        volume: clamp(value, 0, 1),
      }));
    },
    setSpeed(value: number): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        speed: clamp(value, 0.25, 4),
      }));
    },
    setLoop(value: boolean): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        loop: value,
      }));
    },
    setQuality(value: PlaybackQuality): void {
      if (value !== "auto" && value !== "hd" && value !== "sd") return;
      updateSnapshot((snapshot) => ({
        ...snapshot,
        quality: value,
      }));
    },
    setPrivacyMode(value: boolean): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        privacyMode: snapshot.privacyModeLocked ? true : Boolean(value),
      }));
    },
  };
}

export const settingsStore = createSettingsStore();
