export const PLAYER_STATES = [
  "IDLE",
  "RESOLVING",
  "LOADING",
  "PLAYING",
  "PAUSED",
  "SEEKING",
  "BUFFERING",
  "ENDED",
  "ERROR",
] as const;

export type PlayerState = (typeof PLAYER_STATES)[number];
export type PlaybackState = "PLAYING" | "PAUSED";
export type Quality = "auto" | "hd" | "sd";

export type PlayerEvent =
  | { type: "OPEN" }
  | { type: "SOURCE_RESOLVED" }
  | { type: "LOAD_STARTED" }
  | { type: "LOADED_METADATA" }
  | { type: "PLAYING" }
  | { type: "PAUSE" }
  | { type: "SEEKING" }
  | { type: "SEEKED" }
  | { type: "WAITING" }
  | { type: "CAN_PLAY" }
  | { type: "ENDED" }
  | { type: "ERROR" }
  | { type: "RETRY" }
  | { type: "SKIP" }
  | { type: "NEXT" }
  | { type: "LOOP" }
  | { type: "RESET" };

export interface PlayerSnapshot {
  readonly state: PlayerState;
  readonly loop: boolean;
  readonly resumeState: PlaybackState | null;
}

export type NativeMediaEventName =
  | "loadstart"
  | "loadedmetadata"
  | "playing"
  | "pause"
  | "seeking"
  | "seeked"
  | "waiting"
  | "stalled"
  | "canplay"
  | "ended"
  | "error"
  | "emptied"
  | "timeupdate"
  | "durationchange"
  | "volumechange"
  | "progress";
