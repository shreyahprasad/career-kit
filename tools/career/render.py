"""
Makes the PDF of a draft: render(markdown, kind) -> Rendered(pdf, pages, last_page_lines). The
draft is Markdown, laid out by templates/<kind>.typ with Typst (the typst package, which compiles
in-process) and cmarker (vendored in typst-packages/, so nothing is downloaded) in the fonts in
fonts/ (Gelasio for a resume, IBM Plex Sans for a letter) and no font from this Mac, so a PDF
comes out the same on every Mac.

A draft is untrusted text: the templates run none of it as code, and the compile runs in a child
process, in a fresh folder holding only the templates and the draft, with a time limit, so a bad
draft cannot reach another file or hang the writer.

    python render.py resume < draft.md > draft.pdf    (the child; the first line out is "<pages> <last page lines>")
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal, NamedTuple

from writekit.career import MAX_DRAFT_BYTES

Kind = Literal["resume", "cover-letter"]

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
FONTS = HERE / "fonts"
PACKAGES = HERE / "typst-packages"

# A draft of that size compiles in well under a second; this only stops one that never ends.
TIMEOUT_SECONDS = 20

FENCE = re.compile(r"^ {0,3}(```|~~~)")
# A first line that is already Markdown structure, not a name.
NOT_A_NAME = re.compile(r"^\s*([#>*+|<`~=-]|\d+[.)]\s)")


class Rendered(NamedTuple):
    pdf: bytes
    pages: int
    # Lines of body text on the last page, so a resume that runs over can say by how much.
    last_page_lines: int


class RenderError(Exception):
    """A sentence to pass on: why there is no PDF."""


def render(markdown: str, kind: Kind) -> Rendered:
    """The draft's PDF, its page count and how full its last page is, made in a child process."""
    if len(markdown.encode()) > MAX_DRAFT_BYTES:
        raise RenderError(f"The draft is over {MAX_DRAFT_BYTES // 1000} KB, too long to be a {kind}. Shorten it first.")
    try:
        done = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).resolve()), kind],
            input=markdown.encode(),
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise RenderError(
            f"Making the PDF took over {TIMEOUT_SECONDS} seconds, so it was stopped. Check the draft for something odd."
        ) from None
    if done.returncode != 0:
        reason = done.stderr.decode(errors="replace").strip().splitlines()
        raise RenderError(f"Could not make the PDF: {reason[-1] if reason else 'the layout failed'}.")
    counts, pdf = done.stdout.split(b"\n", 1)
    pages, last_page_lines = map(int, counts.split())
    return Rendered(pdf, pages, last_page_lines)


def prepare(markdown: str, kind: Kind) -> dict[str, str]:
    """The draft as the template reads it, by file name. Each new line stays a new line, as in the
    text the page shows (Markdown would join them). A resume's first line, its name, becomes the
    heading, and it and the lines right under it (the contact line) are its head, head.md, laid
    out apart from the rest."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    fenced = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and line.strip() and i + 1 < len(lines) and lines[i + 1].strip() and not line.endswith("  "):
            lines[i] = line + "  "
    if kind == "resume":
        first = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first is not None and not NOT_A_NAME.match(lines[first]):
            lines[first] = "# " + lines[first].strip()
            end = next((i for i in range(first, len(lines)) if not lines[i].strip()), len(lines))
            return {"head.md": "\n".join(lines[first:end]) + "\n", "draft.md": "\n".join(lines[end:])}
    return {"head.md": "", "draft.md": "\n".join(lines)}


def _compile(markdown: str, kind: Kind) -> Rendered:
    """In the child: the templates and the draft alone in a fresh folder, the compile's root."""
    import typst

    with tempfile.TemporaryDirectory() as tmp:
        root, cache = Path(tmp, "root"), Path(tmp, "cache")
        root.mkdir()
        cache.mkdir()
        for name in ("draft.typ", f"{kind}.typ"):
            (root / name).write_bytes((TEMPLATES / name).read_bytes())
        for name, text in prepare(markdown, kind).items():
            (root / name).write_text(text)
        compiler = typst.Compiler(
            str(root / f"{kind}.typ"),
            root=str(root),
            font_paths=[str(FONTS)],
            ignore_system_fonts=True,
            package_path=str(PACKAGES),
            package_cache_path=str(cache),
        )
        pdf = compiler.compile()
        counts = json.loads(compiler.query("<pages>", field="value", one=True))
    return Rendered(pdf, counts["pages"], counts["last-page-lines"])


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind not in ("resume", "cover-letter"):
        sys.exit(f"No layout for {kind}")
    try:
        pdf, pages, last_page_lines = _compile(sys.stdin.buffer.read().decode(errors="replace"), kind)
    except Exception as e:
        sys.exit(str(e).strip() or type(e).__name__)
    sys.stdout.buffer.write(f"{pages} {last_page_lines}\n".encode() + pdf)
