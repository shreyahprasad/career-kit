import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Fold } from "@shell/Fold";
import { href } from "@shell/router";
import { offerUndo } from "@shell/undo";
import { useSave, useSaveEach } from "@shell/useSave";
import { due, groupTodos, splitTodos, withDone, type TodoGroup } from "./career";
import { addTodo, deleteTodo, editTodo, restoreTodo, TODO_KINDS, type OpenTodo, type Todo, type TodoKind } from "./data";
import { TODO_KIND_COLOR, TODO_KIND_LABEL } from "./style";

// A checklist, made for the thumb: the whole row checks a todo off, and every target is at least
// --tap tall. A tick shows the moment you tap, before the save comes back; a refusal undoes it
// and says why, and a row being saved takes no second tap. Done ones fold away. + adds one; Enter
// adds it and leaves the box open for the next. The day beside a todo sets when it is due (the
// phone's own date picker), and its dot, colored by kind, changes the kind (the phone's own
// picker). × deletes it and offers undo, as deleting a role or an event does. Grouped, open todos
// sit under a label per group.

type Item = Todo & { role?: OpenTodo["role"] };

export function TodoList({
  todos,
  today,
  roleId,
  groupBy,
  onChanged,
}: {
  todos: Item[];
  today: string;
  /** Where + adds a todo: this role, or null for your search as a whole. */
  roleId: string | null;
  /** Group the open todos; unset, one list. */
  groupBy?: TodoGroup;
  /** Loads the todos again after a change. */
  onChanged: () => Promise<void>;
}) {
  // Taps not yet saved: the todo id and whether it is now done.
  const { pending, error, save } = useSaveEach<number, boolean>(onChanged);
  const shown = [...pending].reduce((list, [id, done]) => withDone(list, id, done, today), todos);
  const { open, done } = splitTodos(shown);

  const change = (id: number, work: () => Promise<unknown>, done?: boolean) =>
    save(id, work, done ?? !!todos.find((t) => t.id === id)?.done_on);

  const rows = (list: Item[]) => (
    <ul className="flex flex-col">
      {list.map((t) => (
        <Row
          key={t.id}
          todo={t}
          today={today}
          saving={pending.has(t.id)}
          onCheck={(isDone) => change(t.id, () => editTodo(t.id, { done: isDone }), isDone)}
          onDue={(day) => change(t.id, () => editTodo(t.id, { due_on: day || null }))}
          onKind={(kind) => change(t.id, () => editTodo(t.id, { kind }))}
          onDelete={() =>
            change(t.id, async () => {
              await deleteTodo(t.id);
              offerUndo({ what: `“${t.text}”`, restore: () => restoreTodo(t.id), after: onChanged });
            })
          }
        />
      ))}
    </ul>
  );

  return (
    <div className="flex flex-col gap-2">
      {open.length === 0 && <p className="text-small text-muted">Nothing to do.</p>}
      {groupBy
        ? groupTodos(open, groupBy, today).map((g) => (
            <section key={g.label} aria-label={g.label} className="flex flex-col">
              <h3 className="label pt-2">{g.label}</h3>
              {rows(g.todos)}
            </section>
          ))
        : rows(open)}
      <AddTodo roleId={roleId} onAdded={onChanged} />
      {error && <p className="text-small text-negative">{error}</p>}
      {done.length > 0 && <Fold label={`Done · ${done.length}`}>{rows(done)}</Fold>}
    </div>
  );
}

function Row({
  todo: t,
  today,
  saving,
  onCheck,
  onDue,
  onKind,
  onDelete,
}: {
  todo: Item;
  today: string;
  saving: boolean;
  onCheck: (done: boolean) => void;
  /** The new day, or "" to clear it. */
  onDue: (day: string) => void;
  onKind: (kind: TodoKind) => void;
  onDelete: () => void;
}) {
  const when = due(t.due_on, today);
  const isDone = !!t.done_on;

  return (
    <li className="flex items-center gap-1 border-b border-line last:border-b-0">
      <KindDot kind={t.kind} saving={saving} onKind={onKind} />
      <label className={`flex min-h-[var(--tap)] min-w-0 flex-1 cursor-pointer items-center gap-3 py-1 ${saving ? "opacity-60" : ""}`}>
        <input
          type="checkbox"
          checked={isDone}
          disabled={saving}
          onChange={(e) => onCheck(e.target.checked)}
          className="size-[var(--check)] shrink-0 accent-[var(--accent)]"
        />
        <span className="flex min-w-0 flex-col">
          <span className={`leading-snug ${isDone ? "text-muted line-through" : ""}`}>{t.text}</span>
          {t.role && (
            <a href={href("career", t.role.id)} className="truncate text-small text-accent hover:underline">
              {t.role.company} · {t.role.title}
            </a>
          )}
        </span>
      </label>
      {!isDone && <DueChip day={t.due_on} when={when} saving={saving} onDue={onDue} />}
      <button
        type="button"
        aria-label={`Delete “${t.text}”`}
        onClick={onDelete}
        disabled={saving}
        className="grid size-[var(--tap)] shrink-0 place-items-center text-muted hover:text-fg"
      >
        ×
      </button>
    </li>
  );
}

