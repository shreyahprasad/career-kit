import { useState, type FormEvent } from "react";
import { Field } from "@shell/Field";
import { statusEvent } from "./career";
import { setStatus, STATUSES, type RoleDetail, type Status } from "./data";
import { KIND_LABEL, STATUS_LABEL } from "./style";
import { useSave } from "@shell/useSave";

// The role's status. Picking applied, offer or rejected also logs it on the timeline, so those
// ask for the day and, if you like, a line about it.

export function StatusForm({ role, today, onSaved }: { role: RoleDetail; today: string; onSaved: () => Promise<void> }) {
  const [status, setPicked] = useState<Status>(role.status);
  const [date, setDate] = useState(today);
  const [text, setText] = useState("");
  const { busy, error, save } = useSave(onSaved);
  const logs = statusEvent(status);
  const changed = status !== role.status;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (changed) save(() => setStatus(role.id, { ...(logs ? { status, date, text } : { status }), version: role.version }));
  };

  return (
    <section aria-label="Status" className="panel">
      <form onSubmit={submit} className="flex flex-col gap-[var(--gap-item)]">
        <Field label="Status">
          {(id) => (
            <select id={id} value={status} onChange={(e) => setPicked(e.target.value as Status)} className="control">
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          )}
        </Field>
        {changed && logs && (
          <>
            <p className="text-small text-muted">This adds “{KIND_LABEL[logs]}” to the timeline.</p>
            <Field label="Day">
              {(id) => <input id={id} type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} className="control" />}
            </Field>
            <Field label="Note">
              {(id) => (
                <input
                  id={id}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Optional"
                  className="control placeholder:text-muted"
                />
              )}
            </Field>
          </>
        )}
        {error && <p className="text-small text-negative">{error}</p>}
        {changed && (
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setPicked(role.status)} className="button">
              Cancel
            </button>
            <button type="submit" disabled={busy} className="button button-primary">
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        )}
      </form>
    </section>
  );
}
