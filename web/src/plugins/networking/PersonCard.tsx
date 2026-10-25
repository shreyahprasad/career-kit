import { useEffect, useState, type ReactNode, type Ref } from "react";
import { ExternalLink } from "@shell/ExternalLink";
import { Fold } from "@shell/Fold";
import { fetchPerson, type Interaction, type PersonDetail } from "./data";
import { EditPersonForm } from "./EditPersonForm";
import { EditTalkForm } from "./EditTalkForm";
import type { Saved } from "./LogCard";
import { agoLabel, dateLabel, daysBetween } from "./networking";
import { Dot, Tag } from "./parts";
import { NEXT_STEP_LABEL } from "./style";

// The open person: who they are and how you met, beside every talk newest first on
// a line, each with its summary, your notes, the next step, and the transcript when there is one.
// On the phone the talks sit below. Edit swaps who they are, or one talk, for a
// form to fix it.

export function PersonCard({
  id,
  today,
  version,
  onLog,
  knownTags,
  onSaved,
  ref,
}: {
  id: string | null;
  today: string;
  /** Changes when something is saved, so the open person loads again. */
  version: number;
  onLog: (id: string) => void;
  knownTags: string[];
  onSaved: (saved: Saved) => Promise<void>;
  ref: Ref<HTMLElement>;
}) {
  return (
    <section ref={ref} aria-label="Person" className="panel scroll-mt-[var(--page-margin)]">
      {id ? <Person key={`${id}:${version}`} id={id} today={today} onLog={() => onLog(id)} knownTags={knownTags} onSaved={onSaved} /> : <p className="text-muted">Select someone.</p>}
    </section>
  );
}

function Person({
  id,
  today,
  onLog,
  knownTags,
  onSaved,
}: {
  id: string;
  today: string;
  onLog: () => void;
  knownTags: string[];
  onSaved: (saved: Saved) => Promise<void>;
}) {
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [editingTalk, setEditingTalk] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchPerson(id, ctrl.signal)
      .then(setPerson)
      .catch((e: Error) => {
        if (!ctrl.signal.aborted) setError(e.message);
      });
    return () => ctrl.abort();
  }, [id]);

  if (error) return <p className="text-muted">Could not load {id}: {error}</p>;
  if (!person) return <p className="text-muted">Loading</p>;

  const company =
    person.company && person.company_website ? (
      <ExternalLink href={person.company_website}>{person.company} ↗</ExternalLink>
    ) : (
      person.company
    );
  const talks = person.interactions;
  return (
    <div className="flex flex-col gap-[var(--gap-block)] lg:flex-row">
      <div className="flex flex-col gap-[var(--gap-item)] lg:w-[var(--person-profile)] lg:shrink-0">
        {editing ? (
          <EditPersonForm person={person} known={knownTags} onSaved={onSaved} onClose={() => setEditing(false)} />
        ) : (
          <>
            <header className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-title font-semibold leading-tight">{person.name}</h2>
                <button type="button" onClick={() => setEditing(true)} className="link-button">
                  Edit
                </button>
              </div>
              {(person.role || person.company) && (
                <p className="text-copy text-muted">
                  {person.role}
                  {person.role && person.company && " · "}
                  {company}
                </p>
              )}
            </header>
            {person.about && <p className="text-copy">{person.about}</p>}
            {person.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {person.tags.map((t) => (
                  <Tag key={t} tag={t} />
                ))}
              </div>
            )}
            <Facts person={person} />
          </>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-[var(--gap-item)]">
        <header className="flex items-baseline justify-between gap-3">
          <h3 className="label">{talks.length === 0 ? "No talks yet" : `Talks · ${talks.length}`}</h3>
          <button type="button" onClick={onLog} className="link-button">
            + Log a talk
          </button>
        </header>
        {talks.length > 0 && (
          <ol className="prose-width flex flex-col">
            {talks.map((t, i) =>
              t.id === editingTalk ? (
                <li key={t.id} className="pb-[var(--gap-item)]">
                  <EditTalkForm talk={t} personId={id} today={today} onSaved={onSaved} onClose={() => setEditingTalk(null)} />
                </li>
              ) : (
                <Talk key={t.id} talk={t} today={today} newest={i === 0} last={i === talks.length - 1} onEdit={() => setEditingTalk(t.id)} />
              ),
            )}
          </ol>
        )}
      </div>
    </div>
  );
}

