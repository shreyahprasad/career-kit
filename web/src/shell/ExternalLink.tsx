import type { ReactNode } from "react";
import { isWebLink } from "./edits";

// A link out of the dashboard, opened in a new tab with no referrer. Only an https link becomes
// one; anything else (javascript:, a typo) shows as its text, so nothing saved can run when tapped.

export function ExternalLink({ href, children, className = "text-accent hover:underline" }: { href: string; children: ReactNode; className?: string }) {
  if (!isWebLink(href)) return <span className="break-all text-muted">{href}</span>;
  return (
    <a href={href.trim()} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
    </a>
  );
}
