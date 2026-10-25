import { useSyncExternalStore } from "react";

// The one undo on screen. A delete hides a row (the writers never remove one) and offers "Undo"
// for UNDO_MS; so does replacing something you cannot get back otherwise (a saved posting). A
// newer offer replaces the one before. Undoing sends the restore, then runs after: go
// back to what came back, or reload the page it was on. UndoBar shows it.

export const UNDO_MS = 10_000;

export interface UndoOffer {
  /** What was deleted, in your words: "Acme FDE". */
  what: string;
  /** What happened to it: "Deleted" unless said. */
  verb?: string;
  restore: () => Promise<unknown>;
  after?: () => void | Promise<void>;
}

let current: UndoOffer | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
const listeners = new Set<() => void>();

function set(offer: UndoOffer | null) {
  current = offer;
  listeners.forEach((l) => l());
}

/** Shows "<verb> <what>. Undo" for UNDO_MS. */
export function offerUndo(offer: UndoOffer) {
  clearTimeout(timer);
  set(offer);
  timer = setTimeout(() => set(null), UNDO_MS);
}

/** Restores what the offer is for and runs its after. The offer stays up if the restore is refused,
 * so you can try again; the error is thrown for UndoBar to show. */
export async function undo(offer: UndoOffer) {
  clearTimeout(timer);
  await offer.restore();
  if (current === offer) set(null);
  await offer.after?.();
}

export function dismissUndo() {
  clearTimeout(timer);
  set(null);
}

export function useUndoOffer(): UndoOffer | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}

/** The offer on screen now, for tests. */
export const currentUndo = () => current;
