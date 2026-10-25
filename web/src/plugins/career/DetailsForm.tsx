import { useState, type FormEvent } from "react";
import { changedFields } from "@shell/edits";
import { Field } from "@shell/Field";
import { href } from "@shell/router";
import { offerUndo } from "@shell/undo";
import { roleProblem } from "./career";
import { deleteRole, editRole, restoreRole, type RoleDetail } from "./data";
import { useSave } from "@shell/useSave";

// A role's details, edited in place of the facts line. Only what you changed is sent; with
// nothing changed, Save just closes. The status, notes and referral have their own panels.
// Delete hides the role with its timeline and todos, goes back to the board, and offers undo.

const FIELDS = [
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "location", label: "Location" },
  { key: "comp", label: "Comp" },
  { key: "link", label: "Posting link", type: "url" },
  { key: "applied_via", label: "Applied via", type: "url" },
] as const;

type Key = (typeof FIELDS)[number]["key"];

export function DetailsForm({ role, onSaved, onClose }: { role: RoleDetail; onSaved: () => Promise<void>; onClose: () => void }) {
  const [draft, setDraft] = useState(() => Object.fromEntries(FIELDS.map(({ key }) => [key, role[key] ?? ""])) as Record<Key, string>);
  const { busy, error, save } = useSave(onSaved);
  const removing = useSave(async () => {
    location.hash = href("career");
  });
  const problem = roleProblem(draft);

  const remove = () =>
    removing.save(async () => {
      await deleteRole(role.id);
      offerUndo({
        what: `${role.company} ${role.title}`,
        restore: () => restoreRole(role.id),
        after: () => {
          location.hash = href("career", role.id);
        },
      });
    });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (problem) return;
    const changes = changedFields<Key>(draft, role);
    if (Object.keys(changes).length === 0) return onClose();
    save(() => editRole(role.id, changes, role.version));
  };

  return (
    <form onSubmit={submit} aria-label="Role details" className="panel flex flex-col gap-[var(--gap-item)]">
      <div className="grid gap-2 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label}>
            {(id) => (
              <input
                id={id}
                type={"type" in f ? f.type : "text"}
                value={draft[f.key]}
                onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                placeholder={"type" in f ? "https://…" : undefined}
                autoComplete="off"
                className="control placeholder:text-muted"
              />
            )}
          </Field>
        ))}
      </div>
      {(problem || error || removing.error) && <p className="text-small text-negative">{problem ?? error ?? removing.error}</p>}
      <div className="flex items-center justify-end gap-3">
        <button type="button" disabled={removing.busy} onClick={remove} className="link-button link-button-quiet mr-auto">
          {removing.busy ? "Deleting…" : "Delete role"}
        </button>
        <button type="button" onClick={onClose} className="button">
          Cancel
        </button>
        <button type="submit" disabled={busy || problem != null} className="button button-primary">
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
