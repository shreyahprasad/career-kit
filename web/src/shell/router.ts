import { useSyncExternalStore } from "react";

// Hash routing (#/career, #/career/acme-fde). Small enough to own; no router package.

function subscribe(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

/** A hash as path segments, the reverse of href(). */
export function segments(hash: string): string[] {
  return hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
}

let cachedHash = "";
let cachedPath: string[] = [];

function snapshot(): string[] {
  if (window.location.hash !== cachedHash) {
    cachedHash = window.location.hash;
    cachedPath = segments(cachedHash);
  }
  return cachedPath;
}

/** Current route as path segments: "#/career/acme-fde" -> ["career", "acme-fde"]. */
export function useRoute(): string[] {
  return useSyncExternalStore(subscribe, snapshot);
}

export function href(...segments: string[]): string {
  return "#/" + segments.map(encodeURIComponent).join("/");
}

/** A click on a link meant for a new tab or window, which a page that moves itself lets through. */
export const opensElsewhere = (e: { metaKey: boolean; ctrlKey: boolean; shiftKey: boolean }) => e.metaKey || e.ctrlKey || e.shiftKey;
