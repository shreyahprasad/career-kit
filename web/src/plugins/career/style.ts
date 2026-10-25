import type { DraftView } from "./career";
import type { DraftKind, Kind, Status, TodoKind } from "./data";

// How the career page names and colors things. Every value is here or in tokens.css.

export const STATUS_LABEL: Record<Status, string> = {
  interested: "Interested",
  applied: "Applied",
  screen: "Screen",
  interviews: "Interviews",
  offer: "Offer",
  rejected: "Rejected",
};

/** Text color for a status heading, when it has one. The rest use the label default. */
export const STATUS_TONE: Partial<Record<Status, string>> = { rejected: "text-negative" };

export const KIND_LABEL: Record<Kind, string> = {
  applied: "applied",
  "recruiter-call": "recruiter call",
  interview: "interview",
  offer: "offer",
  rejection: "rejection",
  note: "note",
};

/** The dot for each kind on the timeline: a fill, never text, so the saturated series are fine. */
export const KIND_COLOR: Record<Kind, string> = {
  applied: "var(--series-2)",
  "recruiter-call": "var(--series-1)",
  interview: "var(--series-5)",
  offer: "var(--series-7)",
  rejection: "var(--series-neutral)",
  note: "var(--line)",
};

export const TODO_KIND_LABEL: Record<TodoKind, string> = {
  resume: "Resume",
  apply: "Apply",
  outreach: "Outreach",
  prep: "Prep",
  "follow-up": "Follow-up",
  other: "Other",
};

/** The dot before a todo: a fill, never text. Drawn from the CVD-checked series in tokens.css. */
export const TODO_KIND_COLOR: Record<TodoKind, string> = {
  resume: "var(--series-2)",
  apply: "var(--series-7)",
  outreach: "var(--series-1)",
  prep: "var(--series-5)",
  "follow-up": "var(--series-6)",
  other: "var(--series-neutral)",
};

export const DRAFT_KIND_LABEL: Record<DraftKind, string> = {
  resume: "Resume",
  "cover-letter": "Cover letter",
};

/** The two ways to see a draft: as the PDF that would be sent, or as text to copy. */
export const DRAFT_VIEW_LABEL: Record<DraftView, string> = {
  pdf: "PDF",
  text: "Text",
};

/** How long "Copied" shows after copying a draft. */
export const COPIED_MS = 2000;
