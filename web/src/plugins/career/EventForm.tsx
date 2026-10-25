import { useState, type FormEvent } from "react";
import { dateLabel } from "@shell/dates";
import { changedFields } from "@shell/edits";
import { Field } from "@shell/Field";
import { offerUndo } from "@shell/undo";
import { ADDABLE_KINDS } from "./career";
import { addEvent, deleteEvent, editEvent, restoreEvent, type EventChanges, type Kind, type RoleEvent } from "./data";
import { KIND_LABEL } from "./style";
import { useSave } from "@shell/useSave";

// Add a recruiter call, an interview or a note to the timeline, or fix one already there. To add,
// only the kind is needed, and it is today unless you pick a day. To fix, only what you changed
// is sent. Applied, offer and rejection came with a status change, so their kind stays put: the
// status and the timeline never disagree. Delete hides the event and offers undo.

export function EventForm({
  roleId,
  today,
  event,
  onSaved,
  onClose,
}: {
  roleId: string;
  today: string;
  /** The event to fix; unset, the form adds one. */
  event?: RoleEvent;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<Kind>(event?.kind ?? "note");
  const [date, setDate] = useState(event?.date ?? today);
  const [text, setText] = useState(event?.text ?? "");
  const [prep, setPrep] = useState(event?.prep_link ?? "");
  const { busy, error, save } = useSave(onSaved);
  const kindFixed = event != null && !ADDABLE_KINDS.includes(event.kind);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!event) return save(() => addEvent(roleId, { kind, date, text, prep_link: prep }));
    const changes = changedFields<keyof EventChanges>({ kind, date, text, prep_link: prep }, event);
    if (Object.keys(changes).length === 0) return onClose();
    save(() => editEvent(event.id, changes, event.version));
  };

  const remove = (e: RoleEvent) =>
    save(async () => {
      await deleteEvent(e.id);
      offerUndo({ what: `the ${KIND_LABEL[e.kind]} on ${dateLabel(e.date)}`, restore: () => restoreEvent(e.id), after: onSaved });
    });

  return (
    <form onSubmit={submit} className="flex flex-col gap-[var(--gap-item)] border-b border-line pb-[var(--gap-item)]">
      <h2 className="label">{event ? "Fix this event" : "Add to timeline"}</h2>
      <div className="flex flex-wrap gap-2">
        <Field label="Kind">
          {(id) =>
            kindFixed ? (
              <p id={id} className="control flex items-center text-muted">
                {KIND_LABEL[kind]}
              </p>
            ) : (
              <select id={id} value={kind} onChange={(e) => setKind(e.target.value as Kind)} className="control">
                {ADDABLE_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABEL[k]}
                  </option>
                ))}
              </select>
            )
          }
        </Field>
        <Field label="Day">
          {(id) => <input id={id} type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="control" />}
        </Field>
      </div>
      <Field label="What happened">
        {(id) => (
          <textarea
            id={id}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            autoFocus
            className="control resize-y"
          />
        )}
      </Field>
      <Field label="Prep">
        {(id) => (
          <input
            id={id}
            value={prep}
            onChange={(e) => setPrep(e.target.value)}
            placeholder="Optional link or path"
            autoComplete="off"
            className="control placeholder:text-muted"
          />
        )}
      </Field>
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex items-center justify-end gap-3">
        {event && (
          <button type="button" disabled={busy} onClick={() => remove(event)} className="link-button link-button-quiet mr-auto">
            Delete
          </button>
        )}
        <button type="button" onClick={onClose} className="button">
          Cancel
        </button>
        <button type="submit" disabled={busy} className="button button-primary">
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
