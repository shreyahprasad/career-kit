import { describe, expect, it } from "vitest";
import type { Person } from "./data";
import { addTag, emptyDraft, MAX_TAGS, personOptions, saveProblem, tagProblem, toConversation, toggleTag, toNewPerson, personChanges, type Draft } from "./log";

const person = (id: string, name: string, extra: Partial<Person> = {}): Person => ({
  id,
  name,
  company: null,
  role: null,
  location: null,
  tags: [],
  interactions: [],
  next_step: null,
  ...extra,
});

const PEOPLE = [
  person("ann-lee", "Ann Lee", { company: "Acme", interactions: [{ date: "2026-01-02", kind: "call" }] }),
  person("joanna-park", "Joanna Park", { company: "Beta", interactions: [{ date: "2026-09-01", kind: "coffee" }] }),
  person("bo-diaz", "Bo Diaz", { company: "Annex Labs" }),
  person("zoe-obrien", "Zoë O'Brien", { interactions: [{ date: "2026-05-05", kind: "video" }] }),
];

describe("personOptions", () => {
  it("with nothing typed, offers who was talked to most recently", () => {
    expect(personOptions(PEOPLE, "").map((p) => p.id)).toEqual(["joanna-park", "zoe-obrien", "ann-lee", "bo-diaz"]);
  });

  it("ranks a name starting with the query, then a word in the name, then the company or id", () => {
    expect(personOptions(PEOPLE, "an").map((p) => p.id)).toEqual(["ann-lee", "joanna-park", "bo-diaz"]);
  });

  it("ignores case, accents and spacing", () => {
    expect(personOptions(PEOPLE, "  ZOE ").map((p) => p.id)).toEqual(["zoe-obrien"]);
    expect(personOptions(PEOPLE, "o'brien").map((p) => p.id)).toEqual(["zoe-obrien"]);
  });

  it("matches the id, so a slug you remember finds them", () => {
    expect(personOptions(PEOPLE, "bo-d").map((p) => p.id)).toEqual(["bo-diaz"]);
  });

  it("keeps the list short", () => {
    expect(personOptions(PEOPLE, "", 2)).toHaveLength(2);
  });

  it("finds no one for a name not in the phonebook", () => {
    expect(personOptions(PEOPLE, "Priya")).toEqual([]);
  });
});

const TODAY = "2026-10-03";
const base: Draft = emptyDraft(TODAY);

describe("emptyDraft", () => {
  it("is a call today with no one picked", () => {
    expect(base).toMatchObject({ who: null, kind: "call", date: TODAY, title: "", notes: "", next_step: "" });
  });
});

describe("saveProblem", () => {
  it("needs someone picked, and nothing else", () => {
    expect(saveProblem(base)).toBe("Pick who it was with.");
    expect(saveProblem({ ...base, who: { id: "ann-lee" } })).toBeNull();
    expect(saveProblem({ ...base, who: { name: "Priya Shah", details: {}, tags: [] } })).toBeNull();
  });

  it("needs a new person's name to have something in it", () => {
    expect(saveProblem({ ...base, who: { name: "   ", details: {}, tags: [] } })).toBe("Give the new person a name.");
  });

  it("needs a day", () => {
    expect(saveProblem({ ...base, who: { id: "ann-lee" }, date: "" })).toBe("Pick the day you talked.");
  });
});

describe("toConversation", () => {
  it("sends only the person, the kind and the day when nothing else is filled in", () => {
    expect(toConversation({ ...base, who: { id: "ann-lee" } })).toEqual({ person_id: "ann-lee", kind: "call", date: TODAY });
  });

  it("sends a new person by name, with only the details filled in, trimmed", () => {
    const draft: Draft = { ...base, who: { name: " Priya Shah ", details: { company: " Lumen ", role: "", email: "  " }, tags: [] } };
    expect(toConversation(draft)).toEqual({ person: { name: "Priya Shah", company: "Lumen" }, kind: "call", date: TODAY });
  });

  it("sends what you wrote, the notes as typed apart from the ends", () => {
    const draft: Draft = {
      ...base,
      who: { id: "ann-lee" },
      kind: "coffee",
      date: "2026-10-01",
      title: " Catch up ",
      notes: "\n  first line\n\n  second line  \n",
      next_step: "send-resume",
    };
    expect(toConversation(draft)).toEqual({
      person_id: "ann-lee",
      kind: "coffee",
      date: "2026-10-01",
      title: "Catch up",
      notes: "first line\n\n  second line",
      next_step: "send-resume",
    });
  });

  it("refuses a draft that is not ready, so a bad one is never sent", () => {
    expect(() => toConversation(base)).toThrow("Pick who it was with.");
  });
});

