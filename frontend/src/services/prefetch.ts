import type { QueueItem, PlaybackQueue } from "./playbackQueue";

export type SourceResolver<T> = (
  itemId: string,
  signal: AbortSignal,
) => Promise<T>;

export class PlaybackPrefetcher<T> {
  private controller: AbortController | undefined;
  private readonly prepared = new Map<string, T>();

  async prepareNext(
    queue: PlaybackQueue<QueueItem>,
    resolveSource: SourceResolver<T>,
  ): Promise<boolean> {
    this.cancelPending();
    const next = queue.nextItem;
    for (const preparedId of this.prepared.keys()) {
      if (preparedId !== queue.current.id && preparedId !== next?.id) {
        this.prepared.delete(preparedId);
      }
    }
    if (!next) return false;

    const controller = new AbortController();
    this.controller = controller;
    try {
      const source = await resolveSource(next.id, controller.signal);
      if (controller.signal.aborted) return false;
      this.prepared.set(next.id, source);
      return true;
    } catch (error) {
      if (controller.signal.aborted) return false;
      throw error;
    } finally {
      if (this.controller === controller) this.controller = undefined;
    }
  }

  take(itemId: string): T | undefined {
    const source = this.prepared.get(itemId);
    this.prepared.delete(itemId);
    return source;
  }

  cancel(): void {
    this.cancelPending();
    this.prepared.clear();
  }

  private cancelPending(): void {
    this.controller?.abort();
    this.controller = undefined;
  }
}
