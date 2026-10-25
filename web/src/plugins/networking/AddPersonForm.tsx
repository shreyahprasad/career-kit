import { useState, type FormEvent } from "react";
import { useSave } from "@shell/useSave";
import { addPerson } from "./data";
import type { Saved } from "./LogCard";
import { toNewPerson, type NewWho } from "./log";
import { PersonFields } from "./PersonFields";

// Add someone to the phonebook with no talk: a name is enough. Saved, the page opens them.

export function AddPersonForm({
  known,
  onAdded,
  onClose,
}: {
  known: string[];
  /** Resolves once the page has caught up; the form stays "Saving…" until then. */
  onAdded: (added: Saved) => Promise<void>;
  onClose: () => void;
}) {
  const [who, setWho] = useState<NewWho>({ name: "", details: {}, tags: [] });
  const { busy, error, save } = useSave();
  const named = who.name.trim() !== "";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!named) return;
    save(async () => {
      const person = toNewPerson(who);
      const { person_id } = await addPerson(person);
      await onAdded({ personId: person_id, added: person.name });
    });
  };

  return (
    <form onSubmit={submit} aria-label="Add someone" className="flex flex-col gap-[var(--gap-item)] border-b border-line pb-[var(--gap-item)]">
      <PersonFields who={who} known={known} onChange={setWho} autoFocus />
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex justify-end gap-3">
        <button type="button" onClick={onClose} className="button">
          Cancel
        </button>
        <button type="submit" disabled={busy || !named} className="button button-primary">
          {busy ? "Saving…" : "Add"}
        </button>
      </div>
    </form>
  );
}
