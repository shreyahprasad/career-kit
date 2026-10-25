---
name: customize-todos
description: Change the todos every new role in the career tracker starts with (their text, kind, due day and order). Use when they say "change the todos a new role gets", "I don't want the recruiter todo", or "add a prep todo to every new role".
---

# Customize the starter todos

Every new role starts with the todos in `config/starter-todos.json`, which is the owner's own
(updates from the original repo never touch it). It is read each time a role is added, so a
change needs no restart. Each entry is
`{"text": "Update resume", "kind": "resume", "due_in_days": 1}`: `due_in_days` 0 is the day the
role is added, 1 the next day, up to 365. `[]` means a new role starts with none.

## Steps

1. **Read the file and say the list in plain words,** one line each, in order: "Update resume,
   a resume todo, due the next day."
2. **Ask what to change:** add, drop, reword, reorder, or change a day. The kinds are fixed:
   `resume`, `apply`, `outreach`, `prep`, `follow-up`, `other`. Map what they say to the closest
   one and say which you picked ("a prep todo"). If none fits, use `other`.
3. **Show the new list** the same way and ask "Save it?".
4. Once they say yes, write `config/starter-todos.json` (a JSON list, two-space indent, one
   entry per line), then check it loads, from `tools/career`:
   `.venv/bin/python -c "import records; [print(t) for t in records.starter_todos()]"`.
   A problem is printed naming the entry; fix it and check again.
5. **Say that roles already added keep their todos.** Offer to add the new ones to open roles
   too. If they want that, list the roles first (`GET http://127.0.0.1:8100/api/career/roles`,
   leaving out offer and rejected), and only after they say yes,
   `POST http://127.0.0.1:8140/api/career/write/todos` per role with `text`, `kind`, `role_id`
   and `due_on` (today plus `due_in_days`), with the header `X-Career-Kit-Write: 1`.
6. Offer to commit `config/starter-todos.json` to their copy of the repo. Never push unless they
   ask.
