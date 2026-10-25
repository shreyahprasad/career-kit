# `data/style.md`: the format

How the owner wants their resumes and letters to look and read. `tailor-resume` and
`write-cover-letter` read it before drafting and in their check, and save to it as the owner
corrects a draft. It is optional: without it, both skills work as before, and the first save
makes it.

## Style or profile

- **Could it be true or false about them?** Then it is a fact or a claim, and it belongs in
  `data/profile.md` (Never claim for something to leave out), through the `career-interview`
  skill ("update my profile"). Never in this file.
- **Is it how something is said or laid out?** Then it goes here.

"No 'PM' on the resume, I never held that title" is a claim: profile. "No em dashes" and "the
header ends with the GitHub link" are style.

## The file

```markdown
# Style

## Layout

- Font: Gelasio, as the PDF lays it out (you said, 2026-10-22)
- One page, resume and letters (you said, 2026-10-22)
- Header: name, then email, phone, LinkedIn, GitHub (you said, 2026-10-22)
- No location line unless the role asks for one; ask first (you said, 2026-10-22)

## Wording

- No em dashes (you said, 2026-10-22)
- In letters: sign off "Thanks, Sam" (you said, 2026-10-22)
- On the resume: Acme is one entry with both titles and dates (you said, 2026-10-22)

## Turned down

- "drove cross-functional alignment": abstract (you said, 2026-10-22)
- "spearheaded": sounds inflated (you said, 2026-10-22)
```

## Rules

- **Three headings, in this order:** Layout (font, pages, header, links, sections), Wording
  (rules for how things are said), Turned down (phrasings never to bring back).
- **One rule per line, ending with its source,** as in the profile: `(you said, <day>)`.
- **A rule for one kind of writing starts with it:** "On the resume:" or "In letters:". A line
  without one applies to both.
- **Turned down keeps the exact words,** in quotes, with the reason if they gave one. A later
  draft never uses them, reworded included.
- **The PDF layout is the writer's.** A Layout line is a check on the draft, not a setting: a
  font the layout does not use is said in the chat as a code change, not promised.
- **Short.** No line that says what another line already says. A new rule that contradicts an
  old one replaces it. Past about 40 lines, say so and offer to merge lines; never trim it
  unasked.

## Saving to it while drafting

Both drafting skills keep this file up to date, one line at a time, with the Edit tool (the
Write tool only to make it, with the three headings, when it is not there):

- **Saved without asking:**
  - a general rule they state about wording or layout ("never use 'leverage'", "always put
    GitHub last", "no bold in bullets on any resume"): under Layout or Wording.
  - a phrasing you wrote that they turn down ("not 'spearheaded'", "I hate 'drove alignment'"):
    under Turned down, word for word.
- **Not saved:** an edit to one line for this draft ("change this word to 'built'"), or leaving
  out one of their own bullets for this role. Their own words are never turned down.
- **Not sure it is meant for every draft?** Ask in one line: "Keep 'no bold' for every draft?"
- **A fact is never saved here.** Say in a line that "update my profile" keeps it.
- **Say each save in one line,** with how to take it back: "Saved to your style: no 'leverage'
  (say undo to take it out)."
- **"Undo"** takes out exactly the line just added and nothing else: blank lines and headings
  stay as they were, so the file reads as it did before the save. Say so. "Take out the bold
  rule" takes out that line at any time, the same way.
- Before adding, read the file: a rule already there is not added again (say "already in your
  style"), and one that contradicts an old line replaces it (say which).
