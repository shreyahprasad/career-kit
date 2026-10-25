import { useRef, useState, type ClipboardEvent, type FormEvent } from "react";
import { toWebLink } from "@shell/edits";
import { Field } from "@shell/Field";
import { href } from "@shell/router";
import { fillFromPosting, roleProblem, toNewRole, wordCount, type NewRoleDraft } from "./career";
import { addRole, readPosting, type PostingDraft } from "./data";
import { useSave } from "@shell/useSave";

// Add a role from its posting link: pasting the link reads it (Read does too), filling in the
// company, title, location and pay from the posting and keeping its text, and you check them
// before Add. What you typed yourself is kept (fillFromPosting). A read is dropped if the link
// changed while it ran. A site that will not give the posting up says so, and you paste the text
// instead. With no link, company and title are enough. Saved, the page opens the new role, which
// starts with its todos.

const EMPTY: Required<NewRoleDraft> = { company: "", title: "", link: "", location: "", comp: "", posting: "" };

const FOUND: Record<PostingDraft["from"], string> = {
  feed: "Filled in from the job site. Check it, then Add.",
  "page data": "Filled in from the posting. Check it, then Add.",
  page: "Only the title and text could be read. Fill in the company.",
};

const DETAILS = [
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "location", label: "Location" },
  { key: "comp", label: "Comp" },
] as const;

export function AddRoleForm({ onClose }: { onClose: () => void }) {
  const [draft, setDraft] = useState(EMPTY);
  const [reading, setReading] = useState(false);
  const [read, setRead] = useState<{ found: string } | { unreadable: string } | null>(null);
  const [pasting, setPasting] = useState(false);
  // The last read, so a second one replaces what it filled; and which read is current.
  const lastRead = useRef<PostingDraft | undefined>(undefined);
  const readNumber = useRef(0);
  // The role page loads it, so there is nothing to reload here.
  const { busy, error, save } = useSave(async () => {});
  const problem = roleProblem(draft);
  const set = (change: Partial<typeof EMPTY>) => setDraft((d) => ({ ...d, ...change }));
  const linkReady = toWebLink(draft.link) !== null;

  const readLink = async (link: string) => {
    const mine = ++readNumber.current;
    setReading(true);
    setRead(null);
    try {
      const found = await readPosting(link.trim());
      if (mine !== readNumber.current) return;
      setDraft((d) => fillFromPosting(d, found, lastRead.current));
      lastRead.current = found;
      setRead({ found: FOUND[found.from] });
      setPasting(false);
    } catch (e) {
      if (mine === readNumber.current) setRead({ unreadable: (e as Error).message });
    }
    if (mine === readNumber.current) setReading(false);
  };
  const typeLink = (link: string) => {
    readNumber.current++; // a read still running is for the old link
    setReading(false);
    set({ link });
  };
  const pasteLink = (e: ClipboardEvent<HTMLInputElement>) => {
    const link = toWebLink(e.clipboardData.getData("text"));
    if (!link) return;
    e.preventDefault();
    typeLink(link);
    readLink(link);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!problem)
      save(async () => {
        const { role_id } = await addRole(toNewRole(draft));
        location.hash = href("career", role_id);
      });
  };

  return (
    <form onSubmit={submit} aria-label="Add a role" className="panel flex flex-col gap-[var(--gap-item)]">
      <h2 className="label">Add a role</h2>
      <Field label="Posting link">
        {(id) => (
          <div className="flex gap-2">
            <input
              id={id}
              type="url"
              value={draft.link}
              onChange={(e) => typeLink(e.target.value)}
              onPaste={pasteLink}
              placeholder="Paste it and it is read"
              autoFocus
              autoComplete="off"
              className="control min-w-0 flex-1 placeholder:text-muted"
            />
            <button type="button" disabled={!linkReady || reading} onClick={() => readLink(draft.link)} className="button shrink-0">
              {reading ? "Reading…" : "Read"}
            </button>
          </div>
        )}
      </Field>
      {read && "found" in read && <p className="text-small text-muted">{read.found}</p>}
      {read && "unreadable" in read && <p className="text-small text-negative">{read.unreadable}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {DETAILS.map(({ key, label }) => (
          <Field key={key} label={label}>
            {(id) => <input id={id} value={draft[key]} onChange={(e) => set({ [key]: e.target.value })} autoComplete="off" className="control" />}
          </Field>
        ))}
      </div>
      {pasting ? (
        <Field label="Posting text">
          {(id) => (
            <textarea
              id={id}
              value={draft.posting}
              onChange={(e) => set({ posting: e.target.value })}
              rows={8}
              autoFocus
              placeholder="Paste the whole posting. It is kept with the role."
              className="control resize-y placeholder:text-muted"
            />
          )}
        </Field>
      ) : (
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          {draft.posting && (
            <span className="text-small text-muted">{wordCount(draft.posting)} words of the posting are kept.</span>
          )}
          <button type="button" onClick={() => setPasting(true)} className="link-button link-button-quiet">
            {draft.posting ? "Edit the text" : "Paste the posting text"}
          </button>
        </div>
      )}
      {error && <p className="text-small text-negative">{error}</p>}
      <div className="flex flex-wrap items-center justify-end gap-3">
        {problem && (draft.company || draft.title || draft.link) && <span className="text-small text-muted">{problem}</span>}
        <button type="button" onClick={onClose} className="button">
          Cancel
        </button>
        <button type="submit" disabled={busy || reading || problem != null} className="button button-primary">
          {busy ? "Saving…" : "Add"}
        </button>
      </div>
    </form>
  );
}
