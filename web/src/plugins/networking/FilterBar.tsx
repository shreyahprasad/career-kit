import { useMemo, useState } from "react";
import { Fold } from "@shell/Fold";
import { isPhone } from "@shell/phone";
import { NEXT_STEPS, type Person } from "./data";
import { allTags, companies, foldedFilterCount, isFiltered, NO_FILTERS, type Filters } from "./networking";
import { Tag } from "./parts";
import { NEXT_STEP_LABEL, RECENCY, SORTS, type Sort } from "./style";

// In the People card. Search always in view, with Clear. Company, last talked, next step, sort and the tags sit under
// a Filters fold, its label counting the filters on: open on the Mac, folded on the phone, where
// they took three rows. The tags fold again inside it until you open them.

// The bar sits in the People card, so its controls take the page ground like any form's.
const control = "control";

export function FilterBar({
  people,
  filters,
  onFilters,
  sort,
  onSort,
}: {
  people: Person[];
  filters: Filters;
  onFilters: (f: Filters) => void;
  sort: Sort;
  onSort: (s: Sort) => void;
}) {
  const set = (change: Partial<Filters>) => onFilters({ ...filters, ...change });
  const toggleTag = (tag: string) =>
    set({ tags: filters.tags.includes(tag) ? filters.tags.filter((t) => t !== tag) : [...filters.tags, tag] });
  const tags = useMemo(() => allTags(people), [people]);
  const companyNames = useMemo(() => companies(people), [people]);
  const [startOpen] = useState(() => !isPhone());
  const on = foldedFilterCount(filters);

  return (
    <div role="search" aria-label="Search and filters" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <input
          type="search"
          aria-label="Search"
          placeholder="Search names, companies, tags"
          value={filters.query}
          onChange={(e) => set({ query: e.target.value })}
          className={`${control} min-w-0 flex-1 placeholder:text-muted`}
        />
        {isFiltered(filters) && (
          <button type="button" onClick={() => onFilters(NO_FILTERS)} className="link-button link-button-quiet px-1">
            Clear
          </button>
        )}
      </div>
      <Fold label={on ? `Filters · ${on}` : "Filters"} open={startOpen}>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select
            aria-label="Company"
            value={filters.company ?? ""}
            onChange={(e) => set({ company: e.target.value || null })}
            className={control}
          >
            <option value="">All companies</option>
            {companyNames.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            aria-label="Last talked"
            value={filters.recency}
            onChange={(e) => set({ recency: Number(e.target.value) })}
            className={control}
          >
            {RECENCY.map((r, i) => (
              <option key={r.label} value={i}>
                {r.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Next step"
            value={filters.next ?? ""}
            onChange={(e) => set({ next: (e.target.value || null) as Filters["next"] })}
            className={control}
          >
            <option value="">Any next step</option>
            <option value="any">Has a next step</option>
            {NEXT_STEPS.map((s) => (
              <option key={s} value={s}>
                Next: {NEXT_STEP_LABEL[s]}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-small text-muted">
            Sort
            <select aria-label="Sort" value={sort} onChange={(e) => onSort(e.target.value as Sort)} className={`${control} text-fg`}>
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {tags.length > 0 && (
          <div className="mt-2">
            <Fold label={filters.tags.length ? `Tags · ${filters.tags.length}` : "Tags"}>
              <div role="group" aria-label="Tags" className="mt-2 flex flex-wrap items-center gap-1.5">
                {tags.map((t) => (
                  <Tag key={t} tag={t} pressed={filters.tags.includes(t)} onToggle={() => toggleTag(t)} />
                ))}
              </div>
            </Fold>
          </div>
        )}
      </Fold>
    </div>
  );
}
