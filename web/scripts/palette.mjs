// Checks a theme file's colors, so contrast is computed, never judged by eye. Plain Node, no
// packages. Which colors to use is the owner's call; this only keeps text and dots readable.
//
//   node scripts/palette.mjs check [theme.css]   each contrast ratio, pass or fail;
//                                                 exits 1 on any fail
//   node scripts/palette.mjs fit theme.css         lightens or darkens the colors that fail just
//                                                 enough to pass, and rewrites the file
//   node scripts/palette.mjs preview out.html a.css b.css ...
//                                                 one page drawing a mock of both pages in each
//                                                 theme, a switch between them, and each one's
//                                                 check; made-up roles and people only
//
// WCAG contrast: text on its ground, and each dot (a color in a page's style.ts maps) on a card.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
export const THEME = join(WEB, "src/styles/theme.css");
const STYLE_FILES = ["src/plugins/career/style.ts", "src/plugins/networking/style.ts"];

// Text floors (WCAG ratio): [text token, the ground it sits on, least ratio].
export const TEXT_FLOORS = [
  ["--fg", "--bg", 7],
  ["--fg", "--surface", 7],
  ["--muted", "--surface", 4.5],
  ["--accent", "--surface", 4.5],
  ["--negative", "--surface", 4.5],
];
// A dot is a fill beside its label, so 3:1 on the card is enough (WCAG non-text contrast).
const DOT_ON_SURFACE = 3;
// Tokens a map uses that are meant to be faint, not dots (a note's dot is the line color).
const NOT_A_DOT = new Set(["--line"]);

/** The theme's colors: { "--bg": "#1c1f24", ... }. Only 6-digit hex values count. */
export function readTheme(file = THEME) {
  const colors = {};
  for (const [, name, hex] of readFileSync(file, "utf8").matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\b/g)) {
    colors[name] = hex.toLowerCase();
  }
  return colors;
}

/** The color maps in the pages' style.ts files: [{ name, tokens: { key: "--series-1" } }]. */
export function readMaps() {
  const maps = [];
  for (const file of STYLE_FILES) {
    const text = readFileSync(join(WEB, file), "utf8");
    for (const [, name, body] of text.matchAll(/export const (\w+)[^=]*=\s*\{([^}]*)\}/g)) {
      const tokens = Object.fromEntries([...body.matchAll(/"?([\w-]+)"?\s*:\s*"var\((--[\w-]+)\)"/g)].map((m) => [m[1], m[2]]));
      if (Object.keys(tokens).length) maps.push({ name: `${file.split("/")[2]} ${name}`, tokens });
    }
  }
  return maps;
}

