import { describe, expect, it } from "vitest";
import { check, contrast, fit, preview, readMaps, readTheme, rewrite, THEME } from "./palette.mjs";

const failed = (rows) => rows.filter((r) => r.result === "fail").map((r) => r.check);

describe("palette check", () => {
  it("passes the theme in the repo", () => {
    expect(failed(check(readTheme()))).toEqual([]);
  });

  it("reads every color map the pages use", () => {
    expect(readMaps().map((m) => m.name)).toEqual(["career KIND_COLOR", "career TODO_KIND_COLOR", "networking KIND_COLOR"]);
  });

  it("fails text that is too faint on its ground", () => {
    const colors = { ...readTheme(), "--muted": "#4a4f57" };
    expect(failed(check(colors))).toEqual(["--muted on --surface"]);
  });

  it("fails a dot too faint to see on a card, and leaves which colors to use alone", () => {
    const colors = { ...readTheme(), "--series-3": "#3a2f2a", "--series-2": "#2887e8", "--series-6": "#2887e8" };
    expect(failed(check(colors))).toEqual(["--series-3 on --surface"]);
  });

  it("names a color the theme is missing", () => {
    const { "--accent": _, ...colors } = readTheme();
    expect(failed(check(colors))).toEqual(["--accent"]);
  });

  it("measures contrast as WCAG does", () => {
    expect(contrast("#ffffff", "#000000")).toBeCloseTo(21);
    expect(contrast("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });

  it("fits a failing theme until it passes, moving only what failed and never the grounds", () => {
    const before = { ...readTheme(), "--muted": "#4a4f57", "--series-3": "#3a2f2a" };
    const after = fit(before);
    expect(failed(check(after))).toEqual([]);
    const moved = Object.keys(before).filter((t) => after[t] !== before[t]);
    expect(moved.sort()).toEqual(["--muted", "--series-3"]);
  });

  it("darkens a dot on a light card, keeping its hue", () => {
    const light = { ...readTheme(), "--bg": "#f6f6f3", "--surface": "#ffffff", "--fg": "#1d2025", "--muted": "#5d636c", "--accent": "#2f62c9", "--negative": "#c4362b", "--series-5": "#d4a017" };
    const after = fit(light);
    expect(contrast(after["--series-5"], "#ffffff")).toBeGreaterThanOrEqual(3);
    expect(after["--series-5"]).not.toBe("#d4a017");
  });

  it("leaves a passing theme as it is", () => {
    expect(fit(readTheme())).toEqual(readTheme());
  });

  it("rewrites only the colors, keeping names, comments and the rest", () => {
    const text = "/* Theme: Mine */\n:root {\n  --bg: #000000; /* ground */\n  --fg: #ffffff;\n  color-scheme: dark;\n}\n";
    expect(rewrite(text, { "--bg": "#111111" })).toBe(text.replace("#000000", "#111111"));
  });

  it("previews each theme with its name and check, and no real data", () => {
    const html = preview([THEME]);
    expect(html).toContain("A: Soft grey (dark)");
    expect(html).toContain("Every contrast check passes");
    expect(html).not.toContain("/api/");
  });
});
