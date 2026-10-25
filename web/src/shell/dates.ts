// Dates as the pages show them. Dates are YYYY-MM-DD strings, parsed by hand so no time zone can
// shift them; "today" is always passed in.

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY_MS = 86_400_000;

/** Days since 1970-01-01 for a YYYY-MM-DD date. */
export function dayNumber(date: string): number {
  const [y, m, d] = date.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

/** The local calendar date, YYYY-MM-DD. */
export function todayISO(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export const daysBetween = (from: string, to: string) => dayNumber(to) - dayNumber(from);

/** Units for agoLabel, biggest first, in days. */
const AGO_UNITS = [
  { unit: "y", days: 365 },
  { unit: "mo", days: 30 },
  { unit: "w", days: 7 },
];

/** "today", "yesterday", "5d ago", "3w ago", "4mo ago", "2y ago": the biggest unit that
 *  reads 2 or more. A day still to come (days below 0, like an interview logged ahead) reads
 *  "tomorrow", "in 4d", "in 2w". */
export function agoLabel(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days === -1) return "tomorrow";
  const n = Math.abs(days);
  const u = AGO_UNITS.find((u) => n >= 2 * u.days);
  const span = u ? `${Math.round(n / u.days)}${u.unit}` : `${n}d`;
  return days > 0 ? `${span} ago` : `in ${span}`;
}

/** "2026-04-29" -> "Apr 29". */
export function monthDayLabel(date: string): string {
  const [, m, d] = date.split("-");
  return `${MONTHS[Number(m) - 1]} ${Number(d)}`;
}

/** "2026-04-29" -> "Apr 29, 2026". */
export const dateLabel = (date: string) => `${monthDayLabel(date)}, ${date.slice(0, 4)}`;
