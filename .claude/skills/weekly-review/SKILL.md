---
name: weekly-review
description: A read-only look at how the job search is going in the career tracker: roles by status, roles gone quiet, people not talked to in a while, and open and overdue todos. Use when they ask "how's my search going", "weekly review", "what's slipping", or "who should I follow up with".
---

# Weekly review

Read `CLAUDE.md` first if you have not this session. This skill only reads; it changes nothing.
Check the servers are up (`/api/health`, as `CLAUDE.md` says, a host app included).

## The numbers

- `STALE_DAYS = 14`: a role is **stale** when it is not rejected and its last event (applying,
  a call, an interview, a note, an offer) is more than 14 days ago. A role with no event at all
  has no day to measure from, so it is never stale; it shows up in the Interested count.
- `QUIET_DAYS = 30`: a person has **gone quiet** when the last talk with them is more than 30
  days ago. Someone with no talk logged is counted, not listed.
- `SOON_DAYS = 7`: todos due within the next 7 days are counted as **coming up**.

These are the only thresholds. If they ask for others ("stale after a week"), use theirs for
this review and say which you used.

## Steps

1. Get today's date with `date +%F`. Every "days ago" is counted from it.
2. Read, from `http://127.0.0.1:8100`:
   - `/api/career/roles`: each role's `status`, `last_event` (`date`, `kind`, or null) and
     `next_todo`.
   - `/api/networking/people`: each person's `interactions` (oldest first, so the last one is
     the latest) and `next_step`.
   - `/api/career/todos`: every open todo with its `due_on` and role.
3. Say it back, short, in this order:
   - **Roles by status:** one line, in the order Interested, Applied, Screen, Interviews,
     Offer, Rejected, leaving out any at zero. "12 roles: 4 interested, 5 applied, 2
     interviews, 1 rejected."
   - **Stale (no event in 14 days):** one line each, oldest first: company, title, status,
     and the last event with its date and how long ago ("Acme FDE, applied, last: applied Sep
     28, 18 days ago"). Say the next todo if it has one. None stale: say so in a line.
   - **Gone quiet (no talk in 30 days):** one line each, longest first: name, company, the last
     talk's kind and date, and their open next step if there is one. Then "N people with no
     talk logged" if any.
   - **Todos:** overdue first (text, role or "the search", due date, days late), then how many
     are coming up (due in the next 7 days), then how many have no day.
4. End with at most three suggestions drawn only from the above (a follow-up on the oldest
   stale role, a note to the person quiet longest, the most overdue todo), and offer to do any
   of them with the `todos`, `update-role` or `log-talk` skill. Do nothing until they say which.

Never fill a gap with a guess: if a role has no event or a person no talk, say that rather
than a date.
