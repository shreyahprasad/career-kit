import { describe, expect, it } from "vitest";
import { changedFields, isWebLink, toWebLink } from "./edits";

describe("changedFields", () => {
  const saved = { company: "Acme", title: "FDE", comp: null };

  it("is empty when nothing changed, even with spaces typed around a value", () => {
    expect(changedFields({ company: " Acme ", title: "FDE", comp: "" }, saved)).toEqual({});
  });

  it("sends what changed, trimmed", () => {
    expect(changedFields({ company: "Acme Corp ", title: "FDE", comp: " $180k" }, saved)).toEqual({ company: "Acme Corp", comp: "$180k" });
  });

  it("sends a cleared field as null", () => {
    expect(changedFields({ company: "Acme", title: "FDE", comp: "" }, { ...saved, comp: "$150k" })).toEqual({ comp: null });
  });
});

describe("isWebLink", () => {
  it("takes an https link with something after it", () => {
    expect(isWebLink("https://jobs.example/1")).toBe(true);
  });

  it.each([
    "http://jobs.example/1", "jobs.example/1", "https://", "https://a b", "javascript:alert(1)", " javascript:alert(1)",
    "https://me@evil.example/", "https:///jobs",
  ])("refuses %s", (link) => {
    expect(isWebLink(link)).toBe(false);
  });
});

describe("toWebLink", () => {
  it.each([
    ["http://linkedin.com/in/richard-de-leon", "https://linkedin.com/in/richard-de-leon"],
    [" HTTP://jobs.example/1 ", "https://jobs.example/1"],
    ["linkedin.com/in/raj", "https://linkedin.com/in/raj"],
    ["https://jobs.example/1", "https://jobs.example/1"],
  ])("makes %s %s", (typed, link) => {
    expect(toWebLink(typed)).toBe(link);
  });

  it.each(["javascript:alert(1)", "raj", "ftp://jobs.example/1", "https://me@evil.example/", "http://"])("refuses %s", (typed) => {
    expect(toWebLink(typed)).toBeNull();
  });
});
