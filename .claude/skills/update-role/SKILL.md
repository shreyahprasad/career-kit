---
name: update-role
description: Record what happened with a job in the career tracker, such as applying, a recruiter call, an interview, an offer, a rejection, or a note. Use when they say "I applied to X", "X rejected me", "interview with X Thursday", or "X offered".
---

# Update a role

Read `CLAUDE.md` first if you have not this session.

1. **Find the role:** `GET http://127.0.0.1:8100/api/career/roles`. Match on company, then
   title. If more than one could be meant, or none, list the close ones and ask. Never guess.
2. **Pick the change:**
   - Applied, an offer, or a rejection is a **status change**:
     `POST http://127.0.0.1:8140/api/career/write/roles/<id>/status` with `status` (`applied`,
     `offer`, `rejected`, or `screen`, `interviews`, `interested`), `date` if it was not today,
     `text` for anything they said about it, and the role's `version`. The writer logs the event
     on the timeline itself; do not add it again.
   - A recruiter call, an interview, or a note is an **event**:
     `POST .../roles/<id>/events` with `kind` (`recruiter-call`, `interview`, `note`), `date`,
     and `text`. An interview coming up also moves the status to `interviews` if it is not
     there yet: ask first.
3. **Dates:** turn "Thursday" or "yesterday" into a date from today's date, and say the date
   back ("Thursday, Oct 23"). If you cannot tell which day, ask.
4. Say back the change in one line. If applying and the role has a resume attached, say the
   writer kept a copy of it as sent.
5. A 409 that says the role changed: read it again, then try once more with the new `version`.

Fields for each body are in `tools/career/fields.json` (`StatusChange`, `NewEvent`,
`EventEdit`). To fix a logged event, `PATCH .../events/<id>`. To delete one, confirm first; it
can be brought back with `POST .../events/<id>/restore`.
