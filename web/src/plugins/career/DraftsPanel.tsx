import { useEffect, useState } from "react";
import { dateLabel } from "@shell/dates";
import { Field } from "@shell/Field";
import { LoadError } from "@shell/LoadError";
import { PdfView } from "@shell/PdfView";
import { useLoad } from "@shell/useLoad";
import { useSave } from "@shell/useSave";
import { DRAFT_VIEWS, draftLabel, draftShows, isApproved, latestDraft, pagesLabel, sentOn, wordCount, type DraftView } from "./career";
import { approveDraft, draftPdfURL, fetchDrafts, fetchDraftText, fetchSentLetter, makeDraftPdf, pdfName, sentURL, type Draft, type RoleDetail } from "./data";
import { COPIED_MS, DRAFT_KIND_LABEL, DRAFT_VIEW_LABEL } from "./style";

// The resume drafts and cover letters Claude wrote for this role (data/drafts/<role>), to read,
// copy and approve. Pick one to see it as the PDF that would be sent, or switch to its text to
// copy. Approve marks it the one for its kind, replacing the one approved before, and checks off
// its review todo; an approved resume's PDF becomes the role's resume. Once you apply, the copy of
// the approved letter kept then shows here too: exactly what that company got.
// Claude writes drafts; only you approve one. The list loads with the role and after each save.

export function DraftsPanel({ role, onSaved }: { role: RoleDetail; onSaved: () => Promise<void> }) {
  const { load, reload } = useLoad((signal) => fetchDrafts(role.id, signal), `drafts-${role.id}`);

  return (
    <section aria-label="Drafts" className="panel flex flex-col gap-2">
      <h2 className="label">Drafts</h2>
      {role.sent_cover_letter && <SentLetter name={role.sent_cover_letter} on={sentOn(role.events)} hasPdf={role.sent_cover_letter_pdf} />}
      {load.state === "loading" ? (
        <p className="text-small text-muted">Loading drafts</p>
      ) : load.state === "error" ? (
        <LoadError what="the drafts" error={load.error} />
      ) : load.data.length === 0 ? (
        <p className="text-small text-muted">
          None yet. Ask Claude to "tailor my resume for this role" or "write a cover letter for this role".
        </p>
      ) : (
        <Viewer
          role={role}
          drafts={load.data}
          onSaved={async () => {
            await onSaved();
            await reload();
          }}
        />
      )}
    </section>
  );
}

/** The picker, the picked draft as PDF or text, and Approve or Unapprove. Shows the latest
 * draft first, as its PDF. */
