import { describe, expect, it } from "vitest";
import schema from "../../../../tools/career/schema.sql?raw";
import writerFields from "../../../../tools/career/fields.json";
import { ADDABLE_KINDS, byStatus, DRAFT_VIEWS, draftLabel, draftShows, due, pagesLabel, fillFromPosting, groupTodos, isApproved, latestDraft, roleProblem, sentOn, splitTodos, statusEvent, toNewRole, withDone } from "./career";
import { DRAFT_VIEW_LABEL } from "./style";
import { APPROVAL_FIELD, DRAFT_KINDS, draftPdfURL, KINDS, pdfName, SENDS, STATUSES, TODO_KINDS, type Draft, type OpenTodo, type Role, type RoleEvent, type Status, type Todo } from "./data";

const role = (id: string, status: Status, extra: Partial<Role> = {}): Role => ({
  id,
  company: id,
  title: "FDE",
  location: null,
  comp: null,
  status,
  applied_on: null,
  last_event: null,
  todos: { done: 0, total: 0 },
  next_todo: null,
  ...extra,
});

describe("byStatus", () => {
  it("has a column for every status, in order, even an empty one", () => {
    expect(byStatus([]).map((c) => [c.status, c.roles.length])).toEqual(STATUSES.map((s) => [s, 0]));
  });

  it("puts each role in its status's column, keeping their order", () => {
    const roles = [role("a", "applied"), role("b", "interested"), role("c", "applied")];
    const columns = Object.fromEntries(byStatus(roles).map((c) => [c.status, c.roles.map((r) => r.id)]));
    expect(columns.applied).toEqual(["a", "c"]);
    expect(columns.interested).toEqual(["b"]);
  });

  it("puts the most recently active first in a column, by latest event, then the ones with none", () => {
    const roles = [
      role("old", "applied", { last_event: { date: "2026-07-24", kind: "applied" } }),
      role("none", "applied"),
      role("new", "applied", { last_event: { date: "2026-10-01", kind: "recruiter-call" } }),
    ];
    expect(byStatus(roles).find((c) => c.status === "applied")!.roles.map((r) => r.id)).toEqual(["new", "old", "none"]);
  });
});

describe("rejected roles", () => {
  it("stay in the last column, below every open role, even when they are the most recent", () => {
    const roles = [
      role("open", "applied", { last_event: { date: "2026-07-24", kind: "applied" } }),
      role("done", "rejected", { last_event: { date: "2026-10-08", kind: "rejection" } }),
    ];
    const ids = byStatus(roles).flatMap((c) => c.roles.map((r) => r.id));
    expect(ids).toEqual(["open", "done"]);
    expect(byStatus(roles).at(-1)!.status).toBe("rejected");
  });
});

describe("roleProblem", () => {
  const ok = { company: "Acme", title: "FDE", link: "", applied_via: "" };

  it("is null for a company and title with no links", () => {
    expect(roleProblem(ok)).toBeNull();
  });

  it("asks for a company and a title", () => {
    expect(roleProblem({ ...ok, company: " " })).toBe("Give it a company.");
    expect(roleProblem({ ...ok, title: "" })).toBe("Give it a title.");
  });

  it("names the link that is not a web link", () => {
    expect(roleProblem({ ...ok, link: "jobs" })).toBe("The posting link should be a web link, like https://jobs.example/1");
    expect(roleProblem({ ...ok, applied_via: "ftp://x.example" })).toBe("The applied via link should be a web link, like https://jobs.example/1");
  });

  it("takes a link typed with http:// or none, which the writer saves as https", () => {
    expect(roleProblem({ ...ok, link: "http://jobs.example/1", applied_via: "linkedin.com/jobs/view/9" })).toBeNull();
  });
});

describe("toNewRole", () => {
  it("sends the company and title trimmed, and the posting link only when there is one", () => {
    expect(toNewRole({ company: " Acme ", title: "FDE ", link: "" })).toEqual({ company: "Acme", title: "FDE" });
    expect(toNewRole({ company: "Acme", title: "FDE", link: " https://jobs.example/1 " })).toEqual({
      company: "Acme", title: "FDE", link: "https://jobs.example/1" });
  });
});

describe("adding from a link", () => {
  const typed = { company: "", title: "My title", link: "https://jobs.example/1", location: "", comp: "", posting: "" };
  const read = { company: "Acme", title: "FDE", location: null, comp: "$1", posting: "About.", from: "feed" as const };

  it("fills the empty fields from the posting and keeps what you typed", () => {
    expect(fillFromPosting(typed, read)).toEqual({ ...typed, company: "Acme", comp: "$1", posting: "About." });
  });

  it("reading another link replaces what the last read filled in, even with nothing, but not what you typed", () => {
    const first = fillFromPosting(typed, read);
    const second = { company: "Beta", title: "DS", location: "NYC", comp: null, posting: "Other.", from: "page data" as const };
    expect(fillFromPosting(first, second, read)).toEqual({ ...typed, company: "Beta", location: "NYC", comp: "", posting: "Other." });
  });

  it("sends the location, comp and posting only when there are some", () => {
    expect(toNewRole({ ...typed, company: "Acme", location: " Remote ", posting: "About." })).toEqual({
      company: "Acme", title: "My title", link: "https://jobs.example/1", location: "Remote", posting: "About." });
  });
});

