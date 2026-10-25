import { describe, expect, it } from "vitest";
import schema from "../../../../tools/networking/schema.sql?raw";
import writerFields from "../../../../tools/networking/fields.json";
import { KINDS, NEXT_STEPS, SENDS, type Kind, type Person } from "./data";
import {
  addMonths,
  agoLabel,
  allTags,
  companies,
  currentGroup,
  dateLabel,
  daysSince,
  foldedFilterCount,
  groupPeople,
  isFiltered,
  lanes,
  letterOf,
  listOpen,
  matches,
  monthLabel,
  monthRange,
  NO_COMPANY,
  NO_FILTERS,
  NOT_YET,
  position,
  timelineMonths,
  todayISO,
} from "./networking";

const TODAY = "2026-10-02";

const person = (id: string, name: string, extra: Partial<Person> = {}, dates: string[] = []): Person => ({
  id,
  name,
  company: null,
  role: null,
  location: null,
  tags: [],
  interactions: dates.map((date) => ({ date, kind: "call" as Kind })),
  next_step: null,
  ...extra,
});

const ann = person("ann", "Ann Lee", { company: "Acme", role: "Engineer", tags: ["mentor", "ai-infra"], next_step: "follow-up" }, ["2026-01-10", "2026-09-30"]);
const bo = person("bo", "bo Diaz", { location: "Austin" });
const cy = person("cy", "Cy Wu", { company: "Acme", tags: ["recruiter"], next_step: "send-resume" }, ["2026-06-01"]);
const dee = person("dee", "Dee Park", { company: "Beta", tags: ["mentor"] }, ["2026-09-20"]);
const zed = person("zed", "Zed Ali", {}, ["2025-08-15"]);
const PEOPLE = [ann, bo, cy, dee, zed];

