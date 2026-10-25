import { useState } from "react";
import { dateLabel } from "@shell/dates";
import { Field } from "@shell/Field";
import { FoldHeading } from "@shell/Fold";
import { LoadError } from "@shell/LoadError";
import { PdfView } from "@shell/PdfView";
import { useLoad } from "@shell/useLoad";
import { sentOn } from "./career";
import { fetchResumes, resumeURL, sentURL, setResume, type RoleDetail } from "./data";
import { useSave } from "@shell/useSave";

// Which resume this role gets. Once you apply, the copy kept then is what shows, with the day:
// exactly what that company got. Until then you pick a PDF from data/resumes, which saves.
// The PDF itself is folded when the role opens and drawn only when opened.

export function ResumePanel({ role, onSaved }: { role: RoleDetail; onSaved: () => Promise<void> }) {
  const sent = role.sent_file;
  const appliedOn = sentOn(role.events);
  const shown = sent ? { url: sentURL(sent), name: sent } : role.resume_file ? { url: resumeURL(role.resume_file), name: role.resume_file } : null;

  return (
    <section aria-label="Resume" className="panel flex flex-col gap-2">
      <h2 className="label">Resume</h2>
      {sent ? (
        <p className="text-copy">Sent{appliedOn && ` ${dateLabel(appliedOn)}`}. This copy never changes.</p>
      ) : (
        <>
          {appliedOn && <p className="text-small text-muted">No copy was kept when you applied.</p>}
          <Picker role={role} onSaved={onSaved} />
        </>
      )}
      {shown && <Pdf key={shown.url} {...shown} />}
    </section>
  );
}

/** Your PDFs in data/resumes, in a native picker. Picking one saves it. */
function Picker({ role, onSaved }: { role: RoleDetail; onSaved: () => Promise<void> }) {
  // Loaded again when the role's resume changes: approving a resume draft adds its PDF to data/resumes.
  const { load } = useLoad(fetchResumes, `resumes/${role.resume_file ?? ""}`);
  const { busy, error, save } = useSave(onSaved);
  if (load.state === "loading") return <p className="text-small text-muted">Loading your resumes</p>;
  if (load.state === "error") return <LoadError what="your resumes" error={load.error} />;
  const names = load.data.map((r) => r.name);
  if (names.length === 0 && !role.resume_file)
    return <p className="text-small text-muted">Export a PDF into data/resumes to pick it here.</p>;
  const gone = role.resume_file && !names.includes(role.resume_file);

  return (
    <>
      <Field label="Resume to send">
        {(id) => (
          <select
            id={id}
            value={role.resume_file ?? ""}
            disabled={busy}
            onChange={(e) => save(() => setResume(role.id, e.target.value || null))}
            className="control"
          >
            <option value="">None yet</option>
            {gone && <option value={role.resume_file!}>{role.resume_file} (not in data/resumes)</option>}
            {load.data.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name} · {dateLabel(r.modified)}
              </option>
            ))}
          </select>
        )}
      </Field>
      {role.resume_file && <p className="text-small text-muted">A copy is kept when you mark it applied.</p>}
      {busy && <p className="text-small text-muted">Saving…</p>}
      {error && <p className="text-small text-negative">{error}</p>}
    </>
  );
}

/** The PDF, folded at first, with a link to open it full size. name labels its pages
 * for screen readers; the picker already shows it. */
function Pdf({ url, name }: { url: string; name: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <FoldHeading label="PDF" expanded={open} onToggle={() => setOpen(!open)} />
        <a href={url} target="_blank" rel="noreferrer" className="link-button link-button-quiet shrink-0">
          Open ↗
        </a>
      </div>
      {open && <PdfView url={url} label={name} />}
    </div>
  );
}