const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const linear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lin = (hex) => channels(hex).map(linear);
const luminance = (hex) => {
  const [r, g, b] = lin(hex);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

export function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function oklab([r, g, b]) {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

/** Every check on a theme: [{ check, detail, result: "pass" | "fail" }]. */
export function check(colors, maps = readMaps()) {
  const rows = [];
  const missing = (token) => !colors[token] && rows.push({ check: token, detail: "missing from the theme", result: "fail" });

  for (const [text, ground, floor] of TEXT_FLOORS) {
    if ([text, ground].filter(missing).length) continue;
    const ratio = contrast(colors[text], colors[ground]);
    rows.push({ check: `${text} on ${ground}`, detail: `${ratio.toFixed(2)}:1, needs ${floor}:1`, result: ratio >= floor ? "pass" : "fail" });
  }

  const dots = [...new Set(maps.flatMap((m) => Object.values(m.tokens)))].filter((t) => !NOT_A_DOT.has(t));
  for (const dot of dots) {
    if (missing(dot) || !colors["--surface"]) continue;
    const ratio = contrast(colors[dot], colors["--surface"]);
    rows.push({ check: `${dot} on --surface`, detail: `${ratio.toFixed(2)}:1, needs ${DOT_ON_SURFACE}:1`, result: ratio >= DOT_ON_SURFACE ? "pass" : "fail" });
  }
  return rows;
}

// ── Fit ──────────────────────────────────────────────────────────────────────

const LIGHTNESS_STEP = 0.005; // OKLCH L per try
const CHROMA_STEP = 0.005; // OKLCH C taken off when a color is beyond what a screen shows

function toOklch(hex) {
  const [L, a, b] = oklab(lin(hex));
  return [L, Math.hypot(a, b), ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360];
}

/** OKLCH to hex, or null outside what a screen can show. */
function fromOklch([L, C, h]) {
  const [a, b] = [C * Math.cos((h * Math.PI) / 180), C * Math.sin((h * Math.PI) / 180)];
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
  if (rgb.some((v) => v < -1e-4 || v > 1 + 1e-4)) return null;
  const gamma = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
  return `#${rgb.map((v) => Math.round(255 * Math.min(1, Math.max(0, gamma(v)))).toString(16).padStart(2, "0")).join("")}`;
}

/** The color as given, or with only as much chroma taken off as a screen needs to show it. */
function inGamut([L, C, h]) {
  for (let c = C; c > 0; c -= CHROMA_STEP) {
    const hex = fromOklch([L, c, h]);
    if (hex) return hex;
  }
  return fromOklch([L, 0, h]);
}

/** The colors with every floor met: each failing text or dot color made lighter on a dark
 *  ground, darker on a light one, just until it passes. Hue stays; grounds never move. */
export function fit(colors, maps = readMaps()) {
  const out = { ...colors };
  const meet = (token, ground, floor) => {
    const [L, C, h] = toOklch(out[token]);
    const away = toOklch(out[ground])[0] < 0.5 ? 1 : -1;
    for (let next = L; contrast(out[token], out[ground]) < floor && next >= 0 && next <= 1; next += away * LIGHTNESS_STEP) {
      out[token] = inGamut([next, C, h]);
    }
  };
  for (const [text, ground, floor] of TEXT_FLOORS) if (out[text] && out[ground]) meet(text, ground, floor);

  const dots = [...new Set(maps.flatMap((m) => Object.values(m.tokens)))].filter((t) => !NOT_A_DOT.has(t) && out[t]);
  for (const dot of dots) meet(dot, "--surface", DOT_ON_SURFACE);
  return out;
}

/** The theme file with each color replaced by the one in colors, comments and all kept. */
export function rewrite(text, colors) {
  return text.replace(/(--[a-z0-9-]+)(\s*:\s*)(#[0-9a-fA-F]{6})\b/g, (all, name, sep) => (colors[name] ? `${name}${sep}${colors[name]}` : all));
}

// ── Preview ──────────────────────────────────────────────────────────────────

const escape = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const words = (key) => key.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase());

/** The theme's name: the first line of its top comment, up to the first ":" or ";". */
function themeName(file) {
  const first = readFileSync(file, "utf8").match(/\/\*[\s*]*Theme:\s*([^;:\n]+)/);
  return first ? first[1].trim() : file.split("/").pop();
}

/** One theme drawn as the pages draw it: the board, a role's todos and timeline, and the
 *  networking timeline, all from the style.ts maps so a new kind shows up here too. */
function mock(colors, maps, rows) {
  const map = (name) => maps.find((m) => m.name === name)?.tokens ?? {};
  const dot = (token) => `<i class="dot" style="background:var(${token})"></i>`;
  const statuses = [["Interested", "Lumen Labs", "Applied AI Engineer"], ["Applied", "Northwind", "Forward Deployed Engineer"], ["Interviews", "Acme", "Solutions Engineer"]];
  const todos = Object.entries(map("career TODO_KIND_COLOR")).map(([kind, token], i) =>
    `<li>${dot(token)}<span class="box"></span><span>${words(kind)} todo</span><span class="muted">${i ? `Oct ${20 + i}` : "today"}</span></li>`);
  const events = Object.entries(map("career KIND_COLOR")).map(([kind, token]) => `<li>${dot(token)}<span>${words(kind)}</span><span class="muted">Oct 14</span></li>`);
  const talks = Object.entries(map("networking KIND_COLOR"));
  const lanes = ["Alex Chen", "Maya Okafor", "Sam Whitaker"].map((name, row) =>
    `<div class="lane"><span>${name}</span><div class="track">${talks.filter((_, i) => i % 3 === row).map(([, token], i) => `<i class="dot" style="left:${15 + i * 35}%;background:var(${token})"></i>`).join("")}</div></div>`);
  const results = rows.filter((r) => r.result !== "pass");
  return `
    <div class="page">
      <header><h1>Career</h1><span class="button">+ Add a role</span></header>
      <div class="board">${statuses.map(([status, company, title]) => `
        <div><div class="label">${status} · 1</div><div class="panel"><div class="muted small">${company}</div><div class="title">${title}</div><div class="muted small">Remote · applied Oct 2</div></div></div>`).join("")}
        <div><div class="label negative">Rejected · 0</div></div>
      </div>
      <div class="pair">
        <div class="panel"><div class="label">To do · 0 of ${todos.length}</div><ul>${todos.join("")}</ul><span class="link">+ Add a todo</span></div>
        <div class="panel"><div class="label">Timeline</div><ul>${events.join("")}</ul></div>
      </div>
      <div class="panel"><div class="label">Networking timeline</div>
        <div class="legend">${talks.map(([kind, token]) => `<span>${dot(token)}${kind}</span>`).join("")}</div>${lanes.join("")}
      </div>
      <p class="negative small">A change that was refused shows its reason in this color.</p>
      <div class="panel checks"><div class="label">Check</div>${results.length
        ? `<ul>${results.map((r) => `<li class="${r.result}">${r.result.toUpperCase()} ${escape(r.check)}: ${escape(r.detail)}</li>`).join("")}</ul>`
        : `<p class="muted small">Every contrast check passes (${rows.length} checks).</p>`}</div>
    </div>`;
}

/** The preview page for the theme files: a switch on top, one theme showing at a time. */
export function preview(files) {
  const maps = readMaps();
  const themes = files.map((file) => {
    const colors = readTheme(file);
    const scheme = readFileSync(file, "utf8").match(/color-scheme:\s*(\w+)/)?.[1] ?? "dark";
    const vars = Object.entries(colors).map(([k, v]) => `${k}:${v}`).join(";");
    return { name: themeName(file), vars: `${vars};color-scheme:${scheme}`, html: mock(colors, maps, check(colors, maps)) };
  });
  const letter = (i) => String.fromCharCode(65 + i);
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Color options</title>
<style>
  body { margin: 0; font: 15px/1.5 -apple-system, system-ui, sans-serif; }
  input { position: absolute; opacity: 0; }
  nav { position: sticky; top: 0; z-index: 1; display: flex; gap: 8px; padding: 12px; background: #fff; border-bottom: 1px solid #ccc; }
  nav label { padding: 6px 12px; border: 1px solid #999; border-radius: 6px; cursor: pointer; color: #222; }
  .theme { display: none; min-height: 100vh; background: var(--bg); color: var(--fg); }
  ${themes.map((_, i) => `#t${i}:checked ~ nav label[for=t${i}] { background: #222; color: #fff; } #t${i}:checked ~ .t${i} { display: block; }`).join("\n  ")}
  .page { max-width: 1040px; margin: 0 auto; padding: 20px 16px 40px; display: flex; flex-direction: column; gap: 20px; }
  header { display: flex; justify-content: space-between; align-items: center; }
  h1 { margin: 0; font-size: 21px; }
  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; }
  .label { font: 11.5px ui-monospace, Menlo, monospace; letter-spacing: 0.09em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
  .muted { color: var(--muted); } .small { font-size: 13px; } .title { font-size: 17px; font-weight: 500; }
  .negative { color: var(--negative) !important; }
  .button { border: 1px solid var(--accent); color: var(--accent); border-radius: 6px; padding: 6px 12px; font-weight: 500; }
  .link { color: var(--accent); font-size: 13px; }
  .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
  .pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
  ul { list-style: none; margin: 0 0 8px; padding: 0; }
  li { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
  li .muted { margin-left: auto; font-size: 13px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none; }
  .box { width: 18px; height: 18px; border: 1px solid var(--line); border-radius: 4px; background: var(--bg); }
  .legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; color: var(--muted); margin-bottom: 8px; }
  .legend span { display: flex; align-items: center; gap: 6px; }
  .lane { display: grid; grid-template-columns: 120px 1fr; align-items: center; height: 36px; border-top: 1px solid var(--line); font-size: 14px; }
  .track { position: relative; height: 100%; }
  .track .dot { position: absolute; top: 13px; }
  .checks li { font: 12px ui-monospace, Menlo, monospace; display: block; }
  .checks .fail { color: var(--negative); }
</style></head><body>
${themes.map((_, i) => `<input type="radio" name="theme" id="t${i}"${i ? "" : " checked"}>`).join("")}
<nav>${themes.map((t, i) => `<label for="t${i}">${letter(i)}: ${escape(t.name)}</label>`).join("")}</nav>
${themes.map((t, i) => `<section class="theme t${i}" style="${t.vars}">${t.html}</section>`).join("\n")}
</body></html>
`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [command, ...args] = process.argv.slice(2);
  if (command === "check") {
    const file = args[0] ?? THEME;
    const rows = check(readTheme(file));
    for (const { check: name, detail, result } of rows) console.log(`${result.toUpperCase().padEnd(4)}  ${name}  ${detail}`);
    const failed = rows.filter((r) => r.result === "fail").length;
    console.log(failed ? `\n${failed} failed in ${file}` : `\nAll checks pass in ${file}`);
    process.exit(failed ? 1 : 0);
  }
  if (command === "fit" && args.length === 1) {
    const before = readTheme(args[0]);
    const after = fit(before);
    writeFileSync(args[0], rewrite(readFileSync(args[0], "utf8"), after));
    for (const name of Object.keys(after)) if (after[name] !== before[name]) console.log(`${name}  ${before[name]} -> ${after[name]}`);
    const failed = check(after).filter((r) => r.result === "fail").length;
    console.log(failed ? `${failed} still fail: change the colors more and fit again` : `All checks pass in ${args[0]}`);
    process.exit(failed ? 1 : 0);
  }
  if (command === "preview" && args.length >= 2) {
    const [out, ...files] = args;
    writeFileSync(out, preview(files));
    console.log(`Wrote ${out}`);
    process.exit(0);
  }
  console.error("usage: node scripts/palette.mjs check [theme.css]\n       node scripts/palette.mjs fit theme.css\n       node scripts/palette.mjs preview out.html a.css b.css ...");
  process.exit(2);
}
