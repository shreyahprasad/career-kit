// Board and timeline rules for the career page.

import { daysBetween, monthDayLabel, MONTHS } from "@shell/dates";
import { toWebLink } from "@shell/edits";
import { APPROVAL_FIELD, KINDS, STATUSES, TODO_KINDS, type Draft, type Kind, type NewRole, type OpenTodo, type PostingDraft, type Role, type RoleDetail, type RoleEvent, type Status, type Todo } from "./data";
import { DRAFT_KIND_LABEL, TODO_KIND_LABEL } from "./style";

/** The event a status change logs on the timeline, as records.STATUS_EVENT in the writer. */
const STATUS_EVENT: Partial<Record<Status, Kind>> = { applied: "applied", offer: "offer", rejected: "rejection" };

export const statusEvent = (status: Status): Kind | null => STATUS_EVENT[status] ?? null;

/** What the timeline form adds. The rest come with a status change. */
export const ADDABLE_KINDS = KINDS.filter((k) => !Object.values(STATUS_EVENT).includes(k));

/** The day the kept copy of your resume was sent: your latest applied event. events are newest first. */
export const sentOn = (events: RoleEvent[]): string | null => events.find((e) => e.kind === "applied")?.date ?? null;

/** One column per status, in order, each with its most recently active role first. */
export function byStatus(roles: Role[]): { status: Status; roles: Role[] }[] {
  const latest = (r: Role) => r.last_event?.date ?? "";
  return STATUSES.map((status) => ({
    status,
    // sort is stable, so roles with the same latest day keep the API's order.
    roles: roles.filter((r) => r.status === status).sort((a, b) => latest(b).localeCompare(latest(a))),
  }));
}

// ── Adding and editing a role ────────────────────────────────────────────────

/** A role's details as a form holds them, "" for none. */
export type RoleDraft = { company: string; title: string; link: string; applied_via?: string };

const LINK_LABEL = { link: "posting", applied_via: "applied via" } as const;

/** What stops the role saving, in your words, or null. */
export function roleProblem(d: RoleDraft): string | null {
  if (!d.company.trim()) return "Give it a company.";
  if (!d.title.trim()) return "Give it a title.";
  for (const key of ["link", "applied_via"] as const) {
    const link = d[key]?.trim();
    if (link && !toWebLink(link)) return `The ${LINK_LABEL[key]} link should be a web link, like https://jobs.example/1`;
  }
  return null;
}

/** The add-role form: the details, and the posting's text when it was read or pasted. */
export type NewRoleDraft = Omit<RoleDraft, "applied_via"> & { location?: string; comp?: string; posting?: string };

/** The request for POST /roles: company and title trimmed, the rest only when there is some. */
export function toNewRole(d: NewRoleDraft): NewRole {
  const optional = Object.entries({ link: d.link, location: d.location, comp: d.comp, posting: d.posting })
    .map(([key, value]) => [key, value?.trim()] as const)
    .filter(([, value]) => value);
  return { company: d.company.trim(), title: d.title.trim(), ...Object.fromEntries(optional) };
}

/** "1,234": how many words, for a posting's fold. */
export const wordCount = (text: string) => text.split(/\s+/).filter(Boolean).length.toLocaleString();

const FILLED = ["company", "title", "location", "comp", "posting"] as const;

/** The form after reading the posting. A field takes what the posting gives when it is empty or
 * still holds what the last read (last) put there; what you typed yourself is kept. A field the
 * last read filled and this one does not is emptied: it came from another posting. */
export function fillFromPosting<D extends NewRoleDraft>(d: D, read: PostingDraft, last?: PostingDraft): D {
  const next = { ...d };
  for (const key of FILLED) {
    const now = d[key] ?? "";
    if (now === "" || (last && now === (last[key] ?? ""))) next[key] = read[key] ?? "";
  }
  return next;
}

// ── Todos ────────────────────────────────────────────────────────────────────

/** When a todo is due, in words: "today", "tomorrow", "Oct 20", with the year only when it is
 *  not this one. Past days are overdue. Null with no day. */
