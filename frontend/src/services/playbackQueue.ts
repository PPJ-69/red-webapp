export interface QueueItem {
  id: string;
  title: string;
  thumbnailUrl?: string | null;
}

export interface PlaybackQueue<T extends QueueItem = QueueItem> {
  readonly current: T;
  readonly items: readonly T[];
  readonly currentIndex: number;
  readonly hasNext: boolean;
  readonly hasPrevious: boolean;
  readonly canRandom: boolean;
  readonly nextItem: T | undefined;
  select(id: string): T;
  next(): T | undefined;
  previous(): T | undefined;
  random(): T;
  subscribe(listener: (item: T) => void): () => void;
}

export class ArrayPlaybackQueue<T extends QueueItem>
  implements PlaybackQueue<T>
{
  private index: number;
  private readonly seenIds: Set<string>;
  private readonly listeners = new Set<(item: T) => void>();

  constructor(
    private readonly entries: readonly T[],
    initialId: string,
    private readonly randomValue: () => number = Math.random,
    seenIds: Iterable<string> = [],
  ) {
    if (entries.length === 0) {
      throw new TypeError("A playback queue must contain at least one item.");
    }
    if (new Set(entries.map(({ id }) => id)).size !== entries.length) {
      throw new TypeError("Playback queue item IDs must be unique.");
    }
    const initialIndex = entries.findIndex(({ id }) => id === initialId);
    if (initialIndex < 0) {
      throw new RangeError("The initial item must exist in the playback queue.");
    }
    this.index = initialIndex;
    this.seenIds = new Set(seenIds);
    this.seenIds.add(initialId);
  }

  get current(): T {
    return this.entries[this.index];
  }

  get items(): readonly T[] {
    return this.entries;
  }

  get currentIndex(): number {
    return this.index;
  }

  get hasNext(): boolean {
    return this.index < this.entries.length - 1;
  }

  get hasPrevious(): boolean {
    return this.index > 0;
  }

  get canRandom(): boolean {
    return this.entries.length > 1;
  }

  get nextItem(): T | undefined {
    return this.hasNext ? this.entries[this.index + 1] : undefined;
  }

  select(id: string): T {
    const nextIndex = this.entries.findIndex((entry) => entry.id === id);
    if (nextIndex < 0) {
      throw new RangeError("The selected item must exist in the playback queue.");
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
    const unseen = this.entries.filter(
      ({ id }, index) => index !== this.index && !this.seenIds.has(id),
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
    this.seenIds.add(item.id);
    for (const listener of this.listeners) listener(item);
    return item;
  }
}
