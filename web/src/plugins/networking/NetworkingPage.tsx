import { useEffect, useMemo, useRef, useState } from "react";
import { LoadError } from "@shell/LoadError";
import { href } from "@shell/router";
import { fetchPeople, type Person } from "./data";
import type { Who } from "./log";
import { LogCard, type Saved } from "./LogCard";
import { allTags, lanes, matches, NO_FILTERS, todayISO, type Filters } from "./networking";
import { PeopleCard } from "./PeopleCard";
import { PersonCard } from "./PersonCard";
import type { Sort } from "./style";
import { TimelineCard } from "./TimelineCard";

// Networking page: logging a talk, the phonebook with its search and filters, the open person, then
// everyone on a timeline. A saved talk, or someone added from the phonebook, reloads
// everyone and opens who it was with.
// Filters narrow the phonebook and the timeline; the open person stays open even when
// filtered out. The route (#/networking/maya-okafor) is the open person, so reload,
// back/forward and links keep it. No person, or one not on file, opens whoever was talked to
// most recently, and the route is corrected to match.

type Load = { state: "loading" } | { state: "error"; error: Error } | { state: "ready"; people: Person[] };

/** One empty list, so the memos below hold while loading. */
const NO_PEOPLE: Person[] = [];

export function NetworkingPage({ path }: { path: string[] }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [sort, setSort] = useState<Sort>("name");
  /** The log form, open with whoever it starts with; null when closed. */
  const [logging, setLogging] = useState<{ start: Who | null } | null>(null);
  const [added, setAdded] = useState<{ id: string; name: string } | null>(null);
  /** Goes up on every save, so the open person loads again. */
  const [version, setVersion] = useState(0);
  const today = todayISO();

  useEffect(() => {
    const ctrl = new AbortController();
    fetchPeople(ctrl.signal)
      .then((people) => setLoad({ state: "ready", people }))
      .catch((e: Error) => {
        if (!ctrl.signal.aborted) setLoad({ state: "error", error: e });
      });
    return () => ctrl.abort();
  }, []);

  // Everyone loads again before the page goes to who it was with: a new person is not in the
  // old list, and the route to someone not on file is corrected to the latest. The form shows
  // "Saving…" until then.
  const onSaved = async ({ personId, added: name }: Saved) => {
    try {
      setLoad({ state: "ready", people: await fetchPeople() });
    } catch (e) {
      setLoad({ state: "error", error: e as Error });
    }
    setLogging(null);
    setAdded(name ? { id: personId, name } : null);
    setVersion((v) => v + 1);
    location.hash = href("networking", personId);
  };
  const startLog = (start: Who | null) => {
    setAdded(null);
    setLogging({ start });
  };

  const people = load.state === "ready" ? load.people : NO_PEOPLE;
  const shown = useMemo(() => people.filter((p) => matches(p, filters, today)), [people, filters, today]);
  const knownTags = useMemo(() => allTags(people), [people]);
  const latest = useMemo(() => lanes(people)[0]?.id ?? people[0]?.id ?? null, [people]);
  const routed = path[0];
  const open = people.some((p) => p.id === routed) ? routed : latest;

  useEffect(() => {
    if (open && routed !== open) history.replaceState(null, "", href("networking", open));
  }, [open, routed]);

  // The person card sits between the phonebook and the timeline, so bring it into view when
  // someone new opens (a pick, back or forward), but not when the first one loads.
  const card = useRef<HTMLElement>(null);
  const shownOpen = useRef(open);
  useEffect(() => {
    const before = shownOpen.current;
    shownOpen.current = open;
    if (before != null && before !== open) card.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [open]);

  // After a save, show it: the talk is at the top of the person card.
  useEffect(() => {
    if (version > 0) card.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [version]);

  return (
    <div className="flex flex-col gap-[var(--gap-block)] p-[var(--page-margin)]">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1>Networking</h1>
        {load.state === "ready" && !logging && (
          <button type="button" onClick={() => startLog(null)} className="button button-primary">
            + Log a talk
          </button>
        )}
      </header>
      {logging && (
        <LogCard
          // a new start (another person's card) is a new form
          key={logging.start && "id" in logging.start ? logging.start.id : "new"}
          people={people}
          today={today}
          start={logging.start}
          onSaved={onSaved}
          onClose={() => setLogging(null)}
        />
      )}
      {added && (
        <p role="status" className="text-small text-muted">
          Added {added.name} to your phonebook as <span className="font-mono">{added.id}</span>.
        </p>
      )}
      {load.state === "loading" && <p className="text-muted">Loading</p>}
      {load.state === "error" && (
        <LoadError what="your network" error={load.error} className="panel" />
      )}
      {load.state === "ready" && people.length === 0 && (
        <p className="panel text-muted">No one here yet.</p>
      )}
      {people.length > 0 && (
        <>
          <PeopleCard
            everyone={people}
            people={shown}
            filters={filters}
            onFilters={setFilters}
            sort={sort}
            onSort={setSort}
            today={today}
            open={open}
            knownTags={knownTags}
            onAdded={onSaved}
          />
          <PersonCard
            ref={card}
            id={open}
            today={today}
            version={version}
            onLog={(id) => startLog({ id })}
            knownTags={knownTags}
            onSaved={onSaved}
          />
          <TimelineCard people={shown} today={today} open={open} />
        </>
      )}
    </div>
  );
}