export function due(day: string | null, today: string): { label: string; overdue: boolean } | null {
  if (!day) return null;
  const days = daysBetween(today, day);
  if (days === 0) return { label: "today", overdue: false };
  if (days === 1) return { label: "tomorrow", overdue: false };
  const [y, m, d] = day.split("-");
  const label = `${MONTHS[Number(m) - 1]} ${Number(d)}${y === today.slice(0, 4) ? "" : `, ${y}`}`;
  return { label, overdue: days < 0 };
}

/** Open and done, each in the order the API gives. */
export const splitTodos = (todos: Todo[]) => ({
  open: todos.filter((t) => !t.done_on),
  done: todos.filter((t) => t.done_on),
});

/** The list as it will be once the writer checks one off (today, or the day it was already
 *  done) or opens it: shown at once, before the save comes back. */
export const withDone = (todos: Todo[], id: number, done: boolean, today: string): Todo[] =>
  todos.map((t) => (t.id === id ? { ...t, done_on: done ? (t.done_on ?? today) : null } : t));

/** How the board's todo list can be grouped. */
export const TODO_GROUPS = [
  { id: "due", label: "Due" },
  { id: "type", label: "Type" },
  { id: "role", label: "Role" },
] as const;
export type TodoGroup = (typeof TODO_GROUPS)[number]["id"];

/** Days ahead that count as this week. */
const WEEK = 7;

const DUE_GROUPS = ["Overdue", "Today", "This week", "Later", "No day"] as const;

function dueGroup(day: string | null, today: string): (typeof DUE_GROUPS)[number] {
  if (!day) return "No day";
  const days = daysBetween(today, day);
  return days < 0 ? "Overdue" : days === 0 ? "Today" : days <= WEEK ? "This week" : "Later";
}

/** What groupTodos needs of a todo. */
type Groupable = Pick<OpenTodo, "kind" | "due_on"> & { role?: OpenTodo["role"] };

const roleLabel = (t: Groupable) => (t.role ? `${t.role.company} · ${t.role.title}` : "No role");

/** The open todos in groups, each keeping the API's order (soonest due first); empty groups are
 *  left out. By due day; by type, in TODO_KINDS order; or by role, in the order each first comes
 *  due, with todos for no role last. */
export function groupTodos<T extends Groupable>(todos: T[], by: TodoGroup, today: string): { label: string; todos: T[] }[] {
  const keyOf = { due: (t: T) => dueGroup(t.due_on, today), type: (t: T) => TODO_KIND_LABEL[t.kind], role: roleLabel }[by];
  const order: string[] =
    by === "due"
      ? [...DUE_GROUPS]
      : by === "type"
        ? TODO_KINDS.map((k) => TODO_KIND_LABEL[k])
        : [...new Set(todos.filter((t) => t.role).map(roleLabel)), "No role"];
  return order.map((label) => ({ label, todos: todos.filter((t) => keyOf(t) === label) })).filter((g) => g.todos.length > 0);
}

// ── Drafts ───────────────────────────────────────────────────────────────────

type Approvals = Pick<RoleDetail, "approved_resume_draft" | "approved_cover_letter">;

export const isApproved = (d: Draft, role: Approvals) => role[APPROVAL_FIELD[d.kind]] === d.name;

/** "Cover letter 2 · Oct 17 · Approved", as the drafts picker lists it: short, to fit a phone. */
export const draftLabel = (d: Draft, role: Approvals) =>
  [`${DRAFT_KIND_LABEL[d.kind]} ${d.number}`, monthDayLabel(d.modified), ...(isApproved(d, role) ? ["Approved"] : [])].join(" · ");

/** The draft to show first: the one changed last; at the same moment, the first in the API's order. */
export const latestDraft = (drafts: Draft[]): Draft | null =>
  drafts.reduce<Draft | null>((best, d) => (!best || d.modified_at > best.modified_at ? d : best), null);

export const DRAFT_VIEWS = ["pdf", "text"] as const;
export type DraftView = (typeof DRAFT_VIEWS)[number];

/** What the picked view shows: the PDF, the way to make it when there is none yet, or the text. */
export const draftShows = (view: DraftView, hasPdf: boolean): "pdf" | "make-pdf" | "text" =>
  view === "text" ? "text" : hasPdf ? "pdf" : "make-pdf";

/** "1 page", "2 pages". */
export const pagesLabel = (pages: number) => `${pages} ${pages === 1 ? "page" : "pages"}`;
