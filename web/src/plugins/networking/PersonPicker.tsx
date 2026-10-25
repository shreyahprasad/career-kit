import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import type { Person } from "./data";
import { personOptions, type Who } from "./log";

// Who a talk was with: search the phonebook, or add the name typed as someone new.
// A combobox: arrows move, Enter picks, Escape clears. Picked, it shows who with a way to change.
// Other pages pass their own label and placeholder, and canAdd={false} to offer only the phonebook.

export function PersonPicker({
  people,
  value,
  onChange,
  autoFocus,
  label = "Who was it with",
  placeholder = "Who was it with? Search or type a new name",
  canAdd = true,
}: {
  people: Person[];
  value: Who | null;
  onChange: (who: Who | null) => void;
  autoFocus?: boolean;
  label?: string;
  placeholder?: string;
  canAdd?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const list = useId();

  if (value) {
    const known = "id" in value ? people.find((p) => p.id === value.id) : null;
    return (
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-medium">{known ? known.name : "New person"}</span>
        {known?.company && <span className="text-small text-muted">{known.company}</span>}
        <button
          type="button"
          onClick={() => {
            setQuery("name" in value ? value.name : "");
            onChange(null);
          }}
          className="text-small text-accent hover:underline"
        >
          Change
        </button>
      </div>
    );
  }

  const matches = personOptions(people, query);
  const typed = canAdd ? query.trim() : "";
  // The last option adds what you typed as someone new; there is none until you type.
  const count = matches.length + (typed ? 1 : 0);
  const pick = (i: number) => {
    if (i < matches.length) onChange({ id: matches[i].id });
    else if (typed) onChange({ name: typed, details: {}, tags: [] });
  };
  const optionId = (i: number) => `${list}-${i}`;

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (count) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : count - 1)) % count);
    } else if (e.key === "Enter") {
      e.preventDefault(); // picks; never submits the form with no one chosen
      if (count) pick(Math.min(active, count - 1));
    } else if (e.key === "Escape" && query) {
      e.preventDefault();
      setQuery("");
      setActive(0);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <input
        type="search"
        role="combobox"
        aria-label={label}
        aria-expanded={count > 0}
        aria-controls={list}
        aria-autocomplete="list"
        aria-activedescendant={count ? optionId(Math.min(active, count - 1)) : undefined}
        placeholder={placeholder}
        autoComplete="off"
        autoFocus={autoFocus}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
        }}
        onKeyDown={onKey}
        className="control placeholder:text-muted"
      />
      {count > 0 && (
        <ul id={list} role="listbox" aria-label="People" className="flex flex-col rounded-[var(--radius-control)] border border-line bg-bg">
          {matches.map((p, i) => (
            <Option key={p.id} id={optionId(i)} active={i === active} onPick={() => pick(i)}>
              <span>{p.name}</span>
              {p.company && <span className="text-small text-muted">{p.company}</span>}
            </Option>
          ))}
          {typed && (
            <Option id={optionId(matches.length)} active={active === matches.length} onPick={() => pick(matches.length)}>
              <span className="text-accent">+ Add “{typed}” as someone new</span>
            </Option>
          )}
        </ul>
      )}
    </div>
  );
}

function Option({ id, active, onPick, children }: { id: string; active: boolean; onPick: () => void; children: ReactNode }) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      // mousedown, not click: the input keeps focus, so the list does not close first
      onMouseDown={(e) => {
        e.preventDefault();
        onPick();
      }}
      className="flex cursor-pointer items-baseline gap-3 px-2 py-1.5 aria-selected:bg-surface"
    >
      {children}
    </li>
  );
}
