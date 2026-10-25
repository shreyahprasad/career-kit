import { getJSON, send } from "@shell/api";
import type { Covered } from "@shell/fields";

// Shape of GET /api/career/roles and /api/career/roles/{id} (api/career.py). Dates are YYYY-MM-DD.

// The two fixed lists match the CHECKs in tools/career/schema.sql (career.test.ts holds them to
// it). Order here is column and menu order; labels are in style.ts.

export const STATUSES = ["interested", "applied", "screen", "interviews", "offer", "rejected"] as const;
export type Status = (typeof STATUSES)[number];

export const KINDS = ["applied", "recruiter-call", "interview", "offer", "rejection", "note"] as const;
export type Kind = (typeof KINDS)[number];

/** The sorts of todo, which color it and group the same work. */
export const TODO_KINDS = ["resume", "apply", "outreach", "prep", "follow-up", "other"] as const;
export type TodoKind = (typeof TODO_KINDS)[number];

/** One role as the board sees it. */
export interface Role {
  id: string;
  company: string;
  title: string;
  location: string | null;
  comp: string | null;
  status: Status;
  /** The day of its first applied event. */
  applied_on: string | null;
  last_event: { date: string; kind: Kind } | null;
  todos: { done: number; total: number };
  /** The first open todo, in the API's order. */
  next_todo: Pick<Todo, "id" | "text" | "kind" | "due_on"> | null;
}

export interface Todo {
  id: number;
  text: string;
  kind: TodoKind;
  due_on: string | null;
  /** The day it was checked off; null while it is still to do. */
  done_on: string | null;
}

/** An open todo across all roles; role is null for one about your search as a whole. */
export interface OpenTodo extends Omit<Todo, "done_on"> {
  role: { id: string; company: string; title: string } | null;
}

export interface RoleEvent {
  id: number;
  /** Moves on with every change; an edit sends it back, so one from an older copy is refused. */
  version: number;
  date: string;
  kind: Kind;
  text: string | null;
  /** Where your prep for it lives: a link or a path. */
  prep_link: string | null;
}

export interface RoleDetail extends Omit<Role, "applied_on" | "last_event" | "todos" | "next_todo"> {
  /** Moves on with every change; an edit sends it back, so one from an older copy is refused. */
  version: number;
  /** The posting. */
  link: string | null;
  /** Where you applied, when it is not the posting. */
  applied_via: string | null;
  notes: string | null;
  /** A person in networking; name is null when they are not there. */
  referral: { id: string; name: string | null } | null;
  /** The PDF in data/resumes you mean to send. */
  resume_file: string | null;
  /** The copy of it kept when you applied, in data/sent. */
  sent_file: string | null;
  /** The drafts in data/drafts/<role> you approved, by name. */
  approved_resume_draft: string | null;
  approved_cover_letter: string | null;
  /** The copy of the approved letter kept when you applied, in data/sent. */
  sent_cover_letter: string | null;
  /** Whether its PDF was kept beside it (not for a letter sent before PDFs were made). */
  sent_cover_letter_pdf: boolean;
  /** The posting's text, read from its link or pasted, and the day it was saved. */
  posting: string | null;
  posting_on: string | null;
  /** What stands out in it, in your words, one per line. */
  notable: string | null;
  /** Newest first. */
  events: RoleEvent[];
  /** Open first, soonest due first; then done, latest first. */
  todos: Todo[];
}

export const fetchRoles = (signal?: AbortSignal) =>
  getJSON<{ roles: Role[] }>("/api/career/roles", signal).then((r) => r.roles);

export const fetchRole = (id: string, signal?: AbortSignal) =>
  getJSON<RoleDetail>(`/api/career/roles/${encodeURIComponent(id)}`, signal);

/** Every open todo, soonest due first, leaving out rejected roles. */
export const fetchTodos = (signal?: AbortSignal) =>
  getJSON<{ todos: OpenTodo[] }>("/api/career/todos", signal).then((r) => r.todos);

/** A PDF in data/resumes, and the day it last changed. */
export interface Resume {
  name: string;
  modified: string;
}

/** The PDFs you can pick, last changed first. */
export const fetchResumes = (signal?: AbortSignal) =>
  getJSON<{ resumes: Resume[] }>("/api/career/resumes", signal).then((r) => r.resumes);

export const resumeURL = (name: string) => `/api/career/resumes/${encodeURIComponent(name)}`;

export const sentURL = (name: string) => `/api/career/sent/${encodeURIComponent(name)}`;

export const DRAFT_KINDS = ["resume", "cover-letter"] as const;
export type DraftKind = (typeof DRAFT_KINDS)[number];

/** A draft Claude wrote for a role in data/drafts/<role>: resume-2.md is the resume, number 2. */
export interface Draft {
  name: string;
  kind: DraftKind;
  number: number;
  /** The day it last changed, and the day and time, to tell which was written last. */
  modified: string;
  modified_at: string;
  /** Whether its PDF is there, made since the draft last changed. */
  pdf: boolean;
}