function Viewer({ role, drafts, onSaved }: { role: RoleDetail; drafts: Draft[]; onSaved: () => Promise<void> }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [view, setView] = useState<DraftView>("pdf");
  const { busy, error, save } = useSave(onSaved);
  const shown = drafts.find((d) => d.name === picked) ?? latestDraft(drafts)!;
  const approved = isApproved(shown, role);
  const kind = DRAFT_KIND_LABEL[shown.kind].toLowerCase();
  const what = `${DRAFT_KIND_LABEL[shown.kind]} ${shown.number}`;

  return (
    <>
      <Field label="Draft">
        {(id) => (
          <select id={id} value={shown.name} onChange={(e) => setPicked(e.target.value)} className="control">
            {drafts.map((d) => (
              <option key={d.name} value={d.name}>
                {draftLabel(d, role)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <ViewSwitch view={view} onChange={setView} what={what} />
      {draftShows(view, shown.pdf) === "pdf" ? (
        <PdfView key={`${shown.name}@${shown.modified_at}`} url={draftPdfURL(role.id, shown.name)} label={what} />
      ) : draftShows(view, shown.pdf) === "make-pdf" ? (
        <MakePdf key={shown.name} roleId={role.id} name={shown.name} onMade={onSaved} />
      ) : (
        <DraftText
          key={shown.name}
          load={(signal) => fetchDraftText(role.id, shown.name, signal)}
          loadKey={`${role.id}/${shown.name}`}
          what={what}
        />
      )}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={busy}
          onClick={() => save(() => approveDraft(role.id, shown.kind, approved ? null : shown.name))}
          className={approved ? "link-button link-button-quiet" : "button button-primary"}
        >
          {busy ? "Saving…" : approved ? "Unapprove" : `Approve this ${kind}`}
        </button>
      </div>
      {approved && shown.kind === "resume" && (
        <p className="text-small text-muted">Approved. Its PDF is this role's resume, under Resume.</p>
      )}
      {approved && shown.kind === "cover-letter" && !role.sent_cover_letter && (
        <p className="text-small text-muted">Approved. A copy is kept when you mark the role applied.</p>
      )}
      {error && <p className="text-small text-negative">{error}</p>}
    </>
  );
}

/** PDF | Text, as two pressable buttons. what names the draft for screen readers. */
function ViewSwitch({ view, onChange, what }: { view: DraftView; onChange: (v: DraftView) => void; what: string }) {
  return (
    <div role="group" aria-label={`Show ${what} as`} className="flex gap-2">
      {DRAFT_VIEWS.map((v) => (
        <button
          key={v}
          type="button"
          aria-pressed={view === v}
          onClick={() => onChange(v)}
          className="button aria-pressed:border-accent aria-pressed:text-fg"
        >
          {DRAFT_VIEW_LABEL[v]}
        </button>
      ))}
    </div>
  );
}

/** No PDF of this draft yet, or the draft changed since: make it here. */
function MakePdf({ roleId, name, onMade }: { roleId: string; name: string; onMade: () => Promise<void> }) {
  const [pages, setPages] = useState<number | null>(null);
  const { busy, error, save } = useSave(onMade);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-small text-muted">No PDF of this draft yet. Make it here, or ask Claude to.</p>
      <div>
        <button
          type="button"
          disabled={busy}
          onClick={() => save(async () => setPages((await makeDraftPdf(roleId, name)).pages))}
          className="button"
        >
          {busy ? "Making the PDF…" : "Make PDF"}
        </button>
      </div>
      {pages !== null && <p className="text-small text-muted">Made, {pagesLabel(pages)}.</p>}
      {error && <p className="text-small text-negative">{error}</p>}
    </div>
  );
}

/** The kept copy of the approved letter, which never changes: its PDF when one was kept. */
function SentLetter({ name, on, hasPdf }: { name: string; on: string | null; hasPdf: boolean }) {
  const [view, setView] = useState<DraftView>("pdf");
  return (
    <div className="flex flex-col gap-2">
      <p className="text-copy">Cover letter sent{on && ` ${dateLabel(on)}`}. This copy never changes.</p>
      {hasPdf && <ViewSwitch view={view} onChange={setView} what="the sent cover letter" />}
      {hasPdf && view === "pdf" ? (
        <PdfView url={sentURL(pdfName(name))} label="The sent cover letter" />
      ) : (
        <DraftText load={(signal) => fetchSentLetter(name, signal)} loadKey={`sent/${name}`} what="the sent cover letter" />
      )}
    </div>
  );
}

/** A draft's text, scrolling past --draft-max, with its word count and a Copy button. what names
 * it for the button, since the sent letter and a draft can both be on screen. */
function DraftText({
  load: fetcher,
  loadKey,
  what,
}: {
  load: (signal?: AbortSignal) => Promise<string>;
  loadKey: string;
  what: string;
}) {
  const { load } = useLoad(fetcher, loadKey);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), COPIED_MS);
    return () => clearTimeout(timer);
  }, [copied]);

  if (load.state === "loading") return <p className="text-small text-muted">Loading</p>;
  if (load.state === "error") return <LoadError what="this draft" error={load.error} />;
  const text = load.data;
  const copy = async () => {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopyError("Could not copy. Select the text and copy it instead.");
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <p className="max-h-[var(--draft-max)] overflow-y-auto rounded-[var(--radius-control)] border border-line p-2 text-small whitespace-pre-wrap">
        {text}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="num font-mono text-meta text-muted">{wordCount(text)} words</span>
        {navigator.clipboard && (
          <button type="button" onClick={copy} aria-label={copied ? `Copied ${what}` : `Copy ${what}`} aria-live="polite" className="button">
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
      {copyError && <p className="text-small text-negative">{copyError}</p>}
    </div>
  );
}
