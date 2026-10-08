import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

import {
  createPlayerStore,
  IllegalPlayerTransitionError,
  INITIAL_PLAYER_SNAPSHOT,
  playerEventForMediaEvent,
  transitionPlayer,
} from "../../src/stores/playerStore";
import {
  PLAYER_STATES,
  type PlayerEvent,
  type PlayerSnapshot,
  type PlayerState,
} from "../../src/types/player";

const transitions: ReadonlyArray<
  readonly [PlayerState, PlayerEvent["type"], PlayerState]
> = [
  ["IDLE", "OPEN", "RESOLVING"],
  ["RESOLVING", "SOURCE_RESOLVED", "LOADING"],
  ["RESOLVING", "ERROR", "ERROR"],
  ["LOADING", "LOADED_METADATA", "PAUSED"],
  ["LOADING", "LOAD_STARTED", "LOADING"],
  ["LOADING", "PLAYING", "PLAYING"],
  ["LOADING", "PAUSE", "PAUSED"],
  ["LOADING", "SEEKING", "SEEKING"],
  ["LOADING", "ENDED", "ENDED"],
  ["LOADING", "ERROR", "ERROR"],
  ["PLAYING", "PAUSE", "PAUSED"],
  ["PLAYING", "SEEKING", "SEEKING"],
  ["PLAYING", "WAITING", "BUFFERING"],
  ["PLAYING", "ENDED", "ENDED"],
  ["PLAYING", "ERROR", "ERROR"],
  ["PAUSED", "PLAYING", "PLAYING"],
  ["PAUSED", "SEEKING", "SEEKING"],
  ["PAUSED", "WAITING", "BUFFERING"],
  ["PAUSED", "ENDED", "ENDED"],
  ["PAUSED", "ERROR", "ERROR"],
  ["SEEKING", "PLAYING", "PLAYING"],
  ["SEEKING", "PAUSE", "PAUSED"],
  ["SEEKING", "SEEKED", "PAUSED"],
  ["SEEKING", "WAITING", "BUFFERING"],
  ["SEEKING", "ENDED", "ENDED"],
  ["SEEKING", "ERROR", "ERROR"],
  ["BUFFERING", "PLAYING", "PLAYING"],
  ["BUFFERING", "PAUSE", "PAUSED"],
  ["BUFFERING", "SEEKING", "SEEKING"],
  ["BUFFERING", "CAN_PLAY", "PAUSED"],
  ["BUFFERING", "ENDED", "ENDED"],
  ["BUFFERING", "ERROR", "ERROR"],
  ["ENDED", "NEXT", "IDLE"],
  ["ENDED", "SKIP", "IDLE"],
  ["ERROR", "RETRY", "RESOLVING"],
  ["ERROR", "NEXT", "IDLE"],
  ["ERROR", "SKIP", "IDLE"],
];

function snapshotAt(state: PlayerState): PlayerSnapshot {
  return { ...INITIAL_PLAYER_SNAPSHOT, state };
}

