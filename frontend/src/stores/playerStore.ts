import { writable, type Readable } from "svelte/store";

import type {
  NativeMediaEventName,
  PlaybackState,
  PlayerEvent,
  PlayerSnapshot,
  PlayerState,
} from "../types/player";

export class IllegalPlayerTransitionError extends Error {
  constructor(state: PlayerState, event: PlayerEvent["type"]) {
    super(`Cannot apply ${event} while the player is ${state}.`);
    this.name = "IllegalPlayerTransitionError";
  }
}

export const INITIAL_PLAYER_SNAPSHOT: PlayerSnapshot = Object.freeze({
  state: "IDLE",
  loop: false,
  resumeState: null,
});

const NATIVE_EVENT_MAP: Readonly<
  Partial<Record<NativeMediaEventName, PlayerEvent["type"]>>
> = {
  loadstart: "LOAD_STARTED",
  loadedmetadata: "LOADED_METADATA",
  playing: "PLAYING",
  pause: "PAUSE",
  seeking: "SEEKING",
  seeked: "SEEKED",
  waiting: "WAITING",
  stalled: "WAITING",
  canplay: "CAN_PLAY",
  ended: "ENDED",
  error: "ERROR",
  emptied: "RESET",
};

export function playerEventForMediaEvent(
  eventName: NativeMediaEventName,
): PlayerEvent | null {
  const type = NATIVE_EVENT_MAP[eventName];
  return type === undefined ? null : { type };
}

function resumeStateFor(snapshot: PlayerSnapshot): PlaybackState {
  if (snapshot.state === "BUFFERING" && snapshot.resumeState !== null) {
    return snapshot.resumeState;
  }
  return snapshot.state === "PLAYING" ? "PLAYING" : "PAUSED";
}

function transition(
  snapshot: PlayerSnapshot,
  state: PlayerState,
  resumeState: PlaybackState | null = null,
): PlayerSnapshot {
  return { ...snapshot, state, resumeState };
}

export function transitionPlayer(
  snapshot: PlayerSnapshot,
  event: PlayerEvent,
): PlayerSnapshot {
  const state = snapshot.state;
  switch (event.type) {
    case "OPEN":
      return transition(snapshot, "RESOLVING");
    case "SOURCE_RESOLVED":
      if (state === "RESOLVING") return transition(snapshot, "LOADING");
      break;
    case "LOAD_STARTED":
      if (state === "LOADING") return snapshot;
      break;
    case "LOADED_METADATA":
      if (state === "LOADING") return transition(snapshot, "PAUSED");
      break;
    case "PLAYING":
      if (
        state === "LOADING" ||
        state === "PAUSED" ||
        state === "SEEKING" ||
        state === "BUFFERING"
      ) {
        return transition(snapshot, "PLAYING");
      }
      break;
    case "PAUSE":
      if (
        state === "LOADING" ||
        state === "PLAYING" ||
        state === "SEEKING" ||
        state === "BUFFERING"
      ) {
        return transition(snapshot, "PAUSED");
      }
      break;
    case "SEEKING":
      if (
        state === "LOADING" ||
        state === "PLAYING" ||
        state === "PAUSED" ||
        state === "BUFFERING"
      ) {
        return transition(snapshot, "SEEKING", resumeStateFor(snapshot));
      }
      break;
    case "SEEKED":
      if (state === "SEEKING") {
        return transition(snapshot, snapshot.resumeState ?? "PAUSED");
      }
      break;
    case "WAITING":
      if (state === "PLAYING" || state === "PAUSED" || state === "SEEKING") {
        return transition(snapshot, "BUFFERING", resumeStateFor(snapshot));
      }
      break;
    case "CAN_PLAY":
      if (state === "BUFFERING") {
        return transition(snapshot, snapshot.resumeState ?? "PAUSED");
      }
      break;
    case "ENDED":
      if (
        state === "LOADING" ||
        state === "PLAYING" ||
        state === "PAUSED" ||
        state === "SEEKING" ||
        state === "BUFFERING"
      ) {
        return transition(snapshot, "ENDED");
      }
      break;
    case "ERROR":
      if (
        state === "RESOLVING" ||
        state === "LOADING" ||
        state === "PLAYING" ||
        state === "PAUSED" ||
        state === "SEEKING" ||
        state === "BUFFERING"
      ) {
        return transition(snapshot, "ERROR");
      }
      break;
    case "RETRY":
      if (state === "ERROR") return transition(snapshot, "RESOLVING");
      break;
    case "SKIP":
    case "NEXT":
      if (state !== "IDLE") return transition(snapshot, "IDLE");
      break;
    case "LOOP":
      return { ...snapshot, loop: !snapshot.loop };
    case "RESET":
      return transition(snapshot, "IDLE");
  }
  throw new IllegalPlayerTransitionError(state, event.type);
}

export interface PlayerStore extends Readable<PlayerSnapshot> {
  dispatch(event: PlayerEvent): void;
  getSnapshot(): PlayerSnapshot;
  dispatchMediaEvent(eventName: NativeMediaEventName): void;
}

export function createPlayerStore(
  initial: PlayerSnapshot = INITIAL_PLAYER_SNAPSHOT,
): PlayerStore {
  const store = writable<PlayerSnapshot>(initial);
  let snapshot = initial;
  const dispatch = (event: PlayerEvent): void => {
    snapshot = transitionPlayer(snapshot, event);
    store.set(snapshot);
  };

  return {
    subscribe: store.subscribe,
    dispatch,
    getSnapshot() {
      return snapshot;
    },
    dispatchMediaEvent(eventName) {
      const event = playerEventForMediaEvent(eventName);
      if (event !== null) dispatch(event);
    },
  };
}