/** The kind's dot, a fill only. The select lies invisibly over it, so a tap opens the phone's
 *  own picker to change the kind. */
function KindDot({ kind, saving, onKind }: { kind: TodoKind; saving: boolean; onKind: (kind: TodoKind) => void }) {
  return (
    <span className="relative grid min-h-[var(--tap)] w-[var(--kind-box)] shrink-0 place-items-center">
      <span aria-hidden="true" className="size-[var(--lane-dot)] rounded-full" style={{ background: TODO_KIND_COLOR[kind] }} />
      <select
        aria-label={`Kind: ${TODO_KIND_LABEL[kind]}, change`}
        value={kind}
        disabled={saving}
        onChange={(e) => onKind(e.target.value as TodoKind)}
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {TODO_KINDS.map((k) => (
          <option key={k} value={k}>
            {TODO_KIND_LABEL[k]}
          </option>
        ))}
      </select>
    </span>
  );
}

/** When it is due, or "+ day": tapping opens the phone's date picker (a clear button there
 *  takes the day off). The date input lies invisibly over the label, so the tap lands on it. */
function DueChip({
  day,
  when,
  saving,
  onDue,
}: {
  day: string | null;
  when: ReturnType<typeof due>;
  saving: boolean;
  onDue: (day: string) => void;
}) {
  const label = when ? (when.overdue ? `overdue ${when.label}` : `due ${when.label}`) : "+ day";
  return (
    <span className={`relative flex min-h-[var(--tap)] shrink-0 items-center px-1 text-small ${when?.overdue ? "text-negative" : "text-muted"}`}>
      {label}
      <input
        type="date"
        aria-label={when ? `Due ${when.label}, change` : "Set a due day"}
        value={day ?? ""}
        disabled={saving}
        onChange={(e) => onDue(e.target.value)}
        // On the Mac a click on a date field only focuses it; this opens the picker as the phone does.
        onClick={(e) => e.currentTarget.showPicker?.()}
        className="absolute inset-0 cursor-pointer opacity-0"
      />
    </span>
  );
}

/** + opens a box; Enter adds and keeps it open for another; Escape, or Close, shuts it. */
function AddTodo({ roleId, onAdded }: { roleId: string | null; onAdded: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [kind, setKind] = useState<TodoKind>("other");
  const [day, setDay] = useState("");
  const { busy, error, save, clearError } = useSave();
  const box = useRef<HTMLInputElement>(null);

  if (!open)
    return (
      <button type="button" onClick={() => setOpen(true)} className="flex min-h-[var(--tap)] items-center self-start text-accent hover:underline">
        + Add a todo
      </button>
    );

  const close = () => {
    setText("");
    setKind("other");
    setDay("");
    clearError();
    setOpen(false);
  };
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!text.trim()) return;
    save(async () => {
      await addTodo(roleId, { text: text.trim(), kind, ...(day ? { due_on: day } : {}) });
      await onAdded();
      setText("");
      setDay("");
      box.current?.focus();
    });
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") close();
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <input
          ref={box}
          aria-label="New todo"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder="What to do"
          enterKeyHint="done"
          autoFocus
          autoComplete="off"
          className="control min-w-0 flex-1 basis-48 placeholder:text-muted"
        />
        <input aria-label="Due" type="date" value={day} onChange={(e) => setDay(e.target.value)} className="control" />
      </div>
      <div role="radiogroup" aria-label="Kind" className="flex flex-wrap gap-1.5">
        {TODO_KINDS.map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={kind === k}
            onClick={() => setKind(k)}
            className="flex min-h-[var(--tap-chip)] items-center gap-1.5 rounded-full border border-line px-3 text-small text-muted aria-checked:border-accent aria-checked:text-fg"
          >
            <span aria-hidden="true" className="size-[var(--lane-dot)] rounded-full" style={{ background: TODO_KIND_COLOR[k] }} />
            {TODO_KIND_LABEL[k]}
          </button>
        ))}
      </div>
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex justify-end gap-3">
        <button type="button" onClick={close} className="button">
          Close
        </button>
        <button type="submit" disabled={busy || !text.trim()} className="button button-primary">
          {busy ? "Adding…" : "Add"}
        </button>
      </div>
    </form>
  );
}