function Facts({ person: p }: { person: PersonDetail }) {
  const met = [p.met_how, p.met_on && dateLabel(p.met_on)].filter(Boolean).join(" · ");
  const rows: [string, ReactNode][] = [];
  if (met) rows.push(["met", met]);
  if (p.location) rows.push(["based", p.location]);
  if (p.linkedin)
    rows.push([
      "linkedin",
      <ExternalLink href={p.linkedin}>profile ↗</ExternalLink>,
    ]);
  if (p.email)
    rows.push([
      "email",
      <a href={`mailto:${p.email}`} className="break-all text-accent hover:underline">
        {p.email}
      </a>,
    ]);
  if (p.phone)
    rows.push([
      "phone",
      <a href={`tel:${p.phone.replace(/[^\d+]/g, "")}`} className="num text-accent hover:underline">
        {p.phone}
      </a>,
    ]);
  if (rows.length === 0) return null;
  return (
    <dl className="flex flex-col text-small">
      {rows.map(([label, value]) => (
        <div key={label} className="flex gap-3 border-t border-line py-1.5">
          <dt className="w-16 shrink-0 font-mono text-muted">{label}</dt>
          <dd className="min-w-0">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** One talk on the person's line: a dot in the kind's color, then what was said.
 *  Only the newest one's next step is still open; older ones are shown as done. Edit fixes it. */
function Talk({ talk: t, today, newest, last, onEdit }: { talk: Interaction; today: string; newest: boolean; last: boolean; onEdit: () => void }) {
  return (
    <li className="flex gap-3 pb-[var(--gap-item)]">
      <span className="flex flex-col items-center pt-[7px]">
        <Dot kind={t.kind} />
        {!last && <span aria-hidden="true" className="mt-1 w-px flex-1 bg-line" />}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="num flex flex-wrap gap-x-2 font-mono text-meta text-muted">
            <span className="text-fg">{dateLabel(t.date)}</span>
            <span>{t.kind}</span>
            <span>{agoLabel(daysBetween(t.date, today))}</span>
          </p>
          <button type="button" aria-label={`Edit ${t.kind} on ${dateLabel(t.date)}`} onClick={onEdit} className="link-button link-button-quiet">
            Edit
          </button>
        </div>
        {t.title && <p className="font-medium leading-snug">{t.title}</p>}
        {t.summary && <p className="text-copy whitespace-pre-line">{t.summary}</p>}
        {t.notes && (
          // Your brain flush, as you wrote it. Open when there is no summary, since it is all there is.
          <Fold label="Notes" open={!t.summary}>
            <p className="prose-width mt-1 text-copy whitespace-pre-line">{t.notes}</p>
          </Fold>
        )}
        {t.next_step && (
          <p className={`text-copy ${newest ? "" : "text-muted"}`}>
            <span className="label mr-2">{newest ? "Next" : "Was next"}</span>
            <span className={newest ? "font-medium text-accent" : ""}>{NEXT_STEP_LABEL[t.next_step]}</span>
          </p>
        )}
        {t.transcript && (
          <Fold label="Transcript">
            <pre className="mt-2 max-h-[var(--transcript-max)] overflow-y-auto rounded-[var(--radius-control)] border border-line bg-surface p-3 font-mono text-meta whitespace-pre-wrap">
              {t.transcript}
            </pre>
          </Fold>
        )}
      </div>
    </li>
  );
}
