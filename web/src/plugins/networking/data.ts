import { getJSON, send } from "@shell/api";
import type { Covered } from "@shell/fields";

// Shape of GET /api/networking/people and /api/networking/people/{id} (api/networking.py).
// Dates are YYYY-MM-DD.

// The two fixed lists match the CHECKs in tools/networking/schema.sql (networking.test.ts holds
// them to it). Order here is legend and menu order; colors and labels are in style.ts.

export const KINDS = ["call", "video", "coffee", "event", "message", "email"] as const;
export type Kind = (typeof KINDS)[number];

/** What you do next. */
export const NEXT_STEPS = ["follow-up", "reach-out", "catch-up", "send-resume", "ask-intro", "schedule", "share-work"] as const;
export type NextStep = (typeof NEXT_STEPS)[number];

/** One person as the phonebook and the timeline see them. */
export interface Person {
  id: string;
  name: string;
  company: string | null;
  role: string | null;
  location: string | null;
  tags: string[];
  /** Oldest first. */
  interactions: { date: string; kind: Kind }[];
  /** The open next step: the one on their latest interaction. */
  next_step: NextStep | null;
}

export interface Interaction {
  id: number;
  /** Moves on with every change; an edit sends it back, so one from an older copy is refused. */
  version: number;
  date: string;
  kind: Kind;
  title: string | null;
  summary: string | null;
  /** Your own words after the talk, as you typed them. */
  notes: string | null;
  next_step: NextStep | null;
  /** Only when they agreed to be recorded. */
  transcript: string | null;
}

export interface PersonDetail extends Omit<Person, "interactions"> {
  /** Moves on with every change; an edit sends it back, so one from an older copy is refused. */
  version: number;
  met_how: string | null;
  met_on: string | null;
  linkedin: string | null;
  email: string | null;
  phone: string | null;
  /** The website of their company, when one is on file. */
  company_website: string | null;
  about: string | null;
  /** Newest first. */
  interactions: Interaction[];
}

export const fetchPeople = (signal?: AbortSignal) =>
  getJSON<{ people: Person[] }>("/api/networking/people", signal).then((r) => r.people);

export const fetchPerson = (id: string, signal?: AbortSignal) =>
  getJSON<PersonDetail>(`/api/networking/people/${encodeURIComponent(id)}`, signal);

// ── Writing: /api/networking/write (tools/networking/writer.py) ──
// A talk is with someone in the phonebook (person_id) or someone new (person), never a guess
// between them. The writer makes a new person's id from their name and returns it. An edit sends
// the version it was made from, so one over a newer change made elsewhere is refused.

/** The fields each change sends, by the writer's request body in tools/networking/fields.json.
 * networking.test.ts holds each list to that file; Covered, below, holds each change type to its list. */
export const SENDS = {
  NewPerson: ["name", "tags", "company", "role", "met_how", "met_on", "location", "phone", "email", "linkedin", "about"],
  PersonEdit: ["name", "tags", "company", "role", "met_how", "met_on", "location", "phone", "email", "linkedin", "about", "version"],
  Conversation: ["person_id", "person", "date", "kind", "title", "notes", "next_step"],
  TalkEdit: ["date", "kind", "title", "summary", "notes", "next_step", "version"],
} as const;

const WRITE = "/api/networking/write";

/** Someone new: the name, and any of their details. */
export type NewPerson = { name: string; tags?: string[] } & Partial<Record<PersonField, string>>;

type PersonField = "company" | "role" | "met_how" | "met_on" | "location" | "phone" | "email" | "linkedin" | "about";

/** Only the fields sent change; null clears one; tags replace theirs. */
export type PersonEdit = Partial<Record<PersonField | "name", string | null>> & { tags?: string[] };

/** Unset, it is a call, today. */
export type Conversation = {
  date?: string;
  kind?: Kind;
  title?: string;
  /** Your brain flush, kept as typed. */
  notes?: string;
  next_step?: NextStep;
} & ({ person_id: string; person?: never } | { person: NewPerson; person_id?: never });

export const logConversation = (talk: Conversation) =>
  send<{ person_id: string; interaction_id: number }>(`${WRITE}/interactions`, "POST", talk);

const person = (id: string) => `${WRITE}/people/${encodeURIComponent(id)}`;

export const editPerson = (id: string, changes: PersonEdit, version: number) =>
  send<{ person_id: string }>(person(id), "PATCH", { ...changes, version });

/** Hidden with their talks, with undo: restorePerson brings them back. */
export const deletePerson = (id: string) => send<{ person_id: string }>(person(id), "DELETE");

export const restorePerson = (id: string) => send<{ person_id: string }>(`${person(id)}/restore`, "POST");

/** Only the fields sent change; null clears one. date and kind cannot be cleared. */
export type TalkEdit = Partial<Record<"date" | "kind" | "title" | "summary" | "notes" | "next_step", string | null>>;

export const editInteraction = (id: number, changes: TalkEdit, version: number) =>
  send<{ person_id: string; interaction_id: number }>(`${WRITE}/interactions/${id}`, "PATCH", { ...changes, version });

/** Hidden, with undo: restoreInteraction brings it back. */
export const deleteInteraction = (id: number) => send<{ person_id: string; interaction_id: number }>(`${WRITE}/interactions/${id}`, "DELETE");

export const restoreInteraction = (id: number) =>
  send<{ person_id: string; interaction_id: number }>(`${WRITE}/interactions/${id}/restore`, "POST");

/** Someone added with no talk. */
export const addPerson = (who: NewPerson) => send<{ person_id: string }>(`${WRITE}/people`, "POST", who);

// Every change type sends only fields in its SENDS list.
true satisfies Covered<NewPerson, typeof SENDS.NewPerson>;
true satisfies Covered<PersonEdit & { version: number }, typeof SENDS.PersonEdit>;
true satisfies Covered<Conversation, typeof SENDS.Conversation>;
true satisfies Covered<TalkEdit & { version: number }, typeof SENDS.TalkEdit>;
