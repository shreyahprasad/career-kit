// Date, filter and grouping rules for the networking page. Dates are YYYY-MM-DD strings
// (shell/dates.ts); "today" is always passed in.

import type { NextStep, Person } from "./data";
import { dayNumber, daysBetween, MONTHS } from "@shell/dates";
import { RECENCY, RECENT_GROUPS, type Sort } from "./style";

// The shared date helpers, named here too: the page and its tests use them from this file.
export { agoLabel, dateLabel, daysBetween, todayISO } from "@shell/dates";

/** The date of the most recent interaction, or null if they have not talked yet. */
const lastTalked = (p: Person) => p.interactions.at(-1)?.date ?? null;

/** Days since the last interaction, or null if they have not talked yet. */
export function daysSince(p: Person, today: string): number | null {
  const last = lastTalked(p);
  return last == null ? null : daysBetween(last, today);
}

/** "2026-06" -> "Jun"; with the year when asked, "Jun 2026". */
export function monthLabel(month: string, withYear = false): string {
  const [y, m] = month.split("-");
  return withYear ? `${MONTHS[Number(m) - 1]} ${y}` : MONTHS[Number(m) - 1];
}

// ── Filters ─────────────────────────────────────────────────────────────────

export interface Filters {
  query: string;
  company: string | null;
  /** A person must have every one of these. */
  tags: string[];
  recency: number; // index into RECENCY
  /** Their open next step: one action, "any" for anyone with one open, or null for no filter. */
  next: NextStep | "any" | null;
}

export const NO_FILTERS: Filters = { query: "", company: null, tags: [], recency: 0, next: null };

export const isFiltered = (f: Filters) =>
  f.query.trim() !== "" || f.company != null || f.tags.length > 0 || f.recency !== 0 || f.next != null;

/** How many filters are on under the Filters fold (search stays out, in view): one per tag. */
export const foldedFilterCount = (f: Filters) =>
  f.tags.length + Number(f.company != null) + Number(f.recency !== 0) + Number(f.next != null);

/** Whether the phonebook shows its list. A search or filter going on opens it and clearing them
 *  folds it; otherwise it stays as you left it, so you can fold it mid-search. */
export const listOpen = ({ wasFiltered, filtered, expanded }: { wasFiltered: boolean; filtered: boolean; expanded: boolean }) =>
  wasFiltered !== filtered ? filtered : expanded;

export function matches(p: Person, f: Filters, today: string): boolean {
  const q = f.query.trim().toLowerCase();
  if (q && ![p.name, p.company, p.role, p.location, ...p.tags].some((s) => s?.toLowerCase().includes(q))) return false;
  if (f.company != null && p.company !== f.company) return false;
  if (!f.tags.every((t) => p.tags.includes(t))) return false;
  const { within, over } = RECENCY[f.recency];
  const days = daysSince(p, today);
  if (within != null && (days == null || days > within)) return false;
  if (over != null && days != null && days <= over) return false;
  if (f.next === "any") return p.next_step != null;
  if (f.next != null) return p.next_step === f.next;
  return true;
}

const byName = (a: Person, b: Person) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" });

/** Every company, A–Z. */
export function companies(people: Person[]): string[] {
  return [...new Set(people.flatMap((p) => (p.company ? [p.company] : [])))].sort((a, b) => a.localeCompare(b));
}

/** Every tag, most used first, then A–Z. */
export function allTags(people: Person[]): string[] {
  const counts = new Map<string, number>();
  for (const t of people.flatMap((p) => p.tags)) counts.set(t, (counts.get(t) ?? 0) + 1);
  return [...counts].sort(([a, x], [b, y]) => y - x || a.localeCompare(b)).map(([t]) => t);
}

// ── Phonebook groups ────────────────────────────────────────────────────────

export interface Group {
  label: string;
  people: Person[];
}

/** The phonebook letter: the name's first letter, or "#" when it does not start with one. */
export function letterOf(name: string): string {
  const first = name.trim().charAt(0).toUpperCase();
  return /[A-Z]/.test(first) ? first : "#";
}

function groupBy(people: Person[], key: (p: Person) => string): Group[] {
  const groups = new Map<string, Person[]>();
  for (const p of people) {
    const k = key(p);
    const group = groups.get(k);
    if (group) group.push(p);
    else groups.set(k, [p]);
  }
  return [...groups].map(([label, people]) => ({ label, people }));
}

export const NO_COMPANY = "No company";
export const NOT_YET = "Not talked yet";

/**
 * name: by letter, A–Z. company: by company A–Z, people by name inside, no company last.
 * recent: newest first, in RECENT_GROUPS buckets, anyone not talked to yet last.
 */
export function groupPeople(people: Person[], sort: Sort, today: string): Group[] {
  if (sort === "name") return groupBy([...people].sort(byName), (p) => letterOf(p.name));
  if (sort === "company") {
    const sorted = [...people].sort(
      (a, b) => Number(!a.company) - Number(!b.company) || (a.company ?? "").localeCompare(b.company ?? "") || byName(a, b),
    );
    return groupBy(sorted, (p) => p.company ?? NO_COMPANY);
  }
  const days = (p: Person) => daysSince(p, today) ?? Infinity;
  const sorted = [...people].sort((a, b) => days(a) - days(b) || byName(a, b));
  return groupBy(sorted, (p) => {
    const d = daysSince(p, today);
    return d == null ? NOT_YET : RECENT_GROUPS.find((g) => d < g.under)!.label;
  });
}

/** Which group is being read in a scrolled list, given where each group starts (in order)
 *  and how far the list is scrolled: the last one whose start has reached the top. */
export function currentGroup(tops: number[], scrollTop: number): number {
  if (tops.length === 0) return -1;
  let i = 0;
  while (i + 1 < tops.length && tops[i + 1] <= scrollTop) i++;
  return i;
}

// ── Timeline ────────────────────────────────────────────────────────────────

/** "2026-06" plus `n` months, either way. */
export function addMonths(month: string, n: number): string {
  const [y, m] = month.split("-").map(Number);
  const i = y * 12 + (m - 1) + n;
  return `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`;
}

/** Months from `first` through `last`, oldest first. */
export function monthRange(first: string, last: string): string[] {
  const out: string[] = [];
  for (let m = first; m <= last; m = addMonths(m, 1)) out.push(m);
  return out;
}

/** The months the timeline shows, ending with this month: the last `count`, or (null) back
 *  to the month of the first interaction among `people`. */
export function timelineMonths(people: Person[], count: number | null, today: string): string[] {
  const now = today.slice(0, 7);
  if (count != null) return monthRange(addMonths(now, 1 - count), now);
  const first = people.flatMap((p) => p.interactions.map((i) => i.date.slice(0, 7))).sort()[0];
  return monthRange(first && first < now ? first : now, now);
}

/** Where `date` falls across `months`, 0 at the first day of the first month and 1 at the end
 *  of the last; null when outside them. */
export function position(date: string, months: string[]): number | null {
  const start = dayNumber(`${months[0]}-01`);
  const end = dayNumber(`${addMonths(months.at(-1)!, 1)}-01`);
  const day = dayNumber(date);
  return day < start || day >= end ? null : (day - start + 0.5) / (end - start);
}

/** Most recently talked to first, then anyone not talked to yet; A–Z within a day. */
export const byRecent = (a: Person, b: Person) => (lastTalked(b) ?? "").localeCompare(lastTalked(a) ?? "") || byName(a, b);

/** Lanes for the timeline: people with an interaction, most recently talked to first. */
export function lanes(people: Person[]): Person[] {
  return people.filter((p) => p.interactions.length > 0).sort(byRecent);
}