describe("due", () => {
  const today = "2026-10-08";

  it("is nothing with no day", () => {
    expect(due(null, today)).toBeNull();
  });

  it("says today and tomorrow in words, a later day as a date", () => {
    expect(due("2026-10-08", today)).toEqual({ label: "today", overdue: false });
    expect(due("2026-10-09", today)).toEqual({ label: "tomorrow", overdue: false });
    expect(due("2026-10-20", today)).toEqual({ label: "Oct 20", overdue: false });
  });

  it("marks a past day overdue", () => {
    expect(due("2026-10-01", today)).toEqual({ label: "Oct 1", overdue: true });
  });

  it("shows the year only when it is not this year", () => {
    expect(due("2027-01-05", today)).toEqual({ label: "Jan 5, 2027", overdue: false });
  });
});

describe("todos", () => {
  const todo = (id: number, done_on: string | null = null): Todo => ({ id, text: `t${id}`, kind: "other", due_on: null, done_on });

  it("split into open and done, keeping their order", () => {
    expect(splitTodos([todo(1), todo(2, "2026-10-01"), todo(3)])).toEqual({ open: [todo(1), todo(3)], done: [todo(2, "2026-10-01")] });
  });

  it("check off today and open again in place, before the save comes back", () => {
    const todos = [todo(1), todo(2)];
    expect(withDone(todos, 2, true, "2026-10-08")).toEqual([todo(1), todo(2, "2026-10-08")]);
    expect(withDone([todo(1, "2026-10-01")], 1, false, "2026-10-08")).toEqual([todo(1)]);
  });

  it("keep the day a done todo was done when checked again", () => {
    expect(withDone([todo(1, "2026-10-01")], 1, true, "2026-10-08")).toEqual([todo(1, "2026-10-01")]);
  });
});

describe("groupTodos", () => {
  const today = "2026-10-08";
  const acme = { id: "acme-fde", company: "Acme", title: "FDE" };
  const beta = { id: "beta-ds", company: "Beta", title: "DS" };
  // In the API's order: soonest due first, no day last.
  const todos: OpenTodo[] = [
    { id: 1, text: "Ping Ann", kind: "follow-up", due_on: "2026-10-01", role: acme },
    { id: 2, text: "Tailor resume", kind: "resume", due_on: "2026-10-08", role: beta },
    { id: 3, text: "Apply", kind: "apply", due_on: "2026-10-10", role: acme },
    { id: 4, text: "Mock", kind: "prep", due_on: "2026-11-30", role: beta },
    { id: 5, text: "Base resume", kind: "resume", due_on: null, role: null },
  ];
  const shape = (by: Parameters<typeof groupTodos>[1]) => groupTodos(todos, by, today).map((g) => [g.label, g.todos.map((t) => t.id)]);

  it("by due day: overdue, today, this week, later, then no day, leaving out empty ones", () => {
    expect(shape("due")).toEqual([["Overdue", [1]], ["Today", [2]], ["This week", [3]], ["Later", [4]], ["No day", [5]]]);
  });

  it("by type, in the kinds' order, keeping due order inside each", () => {
    expect(shape("type")).toEqual([["Resume", [2, 5]], ["Apply", [3]], ["Prep", [4]], ["Follow-up", [1]]]);
  });

  it("by role, in the order each first comes due, with no role last", () => {
    expect(shape("role")).toEqual([["Acme · FDE", [1, 3]], ["Beta · DS", [2, 4]], ["No role", [5]]]);
  });
});

describe("statusEvent", () => {
  it("names the event applied, offer and rejected log, as the writer does", () => {
    expect(statusEvent("applied")).toBe("applied");
    expect(statusEvent("offer")).toBe("offer");
    expect(statusEvent("rejected")).toBe("rejection");
  });

  it("is null for the statuses that log nothing", () => {
    expect(["interested", "screen", "interviews"].map((s) => statusEvent(s as Status))).toEqual([null, null, null]);
  });
});

describe("ADDABLE_KINDS", () => {
  it("are the kinds a status change does not log", () => {
    expect(ADDABLE_KINDS).toEqual(["recruiter-call", "interview", "note"]);
  });
});

