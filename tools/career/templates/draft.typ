// What both layouts share: the draft read as Markdown with nothing in it run as code, and the
// counts render.py reads back. render.py copies this beside resume.typ or cover-letter.typ and
// the draft, alone in a fresh folder (the compile's root), so read() reaches nothing else.
#import "@preview/cmarker:0.1.6"

// A draft is untrusted text. Raw Typst in a comment stays a comment, smart quotes and dashes stay
// as written, and nothing in it can read a file (images) or need a label to exist (references
// and #links), which would stop the PDF. Only an https link stays a link in the PDF that is sent;
// any other (javascript:, file:, a label) prints as its text.
#let markdown(text) = cmarker.render(
  text,
  smart-punctuation: false,
  raw-typst: false,
  html: (a: (attrs, body) => body, img: ("void", attrs => [])),
  scope: (
    image: (..args) => [],
    ref: (target, ..args) => [\[\@#str(target)\]],
    link: (dest, ..rest) => if type(dest) == str and dest.starts-with("https://") { link(dest, ..rest) } else { rest.pos().at(0, default: []) },
  ),
)

// The page count, and how many lines of body text are on the last page (where the draft ends,
// below its top margin), which render.py reads back.
#let page-count = context {
  let line = measure[x \ x].height - measure[x].height
  let top = if type(page.margin) == dictionary { page.margin.top } else { page.margin }
  let used = here().position().y - top.length
  [#metadata((pages: counter(page).final().first(), last-page-lines: int(calc.round(used / line)))) <pages>]
}
