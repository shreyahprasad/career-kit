import { useState } from "react";
import { dismissUndo, undo, useUndoOffer } from "./undo";

// "Deleted Acme FDE. Undo", under the page and above the phone's tab bar, while an undo is on offer
// (shell/undo.ts). It takes its own row rather than covering the page, so it never hides a control.

export function UndoBar() {
  const offer = useUndoOffer();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!offer) return null;

  const onUndo = async () => {
    setBusy(true);
    setError(null);
    try {
      await undo(offer);
    } catch (e) {
      setError((e as Error).message);
    }
    setBusy(false);
  };

  return (
    <div role="status" className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-surface px-[var(--page-margin)] py-2">
      <p className="min-w-0 flex-1 text-copy">
        {offer.verb ?? "Deleted"} {offer.what}.{error && <span className="ml-2 text-small text-negative">{error}</span>}
      </p>
      <button type="button" disabled={busy} onClick={onUndo} className="link-button">
        {busy ? "Bringing it back…" : "Undo"}
      </button>
      <button type="button" aria-label="Dismiss" onClick={dismissUndo} className="link-button link-button-quiet">
        ×
      </button>
    </div>
  );
}
