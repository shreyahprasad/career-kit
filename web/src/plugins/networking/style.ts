/*
 * Networking page settings. Colors and sizes live in src/styles/tokens.css; this file only
 * says which series color each kind of interaction wears and which filters and ranges exist.
 */

import type { Kind, NextStep } from "./data";

/** Fixed per kind, so a color means the same thing in every view. */
export const KIND_COLOR: Record<Kind, string> = {
  call: "var(--series-1)",
  video: "var(--series-2)",
  coffee: "var(--series-3)",
  event: "var(--series-4)",
  message: "var(--series-5)",
  email: "var(--series-6)",
};

export const NEXT_STEP_LABEL: Record<NextStep, string> = {
  "follow-up": "follow up",
  "reach-out": "reach out",
  "catch-up": "catch up",
  "send-resume": "send resume",
  "ask-intro": "ask for intro",
  schedule: "schedule",
  "share-work": "share work",
};

/** The longest each span runs, in days, so "last month" never cuts off a day of it. */
const WEEK = 7;
const MONTH = 31;
const QUARTER = 92;
const YEAR = 366;

/** Last talked, in days. "within" keeps people talked to that recently; "over" keeps the
 *  ones gone quiet, including anyone never talked to. */
export const RECENCY: { label: string; within?: number; over?: number }[] = [
  { label: "Any time" },
  { label: "Last 2 weeks", within: 2 * WEEK },
  { label: "Last month", within: MONTH },
  { label: "Last 3 months", within: QUARTER },
  { label: "Quiet 3+ months", over: QUARTER },
];

/** Talked to within this many days: the phonebook shows "last talked" in full color. */
export const FRESH_DAYS = MONTH;

export const SORTS = [
  { id: "name", label: "A–Z" },
  { id: "recent", label: "Last talked" },
  { id: "company", label: "Company" },
] as const;

export type Sort = (typeof SORTS)[number]["id"];

/** Groups for the "Last talked" sort: the first whose limit the days fall under. */
export const RECENT_GROUPS: { label: string; under: number }[] = [
  { label: "This week", under: WEEK },
  { label: "This month", under: MONTH },
  { label: "Last 3 months", under: QUARTER },
  { label: "This year", under: YEAR },
  { label: "Longer ago", under: Infinity },
];

/** count null = from the first interaction shown. */
export const TIMELINE_RANGES = [
  { label: "Last 6 months", count: 6 },
  { label: "Last 12 months", count: 12 },
  { label: "All time", count: null },
] as const;

export const DEFAULT_TIMELINE_RANGE = 1; // index into TIMELINE_RANGES
