---
name: todos
description: Show, add, and check off todos in the career tracker. Use when they ask "what should I do today", "what's on my list", "remind me to follow up with X Friday", or "I did the X todo".
---

# Todos

Read `CLAUDE.md` first if you have not this session.

**What to do:** `GET http://127.0.0.1:8100/api/career/todos` lists every open todo, each with
its role (or none, for the search as a whole), kind and due day. Show overdue first, then today,
then the next few days, then ones with no day. Group by role when there are many. Keep it short:
a line each, "Apply to role: Acme FDE, due today".

**Add one:** `POST http://127.0.0.1:8140/api/career/write/todos` with `text`, `kind` (`resume`,
`apply`, `outreach`, `prep`, `follow-up`, `other`; pick the closest and say which), `role_id`
when it is about a role (find it in `/api/career/roles`, ask if unclear), and `due_on` as a date
when they gave a day. Say the day back as a date.

**Check one off:** find it in the list (ask if more than one could be meant), then
`PATCH .../todos/<id>` with `{"done": true}`. Unchecking is `{"done": false}`. Fixing text, kind
or day is the same route with those fields.

**Delete one:** confirm first. `DELETE .../todos/<id>`; it comes back with
`POST .../todos/<id>/restore`.

Every change sends the header `X-Career-Kit-Write: 1`.