describe("player state machine", () => {
  it.each(transitions)("%s + %s -> %s", (state, event, expected) => {
    const result = transitionPlayer(snapshotAt(state), { type: event });

    expect(result.state).toBe(expected);
  });

  it("preserves whether playback was active across seek completion", () => {
    const playingSeek = transitionPlayer(snapshotAt("PLAYING"), { type: "SEEKING" });
    const pausedSeek = transitionPlayer(snapshotAt("PAUSED"), { type: "SEEKING" });

    expect(transitionPlayer(playingSeek, { type: "SEEKED" }).state).toBe("PLAYING");
    expect(transitionPlayer(pausedSeek, { type: "SEEKED" }).state).toBe("PAUSED");
  });

  it("restores the playback state after buffering and seeking while buffering", () => {
    const buffering = transitionPlayer(snapshotAt("PLAYING"), { type: "WAITING" });
    const seeking = transitionPlayer(buffering, { type: "SEEKING" });

    expect(transitionPlayer(buffering, { type: "CAN_PLAY" }).state).toBe("PLAYING");
    expect(transitionPlayer(seeking, { type: "SEEKED" }).state).toBe("PLAYING");
    expect(
      transitionPlayer(
        transitionPlayer(snapshotAt("PAUSED"), { type: "WAITING" }),
        { type: "CAN_PLAY" },
      ).state,
    ).toBe("PAUSED");
  });

  it("toggles loop without changing the media state", () => {
    const first = transitionPlayer(snapshotAt("PLAYING"), { type: "LOOP" });
    const second = transitionPlayer(first, { type: "LOOP" });

    expect(first).toMatchObject({ state: "PLAYING", loop: true });
    expect(second).toMatchObject({ state: "PLAYING", loop: false });
  });

  it("allows reopening from any state and resetting to idle", () => {
    for (const state of PLAYER_STATES) {
      expect(transitionPlayer(snapshotAt(state), { type: "OPEN" }).state).toBe(
        "RESOLVING",
      );
      expect(transitionPlayer(snapshotAt(state), { type: "RESET" }).state).toBe(
        "IDLE",
      );
    }
  });

  it("rejects every unlisted state/event pair", () => {
    const allowed = new Set(
      transitions.map(([state, event]) => `${state}:${event}`),
    );
    for (const state of PLAYER_STATES) {
      for (const event of [
        "OPEN",
        "SOURCE_RESOLVED",
        "LOAD_STARTED",
        "LOADED_METADATA",
        "PLAYING",
        "PAUSE",
        "SEEKING",
        "SEEKED",
        "WAITING",
        "CAN_PLAY",
        "ENDED",
        "ERROR",
        "RETRY",
        "SKIP",
        "NEXT",
      ] as const) {
        if (
          event === "OPEN" ||
          event === "RESET" ||
          event === "LOOP" ||
          ((event === "NEXT" || event === "SKIP") && state !== "IDLE")
        ) {
          continue;
        }
        if (allowed.has(`${state}:${event}`)) continue;
        expect(() =>
          transitionPlayer(snapshotAt(state), { type: event }),
        ).toThrow(IllegalPlayerTransitionError);
      }
    }
  });

  it("maps native media events to state events and ignores irrelevant event types", () => {
    expect(playerEventForMediaEvent("playing")).toEqual({ type: "PLAYING" });
    expect(playerEventForMediaEvent("stalled")).toEqual({ type: "WAITING" });
    expect(playerEventForMediaEvent("emptied")).toEqual({ type: "RESET" });
    expect(playerEventForMediaEvent("timeupdate")).toBeNull();
    expect(playerEventForMediaEvent("durationchange")).toBeNull();
  });

  it("dispatches simulated startup, seek, stall, end, and error event sequences", () => {
    const store = createPlayerStore();
    store.dispatch({ type: "OPEN" });
    expect(store.getSnapshot().state).toBe("RESOLVING");
    store.dispatch({ type: "SOURCE_RESOLVED" });
    store.dispatchMediaEvent("loadstart");
    expect(store.getSnapshot().state).toBe("LOADING");
    store.dispatchMediaEvent("loadedmetadata");
    expect(store.getSnapshot().state).toBe("PAUSED");
    store.dispatchMediaEvent("playing");
    store.dispatchMediaEvent("seeking");
    store.dispatchMediaEvent("seeked");
    expect(store.getSnapshot().state).toBe("PLAYING");
    store.dispatchMediaEvent("stalled");
    expect(store.getSnapshot().state).toBe("BUFFERING");
    store.dispatchMediaEvent("canplay");
    store.dispatchMediaEvent("ended");
    expect(store.getSnapshot().state).toBe("ENDED");
    store.dispatch({ type: "NEXT" });
    store.dispatch({ type: "OPEN" });
    store.dispatch({ type: "SOURCE_RESOLVED" });
    store.dispatchMediaEvent("loadstart");
    expect(store.getSnapshot().state).toBe("LOADING");
    store.dispatchMediaEvent("error");
    expect(store.getSnapshot().state).toBe("ERROR");
    store.dispatch({ type: "RETRY" });
    expect(store.getSnapshot().state).toBe("RESOLVING");
  });

  it("notifies subscribers with state updates", () => {
    const store = createPlayerStore();
    const observed: PlayerState[] = [];
    const unsubscribe = store.subscribe(({ state }) => observed.push(state));
    store.dispatch({ type: "OPEN" });
    store.dispatch({ type: "SOURCE_RESOLVED" });
    unsubscribe();

    expect(observed).toEqual(["IDLE", "RESOLVING", "LOADING"]);
  });

  it("contains no custom playback clock or polling timer", async () => {
    const contents = readFileSync(
      new URL("../../src/stores/playerStore.ts", import.meta.url),
      "utf8",
    );

    expect(contents).not.toMatch(/\b(setInterval|setTimeout|requestAnimationFrame)\s*\(/);
    expect(contents).not.toMatch(/\b(currentTime|duration|buffered)\b/);
  });
});
