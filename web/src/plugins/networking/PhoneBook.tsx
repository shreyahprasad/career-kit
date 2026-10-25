import { useLayoutEffect, useRef, useState } from "react";
import type { Person } from "./data";
import { agoLabel, currentGroup, daysSince, type Group } from "./networking";
import { PersonLink, Tag } from "./parts";
import { FRESH_DAYS, NEXT_STEP_LABEL } from "./style";

// The list of people, scrolling inside its own box with each group's header pinned to the top
// while it is read. Sorted A–Z, an index down the right jumps to a letter and marks the one
// being read, like the contacts on a phone.

const LETTERS = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ#"];

export function PhoneBook({
  groups,
  letters,
  today,
  open,
}: {
  groups: Group[];
  /** Show the A–Z index (the groups are letters). */
  letters: boolean;
  today: string;
  open: string | null;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const starts = useRef<(HTMLElement | null)[]>([]);
  const [reading, setReading] = useState(0);

  const update = () => {
    const tops = groups.map((_, i) => starts.current[i]?.offsetTop ?? 0);
    setReading(currentGroup(tops, scroller.current!.scrollTop));
  };
  useLayoutEffect(update, [groups]);

  const jump = (i: number) => scroller.current!.scrollTo({ top: starts.current[i]!.offsetTop, behavior: "smooth" });

  return (
    <div className="flex h-[var(--people-list)] gap-2">
      <div ref={scroller} onScroll={update} className="relative min-w-0 flex-1 overflow-y-auto overscroll-contain">
        {groups.length === 0 && <p className="text-small text-muted">No one matches these filters.</p>}
        {groups.map((g, i) => (
          // The last group fills the box, so any group, however near the end, can reach the top.
          <div key={g.label} ref={(el) => void (starts.current[i] = el)} className="last:min-h-full">
            <h3 className="label sticky top-0 z-10 border-b border-line bg-surface pt-2 pb-1.5">{g.label}</h3>
            <ul className="flex flex-col">
              {g.people.map((p) => (
                <li key={p.id}>
                  <Row person={p} today={today} open={p.id === open} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {letters && <LetterIndex labels={groups.map((g) => g.label)} reading={groups[reading]?.label} onJump={jump} />}
    </div>
  );
}

/** A–Z down the side. Letters with no one under them are dimmed; the one being read is lit.
 *  Each letter fills its share of the height and a chip's width, so a thumb can hit it. */
function LetterIndex({ labels, reading, onJump }: { labels: string[]; reading?: string; onJump: (i: number) => void }) {
  return (
    <nav aria-label="Jump to letter" className="flex flex-col font-mono text-meta leading-none">
      {LETTERS.filter((l) => l !== "#" || labels.includes(l)).map((l) => {
        const i = labels.indexOf(l);
        if (i < 0) {
          return (
            <span key={l} aria-hidden="true" className="grid w-[var(--tap-chip)] flex-1 place-items-center text-line">
              {l}
            </span>
          );
        }
        return (
          <button
            key={l}
            type="button"
            aria-label={`Jump to ${l}`}
            aria-current={l === reading ? "true" : undefined}
            onClick={() => onJump(i)}
            className="grid w-[var(--tap-chip)] flex-1 place-items-center rounded text-muted hover:text-fg aria-[current]:font-medium aria-[current]:text-accent"
          >
            {l}
          </button>
        );
      })}
    </nav>
  );
}

function Row({ person: p, today, open }: { person: Person; today: string; open: boolean }) {
  const days = daysSince(p, today);
  const count = p.interactions.length;
  const where = [p.role, p.company].filter(Boolean).join(" · ");
  return (
    <PersonLink
      id={p.id}
      current={open}
      className="flex items-start gap-3 border-b border-line px-2 py-2.5 hover:bg-bg/60 aria-[current]:bg-bg/60"
    >
      <span
        aria-hidden="true"
        className="grid size-8 shrink-0 place-items-center rounded-full border border-line font-mono text-meta text-muted"
      >
        {initials(p.name)}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="leading-tight">{p.name}</span>
        {where && <span className="truncate text-small leading-tight text-muted">{where}</span>}
        {p.tags.length > 0 && (
          <span className="flex flex-wrap gap-1">
            {p.tags.map((t) => (
              <Tag key={t} tag={t} />
            ))}
          </span>
        )}
      </span>
      <span className="num flex shrink-0 flex-col items-end gap-1 font-mono text-meta leading-tight text-muted">
        <span className={days != null && days < FRESH_DAYS ? "text-fg" : ""}>{days == null ? "not yet" : agoLabel(days)}</span>
        {count > 0 && <span>{count === 1 ? "1 talk" : `${count} talks`}</span>}
        {p.next_step && <span className="text-accent">→ {NEXT_STEP_LABEL[p.next_step]}</span>}
      </span>
    </PersonLink>
  );
}

/** "Maya Okafor" -> "MO"; one name -> its first letter. */
const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join("");
