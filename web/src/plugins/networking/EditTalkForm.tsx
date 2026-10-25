import { useState, type FormEvent } from "react";
import { changedFields } from "@shell/edits";
import { Field } from "@shell/Field";
import { offerUndo } from "@shell/undo";
import { useSave } from "@shell/useSave";
import { deleteInteraction, editInteraction, KINDS, NEXT_STEPS, restoreInteraction, type Interaction, type TalkEdit } from "./data";
import { dateLabel } from "./networking";
import type { Saved } from "./LogCard";
import { NEXT_STEP_LABEL } from "./style";

// Fix a logged talk, in place of it on the person's line. Only what you changed is sent;
// with nothing changed, Save just closes. The summary shows only when the talk has one, so you
// can fix or clear it; the transcript is kept as recorded. Delete hides it and offers undo.

type Key = keyof TalkEdit;

export function EditTalkForm({
  talk,
  personId,
  today,
  onSaved,
  onClose,
}: {
  talk: Interaction;
  personId: string;
  today: string;
  onSaved: (saved: Saved) => Promise<void>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Record<Key, string>>(() => ({
    date: talk.date,
    kind: talk.kind,
    next_step: talk.next_step ?? "",
    title: talk.title ?? "",
    summary: talk.summary ?? "",
    notes: talk.notes ?? "",
  }));
  const back = () => onSaved({ personId, added: null });
  const { busy, error, save } = useSave(back);
  const set = (change: Partial<Record<Key, string>>) => setDraft((d) => ({ ...d, ...change }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const changes = changedFields<Key>(draft, talk);
    if (Object.keys(changes).length === 0) return onClose();
    save(() => editInteraction(talk.id, changes, talk.version));
  };

  const remove = () =>
    save(async () => {
      await deleteInteraction(talk.id);
      offerUndo({ what: `the ${talk.kind} on ${dateLabel(talk.date)}`, restore: () => restoreInteraction(talk.id), after: back });
    });

  return (
    <form onSubmit={submit} aria-label="Fix this talk" className="flex flex-col gap-[var(--gap-item)]">
      <div className="flex flex-wrap gap-2">
        <Field label="Kind">
          {(id) => (
            <select id={id} value={draft.kind} onChange={(e) => set({ kind: e.target.value })} className="control">
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Day">
          {(id) => (
            <input id={id} type="date" required value={draft.date} max={today} onChange={(e) => set({ date: e.target.value })} className="control" />
          )}
        </Field>
        <Field label="Next step">
          {(id) => (
            <select id={id} value={draft.next_step} onChange={(e) => set({ next_step: e.target.value })} className="control">
              <option value="">none</option>
              {NEXT_STEPS.map((s) => (
                <option key={s} value={s}>
                  {NEXT_STEP_LABEL[s]}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <Field label="Title">
        {(id) => <input id={id} value={draft.title} onChange={(e) => set({ title: e.target.value })} autoComplete="off" className="control" />}
      </Field>
      {talk.summary && (
        <Field label="Summary">
          {(id) => (
            <textarea id={id} value={draft.summary} onChange={(e) => set({ summary: e.target.value })} rows={3} className="control resize-y" />
          )}
        </Field>
      )}
      <Field label="Notes">
        {(id) => (
          <textarea id={id} value={draft.notes} onChange={(e) => set({ notes: e.target.value })} rows={6} className="control resize-y" />
        )}
      </Field>
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex items-center justify-end gap-3">
        <button type="button" disabled={busy} onClick={remove} className="link-button link-button-quiet mr-auto">
          Delete
        </button>
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
