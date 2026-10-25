import { Field } from "@shell/Field";
import { Fold } from "@shell/Fold";
import { PERSON_FIELDS, type NewWho } from "./log";
import { TagPicker } from "./TagPicker";

// A person's name, details and tags. Adding someone folds the details away so the phone form
// stays short; editing opens them. Each input is the type that brings up the right phone
// keyboard, and none autofill, since the browser would offer your own name and number.

export function PersonFields({
  who,
  known,
  onChange,
  autoFocus,
  open,
}: {
  who: NewWho;
  /** Your tags, to pick from. */
  known: string[];
  onChange: (who: NewWho) => void;
  autoFocus?: boolean;
  /** Show the details, not folded. */
  open?: boolean;
}) {
  const set = (key: keyof NewWho["details"], value: string) => onChange({ ...who, details: { ...who.details, [key]: value } });
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="sr-only">Who they are</legend>
      <Field label="Name">
        {(id) => (
          <input id={id} value={who.name} onChange={(e) => onChange({ ...who, name: e.target.value })} autoFocus={autoFocus} autoComplete="off" className="control" />
        )}
      </Field>
      <Fold label="More about them" open={open}>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {PERSON_FIELDS.map((f) => (
            <Field key={f.key} label={f.label} className={"type" in f && f.type === "textarea" ? "sm:col-span-2" : ""}>
              {(id) =>
                "type" in f && f.type === "textarea" ? (
                  <textarea id={id} value={who.details[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} rows={3} className="control resize-y" />
                ) : (
                  <input
                    id={id}
                    // A url field would refuse "linkedin.com/in/x" before the writer adds its https://
                    // (forms.py WebLink), so it is text with the url keyboard.
                    type={!("type" in f) || f.type === "url" ? "text" : f.type}
                    inputMode={"type" in f && f.type === "url" ? "url" : undefined}
                    value={who.details[f.key] ?? ""}
                    onChange={(e) => set(f.key, e.target.value)}
                    autoComplete="off"
                    className="control"
                  />
                )
              }
            </Field>
          ))}
        </div>
      </Fold>
      <TagPicker known={known} tags={who.tags} onChange={(tags) => onChange({ ...who, tags })} />
    </fieldset>
  );
}
