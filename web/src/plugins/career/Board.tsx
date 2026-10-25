import { useState } from "react";
import { agoLabel, dateLabel, daysBetween, todayISO } from "@shell/dates";
import { LoadError } from "@shell/LoadError";
import { href } from "@shell/router";
import { FoldHeading } from "@shell/Fold";
import { useLoad, type Load } from "@shell/useLoad";
import { AddRoleForm } from "./AddRoleForm";
import { byStatus, due, TODO_GROUPS, type TodoGroup } from "./career";
import { fetchDeleted, fetchRoles, fetchTodos, type OpenTodo, type Role } from "./data";
import { RecentlyDeleted } from "./RecentlyDeleted";
import { KIND_LABEL, STATUS_LABEL, STATUS_TONE, TODO_KIND_COLOR } from "./style";
import { TodoList } from "./TodoList";

// Every open todo across roles, then every role by status, and + Add a role; Recently deleted at
// the end. On the Mac a column per status, side by side, scrolling sideways when they don't fit;
// on the phone the same groups stacked, with empty ones left out. A change to a todo, or bringing
// something back, loads all three again, since cards show their next todo.

export function Board() {
  const { load, reload } = useLoad(fetchRoles, "roles");
  const todos = useLoad(fetchTodos, "todos");
  const deleted = useLoad(fetchDeleted, "deleted");
  const [adding, setAdding] = useState(false);
  const today = todayISO();
  const reloadAll = () => Promise.all([reload(), todos.reload(), deleted.reload()]);

  return (
    <div className="flex flex-col gap-[var(--gap-block)] p-[var(--page-margin)]">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1>Career</h1>
        {!adding && (
          <button type="button" onClick={() => setAdding(true)} className="button button-primary">
            + Add a role
          </button>
        )}
      </header>
      {adding && <AddRoleForm onClose={() => setAdding(false)} />}
      <TodoStrip load={todos.load} today={today} onChanged={reloadAll} />
      {load.state === "loading" && <p className="text-muted">Loading</p>}
      {load.state === "error" && <LoadError what="roles" error={load.error} />}
      {load.state === "ready" && (
        <div className="flex flex-col gap-[var(--gap-block)] lg:flex-row lg:items-start lg:gap-[var(--gap-panel)] lg:overflow-x-auto">
          {byStatus(load.data).map(({ status, roles }) => (
            <section
              key={status}
              aria-label={STATUS_LABEL[status]}
              className={`flex-col gap-2 lg:flex lg:w-[var(--career-column)] lg:shrink-0 ${roles.length ? "flex" : "hidden"}`}
            >
              <h2 className={`label ${STATUS_TONE[status] ?? ""}`}>
                {STATUS_LABEL[status]} · {roles.length}
              </h2>
              {roles.map((r) => (
                <RoleCard key={r.id} role={r} today={today} />
              ))}
            </section>
          ))}
        </div>
      )}
      {deleted.load.state === "ready" && <RecentlyDeleted deleted={deleted.load.data} onRestored={reloadAll} />}
    </div>
  );
}

function RoleCard({ role: r, today }: { role: Role; today: string }) {
  const facts = [r.location, r.comp].filter(Boolean).join(" · ");
  return (
    <a href={href("career", r.id)} className="panel flex flex-col gap-1 hover:border-muted">
      <span className="text-small font-semibold text-muted">{r.company}</span>
      <span className="font-medium leading-snug">{r.title}</span>
      {facts && <span className="text-small text-muted">{facts}</span>}
      {r.status !== "rejected" && r.todos.total > 0 && <NextTodo role={r} today={today} />}
      {r.last_event && (
        <span className="num font-mono text-meta text-muted">
          {KIND_LABEL[r.last_event.kind]} {dateLabel(r.last_event.date)} · {agoLabel(daysBetween(r.last_event.date, today))}
        </span>
      )}
    </a>
  );
}

/** "2 of 3 · next: Apply to role, due tomorrow", or all done. */
function NextTodo({ role: r, today }: { role: Role; today: string }) {
  const when = r.next_todo && due(r.next_todo.due_on, today);
  return (
    <span className="text-small text-muted">
      <span className="num font-mono">
        {r.todos.done} of {r.todos.total}
      </span>
      {r.next_todo ? (
        <>
          {" · next: "}
          <span aria-hidden="true" className="mr-1 inline-block size-[var(--lane-dot)] rounded-full" style={{ background: TODO_KIND_COLOR[r.next_todo.kind] }} />
          <span className="text-fg">{r.next_todo.text}</span>
          {when && <span className={when.overdue ? "text-negative" : ""}>{when.overdue ? `, overdue ${when.label}` : `, due ${when.label}`}</span>}
        </>
      ) : (
        " · all done"
      )}
    </span>
  );
}

/** Every open todo across roles, folded until you open it; the heading still says how many,
 *  and how many are overdue. Open, it groups by due day, type or role. */
function TodoStrip({ load, today, onChanged }: { load: Load<OpenTodo[]>; today: string; onChanged: () => Promise<unknown> }) {
  const [expanded, setExpanded] = useState(false);
  const [groupBy, setGroupBy] = useState<TodoGroup>("due");
  const todos = load.state === "ready" ? load.data : [];
  const overdue = todos.filter((t) => due(t.due_on, today)?.overdue).length;

  return (
    <section aria-label="To do" className="panel prose-width flex flex-col gap-2">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <FoldHeading label={load.state === "ready" ? `To do · ${todos.length}` : "To do"} expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
        {overdue > 0 && <span className="text-small text-negative">{overdue} overdue</span>}
        {expanded && (
          <div role="radiogroup" aria-label="Group by" className="ml-auto flex rounded-[var(--radius-control)] border border-line text-small">
            {TODO_GROUPS.map((g) => (
              <button
                key={g.id}
                type="button"
                role="radio"
                aria-checked={groupBy === g.id}
                onClick={() => setGroupBy(g.id)}
                className="min-h-[var(--tap-chip)] px-3 text-muted aria-checked:bg-bg aria-checked:text-fg"
              >
                {g.label}
              </button>
            ))}
          </div>
        )}
      </header>
      {expanded && load.state === "loading" && <p className="text-small text-muted">Loading</p>}
      {load.state === "error" && <LoadError what="todos" error={load.error} />}
      {expanded && load.state === "ready" && (
        <TodoList
          todos={todos.map((t) => ({ ...t, done_on: null }))}
          today={today}
          roleId={null}
          groupBy={groupBy}
          onChanged={async () => {
            await onChanged();
          }}
        />
      )}
    </section>
  );
}
