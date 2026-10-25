// A cover letter: the page's font (IBM Plex Sans), wide margins, a space between paragraphs.
#import "draft.typ": markdown, page-count

#let font = "IBM Plex Sans"

#set document(title: "Cover letter", date: none)
#set page(paper: "us-letter", margin: 1in)
#set text(font: font, size: 11pt)
#set par(leading: 0.6em, spacing: 1.2em)
#show heading: it => block(below: 0.8em, text(size: 11pt, weight: "bold", it.body))

#markdown(read("draft.md"))
#page-count
