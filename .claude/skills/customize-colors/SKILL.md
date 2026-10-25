---
name: customize-colors
description: Change the colors of the career-kit page, dark or light, by showing a few checked palettes drawn on a mock of the page and keeping the one the owner picks. Use when they say "change my colors", "make it more green", "I want a light theme", or "the page is hard to read".
---

# Customize colors

The page's colors are all in `web/src/styles/theme.css`, which is the owner's own (updates from
the original repo never touch it). Sizes and type are in `tokens.css`; do not change those.

Which colors to use is the owner's call. `web/scripts/palette.mjs` only keeps the page readable
(text contrast, and dots visible on a card), so never judge contrast by eye. Run it with Node 24
from `web/` (`eval "$(fnm env)"; fnm use 24`):

- `node scripts/palette.mjs check <file>`: every check, exits 1 on any fail.
- `node scripts/palette.mjs fit <file>`: makes each failing color lighter or darker just until it
  passes, keeping its hue, and rewrites the file. The grounds (`--bg`, `--surface`, `--line`)
  never move.
- `node scripts/palette.mjs preview <out.html> <a.css> <b.css> ...`: one page with a mock of the
  board, todos, timeline and networking dots in each theme, a switch between them, and each
  one's check result. Made-up data only.

## Steps

1. **Ask what they like,** in one message: dark or light; a color they love (or hate); anything
   that tires their eyes; whether they mostly look on the phone or the Mac. Ask a "which do you
   prefer" question, not an open design brief.
2. **Write three candidates** to a scratch folder (not `web/`), each a copy of `theme.css` with
   new values and its own `Theme: <name>` line at the top. Make them three real takes, for
   example: one close to the current look with their color as `--accent`; one warmer or cooler;
   one with higher contrast. Keep `color-scheme` right (`dark` or `light`). For a light theme,
   `--bg` is the page and `--surface` the cards, usually white or near it.
   Keep every token the current file has; the dots (`--series-*`) keep their order of hues
   (teal, blue, orange, magenta, gold, purple, green, then a grey) so a kind keeps its color's
   family.
3. **Fit and check each:** `fit`, then `check`. If `fit` says some still fail (usually a ground
   too close to mid-grey for any text to stand out), change the ground and fit again. Never show
   a candidate that fails.
4. **Show them** with `preview`, using the first of these that works in this session:
   - A tool that publishes an HTML page or sends a file to their phone (an artifact tool, or one
     that sends a file to the user): send the preview file. This is best: they see it on their
     phone, which is where they mostly are.
   - If they set up Tailscale phone access (`TAILNET_HOSTS` in `.env` is not blank), write the
     preview to `web/dist/palette-preview.html` and send the link
     `https://<their tailnet host>/palette-preview.html`. Delete that file after they pick.
   - Otherwise, list each candidate as its name and a few named swatches with hex codes
     (background, cards, text, accent, and the seven dot colors), and tell them the preview file's
     path to open on the Mac.
   Call them A, B and C, as the preview does, and ask which they like or what to change
   ("B but bluer").
5. **Another round,** if they want changes: make up to three new ones from their answer. Keep a
   short list of what they turned down and why, and do not offer it, or something close to it,
   again.
6. **Keep the pick:** copy it over `web/src/styles/theme.css`, with the top comment naming the
   palette and today's date. Run `check` on it (it must pass), then `pnpm build` in `web/`. The
   running page serves the new build at once: tell them to reload, no restart needed.
7. Offer to commit `web/src/styles/theme.css` to their copy of the repo. Never push unless they
   ask.

If they say something on the page is hard to see, ask which part, find its token in `theme.css`
(`--muted` is secondary text, `--line` the borders, `--series-*` the dots), and start from step 2
with that as the thing to fix.
