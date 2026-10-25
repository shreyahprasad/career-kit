import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Refusal } from "@shell/api";
import { FoldHeading } from "@shell/Fold";
import { fetchRole, saveText, type RoleDetail } from "./data";
import { useSave } from "@shell/useSave";

// Free text you write about the role (your notes, or what stands out in the posting), edited in
// place. Save shows once it differs from what is saved; ⌘/Ctrl-Enter saves too. Always folded when
// the role opens, so the page leads with what matters; the label says how much is inside, and
// "unsaved" when folded over an edit not yet saved.
//
// A save refused because the role changed elsewhere (409) never loses what you typed. If this
// text is as you found it, something else on the role changed, so it saves again over the new
// version. If this text changed too, the newer text shows and you pick: yours or that one.

export function TextForm({
  role,
  field,
  label,
  placeholder,
  onSaved,
}: {
  role: RoleDetail;
  field: "notes" | "notable";
  label: string;
  placeholder: string;
  onSaved: () => Promise<void>;
}) {
  const saved = role[field] ?? "";
  const [notes, setNotes] = useState(saved);
  const [expanded, setExpanded] = useState(false);
  // The text as saved elsewhere since you opened it, and the version to save yours over it.
  const [newer, setNewer] = useState<{ text: string; version: number } | null>(null);
  const lines = saved ? saved.split("\n").filter((l) => l.trim()).length : 0;
  const { busy, error, save } = useSave(onSaved);
  const changed = notes !== saved;

  const saveFrom = async (version: number) => {
    try {
      await saveText(role.id, field, notes, version);
    } catch (e) {
      if (!(e instanceof Refusal && e.status === 409)) throw e;
      const latest = await fetchRole(role.id);
      if (latest.version === version) throw e;
      const text = latest[field] ?? "";
      if (text !== saved) {
        setNewer({ text, version: latest.version });
        throw new Error("This was changed somewhere else since you opened it. Yours is still here.");
      }
      await saveText(role.id, field, notes, latest.version);
    }
  };

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (changed) save(() => saveFrom(newer?.version ?? role.version));
  };
  const saveOnModEnter = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
  };

  const counted = lines ? `${label} · ${lines} ${lines === 1 ? "line" : "lines"}` : label;
  return (
    <section aria-label={label} className="panel flex flex-col gap-2">
      <FoldHeading label={changed && !expanded ? `${counted} · unsaved` : counted} expanded={expanded} onToggle={() => setExpanded((e) => !e)} />
      {expanded && (
        <form onSubmit={submit} className="flex flex-col gap-[var(--gap-item)]">
          <textarea
            aria-label={label}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onKeyDown={saveOnModEnter}
            rows={6}
            placeholder={placeholder}
            autoFocus={saved === ""}
            className="control resize-y placeholder:text-muted"
          />
          {error && <p className="text-small text-negative">{error}</p>}
          {newer && (
            <div className="flex flex-col gap-1">
              <p className="label">Saved elsewhere</p>
              <p className="max-h-[var(--posting-max)] overflow-y-auto rounded-[var(--radius-control)] border border-line p-2 text-small whitespace-pre-line">
                {newer.text || "(empty)"}
              </p>
            </div>
          )}
          {changed && (
            <div className="flex flex-wrap justify-end gap-3">
              {newer ? (
                <button type="button" disabled={busy} onClick={onSaved} className="button">
                  Use the one saved elsewhere
                </button>
              ) : (
                <button type="button" onClick={() => setNotes(saved)} className="button">
                  Cancel
                </button>
              )}
              <button type="submit" disabled={busy} className="button button-primary">
                {busy ? "Saving…" : newer ? "Save mine over it" : "Save"}
              </button>
            </div>
          )}
        </form>
      )}
    </section>
  );
}
