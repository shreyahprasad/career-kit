# `data/profile.md`: the format

The `career-interview` skill writes this file; the skills that draft resumes and cover letters
read it. Keep to these headings, in this order, so every skill finds what it needs. Change the
format only with care: a draft skill that cannot find a section works without it.

## Sources

**Every fact ends with its source in brackets**, so a draft can say where each claim came from:

- A file, by its path inside `data/`: `(resumes/resume-v3.pdf)`,
  `(examples/cover-letters/acme.md)`, `(examples/resumes/everything.md)`.
- Something they said: `(you said, 2026-10-17)`, with the day they said it, and where if it was
  not in the interview: `(you said, 2026-10-03, Acme call)`.
- Two sources that agree: `(resumes/resume-v3.pdf; you said, 2026-10-17)`.

A line with no source is not a fact yet. The drafting skills use only facts with a source, and
**nothing under Still to ask is a fact**, even with a source: it is waiting for their answer.

## The file

```markdown
# Profile

Last updated: 2026-10-17

## Aiming for

- Roles: Senior data analyst, analytics engineer (you said, 2026-10-17)
- Level: senior, individual contributor (you said, 2026-10-17)
- Industries: healthcare, fintech (you said, 2026-10-17)
- Play down: the year in sales (you said, 2026-10-17)

## Jobs

### Acme Corp, Data Analyst, 2021-03 to now

- Built the weekly churn dashboard the sales team uses (resumes/master.md)
  - Used by: 12 sales reps, every Monday (you said, 2026-10-03, Acme call; you said, 2026-10-17)
  - Their part: built it alone; the data team owns the billing tables (you said, 2026-10-17)
- Cut report run time from 3 hours to 20 minutes by moving it to dbt (resumes/master.md)
  - Numbers: timed before and after on the same month of data (you said, 2026-10-17)

### Beta Inc, Sales Associate, 2019-06 to 2021-02

- Top 10% of the team for renewals in 2020 (examples/resumes/everything.md)

## Projects and stories

### Churn dashboard

- Problem: sales found out about churn a month late (you said, 2026-10-17)
- What they did: built a weekly dashboard from billing data in Looker (resumes/resume-v3.pdf)
- Result: renewals team calls at-risk accounts the same week (you said, 2026-10-17)
- Numbers: churn down from 8% to 6% in two quarters (you said, 2026-10-17)

## Skills

- SQL: daily at Acme; the churn dashboard (resumes/resume-v3.pdf)
- dbt: the report rebuild at Acme (resumes/resume-v3.pdf)

## Education

- B.S. Statistics, Ohio State University, 2019 (resumes/resume-v3.pdf)
- Google Data Analytics certificate, 2022 (examples/resumes/everything.md)

## Voice

- Tone: plain, not formal (examples/cover-letters/acme.md)
- Letter length: about 200 words, three short paragraphs (examples/cover-letters/acme.md)
- Opens with: why this company, in one sentence (examples/cover-letters/acme.md)
- Signs off: "Thanks, Sam" (examples/cover-letters/acme.md; examples/cover-letters/beta.md)
- Never uses: "passionate", "synergy" (you said, 2026-10-17)

## Never claim

- Python as a main skill: only used it in a course (you said, 2026-10-17)
- The churn dashboard bullet at Acme: never say how many accounts it covers (you said, 2026-10-17)
- The dbt move, in cover letters: it reads as a tools story (you said, 2026-10-17)

## Still to ask

- Behind: Beta Inc, bullet 1, "Top 10% of the team for renewals"
- Confirm: the team was 40 people (you said, 2026-10-03, Acme call)
- Projects outside work
```

## Rules for each section

- **Aiming for:** roles, level, industries, and anything to play down.
- **Jobs:** one `###` block per job, newest first: company, title, start and end as `YYYY-MM`
  (or `now`), as the files or they give them. Achievements as bullets, in their words where
  possible; a bullet from their master resume is copied word for word. Leave out a date nobody
  gave; never guess one.
- **What a bullet rests on:** indented lines under a bullet, each a fact with its source, with
  one of these labels: `Numbers:` (where a number comes from, or what changed), `Scope:` (how
  big), `Their part:` (what they did, and what the team did) and `Used by:` (who uses it, how
  often). Leave out a label nobody has answered. The same goes for a bullet under a project.
- **Projects and stories:** one `###` block each, with Problem, What they did, Result and
  Numbers. Leave out a line nobody has answered yet and put it under Still to ask. A project on
  their master resume starts with its bullets, word for word, each with what it rests on.
- **Skills:** each with where it was used. A skill with nowhere to point to goes under
  Still to ask, not here.
- **Education:** degrees, certificates and courses, with the year if a file or they give it.
- **Voice:** tone, letter length, how letters open and sign off, words they never use. From
  their example letters first, then what they say. Letter length is each letter's word count
  from greeting to sign-off, both included.
- **Never claim:** what they asked to leave out of every draft, or of some ("not in cover
  letters"), with the reason if they gave one. A rule about one bullet names it.
- **Still to ask:** what is not answered yet, most useful first. The interview picks up from the
  first item here. `Behind: <job or project>, bullet <n>, "<its first words>"` is a master
  resume bullet still to go through, ending `; skipped: <labels>` for the asks they skipped. `Confirm: <fact> (<source>)` is something a note in
  `data/notes/` says they said, to confirm before it is a fact. The rest are gaps.