describe("tags for someone new", () => {
  const KNOWN = ["warm", "referral", "AI"];

  it("toggles a tag on and off, keeping the order you picked them in", () => {
    expect(toggleTag(["warm"], "referral")).toEqual(["warm", "referral"]);
    expect(toggleTag(["warm", "referral"], "warm")).toEqual(["referral"]);
  });

  it("adds a typed tag, trimmed, with spaces inside kept to one", () => {
    expect(addTag([], "  new   york ", KNOWN)).toEqual(["new york"]);
  });

  it("reuses an existing tag's spelling, so one tag is never two", () => {
    expect(addTag([], "Warm", KNOWN)).toEqual(["warm"]);
    expect(addTag([], "ai", KNOWN)).toEqual(["AI"]);
  });

  it("adds nothing for a blank, or a tag you already picked", () => {
    expect(addTag(["warm"], "   ", KNOWN)).toEqual(["warm"]);
    expect(addTag(["warm"], "WARM", KNOWN)).toEqual(["warm"]);
  });

  it("says why a typed tag can't be added", () => {
    expect(tagProblem("x".repeat(51), [])).toBe("A tag is at most 50 characters.");
    expect(tagProblem("one more", Array.from({ length: MAX_TAGS }, (_, i) => `t${i}`))).toBe(`At most ${MAX_TAGS} tags.`);
    expect(tagProblem("fine", [])).toBeNull();
  });

  it("sends the tags picked, and no tags key when there are none", () => {
    const who = { name: "Julia N", details: {}, tags: ["referral", "warm"] };
    expect(toConversation({ ...base, who })).toEqual({ person: { name: "Julia N", tags: ["referral", "warm"] }, kind: "call", date: TODAY });
    expect(toConversation({ ...base, who: { ...who, tags: [] } })).toEqual({ person: { name: "Julia N" }, kind: "call", date: TODAY });
  });
});

describe("toNewPerson", () => {
  it("sends the trimmed name and only the details and tags filled in", () => {
    const who = { name: "  Sofia Ruiz ", details: { company: " Lumen ", role: "", phone: "(555) 010-0000" }, tags: ["friend"] };
    expect(toNewPerson(who)).toEqual({ name: "Sofia Ruiz", company: "Lumen", phone: "(555) 010-0000", tags: ["friend"] });
  });

  it("sends no tags when none are picked", () => {
    expect(toNewPerson({ name: "Bo", details: {}, tags: [] })).toEqual({ name: "Bo" });
  });

  it("refuses a blank name", () => {
    expect(() => toNewPerson({ name: "  ", details: {}, tags: [] })).toThrow("Give the new person a name.");
  });
});

describe("personChanges", () => {
  const saved = { name: "Sofia Ruiz", company: "Lumen", role: null, phone: null, tags: ["ai", "friend"] };

  it("sends only what changed, a cleared field as null", () => {
    const draft = { name: "Sofia Ruiz", details: { company: "", role: "PM", phone: "" }, tags: ["ai", "friend"] };
    expect(personChanges(draft, saved)).toEqual({ company: null, role: "PM" });
  });

  it("sends the tags when they changed, in any way", () => {
    const draft = { name: "Sofia Ruiz", details: { company: "Lumen" }, tags: ["ai"] };
    expect(personChanges(draft, saved)).toEqual({ tags: ["ai"] });
  });

  it("is empty when nothing changed", () => {
    expect(personChanges({ name: " Sofia Ruiz ", details: { company: "Lumen" }, tags: ["friend", "ai"] }, saved)).toEqual({});
  });

  it("refuses a blank name", () => {
    expect(() => personChanges({ name: " ", details: {}, tags: [] }, saved)).toThrow("Give them a name.");
  });
});
