---
name: log-talk
description: Log a talk with someone in the networking tracker, adding them if new, and link them as a referral on a role. Use when they say "had coffee with Sam from Acme", "talked to my recruiter friend", or "they offered to refer me".
---

# Log a talk

Read `CLAUDE.md` first if you have not this session.

1. **Find the person:** `GET http://127.0.0.1:8100/api/networking/people` and match on name,
   then company. One clear match: use their `id`. Several: list them and ask. None: they are new.
2. **Work out the talk:** `kind` is one of `call`, `video`, `coffee`, `event`, `message`,
   `email`; `date` (today unless they said otherwise; say it back as a date); a short `title`;
   `summary` (a line or two in your words of what they told you); `notes` (what they said, as
   they said it, if they gave detail); `next_step` if there is one: `follow-up`, `reach-out`,
   `catch-up`, `send-resume`, `ask-intro`, `schedule`, `share-work`.
3. **Show it** in a few lines and ask "Log it?". For someone new, include what you will save
   about them (name, company, role, how they met) and nothing they did not say.
4. Once they say yes, `POST http://127.0.0.1:8120/api/networking/write/interactions` with the
   header `X-Career-Kit-Write: 1` and either `person_id` (someone known) or `person`
   (`{"name": ..., "company": ..., ...}`, someone new), never both.
5. **A referral:** if they say this person will refer them or did, find the role in
   `GET http://127.0.0.1:8100/api/career/roles` (same company first). Offer to set the person as
   its referral; once they say yes, `PATCH http://127.0.0.1:8140/api/career/write/roles/<id>`
   with `referral_person_id` and the role's `version` (from `/api/career/roles/<id>`).

Fields are in `tools/networking/fields.json` (`Conversation`, `NewPerson`, `TalkEdit`).
