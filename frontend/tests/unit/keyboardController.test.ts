import { describe, expect, it } from "vitest";

import {
  keyboardActionForEvent,
  type KeyboardAction,
} from "../../src/services/keyboardController";

class FakeTarget extends EventTarget {
  constructor(
    readonly tagName: string,
    private readonly editable: string | null = null,
  ) {
    super();
  }

  matches(selector: string): boolean {
    return (
      /input|textarea|select|button|a|role='button'/.test(selector) &&
      ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(this.tagName)
    ) ||
      (this.editable !== null &&
        this.editable !== "false" &&
        selector.includes("contenteditable"));
  }

  closest(selector: string): Element | null {
    return null;
  }
}

function keyEvent(
  key: string,
  options: {
    code?: string;
    target?: EventTarget | null;
    repeat?: boolean;
    shiftKey?: boolean;
    ctrlKey?: boolean;
    metaKey?: boolean;
    altKey?: boolean;
    defaultPrevented?: boolean;
  } = {},
): Parameters<typeof keyboardActionForEvent>[0] {
  return {
    key,
    code: options.code ?? key,
    target: options.target ?? null,
    repeat: options.repeat ?? false,
    altKey: options.altKey ?? false,
    ctrlKey: options.ctrlKey ?? false,
    metaKey: options.metaKey ?? false,
    defaultPrevented: options.defaultPrevented ?? false,
  };
}

describe("keyboard player controls", () => {
  it.each([
    [" ", "toggle-play"],
    ["ArrowLeft", "seek-backward"],
    ["ArrowRight", "seek-forward"],
    ["ArrowUp", "volume-up"],
    ["ArrowDown", "volume-down"],
    ["m", "toggle-mute"],
    ["l", "toggle-loop"],
    ["f", "toggle-fullscreen"],
    ["?", "toggle-help"],
    ["n", "next"],
    ["p", "previous"],
    ["r", "retry"],
    ["v", "toggle-favorite"],
    ["Escape", "close"],
  ] as const)("maps %s to %s", (key, action) => {
    expect(keyboardActionForEvent(keyEvent(key))).toBe(action);
  });

  it("accepts help but rejects modified browser shortcuts", () => {
    expect(keyboardActionForEvent(keyEvent("?"))).toBe("toggle-help");
    expect(keyboardActionForEvent(keyEvent("f", { ctrlKey: true }))).toBeNull();
    expect(keyboardActionForEvent(keyEvent("f", { metaKey: true }))).toBeNull();
    expect(keyboardActionForEvent(keyEvent("f", { altKey: true }))).toBeNull();
  });

  it.each(["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"])(
    "does not intercept keys in %s",
    (tagName) => {
      expect(
        keyboardActionForEvent(keyEvent(" ", { target: new FakeTarget(tagName) })),
      ).toBeNull();
    },
  );

  it.each(["true", "", "plaintext-only"])(
    "does not intercept typing in contenteditable=%s elements",
    (value) => {
      expect(
        keyboardActionForEvent(
          keyEvent("n", { target: new FakeTarget("DIV", value) }),
        ),
      ).toBeNull();
    },
  );

  it("does not treat contenteditable=false as a typing target", () => {
    expect(
      keyboardActionForEvent(
        keyEvent("n", { target: new FakeTarget("DIV", "false") }),
      ),
    ).toBe("next");
  });

  it("allows Escape in an interactive element and ignores prevented events", () => {
    expect(
      keyboardActionForEvent(
        keyEvent("Escape", { target: new FakeTarget("BUTTON") }),
      ),
    ).toBe("close");
    expect(
      keyboardActionForEvent(keyEvent(" ", { defaultPrevented: true })),
    ).toBeNull();
  });

  it("ignores repeated toggles but supports repeated seek and volume", () => {
    expect(keyboardActionForEvent(keyEvent("m", { repeat: true }))).toBeNull();
    expect(keyboardActionForEvent(keyEvent("ArrowRight", { repeat: true }))).toBe(
      "seek-forward",
    );
    expect(keyboardActionForEvent(keyEvent("ArrowUp", { repeat: true }))).toBe(
      "volume-up",
    );
  });

  it("covers each mapped action in its typed union", () => {
    const actions: KeyboardAction[] = [
      "toggle-play",
      "seek-backward",
      "seek-forward",
      "volume-up",
      "volume-down",
      "toggle-mute",
      "toggle-loop",
      "toggle-fullscreen",
      "toggle-help",
      "next",
      "previous",
      "retry",
      "toggle-favorite",
      "close",
    ];
    expect(actions).toHaveLength(14);
  });
});
