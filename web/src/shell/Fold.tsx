import { useState, type ReactNode } from "react";

// Every fold looks and behaves the same: a › that turns down when open, and aria-expanded for
// screen readers. FoldHeading is a card's heading, its card holding whether it is open. Fold is a
// part inside a card or form that opens on its own; folded, its body stays (hidden), so what you
// typed in it is kept.

function FoldToggle({ label, expanded, onToggle }: { label: string; expanded: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className="group label flex min-h-[var(--tap-min)] items-center gap-2 hover:text-fg"
    >
      <span aria-hidden="true" className="inline-block transition-transform group-aria-expanded:rotate-90">
        ›
      </span>
      {label}
    </button>
  );
}

export function FoldHeading(props: { label: string; expanded: boolean; onToggle: () => void }) {
  return (
    <h2>
      <FoldToggle {...props} />
    </h2>
  );
}

/** open: whether it starts open. */
export function Fold({ label, open = false, children }: { label: string; open?: boolean; children: ReactNode }) {
  const [expanded, setExpanded] = useState(open);
  return (
    <div>
      <FoldToggle label={label} expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
      <div hidden={!expanded}>{children}</div>
    </div>
  );
}
