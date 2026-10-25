import { useState } from "react";
import { dateLabel } from "@shell/dates";
import { FoldHeading } from "@shell/Fold";
import { useSaveEach } from "@shell/useSave";
import { restoreEvent, restoreRole, restoreTodo, type Deleted } from "./data";
import { KIND_LABEL } from "./style";

// What undo can still bring back once its 10 seconds are up: deleted roles, and events and todos
// deleted on their own, latest first. Folded, and not shown at all when there is nothing.

type Item = { key: string; what: string; role?: string; deleted_on: string; restore: () => Promise<unknown> };

function items(d: Deleted): Item[] {
  const roleLine = (r: { company: string; title: string } | null) => (r ? `${r.company} · ${r.title}` : undefined);
  return [
    ...d.roles.map((r) => ({ key: `role-${r.id}`, what: `${r.company} ${r.title}`, deleted_on: r.deleted_on, restore: () => restoreRole(r.id) })),
    ...d.events.map((e) => ({
      key: `event-${e.id}`, what: `${KIND_LABEL[e.kind]}, ${dateLabel(e.date)}`, role: roleLine(e.role), deleted_on: e.deleted_on,
      restore: () => restoreEvent(e.id),
    })),
    ...d.todos.map((t) => ({
      key: `todo-${t.id}`, what: `“${t.text}”`, role: roleLine(t.role), deleted_on: t.deleted_on, restore: () => restoreTodo(t.id),
    })),
  ].sort((a, b) => b.deleted_on.localeCompare(a.deleted_on));
}

export function RecentlyDeleted({ deleted, onRestored }: { deleted: Deleted; onRestored: () => Promise<unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const { pending, error, save } = useSaveEach<string>(onRestored);
  const list = items(deleted);
  if (list.length === 0) return null;

  const bringBack = (item: Item) => save(item.key, item.restore);

  return (
    <section aria-label="Recently deleted" className="panel prose-width flex flex-col gap-2">
      <FoldHeading label={`Recently deleted · ${list.length}`} expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
      {expanded && (
        <ul className="flex flex-col">
          {list.map((item) => (
            <li key={item.key} className="flex min-h-[var(--tap)] items-center gap-3 border-b border-line py-1 last:border-b-0">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="leading-snug">{item.what}</span>
                <span className="truncate text-small text-muted">
                  {item.role && `${item.role} · `}deleted {dateLabel(item.deleted_on)}
                </span>
              </span>
              <button type="button" disabled={pending.size > 0} onClick={() => bringBack(item)} className="link-button min-h-[var(--tap)] shrink-0">
                {pending.has(item.key) ? "Bringing it back…" : "Bring back"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-small text-negative">{error}</p>}
    </section>
  );
}
