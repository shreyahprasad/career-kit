import { useState, type FormEvent } from "react";
import { offerUndo } from "@shell/undo";
import { useSave } from "@shell/useSave";
import { deletePerson, editPerson, restorePerson, type PersonDetail } from "./data";
import type { Saved } from "./LogCard";
import { PERSON_FIELDS, personChanges, type NewWho } from "./log";
import { PersonFields } from "./PersonFields";

// Fix someone's details or tags. Only what you changed is sent; with nothing changed, Save just
// closes. Saved, the page reloads everyone, since a name, company or tag shows in the phonebook.
// Delete hides them with their talks, and offers undo.

const fromPerson = (p: PersonDetail): NewWho => ({
  name: p.name,
  details: Object.fromEntries(PERSON_FIELDS.map(({ key }) => [key, p[key] ?? ""])),
  tags: p.tags,
});

export function EditPersonForm({
  person,
  known,
  onSaved,
  onClose,
}: {
  person: PersonDetail;
  known: string[];
  onSaved: (saved: Saved) => Promise<void>;
  onClose: () => void;
}) {
  const [who, setWho] = useState(() => fromPerson(person));
  const back = () => onSaved({ personId: person.id, added: null });
  const { busy, error, save } = useSave(back);
  const named = who.name.trim() !== "";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!named || busy) return;
    const changes = personChanges(who, person);
    if (Object.keys(changes).length === 0) return onClose();
    save(() => editPerson(person.id, changes, person.version));
  };

  const remove = () =>
    save(async () => {
      await deletePerson(person.id);
      offerUndo({ what: person.name, restore: () => restorePerson(person.id), after: back });
    });

  return (
    <form onSubmit={submit} aria-label={`Edit ${person.name}`} className="flex flex-col gap-[var(--gap-item)]">
      <PersonFields who={who} known={known} onChange={setWho} open />
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex items-center justify-end gap-3">
        <button type="button" disabled={busy} onClick={remove} className="link-button link-button-quiet mr-auto">
          Delete person
        </button>
        <button type="button" onClick={onClose} className="button">
          Cancel
        </button>
        <button type="submit" disabled={busy || !named} className="button button-primary">
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </form>
  );
}
