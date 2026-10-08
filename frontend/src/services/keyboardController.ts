export type KeyboardAction =
  | "toggle-play"
  | "seek-backward"
  | "seek-forward"
  | "volume-up"
  | "volume-down"
  | "toggle-mute"
  | "toggle-loop"
  | "toggle-fullscreen"
  | "toggle-help"
  | "next"
  | "previous"
  | "retry"
  | "toggle-favorite"
  | "close";

type KeyboardInput = Pick<
  KeyboardEvent,
  "key" | "code" | "target" | "repeat" | "altKey" | "ctrlKey" | "metaKey" | "defaultPrevented"
>;

const KEY_ACTIONS: Readonly<Record<string, KeyboardAction>> = {
  " ": "toggle-play",
  Space: "toggle-play",
  ArrowLeft: "seek-backward",
  ArrowRight: "seek-forward",
  ArrowUp: "volume-up",
  ArrowDown: "volume-down",
  m: "toggle-mute",
  M: "toggle-mute",
  l: "toggle-loop",
  L: "toggle-loop",
  f: "toggle-fullscreen",
  F: "toggle-fullscreen",
  "?": "toggle-help",
  n: "next",
  N: "next",
  p: "previous",
  P: "previous",
  r: "retry",
  R: "retry",
  v: "toggle-favorite",
  V: "toggle-favorite",
  Escape: "close",
};

const REPEATABLE_ACTIONS: ReadonlySet<KeyboardAction> = new Set([
  "seek-backward",
  "seek-forward",
  "volume-up",
  "volume-down",
]);

function isTypingTarget(target: EventTarget | null): boolean {
  if (
    target === null ||
    typeof target !== "object" ||
    !("matches" in target) ||
    typeof target.matches !== "function" ||
    !("closest" in target) ||
    typeof target.closest !== "function"
  ) {
    return false;
  }
  if (
    target.matches.call(
      target,
      "input, textarea, select, button, a, [role='button'], [contenteditable]:not([contenteditable='false'])",
    )
  ) {
    return true;
  }
  return (
    target.closest.call(
      target,
      "[contenteditable]:not([contenteditable='false'])",
    ) !== null
  );
}

export function keyboardActionForEvent(
  event: KeyboardInput,
): KeyboardAction | null {
  const action = KEY_ACTIONS[event.key] ?? KEY_ACTIONS[event.code];
  if (
    event.defaultPrevented ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    (isTypingTarget(event.target) && action !== "close")
  ) {
    return null;
  }

  if (
    action === undefined ||
    (event.repeat && !REPEATABLE_ACTIONS.has(action))
  ) {
    return null;
  }
  return action;
}

export function installKeyboardController(
  target: Window,
  onAction: (action: KeyboardAction) => void,
): () => void {
  const handleKeydown = (event: KeyboardEvent): void => {
    const action = keyboardActionForEvent(event);
    if (action === null) return;
    event.preventDefault();
    onAction(action);
  };

  target.addEventListener("keydown", handleKeydown);
  return () => target.removeEventListener("keydown", handleKeydown);
}