/** Resumes first, then letters, newest first in each. */
export const fetchDrafts = (roleId: string, signal?: AbortSignal) =>
  getJSON<{ drafts: Draft[] }>(`/api/career/roles/${encodeURIComponent(roleId)}/drafts`, signal).then((r) => r.drafts);

export const fetchDraftText = (roleId: string, name: string, signal?: AbortSignal) =>
  getJSON<{ text: string }>(`/api/career/roles/${encodeURIComponent(roleId)}/drafts/${encodeURIComponent(name)}`, signal).then((r) => r.text);

/** The PDF the writer made of a draft. */
export const draftPdfURL = (roleId: string, name: string) =>
  `/api/career/roles/${encodeURIComponent(roleId)}/drafts/${encodeURIComponent(pdfName(name))}`;

/** A draft's PDF, or the kept letter's: the same name ending in .pdf. */
export const pdfName = (name: string) => name.replace(/\.md$/, ".pdf");

/** The copy of the approved letter kept when you applied. */
export const fetchSentLetter = (name: string, signal?: AbortSignal) =>
  getJSON<{ text: string }>(`/api/career/sent-letters/${encodeURIComponent(name)}`, signal).then((r) => r.text);

type RoleName = { id: string; company: string; title: string };

/** What undo can still bring back, latest deleted first (GET /api/career/deleted). What went with
 * a deleted role comes back with it, so it is not listed apart. */
export interface Deleted {
  roles: (RoleName & { deleted_on: string })[];
  events: { id: number; date: string; kind: Kind; role: RoleName; deleted_on: string }[];
  todos: { id: number; text: string; role: RoleName | null; deleted_on: string }[];
}

export const fetchDeleted = (signal?: AbortSignal) => getJSON<Deleted>("/api/career/deleted", signal);

// ── Changes: /api/career/write (tools/career/writer.py) ─────────────────────
// Forms that edit free text from what was loaded (details, notes, status, an event) send its
// version, so a save over a newer change made elsewhere is refused. One-tap choices (referral,
// resume, a todo's check, day or kind) set one field to a value you just picked, so they send none.

/** The fields each change sends, by the writer's request body in tools/career/fields.json.
 * career.test.ts holds each list to that file; Covered, below, holds each change type to its list. */
export const SENDS = {
  PostingLink: ["link"],
  NewRole: ["company", "title", "link", "location", "comp", "posting"],
  RoleEdit: [
    "company", "title", "location", "comp", "link", "applied_via", "notes", "referral_person_id", "resume_file", "posting", "notable",
    "approved_resume_draft", "approved_cover_letter", "version",
  ],
  StatusChange: ["status", "date", "text", "version"],
  NewEvent: ["kind", "date", "text", "prep_link"],
  EventEdit: ["date", "kind", "text", "prep_link", "version"],
  NewTodo: ["text", "kind", "due_on", "role_id"],
  TodoEdit: ["done", "text", "kind", "due_on"],
} as const;

const WRITE = "/api/career/write";
const role = (id: string) => `${WRITE}/roles/${encodeURIComponent(id)}`;

/** A new role: only company and title are needed. It starts as interested, with its starter todos. */
export type NewRole = { company: string; title: string; link?: string; location?: string; comp?: string; posting?: string };

/** What reading a posting found (tools/career/posting.py). from: the job feed, the page's job data,
 * or only the page's title and text. */
export interface PostingDraft {
  company: string | null;
  title: string | null;
  location: string | null;
  comp: string | null;
  posting: string;
  from: "feed" | "page data" | "page";
}

/** Reads the posting at link for the add-role form. Nothing is saved; a page that cannot be read
 * is refused with why, and what to do instead. */
export const readPosting = (link: string) => send<PostingDraft>(`${WRITE}/postings/read`, "POST", { link } satisfies { link: string });

export const addRole = (r: NewRole) => send<{ role_id: string }>(`${WRITE}/roles`, "POST", r);

/** The details a role's edit form changes; null clears one. */
export type RoleChanges = Partial<Record<"company" | "title" | "location" | "comp" | "link" | "applied_via", string | null>>;

/** Everything a role's PATCH can carry. */
type RoleEdit = RoleChanges &
  Partial<Record<"notes" | "referral_person_id" | "resume_file" | "posting" | "notable" | ApprovalField, string | null>> & { version?: number };

export const editRole = (id: string, changes: RoleChanges, version: number) =>
  send<{ role_id: string }>(role(id), "PATCH", { ...changes, version } satisfies RoleEdit);

/** Hidden with its timeline and todos, with undo: restoreRole brings it all back. */
export const deleteRole = (id: string) => send<{ role_id: string }>(role(id), "DELETE");

export const restoreRole = (id: string) => send<{ role_id: string }>(`${role(id)}/restore`, "POST");

/** Unset, the date is today. text goes on the event the status logs (statusEvent). */
export type StatusChange = { status: Status; date?: string; text?: string; version: number };

