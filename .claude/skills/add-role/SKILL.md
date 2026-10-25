---
name: add-role
description: Add a job the owner is interested in to their career tracker, from a posting link or pasted posting text. Use when they say "add this job", "track this role", or send a job link.
---

# Add a role

Read `CLAUDE.md` first if you have not this session: it has the ports, the write header and the
rules. Check the servers are up (`/api/health`, as `CLAUDE.md` says, a host app included).

1. **From a link:** `POST http://127.0.0.1:8140/api/career/write/postings/read` with
   `{"link": "<the link>"}`. It saves nothing and returns a draft: company, title, location,
   comp, posting text, and where the facts came from.
   - A refusal saying the site gives nothing to read (Workday and LinkedIn often do): ask them
     to paste the posting text, and take company and title from it or from them.
   - **Without a link:** ask for the company and title at least.
2. **Check it is not already there:** `GET http://127.0.0.1:8100/api/career/roles` and look for
   the same company and a close title. If there is one, show it and ask before adding another.
3. **Show the draft** in a few lines (company, title, location, pay, link) and ask "Add it?".
   Leave out any field the posting did not give. Never fill one in from what you know about
   the company.
4. Once they say yes, `POST http://127.0.0.1:8140/api/career/write/roles` with the fields from
   `tools/career/fields.json` `NewRole` that you have: `company`, `title`, and any of
   `location`, `comp`, `link`, `posting` (the full text), `notes` (their words, if they said
   something about it). Send the header `X-Career-Kit-Write: 1`.
5. Say it is added, its status (Interested), and the starter todos it got: read them from
   `GET http://127.0.0.1:8100/api/career/roles/<role_id>`.

If they mention a referral, use the `log-talk` skill's lookup to find the person, then
`PATCH /roles/<role_id>` with `referral_person_id` and the role's `version`.
