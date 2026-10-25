// A resume in the classic one-page US layout: Gelasio (Georgia's metrics), the name in caps and
// the lines under it centered, section headings in caps over a rule, "•" bullets with a hanging
// indent, and " | " spaced wide. render.py hands it the name and contact lines as head.md and
// the rest as draft.md.
#import "draft.typ": markdown, page-count

#let font = "Gelasio"
// Georgia's ascent and descent, so lines sit as far apart as in a resume set in Georgia (Gelasio
// matches its widths, not its line height).
#let ascent = 0.917em
#let descent = -0.219em
#let body-size = 10.5pt
#let head-size = 9pt
#let name-size = 16pt
#let heading-size = 11pt
#let leading = 1.9pt
// Between bullets, and from a job's line to its first bullet.
#let item-gap = 2.9pt
// Before a job or project after the bullets of the one above.
#let entry-gap = 7.9pt
#let heading-gap = 11.3pt
#let rule = 0.75pt
#let hang = 18.85pt
// Beside the spaces around a "|": Pages puts two spaces on each side.
#let separator = 0.241em

#set document(title: "Resume", date: none)
#set page(paper: "us-letter", margin: (x: 0.8in, top: 0.2in, bottom: 0.3in))
#set text(font: font, size: body-size, top-edge: ascent, bottom-edge: descent)
#set par(leading: leading, spacing: entry-gap)
#set list(marker: box(width: hang, align(start, [•])), indent: 0pt, body-indent: 0pt, spacing: item-gap)
#show list: set block(above: item-gap, below: entry-gap)
#show strong: set text(weight: "bold")
#show "|": [#h(separator)|#h(separator)]

#show heading.where(level: 1): it => block(below: 4.6pt, text(size: name-size, weight: "bold", upper(it.body)))
#show heading.where(level: 2): it => block(above: heading-gap, below: 4.4pt, width: 100%, stroke: (bottom: rule), inset: (bottom: 1.6pt),
  text(size: heading-size, weight: "bold", upper(it.body)))
#show heading.where(level: 3): it => block(above: entry-gap, below: item-gap, text(weight: "bold", it.body))

#align(center, text(size: head-size, markdown(read("head.md"))))
#markdown(read("draft.md"))
#page-count
