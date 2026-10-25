import { describe, expect, it } from "vitest";
import { href, segments } from "./router";

describe("href and segments", () => {
  it("reads a hash as its path segments", () => {
    expect(segments("#/career/acme-fde")).toEqual(["career", "acme-fde"]);
    expect(segments("#career/")).toEqual(["career"]);
    expect(segments("")).toEqual([]);
  });

  it("gives back every segment href was given, odd characters and all", () => {
    const route = ["career", "a b/c?d#e%f", "café & co"];
    expect(segments(href(...route))).toEqual(route);
  });
});