describe("the fixed lists", () => {
  const checked = (column: string) =>
    [...schema.match(new RegExp(`${column}\\s+IN\\s*\\(([^)]*)\\)`))![1].matchAll(/'([^']+)'/g)].map((m) => m[1]);

  it("match the CHECKs in schema.sql", () => {
    expect(STATUSES).toEqual(checked("status"));
    expect(KINDS).toEqual(checked("kind"));
  });

  it("know the kinds of todo in schema.sql", () => {
    const todos = schema.slice(schema.indexOf("CREATE TABLE todos"));
    const kinds = [...todos.match(/kind\s+[^;]*?IN\s*\(([^)]*)\)/)![1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
    expect(TODO_KINDS).toEqual(kinds);
  });
});

describe("sentOn", () => {
  const event = (id: number, date: string, kind: RoleEvent["kind"]): RoleEvent => ({ id, date, kind, text: null, prep_link: null, version: 1 });

  it("is the day of the latest applied event, the one the kept copy was made for", () => {
    // Newest first, as the API sends them: applied, rejected, then applied again.
    const events = [event(4, "2026-10-01", "interview"), event(3, "2026-09-20", "applied"), event(2, "2026-09-01", "rejection"), event(1, "2026-07-24", "applied")];
    expect(sentOn(events)).toBe("2026-09-20");
  });

  it("is null with no applied event", () => {
    expect(sentOn([event(1, "2026-07-24", "note")])).toBeNull();
  });
});

describe("what the page sends", () => {
  it("is only fields the writer takes, for each change (tools/career/fields.json)", () => {
    for (const [body, fields] of Object.entries(SENDS)) {
      const takes: string[] = writerFields[body as keyof typeof writerFields];
      expect(fields.filter((f) => !takes.includes(f)), body).toEqual([]);
    }
  });
});

describe("drafts", () => {
  const draft = (name: string, modifiedAt: string): Draft => {
    const [, kind, number] = name.match(/^(resume|cover-letter)-(\d+)\.md$/)!;
    return { name, kind: kind as Draft["kind"], number: Number(number), modified: modifiedAt.slice(0, 10), modified_at: modifiedAt, pdf: false };
  };
  const none = { approved_resume_draft: null, approved_cover_letter: null };

  it("labels each with its kind, number and day, and says which is approved", () => {
    const letter = draft("cover-letter-2.md", "2026-10-17T09:00:00");
    expect(draftLabel(letter, none)).toBe("Cover letter 2 · Oct 17");
    expect(draftLabel(letter, { ...none, approved_cover_letter: "cover-letter-2.md" })).toBe("Cover letter 2 · Oct 17 · Approved");
  });

  it("is approved only by the field of its own kind", () => {
    const resume = draft("resume-1.md", "2026-10-17T09:00:00");
    expect(isApproved(resume, { approved_resume_draft: "resume-1.md", approved_cover_letter: null })).toBe(true);
    expect(isApproved(resume, { approved_resume_draft: "resume-2.md", approved_cover_letter: "resume-1.md" })).toBe(false);
  });

  it("shows the draft changed last first, by the time on the same day", () => {
    const list = [draft("resume-1.md", "2026-10-17T16:33:00"), draft("cover-letter-2.md", "2026-10-17T16:35:00"), draft("cover-letter-1.md", "2026-10-17T16:34:00")];
    expect(latestDraft(list)?.name).toBe("cover-letter-2.md");
    expect(latestDraft([draft("resume-2.md", "2026-10-17T09:00:00"), draft("cover-letter-1.md", "2026-10-16T23:00:00")])?.name).toBe("resume-2.md");
    expect(latestDraft([draft("resume-1.md", "2026-10-17T09:00:00"), draft("cover-letter-1.md", "2026-10-17T09:00:00")])?.name).toBe("resume-1.md");
    expect(latestDraft([])).toBeNull();
  });

  it("has an approval field the writer takes for every kind", () => {
    for (const kind of DRAFT_KINDS) expect(writerFields.RoleEdit).toContain(APPROVAL_FIELD[kind]);
  });

  it("shows the PDF first, the way to make it when there is none, and the text when asked", () => {
    expect(DRAFT_VIEWS[0]).toBe("pdf");
    expect(draftShows("pdf", true)).toBe("pdf");
    expect(draftShows("pdf", false)).toBe("make-pdf");
    expect(draftShows("text", true)).toBe("text");
    expect(draftShows("text", false)).toBe("text");
  });

  it("labels the switch and the pages in plain words", () => {
    expect(DRAFT_VIEWS.map((v) => DRAFT_VIEW_LABEL[v])).toEqual(["PDF", "Text"]);
    expect([pagesLabel(1), pagesLabel(2)]).toEqual(["1 page", "2 pages"]);
  });

  it("finds a draft's PDF, and the kept letter's, by the same name ending in .pdf", () => {
    expect(pdfName("resume-12.md")).toBe("resume-12.pdf");
    expect(pdfName("acme-fde-2026-10-09-2-cover-letter.md")).toBe("acme-fde-2026-10-09-2-cover-letter.pdf");
    expect(draftPdfURL("acme-fde", "cover-letter-2.md")).toBe("/api/career/roles/acme-fde/drafts/cover-letter-2.pdf");
  });
});
