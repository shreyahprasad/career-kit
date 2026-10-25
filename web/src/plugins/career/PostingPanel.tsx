import { useState } from "react";
import { dateLabel } from "@shell/dates";
import { FoldHeading } from "@shell/Fold";
import { offerUndo } from "@shell/undo";
import { wordCount } from "./career";
import { readPosting, savePosting, type PostingDraft, type RoleDetail } from "./data";
import { useSave } from "@shell/useSave";

// The posting as it was when saved: postings come down when a role closes. Read from the posting
// link, or pasted when a site will not give it up (Workday and LinkedIn often will not). The text
// is folded at first; it is long.
//
// A saved posting is never replaced unseen. Read again shows what came back and asks first, and
// warns when only the page's text could be read: a closed job's page can still answer, with
// nothing of the posting on it. Replacing it, read or pasted, offers undo.

export function PostingPanel({ role, onSaved }: { role: RoleDetail; onSaved: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState("");
  // What Read again found, waiting for you to replace the saved posting with it or not.
  const [found, setFound] = useState<PostingDraft | null>(null);
  const { busy, error, save } = useSave(async () => {
    await onSaved();
    setPasting(false);
    setPasted("");
    setFound(null);
  });
  const reading = useSave(async () => {});

  const replace = async (text: string) => {
    const before = role.posting;
    await savePosting(role.id, text);
    if (before)
      offerUndo({ what: "the saved posting", verb: "Replaced", restore: () => savePosting(role.id, before), after: onSaved });
  };
  const read = () =>
    reading.save(async () => {
      const draft = await readPosting(role.link!);
      if (role.posting) return setFound(draft);
      await savePosting(role.id, draft.posting);
      await onSaved();
    });

  return (
    <section aria-label="Posting" className="panel flex flex-col gap-2">
      <h2 className="label">Posting{role.posting_on && ` · saved ${dateLabel(role.posting_on)}`}</h2>
      {role.posting ? (
        <>
          <FoldHeading label={`${wordCount(role.posting)} words`} expanded={open} onToggle={() => setOpen(!open)} />
          {open && <p className="max-h-[var(--posting-max)] overflow-y-auto text-small whitespace-pre-line">{role.posting}</p>}
        </>
      ) : (
        !pasting && <p className="text-small text-muted">None saved yet.</p>
      )}
      {found ? (
        <div className="flex flex-col gap-[var(--gap-item)]">
          <p className="text-copy">
            Read {wordCount(found.posting)} words from the link. Replace the saved posting ({wordCount(role.posting ?? "")} words)?
          </p>
          {found.from === "page" && (
            <p className="text-small text-negative">Only the page's text could be read. Check it is still the posting, not a closed job's page.</p>
          )}
          <p className="max-h-[var(--posting-max)] overflow-y-auto rounded-[var(--radius-control)] border border-line p-2 text-small whitespace-pre-line">
            {found.posting}
          </p>
          <div className="flex flex-wrap justify-end gap-3">
            <button type="button" onClick={() => setFound(null)} className="button">
              Keep the saved one
            </button>
            <button type="button" disabled={busy} onClick={() => save(() => replace(found.posting))} className="button button-primary">
              {busy ? "Saving…" : "Replace"}
            </button>
          </div>
        </div>
      ) : pasting ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (pasted.trim()) save(() => replace(pasted));
          }}
          className="flex flex-col gap-[var(--gap-item)]"
        >
          <textarea
            aria-label="Posting text"
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            rows={8}
            autoFocus
            placeholder="Paste the whole posting."
            className="control resize-y placeholder:text-muted"
          />
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setPasting(false)} className="button">
              Cancel
            </button>
            <button type="submit" disabled={busy || !pasted.trim()} className="button button-primary">
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {role.link && (
            <button type="button" disabled={busy || reading.busy} onClick={read} className="link-button">
              {reading.busy ? "Reading…" : role.posting ? "Read again from link" : "Read from posting link"}
            </button>
          )}
          <button type="button" onClick={() => setPasting(true)} className="link-button link-button-quiet">
            {role.posting ? "Replace with pasted text" : "Paste it"}
          </button>
        </div>
      )}
      {(error ?? reading.error) && <p className="text-small text-negative">{error ?? reading.error}</p>}
    </section>
  );
}