describe("todayISO", () => {
  it("uses the local calendar date, zero padded", () => {
    expect(todayISO(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });
});

describe("daysSince", () => {
  it("counts from the newest interaction", () => {
    expect(daysSince(ann, TODAY)).toBe(2);
  });

  it("is null for someone not talked to yet", () => {
    expect(daysSince(bo, TODAY)).toBeNull();
  });

  it("crosses month and year ends", () => {
    expect(daysSince(person("x", "X", {}, ["2025-12-31"]), "2026-01-01")).toBe(1);
  });
});

describe("agoLabel", () => {
  it.each([
    [0, "today"],
    [1, "yesterday"],
    [5, "5d ago"],
    [13, "13d ago"],
    [14, "2w ago"],
    [59, "8w ago"],
    [60, "2mo ago"],
    [400, "13mo ago"],
    [730, "2y ago"],
    [1000, "3y ago"],
    [-1, "tomorrow"],
    [-4, "in 4d"],
    [-14, "in 2w"],
  ])("%i days -> %s", (days, label) => {
    expect(agoLabel(days)).toBe(label);
  });
});

describe("labels", () => {
  it("formats dates and months without a time zone", () => {
    expect(dateLabel("2026-04-09")).toBe("Apr 9, 2026");
    expect(monthLabel("2026-01")).toBe("Jan");
    expect(monthLabel("2026-01", true)).toBe("Jan 2026");
  });
});

describe("matches", () => {
  const keep = (f: Partial<typeof NO_FILTERS>) => PEOPLE.filter((p) => matches(p, { ...NO_FILTERS, ...f }, TODAY)).map((p) => p.id);

  it("keeps everyone with no filters", () => {
    expect(keep({})).toEqual(["ann", "bo", "cy", "dee", "zed"]);
    expect(isFiltered(NO_FILTERS)).toBe(false);
  });

  it("searches name, company, role, location and tags, ignoring case", () => {
    expect(keep({ query: "acme" })).toEqual(["ann", "cy"]);
    expect(keep({ query: "ENGINEER" })).toEqual(["ann"]);
    expect(keep({ query: "austin" })).toEqual(["bo"]);
    expect(keep({ query: "recruit" })).toEqual(["cy"]);
    expect(keep({ query: "   " })).toHaveLength(5);
  });

  it("filters by company", () => {
    expect(keep({ company: "Beta" })).toEqual(["dee"]);
  });

  it("needs every selected tag", () => {
    expect(keep({ tags: ["mentor"] })).toEqual(["ann", "dee"]);
    expect(keep({ tags: ["mentor", "ai-infra"] })).toEqual(["ann"]);
  });

  it("keeps people talked to within the range, never anyone not talked to yet", () => {
    expect(keep({ recency: 1 })).toEqual(["ann", "dee"]); // last 2 weeks
    expect(keep({ recency: 3 })).toEqual(["ann", "dee"]); // last 3 months: cy was 123 days ago
  });

  it("counts anyone not talked to yet as gone quiet", () => {
    expect(keep({ recency: 4 })).toEqual(["bo", "cy", "zed"]);
  });

  it("filters by open next step: one action, or anyone with one", () => {
    expect(keep({ next: "follow-up" })).toEqual(["ann"]);
    expect(keep({ next: "any" })).toEqual(["ann", "cy"]);
    expect(keep({ next: "schedule" })).toEqual([]);
    expect(isFiltered({ ...NO_FILTERS, next: "any" })).toBe(true);
  });

  it("counts the filters on under the fold: each tag, company, last talked, next step; not search", () => {
    expect(foldedFilterCount(NO_FILTERS)).toBe(0);
    expect(foldedFilterCount({ ...NO_FILTERS, query: "ann" })).toBe(0);
    expect(foldedFilterCount({ query: "x", company: "Acme", tags: ["a", "b"], recency: 1, next: "any" })).toBe(5);
  });

  it("opens the phonebook when a search or filter goes on, folds it when they clear, and leaves your choice otherwise", () => {
    expect(listOpen({ wasFiltered: false, filtered: true, expanded: false })).toBe(true);
    expect(listOpen({ wasFiltered: true, filtered: false, expanded: true })).toBe(false);
    // Narrowing further keeps it as you left it, so you can fold it while a search is on.
    expect(listOpen({ wasFiltered: true, filtered: true, expanded: false })).toBe(false);
    expect(listOpen({ wasFiltered: false, filtered: false, expanded: true })).toBe(true);
  });

  it("combines filters", () => {
    expect(keep({ company: "Acme", recency: 1 })).toEqual(["ann"]);
    expect(isFiltered({ ...NO_FILTERS, tags: ["x"] })).toBe(true);
  });
});

describe("companies and tags", () => {
  it("lists companies once, A–Z, without blanks", () => {
    expect(companies(PEOPLE)).toEqual(["Acme", "Beta"]);
  });

  it("lists tags most used first, then A–Z", () => {
    expect(allTags(PEOPLE)).toEqual(["mentor", "ai-infra", "recruiter"]);
  });
});

describe("groupPeople", () => {
  const shape = (sort: "name" | "company" | "recent") =>
    groupPeople(PEOPLE, sort, TODAY).map((g) => [g.label, g.people.map((p) => p.id)]);

  it("groups by first letter, A–Z, ignoring case", () => {
    expect(shape("name")).toEqual([
      ["A", ["ann"]],
      ["B", ["bo"]],
      ["C", ["cy"]],
      ["D", ["dee"]],
      ["Z", ["zed"]],
    ]);
  });

  it("puts names that do not start with a letter under #", () => {
    expect(letterOf("  émile")).toBe("#");
    expect(letterOf("4ward")).toBe("#");
    expect(letterOf("ann")).toBe("A");
  });

  it("groups by company, no company last", () => {
    expect(shape("company")).toEqual([
      ["Acme", ["ann", "cy"]],
      ["Beta", ["dee"]],
      [NO_COMPANY, ["bo", "zed"]],
    ]);
  });

  it("groups by how long since they talked, newest first", () => {
    expect(shape("recent")).toEqual([
      ["This week", ["ann"]],
      ["This month", ["dee"]],
      ["This year", ["cy"]],
      ["Longer ago", ["zed"]],
      [NOT_YET, ["bo"]],
    ]);
  });
});

describe("currentGroup", () => {
  const tops = [0, 200, 500];

  it("is the last group whose start has reached the top", () => {
    expect(currentGroup(tops, 0)).toBe(0);
    expect(currentGroup(tops, 199)).toBe(0);
    expect(currentGroup(tops, 200)).toBe(1);
    expect(currentGroup(tops, 650)).toBe(2);
  });

  it("is -1 with no groups", () => {
    expect(currentGroup([], 0)).toBe(-1);
  });
});

describe("timeline months", () => {
  it("adds months across years", () => {
    expect(addMonths("2026-01", -1)).toBe("2025-12");
    expect(addMonths("2025-12", 1)).toBe("2026-01");
    expect(addMonths("2026-10", -11)).toBe("2025-11");
  });

  it("ranges from first to last", () => {
    expect(monthRange("2025-11", "2026-02")).toEqual(["2025-11", "2025-12", "2026-01", "2026-02"]);
  });

  it("shows the last n months ending this month", () => {
    const months = timelineMonths(PEOPLE, 6, TODAY);
    expect(months).toEqual(["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]);
  });

  it("shows all time back to the first interaction", () => {
    expect(timelineMonths(PEOPLE, null, TODAY)[0]).toBe("2025-08");
    expect(timelineMonths(PEOPLE, null, TODAY).at(-1)).toBe("2026-10");
  });

  it("shows only this month when nobody has talked yet", () => {
    expect(timelineMonths([bo], null, TODAY)).toEqual(["2026-10"]);
  });
});

describe("position", () => {
  const months = ["2026-01", "2026-02"]; // 59 days

  it("places a day at its middle", () => {
    expect(position("2026-01-01", months)).toBeCloseTo(0.5 / 59);
    expect(position("2026-02-28", months)).toBeCloseTo(58.5 / 59);
  });

  it("is null outside the months shown", () => {
    expect(position("2025-12-31", months)).toBeNull();
    expect(position("2026-03-01", months)).toBeNull();
  });
});

describe("lanes", () => {
  it("lists people with interactions, most recent first", () => {
    expect(lanes(PEOPLE).map((p) => p.id)).toEqual(["ann", "dee", "cy", "zed"]);
  });
});

describe("fixed lists", () => {
  /** The quoted values in a column's `IN (...)` CHECK. */
  const checked = (column: string) =>
    [...schema.match(new RegExp(`${column}\\s+IN\\s*\\(([^)]*)\\)`))![1].matchAll(/'([^']+)'/g)].map((m) => m[1]);

  it("match the CHECKs in schema.sql", () => {
    expect(KINDS).toEqual(checked("kind"));
    expect(NEXT_STEPS).toEqual(checked("next_step"));
  });
});

describe("what the page sends", () => {
  it("is only fields the writer takes, for each change (tools/networking/fields.json)", () => {
    for (const [body, fields] of Object.entries(SENDS)) {
      const takes: string[] = writerFields[body as keyof typeof writerFields];
      expect(fields.filter((f) => !takes.includes(f)), body).toEqual([]);
    }
  });
});
