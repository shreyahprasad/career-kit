// Edit forms: what a form holds against what is saved. A PATCH carries only the fields you
// changed, so a save never writes over a field it did not touch (one changed on another device).

const blankToNull = (v: string | null | undefined) => v?.trim() || null;

/** The fields in draft that differ from saved, trimmed, with a cleared field as null. */
export function changedFields<K extends string>(
  draft: Partial<Record<K, string>>,
  saved: Partial<Record<K, string | null>>,
): Partial<Record<K, string | null>> {
  const changes: Partial<Record<K, string | null>> = {};
  for (const key of Object.keys(draft) as K[]) {
    const value = blankToNull(draft[key]);
    if (value !== blankToNull(saved[key])) changes[key] = value;
  }
  return changes;
}

/** The writers' WebLink (tools/writekit/writekit/forms.py): https, a host, no login, no spaces.
 * Only such a link is ever put in an href (ExternalLink), so javascript: and the like never run. */
export const isWebLink = (link: string) => /^https:\/\/[^\s/?#@]+(?:[/?#]\S*)?$/.test(link.trim());

/** A link as typed or pasted, made a WebLink the way the writers make it (forms.py _as_https):
 * http:// becomes https://, and a bare "linkedin.com/in/x" gets https:// in front. Null when it
 * is still not one. */
export function toWebLink(link: string): string | null {
  let l = link.trim();
  if (/^http:\/\//i.test(l)) l = "https://" + l.slice("http://".length);
  else if (/^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:[/?#]|$)/.test(l)) l = "https://" + l;
  return isWebLink(l) ? l : null;
}
