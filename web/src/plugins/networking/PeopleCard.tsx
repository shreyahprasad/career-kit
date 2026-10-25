import { useMemo, useState } from "react";
import { FoldHeading } from "@shell/Fold";
import { AddPersonForm } from "./AddPersonForm";
import type { Person } from "./data";
import { FilterBar } from "./FilterBar";
import type { Saved } from "./LogCard";
import { groupPeople, isFiltered, listOpen, type Filters } from "./networking";
import { PhoneBook } from "./PhoneBook";
import type { Sort } from "./style";

// The phonebook: everyone shown, in groups (letters, companies or how long since you talked).
// It starts folded, so a person opened from another page is in view; the header opens it at the top.
// Search and Filters sit in the card, always in view: a search or filter going on opens the list
// to its matches, and clearing them folds it again. + adds someone with no talk.

export function PeopleCard({
  everyone,
  people,
  filters,
  onFilters,
  sort,
  onSort,
  today,
  open,
  knownTags,
  onAdded,
}: {
  /** Everyone, for the filter choices; people are the ones the filters keep. */
  everyone: Person[];
  people: Person[];
  filters: Filters;
  onFilters: (f: Filters) => void;
  sort: Sort;
  onSort: (s: Sort) => void;
  today: string;
  open: string | null;
  knownTags: string[];
  onAdded: (added: Saved) => Promise<void>;
}) {
  const groups = useMemo(() => groupPeople(people, sort, today), [people, sort, today]);
  const [expanded, setExpanded] = useState(false);
  // Follow a search or filter going on or off, set while rendering so the list opens with it.
  const filtered = isFiltered(filters);
  const [wasFiltered, setWasFiltered] = useState(filtered);
  if (wasFiltered !== filtered) {
    setWasFiltered(filtered);
    setExpanded(listOpen({ wasFiltered, filtered, expanded }));
  }
  const total = everyone.length;
  const [adding, setAdding] = useState(false);

  return (
    <section aria-label="People" className="panel flex flex-col gap-[var(--gap-item)]">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <FoldHeading label="People" expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
        <span className="flex items-baseline gap-3">
          <span className="num font-mono text-small text-muted">
            {people.length === total ? total : `${people.length} of ${total}`}
          </span>
          {!adding && (
            <button type="button" aria-label="Add someone" onClick={() => setAdding(true)} className="button">
              +
            </button>
          )}
        </span>
      </header>
      <FilterBar people={everyone} filters={filters} onFilters={onFilters} sort={sort} onSort={onSort} />
      {adding && (
        <AddPersonForm
          known={knownTags}
          onAdded={async (added) => {
            await onAdded(added);
            setAdding(false);
          }}
          onClose={() => setAdding(false)}
        />
      )}
      {expanded && <PhoneBook groups={groups} letters={sort === "name"} today={today} open={open} />}
    </section>
  );
}
