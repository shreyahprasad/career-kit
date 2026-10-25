import type { ComponentProps } from "react";
import { href } from "@shell/router";
import type { Kind } from "./data";
import { KIND_COLOR } from "./style";

/** A plain link to a person's route, so a click opens them and ⌘-click opens a new tab. */
export function PersonLink({ id, current, ...props }: { id: string; current?: boolean } & Omit<ComponentProps<"a">, "href">) {
  return <a href={href("networking", id)} aria-current={current ? "true" : undefined} {...props} />;
}

/** The round mark for a kind of interaction, beside its label or on a lane. */
export function Dot({ kind }: { kind: Kind }) {
  return (
    <span
      aria-hidden="true"
      className="size-[var(--lane-dot)] shrink-0 rounded-full"
      style={{ background: KIND_COLOR[kind] }}
    />
  );
}

/** The shape of a tag chip, for a tag or something that sits among them. */
export const TAG_CHIP = "rounded-full border px-2 font-mono text-meta leading-5";

/** What a chip adds when it is pressable: a thumb's height on the phone. */
export const PRESSABLE_CHIP = "inline-flex min-h-[var(--chip-min)] items-center";

/** A tag as a small outlined chip. Pressable when it is a filter. */
export function Tag({ tag, pressed, onToggle }: { tag: string; pressed?: boolean; onToggle?: () => void }) {
  if (!onToggle) return <span className={`${TAG_CHIP} border-line text-muted`}>{tag}</span>;
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={`${TAG_CHIP} ${PRESSABLE_CHIP} border-line text-muted hover:text-fg aria-pressed:border-accent aria-pressed:text-fg`}
    >
      {tag}
    </button>
  );
}
