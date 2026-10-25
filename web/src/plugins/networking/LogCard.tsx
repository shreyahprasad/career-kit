import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Field } from "@shell/Field";
import { useSave } from "@shell/useSave";
import { KINDS, logConversation, NEXT_STEPS, type Person } from "./data";
import { emptyDraft, saveProblem, toConversation, type Draft, type Who } from "./log";
import { allTags } from "./networking";
import { PersonFields } from "./PersonFields";
import { PersonPicker } from "./PersonPicker";
import { NEXT_STEP_LABEL } from "./style";

// Log a talk: who it was with, then anything you want to add. Picking someone is
// enough; it saves as a call, today. Enter in a one-line field saves, and so does ⌘/Ctrl-Enter
// in the notes. Someone new gets a name and, if you like, a few details and tags; the writer makes
// their id and the page opens them.

export type Saved = { personId: string; added: string | null };

export function LogCard({
  people,
  today,
  start,
  onSaved,
  onClose,
}: {
  people: Person[];
  today: string;
  start: Who | null;
  /** Resolves once the page has caught up; the form stays "Saving…" until then. */
  onSaved: (saved: Saved) => Promise<void>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => emptyDraft(today, start));
  const { busy, error, save } = useSave();
  const set = (change: Partial<Draft>) => setDraft((d) => ({ ...d, ...change }));
  const problem = saveProblem(draft);
  const who = draft.who;
  const knownTags = useMemo(() => allTags(people), [people]);

  // Someone from the phonebook picked: the title is next, and Enter there saves. (A new
  // person's name field mounts with focus on its own.)
  const title = useRef<HTMLInputElement>(null);
  const pickedId = who && "id" in who ? who.id : null;
  useEffect(() => {
    if (pickedId) title.current?.focus();
  }, [pickedId]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (problem) return;
    save(async () => {
      const sent = toConversation(draft);
      const { person_id } = await logConversation(sent);
      await onSaved({ personId: person_id, added: sent.person?.name ?? null });
    });
  };

  const saveOnModEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
  };

  return (
    <section aria-label="Log a talk" className="panel">
      <form onSubmit={submit} className="flex flex-col gap-[var(--gap-item)]">
        <h2 className="label">Log a talk</h2>

        <PersonPicker people={people} value={who} onChange={(w) => set({ who: w })} autoFocus={!start} />

        {who && "name" in who && (
          <PersonFields who={who} known={knownTags} onChange={(w) => set({ who: w })} autoFocus />
        )}

        <div className="flex flex-wrap gap-2">
          <Field label="Kind">
            {(id) => (
              <select id={id} value={draft.kind} onChange={(e) => set({ kind: e.target.value as Draft["kind"] })} className="control">
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
              <input id={id} type="date" value={draft.date} max={today} onChange={(e) => set({ date: e.target.value })} className="control" />
            )}
          </Field>
          <Field label="Next step">
            {(id) => (
              <select id={id} value={draft.next_step} onChange={(e) => set({ next_step: e.target.value as Draft["next_step"] })} className="control">
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
          {(id) => (
            <input
              id={id}
              value={draft.title}
              onChange={(e) => set({ title: e.target.value })}
              placeholder="Optional, e.g. Intro chat"
              ref={title}
              className="control placeholder:text-muted"
            />
          )}
        </Field>

        <Field label="Notes">
          {(id) => (
            <textarea
              id={id}
              value={draft.notes}
              onChange={(e) => set({ notes: e.target.value })}
              onKeyDown={saveOnModEnter}
              rows={6}
              placeholder="Brain flush: everything you remember, in any order. Saved exactly as you write it."
              className="control resize-y placeholder:text-muted"
            />
          )}
        </Field>

        {error && <p className="text-small text-negative">{error}</p>}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {who && problem && <span className="text-small text-muted">{problem}</span>}
          <button type="button" onClick={onClose} className="button">
            Cancel
          </button>
          <button type="submit" disabled={busy || problem != null} className="button button-primary">
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </section>
  );
}

/** A labelled control. The label points at the control by id, not by wrapping it, so a
 *  select is named "Kind" and not "Kind" followed by every option. */
