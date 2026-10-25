import { changedFields } from "@shell/edits";
import type { Conversation, Kind, NewPerson, NextStep, Person, PersonEdit } from "./data";
import { byRecent } from "./networking";

// Logging a talk: finding who it was with, and turning the form into what the
// networking writer takes. Nothing is guessed: you pick someone in the phonebook or adds
// someone new by name, and the writer makes the new person's id.

/** A person's details, in form order, with the input that fits each (the phone keyboard
 *  follows the type). Adding someone and editing them use the same list. */
export const PERSON_FIELDS = [
  { key: "company", label: "Company" },
  { key: "role", label: "Role" },
  { key: "met_how", label: "How you met" },
  { key: "met_on", label: "Met on", type: "date" },
  { key: "location", label: "Based in" },
  { key: "phone", label: "Phone", type: "tel" },
  { key: "email", label: "Email", type: "email" },
  { key: "linkedin", label: "LinkedIn", type: "url" },
  { key: "about", label: "About", type: "textarea" },
] as const satisfies readonly {
  key: Exclude<keyof NewPerson, "name" | "tags">;
  label: string;
  type?: "date" | "tel" | "email" | "url" | "textarea";
}[];

/** Someone to add, as the form holds them. */
export type NewWho = { name: string; details: Omit<NewPerson, "name" | "tags">; tags: string[] };

/** Someone in the phonebook, or someone to add. */
export type Who = { id: string } | NewWho;

/** The form as typed. Blank fields are "" until toConversation drops them. */
export interface Draft {
  who: Who | null;
  kind: Kind;
  date: string;
  title: string;
  /** Your brain flush, sent as typed apart from blank lines at the ends. */
  notes: string;
  next_step: NextStep | "";
}

/** A call, today, with no one picked yet. */
export const emptyDraft = (today: string, who: Who | null = null): Draft => ({
  who,
  kind: "call",
  date: today,
  title: "",
  notes: "",
  next_step: "",
});

/** Lowercase, without accents, one space between words: "  Zoë  O'Brien" -> "zoe o'brien". */
const fold = (s: string) =>
  s.normalize("NFKD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim().replace(/\s+/g, " ");

/** 0: the name starts with the query; 1: a word in it does; 2: the name, company or id has it. */
function rank(p: Person, q: string): number | null {
  const name = fold(p.name);
  if (name.startsWith(q)) return 0;
  if (name.split(/[\s-]+/).some((word) => word.startsWith(q))) return 1;
  if ([name, fold(p.company ?? ""), p.id].some((s) => s.includes(q))) return 2;
  return null;
}

/** The people to offer for what you have typed, best match first and most recent within a
 *  rank. With nothing typed, whoever you talked to most recently. */
export function personOptions(people: Person[], query: string, limit = 6): Person[] {
  const q = fold(query);
  if (!q) return [...people].sort(byRecent).slice(0, limit);
  return people
    .map((p) => ({ p, r: rank(p, q) }))
    .filter((x): x is { p: Person; r: number } => x.r != null)
    .sort((a, b) => a.r - b.r || byRecent(a.p, b.p))
    .slice(0, limit)
    .map((x) => x.p);
}

// ── Tags for someone new ─────────────────────────────────────────────────────

/** The writer's limits (writer.PersonDetails). */
export const MAX_TAGS = 20;
const MAX_TAG_LENGTH = 50;

/** One space between words, none at the ends. */
const tidy = (tag: string) => tag.trim().replace(/\s+/g, " ");

/** Picked, it is dropped; not picked, it is added at the end. */
export const toggleTag = (tags: string[], tag: string) => (tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag]);

/** What stops a typed tag from being added, or null. */
export function tagProblem(typed: string, tags: string[]): string | null {
  if (tidy(typed).length > MAX_TAG_LENGTH) return `A tag is at most ${MAX_TAG_LENGTH} characters.`;
  if (tags.length >= MAX_TAGS) return `At most ${MAX_TAGS} tags.`;
  return null;
}

/** Adds what you typed. A tag you already have, in any case, is used as you first spelled it,
 *  so "Warm" picks "warm". A blank, or one already picked, changes nothing. */
export function addTag(tags: string[], typed: string, known: string[]): string[] {
  const tag = tidy(typed);
  if (!tag) return tags;
  const same = (t: string) => t.toLowerCase() === tag.toLowerCase();
  if (tags.some(same)) return tags;
  return [...tags, known.find(same) ?? tag];
}

/** What still stops the save, in your words, or null when it can be sent. */
export function saveProblem(d: Draft): string | null {
  if (d.who == null) return "Pick who it was with.";
  if ("name" in d.who && !d.who.name.trim()) return "Give the new person a name.";
  if (!d.date) return "Pick the day you talked.";
  return null;
}

/** Only the fields with something in them, trimmed. */
function filled<K extends string>(fields: Partial<Record<K, string>>): Partial<Record<K, string>> {
  return Object.fromEntries(
    Object.entries(fields as Record<string, string>)
      .map(([k, v]) => [k, v.trim()])
      .filter(([, v]) => v),
  ) as Partial<Record<K, string>>;
}

/** Someone new as the writer takes them, for POST /people or inside a talk. */
export function toNewPerson(who: NewWho): NewPerson {
  const name = who.name.trim();
  if (!name) throw new Error("Give the new person a name.");
  return { name, ...filled(who.details), ...(who.tags.length ? { tags: who.tags } : {}) };
}

/** The request for PATCH /people/{id}: only what changed against saved, a cleared field as
 *  null, and the tags when they are not the same set. */
export function personChanges(
  who: NewWho,
  saved: Partial<Record<keyof NewWho["details"] | "name", string | null>> & { tags: string[] },
): PersonEdit {
  if (!who.name.trim()) throw new Error("Give them a name.");
  const { tags, ...fields } = saved;
  const changes = changedFields({ name: who.name, ...who.details }, fields);
  const sameTags = who.tags.length === tags.length && who.tags.every((t) => tags.includes(t));
  return sameTags ? changes : { ...changes, tags: who.tags };
}

/** The request for POST /interactions. Throws on a draft saveProblem would stop. */
export function toConversation(d: Draft): Conversation {
  const problem = saveProblem(d);
  if (problem) throw new Error(problem);
  const who = d.who!;
  const person = "id" in who ? { person_id: who.id } : { person: toNewPerson(who) };
  return {
    ...person,
    kind: d.kind,
    date: d.date,
    ...filled({ title: d.title, notes: d.notes }),
    ...(d.next_step ? { next_step: d.next_step } : {}),
  };
}
