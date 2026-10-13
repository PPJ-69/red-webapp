import type { PlaybackQueue, QueueItem } from "./playbackQueue";

export class ResultsPlaybackQueue<T extends QueueItem>
  implements PlaybackQueue<T>
{
  private entries: readonly T[] = [];
  private index = -1;
  private readonly listeners = new Set<(item: T) => void>();

  constructor(
    private readonly randomValue: () => number = Math.random,
    private readonly seenIds: () => Iterable<string> = () => [],
  ) {}

  get current(): T {
    const item = this.currentOrUndefined;
    if (item === undefined) {
      throw new RangeError("There is no current item in the results queue.");
    }
    return item;
  }

  get currentOrUndefined(): T | undefined {
    return this.entries[this.index];
  }

  get items(): readonly T[] {
    return this.entries;
  }

  get currentIndex(): number {
    return this.index;
  }

  get hasNext(): boolean {
    return this.index >= 0 && this.index < this.entries.length - 1;
  }

  get hasPrevious(): boolean {
    return this.index > 0;
  }

  get canRandom(): boolean {
    return this.index >= 0 && this.entries.length > 1;
  }

  get nextItem(): T | undefined {
    return this.hasNext ? this.entries[this.index + 1] : undefined;
  }

  replaceItems(items: readonly T[]): void {
    const previousId = this.currentOrUndefined?.id;
    const ids = new Set<string>();
    for (const item of items) {
      if (ids.has(item.id)) {
        throw new TypeError("Result queue item IDs must be unique.");
      }
      ids.add(item.id);
    }

    this.entries = [...items];
    const retainedIndex =
      previousId === undefined
        ? -1
        : this.entries.findIndex(({ id }) => id === previousId);
    this.index = retainedIndex;
  }

  select(id: string): T {
    const nextIndex = this.entries.findIndex((entry) => entry.id === id);
    if (nextIndex < 0) {
      throw new RangeError("The selected item must exist in the results queue.");
    }
    return this.moveTo(nextIndex);
  }

  next(): T | undefined {
    return this.hasNext ? this.moveTo(this.index + 1) : undefined;
  }

  previous(): T | undefined {
    return this.hasPrevious ? this.moveTo(this.index - 1) : undefined;
  }

  random(): T {
    if (this.index < 0) {
      throw new RangeError("There is no current item in the results queue.");
    }
    const seen = new Set(this.seenIds());
    const unseen = this.entries.filter(
      ({ id }, index) => index !== this.index && !seen.has(id),
    );
    const candidates =
      unseen.length > 0
        ? unseen
        : this.entries.filter((_, index) => index !== this.index);
    if (candidates.length === 0) return this.current;

    const value = this.randomValue();
    if (!Number.isFinite(value) || value < 0 || value >= 1) {
      throw new RangeError("The random value must be in the range [0, 1).");
    }
    const selected = candidates[Math.floor(value * candidates.length)];
    return this.select(selected.id);
  }

  subscribe(listener: (item: T) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private moveTo(nextIndex: number): T {
    if (nextIndex === this.index) return this.current;
    this.index = nextIndex;
    const item = this.current;
    for (const listener of this.listeners) listener(item);
    return item;
  }
}
