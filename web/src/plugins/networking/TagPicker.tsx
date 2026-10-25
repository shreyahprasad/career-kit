import { useState, type KeyboardEvent } from "react";
import { Fold } from "@shell/Fold";
import { addTag, tagProblem, toggleTag } from "./log";
import { PRESSABLE_CHIP, Tag, TAG_CHIP } from "./parts";

// Tags for someone new, folded away until you want them: your tags as chips to tap on or off,
// and + to type one that is not there yet. Enter adds it and leaves the box open for another;
// Escape, or leaving it empty, closes it.

export function TagPicker({ known, tags, onChange }: { known: string[]; tags: string[]; onChange: (tags: string[]) => void }) {
  const [adding, setAdding] = useState(false);
  const [typed, setTyped] = useState("");
  const problem = typed ? tagProblem(typed, tags) : null;
  // Your tags, most used first, then any new ones picked here.
  const shown = [...known, ...tags.filter((t) => !known.includes(t))];

  const add = () => {
    if (problem) return;
    onChange(addTag(tags, typed, known));
    setTyped("");
  };
  const close = () => {
    setTyped("");
    setAdding(false);
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault(); // adds the tag; never saves the form
      add();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };

  return (
    <Fold label={tags.length ? `Tags · ${tags.length}` : "Tags"}>
      <div role="group" aria-label="Tags" className="mt-2 flex flex-wrap items-center gap-1">
        {shown.map((t) => (
          <Tag key={t} tag={t} pressed={tags.includes(t)} onToggle={() => onChange(toggleTag(tags, t))} />
        ))}
        {adding ? (
          <input
            aria-label="New tag"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={onKey}
            onBlur={() => (typed.trim() ? add() : close())}
            placeholder="new tag"
            autoFocus
            className="control w-36 font-mono placeholder:text-muted"
          />
        ) : (
          <button type="button" aria-label="Add a new tag" onClick={() => setAdding(true)} className={`${TAG_CHIP} ${PRESSABLE_CHIP} border-dashed border-line text-accent`}>
            +
          </button>
        )}
      </div>
      {problem && <p className="mt-1 text-small text-negative">{problem}</p>}
    </Fold>
  );
}
