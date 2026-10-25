import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { FoldHeading } from "@shell/Fold";
import { isPhone } from "@shell/phone";
import { KINDS, type Person } from "./data";
import { agoLabel, dateLabel, daysSince, lanes, monthLabel, position, timelineMonths } from "./networking";
import { Dot, PersonLink } from "./parts";
import { DEFAULT_TIMELINE_RANGE, KIND_COLOR, TIMELINE_RANGES } from "./style";

// One lane per person, most recently talked to on top, a dot for each talk in its
// kind's color. Months run left to right, scrolled to today, so gaps and people gone quiet
// show at a glance. Clicking a lane or a dot opens that person. Past --timeline-max the lanes
// scroll under the pinned months. Folded at first on the phone, where the sideways chart says little.

export function TimelineCard({
  people,
  today,
  open,
}: {
  people: Person[];
  today: string;
  open: string | null;
}) {
  const [expanded, setExpanded] = useState(() => !isPhone());
  const [range, setRange] = useState(DEFAULT_TIMELINE_RANGE);
  const rows = useMemo(() => lanes(people), [people]);
  const months = useMemo(() => timelineMonths(rows, TIMELINE_RANGES[range].count, today), [rows, range, today]);
  const now = position(today, months);
  // Months share the card's width, and scroll once they would be narrower than --lane-month.
  const track = { flex: "1 0 auto", minWidth: `calc(${months.length} * var(--lane-month))` };
  // A lane's track, with a hairline at the start of each month.
  const grid = {
    ...track,
    backgroundImage: "linear-gradient(to right, var(--line) 1px, transparent 1px)",
    backgroundSize: `calc(100% / ${months.length}) 100%`,
  };

  const scroller = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [range, expanded]);

  return (
    <section aria-label="Timeline" className="panel flex flex-col gap-[var(--gap-item)]">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <FoldHeading label="Timeline" expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
        {expanded && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <ul aria-label="Kinds" className="flex flex-wrap gap-x-3 gap-y-1 text-small text-muted">
              {KINDS.map((k) => (
                <li key={k} className="flex items-center gap-1.5">
                  <Dot kind={k} />
                  {k}
                </li>
              ))}
            </ul>
            <select
              aria-label="Range"
              value={range}
              onChange={(e) => setRange(Number(e.target.value))}
              className="control"
            >
              {TIMELINE_RANGES.map((r, i) => (
                <option key={r.label} value={i}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
        )}
      </header>

      {!expanded ? null : rows.length === 0 ? (
        <p className="text-small text-muted">No talks among the people shown.</p>
      ) : (
        <div ref={scroller} className="max-h-[var(--timeline-max)] overflow-auto overscroll-contain">
          <div className="flex w-max min-w-full flex-col font-mono text-meta">
            <div className="sticky top-0 z-20 flex bg-surface">
              <div className={`${stickyLeft} bg-surface`} />
              <div className="flex" style={track}>
                {months.map((m, i) => (
                  <span key={m} className="flex-1 basis-0 border-l border-line px-1.5 pb-1.5 whitespace-nowrap text-muted">
                    {monthLabel(m, i === 0 || m.endsWith("-01"))}
                  </span>
                ))}
              </div>
            </div>

            {rows.map((p) => {
              const on = p.id === open;
              const days = daysSince(p, today)!;
              return (
                <div key={p.id} className={`flex h-[var(--lane-row)] border-t border-line ${on ? openTint : ""}`}>
                  <PersonLink
                    id={p.id}
                    current={on}
                    className={`${stickyLeft} ${on ? openTint : "bg-surface"} flex items-center justify-between gap-2 pr-3`}
                  >
                    <span className={`truncate font-sans text-copy ${on ? "font-semibold" : ""}`}>{p.name}</span>
                    <span className="num shrink-0 text-muted">{agoLabel(days)}</span>
                  </PersonLink>
                  {/* The whole lane opens the person on a click; the keyboard reaches them by name. */}
                  <PersonLink id={p.id} tabIndex={-1} aria-hidden="true" className="relative" style={grid}>
                    {now != null && (
                      <span className="absolute inset-y-0 border-l border-dashed border-accent/60" style={{ left: `${now * 100}%` }} />
                    )}
                    {p.interactions.map((t, i) => {
                      const x = position(t.date, months);
                      if (x == null) return null;
                      return (
                        <span
                          key={i}
                          title={`${t.kind}, ${dateLabel(t.date)}`}
                          className="absolute top-1/2 size-[var(--lane-dot)] -translate-1/2 rounded-full ring-2 ring-surface hover:scale-150"
                          style={{ left: `${x * 100}%`, background: KIND_COLOR[t.kind] }}
                        />
                      );
                    })}
                  </PersonLink>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

/** The name column stays put while the months scroll under it, so its background is opaque. */
const stickyLeft = "sticky left-0 z-10 w-[var(--lane-label)] shrink-0";

/** The open person's lane: --bg at 60% over --surface, mixed so the name column can wear it too. */
const openTint = "bg-[color-mix(in_srgb,var(--bg)_60%,var(--surface))]";
