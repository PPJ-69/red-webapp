import { createMemoryStore, type Store } from "./storeInterface";
import type { SearchOrder } from "../types/search";

export type SessionSavedSearch = {
  id: string;
  query: string;
  order: SearchOrder | null;
  createdAt: number;
};

export type SessionSnapshot = {
  favorites: string[];
  seen: string[];
  searchHistory: string[];
  savedSearches: SessionSavedSearch[];
  privacyMode: boolean;
  privacyModeLocked: boolean;
};

export const INITIAL_SESSION_SNAPSHOT: SessionSnapshot = Object.freeze({
  favorites: [],
  seen: [],
  searchHistory: [],
  savedSearches: [],
  privacyMode: true,
  privacyModeLocked: true,
});

export interface SessionStore extends Store<SessionSnapshot> {
  toggleFavorite(id: string): void;
  isFavorite(id: string): boolean;
  markSeen(id: string): void;
  hasSeen(id: string): boolean;
  addSearchHistory(query: string, order?: string | null): void;
  saveSearch(query: string, order?: string | null): void;
  removeSavedSearch(id: string): void;
  clear(): void;
}

function nextUniqueList(values: readonly string[], item: string): string[] {
  if (!item.trim()) return [...values];
  if (values.includes(item)) return [...values];
  return [...values, item];
}

function isSearchOrder(value: string | null | undefined): value is SearchOrder {
  return (
    value === "trending" ||
    value === "latest" ||
    value === "top" ||
    value === "score"
  );
}

export function createSessionStore(
  initialSnapshot: Partial<SessionSnapshot> = {},
): SessionStore {
  const base = {
    ...INITIAL_SESSION_SNAPSHOT,
    ...initialSnapshot,
    favorites: [...(initialSnapshot.favorites ?? INITIAL_SESSION_SNAPSHOT.favorites)],
    seen: [...(initialSnapshot.seen ?? INITIAL_SESSION_SNAPSHOT.seen)],
    searchHistory: [...(initialSnapshot.searchHistory ?? INITIAL_SESSION_SNAPSHOT.searchHistory)],
    savedSearches: [...(initialSnapshot.savedSearches ?? INITIAL_SESSION_SNAPSHOT.savedSearches)],
  };

  const store = createMemoryStore(base);
  let nextSavedSearchId = 0;

  function updateSnapshot(mutator: (snapshot: SessionSnapshot) => SessionSnapshot): void {
    const next = mutator(store.getSnapshot());
    store.set(next);
  }

  return {
    subscribe: store.subscribe,
    getSnapshot: store.getSnapshot,
    set: store.set,
    update: store.update,
    reset: () => store.set({ ...INITIAL_SESSION_SNAPSHOT }),
    toggleFavorite(id: string): void {
      updateSnapshot((snapshot) => {
        const favorites = snapshot.favorites.includes(id)
          ? snapshot.favorites.filter((favorite) => favorite !== id)
          : [...snapshot.favorites, id];
        return { ...snapshot, favorites };
      });
    },
    isFavorite(id: string): boolean {
      return store.getSnapshot().favorites.includes(id);
    },
    markSeen(id: string): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        seen: nextUniqueList(snapshot.seen, id),
      }));
    },
    hasSeen(id: string): boolean {
      return store.getSnapshot().seen.includes(id);
    },
    addSearchHistory(query: string, _order?: string | null): void {
      const trimmed = query.trim();
      if (!trimmed) return;
      updateSnapshot((snapshot) => {
        const history = snapshot.searchHistory.filter((entry) => entry !== trimmed);
        return {
          ...snapshot,
          searchHistory: [trimmed, ...history].slice(0, 25),
        };
      });
    },
    saveSearch(query: string, order?: string | null): void {
      const trimmed = query.trim();
      if (!trimmed) return;
      const normalizedOrder = isSearchOrder(order) ? order : null;
      updateSnapshot((snapshot) => {
        const saved = snapshot.savedSearches.find((entry) => entry.query === trimmed);
        if (saved) {
          return {
            ...snapshot,
            savedSearches: snapshot.savedSearches.map((entry) =>
              entry.id === saved.id
                ? {
                    ...entry,
                    order: normalizedOrder ?? entry.order,
                    createdAt: Date.now(),
                  }
                : entry,
            ),
          };
        }

        const existingIds = new Set(snapshot.savedSearches.map(({ id }) => id));
        let id = `saved-${Date.now()}-${nextSavedSearchId++}`;
        while (existingIds.has(id)) {
          id = `saved-${Date.now()}-${nextSavedSearchId++}`;
        }
        const newEntry: SessionSavedSearch = {
          id,
          query: trimmed,
          order: normalizedOrder,
          createdAt: Date.now(),
        };
        return { ...snapshot, savedSearches: [newEntry, ...snapshot.savedSearches].slice(0, 25) };
      });
    },
    removeSavedSearch(id: string): void {
      updateSnapshot((snapshot) => ({
        ...snapshot,
        savedSearches: snapshot.savedSearches.filter((entry) => entry.id !== id),
      }));
    },
    clear(): void {
      store.set({ ...INITIAL_SESSION_SNAPSHOT });
    },
  };
}

export const sessionStore = createSessionStore();