export const setStatus = (id: string, change: StatusChange) =>
  send<{ role_id: string; event_id: number | null }>(`${role(id)}/status`, "POST", change);

/** Unset, the date is today. */
export type NewEvent = { kind: Kind; date?: string; text?: string; prep_link?: string };

export const addEvent = (id: string, event: NewEvent) =>
  send<{ role_id: string; event_id: number }>(`${role(id)}/events`, "POST", event);

/** Only the fields sent change; null clears text or prep_link. date and kind cannot be cleared. */
export type EventChanges = Partial<Record<"date" | "kind" | "text" | "prep_link", string | null>>;

export const editEvent = (eventId: number, changes: EventChanges, version: number) =>
  send<{ role_id: string; event_id: number }>(`${WRITE}/events/${eventId}`, "PATCH", { ...changes, version });

/** Hidden, with undo: restoreEvent brings it back. */
export const deleteEvent = (eventId: number) => send<{ role_id: string; event_id: number }>(`${WRITE}/events/${eventId}`, "DELETE");

export const restoreEvent = (eventId: number) =>
  send<{ role_id: string; event_id: number }>(`${WRITE}/events/${eventId}/restore`, "POST");

/** Your notes, or what stands out in the posting: free text, saved as none when blank. */
export const saveText = (id: string, field: "notes" | "notable", text: string, version: number) =>
  send<{ role_id: string }>(role(id), "PATCH", { [field]: text, version } satisfies RoleEdit);

/** The posting's text, read or pasted, or null to clear it. The writer keeps the day. */
export const savePosting = (id: string, text: string | null) =>
  send<{ role_id: string }>(role(id), "PATCH", { posting: text } satisfies RoleEdit);

/** A PDF in data/resumes, or null for none. Applying keeps a copy of it. */
export const setResume = (id: string, name: string | null) =>
  send<{ role_id: string }>(role(id), "PATCH", { resume_file: name } satisfies RoleEdit);

/** The role's field that holds the approved draft of each kind. */
export const APPROVAL_FIELD = { resume: "approved_resume_draft", "cover-letter": "approved_cover_letter" } as const satisfies Record<DraftKind, string>;
type ApprovalField = (typeof APPROVAL_FIELD)[DraftKind];

/** Approves the draft of its kind, replacing the one approved before, or null for none. Approving
 * checks off its review todo, and a resume's PDF becomes the role's resume; applying keeps a copy
 * of the approved letter. */
export const approveDraft = (id: string, kind: DraftKind, name: string | null) =>
  send<{ role_id: string }>(role(id), "PATCH", { [APPROVAL_FIELD[kind]]: name } satisfies RoleEdit);

/** Makes the PDF of a draft, beside it, replacing an older one. Claude's skills do this after
 * writing a draft; this is for one written before, or changed by hand. */
export const makeDraftPdf = (id: string, name: string) =>
  send<{ role_id: string; name: string; pages: number }>(`${role(id)}/drafts/${encodeURIComponent(name)}/pdf`, "POST");

/** A person in networking, or null for no one. */
export const setReferral = (id: string, personId: string | null) =>
  send<{ role_id: string }>(role(id), "PATCH", { referral_person_id: personId } satisfies RoleEdit);

type NewTodo = { text: string; kind?: TodoKind; due_on?: string; role_id?: string };

/** A todo for roleId, or for no role when it is null. Unset, it is "other" with no day. */
export const addTodo = (roleId: string | null, todo: Omit<NewTodo, "role_id">) =>
  send<{ todo_id: number }>(`${WRITE}/todos`, "POST", { ...todo, ...(roleId ? { role_id: roleId } : {}) } satisfies NewTodo);

const todo = (id: number) => `${WRITE}/todos/${id}`;

type TodoEdit = { done?: boolean; text?: string; kind?: TodoKind; due_on?: string | null };

/** Checks it off or opens it, or fixes its text, kind or day (null clears the day). */
export const editTodo = (id: number, change: TodoEdit) => send<{ todo_id: number }>(todo(id), "PATCH", change);

/** Hidden, with undo: restoreTodo brings it back. */
export const deleteTodo = (id: number) => send<{ todo_id: number }>(todo(id), "DELETE");

export const restoreTodo = (id: number) => send<{ todo_id: number }>(`${todo(id)}/restore`, "POST");

// Every change type sends only fields in its SENDS list.
true satisfies Covered<{ link: string }, typeof SENDS.PostingLink>;
true satisfies Covered<NewRole, typeof SENDS.NewRole>;
true satisfies Covered<RoleEdit, typeof SENDS.RoleEdit>;
true satisfies Covered<StatusChange, typeof SENDS.StatusChange>;
true satisfies Covered<NewEvent, typeof SENDS.NewEvent>;
true satisfies Covered<EventChanges & { version: number }, typeof SENDS.EventEdit>;
true satisfies Covered<NewTodo, typeof SENDS.NewTodo>;
true satisfies Covered<TodoEdit, typeof SENDS.TodoEdit>;
