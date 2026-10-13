import { writable, type Readable } from "svelte/store";

export interface Store<T> extends Readable<T> {
  getSnapshot(): T;
  set(nextValue: T): void;
  update(updater: (current: T) => T): void;
  reset(): void;
}

export function createMemoryStore<T>(initialValue: T): Store<T> {
  const store = writable<T>(initialValue);
  let snapshot = initialValue;

  function publish(nextValue: T): void {
    snapshot = nextValue;
    store.set(snapshot);
  }

  return {
    subscribe: store.subscribe,
    getSnapshot: () => snapshot,
    set: publish,
    update: (updater) => publish(updater(snapshot)),
    reset: () => publish(initialValue),
  };
}
