import { useState, type ReactNode } from "react";
import { Breadcrumb } from "@shell/Breadcrumb";
import { isWebLink } from "@shell/edits";
import { ExternalLink } from "@shell/ExternalLink";
import { agoLabel, dateLabel, daysBetween, todayISO } from "@shell/dates";
import { LoadError } from "@shell/LoadError";
import { href } from "@shell/router";
import { useLoad } from "@shell/useLoad";
import { fetchRole, type RoleDetail, type RoleEvent } from "./data";
import { DetailsForm } from "./DetailsForm";
import { DraftsPanel } from "./DraftsPanel";
import { EventForm } from "./EventForm";
import { PostingPanel } from "./PostingPanel";
import { ReferralForm } from "./ReferralForm";
import { ResumePanel } from "./ResumePanel";
import { StatusForm } from "./StatusForm";
import { TextForm } from "./TextForm";
import { TodoList } from "./TodoList";
import { KIND_COLOR, KIND_LABEL } from "./style";

// One role: what it is (Edit fixes it), then its status, todos, referral, resume, drafts, posting and notes beside
// its timeline on the Mac. On the phone the timeline comes right after the status and todos: the side column
// dissolves (contents) and the order classes place it. Every save reloads the role, keeping it on
// screen until the new one arrives.

export function RolePage({ id }: { id: string }) {
  const { load, reload } = useLoad((signal) => fetchRole(id, signal), id);
  const [editing, setEditing] = useState(false);
  // The timeline's one open form: "new" to add, or the id of the event being fixed.
  const [eventForm, setEventForm] = useState<"new" | number | null>(null);
  const today = todayISO();

  const savedEvent = async () => {
    await reload();
    setEventForm(null);
  };

  if (load.state === "loading") return <p className="p-[var(--page-margin)] text-muted">Loading</p>;
  if (load.state === "error") return <LoadError what={id} error={load.error} className="p-[var(--page-margin)]" />;
  const role = load.data;

  return (
    <div className="flex flex-col gap-[var(--gap-block)] p-[var(--page-margin)]">
      <header className="flex flex-col gap-2">
        <Breadcrumb crumbs={[{ label: "Career", href: href("career") }, { label: role.company, href: href("career", id) }]} />
        <div className="flex items-baseline justify-between gap-3">
          <h1>{role.title}</h1>
          {!editing && (
            <button type="button" onClick={() => setEditing(true)} className="link-button">
              Edit
            </button>
          )}
        </div>
        {editing ? (
          <DetailsForm
            role={role}
            onSaved={async () => {
              await reload();
              setEditing(false);
            }}
            onClose={() => setEditing(false)}
          />
        ) : (
          <Facts role={role} />
        )}
      </header>

      <div className="flex flex-col gap-[var(--gap-block)] lg:flex-row lg:items-start">
        <div className="contents lg:flex lg:w-[var(--role-side)] lg:shrink-0 lg:flex-col lg:gap-[var(--gap-panel)]">
          {/* Keyed by what was saved, so a form starts fresh from the saved values. */}
          <StatusForm key={role.status} role={role} today={today} onSaved={reload} />
          <section aria-label="To do" className="panel flex flex-col gap-2">
            <h2 className="label">
              To do · {role.todos.filter((t) => t.done_on).length} of {role.todos.length}
            </h2>
            <TodoList todos={role.todos} today={today} roleId={id} onChanged={reload} />
          </section>
          <div className="order-2 flex flex-col gap-[var(--gap-panel)] lg:order-none">
            <ReferralForm key={`referral-${role.referral?.id ?? ""}`} role={role} onSaved={reload} />
            <ResumePanel role={role} onSaved={reload} />
            <DraftsPanel role={role} onSaved={reload} />
            <PostingPanel role={role} onSaved={reload} />
            <TextForm
              key={`notable-${role.notable ?? ""}`}
              role={role}
              field="notable"
              label="What stands out"
              placeholder="In your words, one per line: travel, team size, what they keep asking for."
              onSaved={reload}
            />
            <TextForm key={`notes-${role.notes ?? ""}`} role={role} field="notes" label="Notes" placeholder="Anything about this role." onSaved={reload} />
          </div>
        </div>
        <section aria-label="Timeline" className="panel order-1 flex min-w-0 flex-1 flex-col gap-[var(--gap-item)] lg:order-none">
          {eventForm === "new" ? (
            <EventForm roleId={id} today={today} onSaved={savedEvent} onClose={() => setEventForm(null)} />
          ) : (
            <header className="flex items-baseline justify-between gap-3">
              <h2 className="label">Timeline</h2>
              <button type="button" onClick={() => setEventForm("new")} className="link-button">
                + Add to timeline
              </button>
            </header>
          )}
          {role.events.length === 0 ? (
            <p className="text-muted">Nothing on the timeline yet.</p>
          ) : (
            <ol className="prose-width flex flex-col">
              {role.events.map((e, i) =>
                eventForm === e.id ? (
                  <li key={e.id} className="pb-[var(--gap-item)]">
                    <EventForm roleId={id} today={today} event={e} onSaved={savedEvent} onClose={() => setEventForm(null)} />
                  </li>
                ) : (
                  <Event key={e.id} event={e} today={today} last={i === role.events.length - 1} onEdit={() => setEventForm(e.id)} />
                ),
              )}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}

function Facts({ role: r }: { role: RoleDetail }) {
  const facts: ReactNode[] = [r.company, r.location, r.comp].filter(Boolean);
  if (r.link)
    facts.push(
      <ExternalLink href={r.link}>posting ↗</ExternalLink>,
    );
  if (r.applied_via)
    facts.push(
      <ExternalLink href={r.applied_via}>applied via ↗</ExternalLink>,
    );
  return (
    <p className="flex flex-wrap gap-x-2 text-copy text-muted">
      {facts.map((f, i) => (
        <span key={i}>
          {i > 0 && <span aria-hidden="true">· </span>}
          {f}
        </span>
      ))}
    </p>
  );
}

/** One event on the role's line: a dot in its kind's color, then what you wrote. Edit fixes it. */
function Event({ event: e, today, last, onEdit }: { event: RoleEvent; today: string; last: boolean; onEdit: () => void }) {
  return (
    <li className="flex gap-3 pb-[var(--gap-item)]">
      <span className="flex flex-col items-center pt-[7px]">
        <span aria-hidden="true" className="size-[var(--lane-dot)] shrink-0 rounded-full" style={{ background: KIND_COLOR[e.kind] }} />
        {!last && <span aria-hidden="true" className="mt-1 w-px flex-1 bg-line" />}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="num flex flex-wrap gap-x-2 font-mono text-meta text-muted">
            <span className="text-fg">{dateLabel(e.date)}</span>
            <span>{KIND_LABEL[e.kind]}</span>
            <span>{agoLabel(daysBetween(e.date, today))}</span>
          </p>
          <button type="button" aria-label={`Edit ${KIND_LABEL[e.kind]} on ${dateLabel(e.date)}`} onClick={onEdit} className="link-button link-button-quiet">
            Edit
          </button>
        </div>
        {e.text && <p className="text-copy whitespace-pre-line">{e.text}</p>}
        {e.prep_link && (
          <p className="text-small">
            <span className="label mr-2">Prep</span>
            {isWebLink(e.prep_link) ? (
              <ExternalLink href={e.prep_link} className="break-all text-accent hover:underline">
                {e.prep_link} ↗
              </ExternalLink>
            ) : (
              <span className="break-all font-mono text-muted">{e.prep_link}</span>
            )}
          </p>
        )}
      </div>
    </li>
  );
}
