"""
Request bodies. Every body a writer takes is a Form: a key it does not know is refused (422),
since it is a typo on the page and never something to drop quietly.
"""

import re
from typing import Annotated

from fastapi import Path as PathParam
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Versioned(Form):
    """version: the row's version as the page saw it. Sent, a row changed since is refused
    (rows.update_versioned)."""

    version: Annotated[int, Field(ge=1)] | None = None


def _blank_is_none(value):
    """A form sends "" for a field left empty; that is no value, not an empty one."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def text(max_length: int):
    """Optional text, stripped, with a blank as None. The limit sits on the str, so None passes it."""
    return Annotated[Annotated[str, Field(max_length=max_length)] | None, BeforeValidator(_blank_is_none)]


MAX_LINE = 500  # a name, a title, an email
MAX_LONG = 100_000  # free writing: an hour's notes is well under this

Line = text(MAX_LINE)
Long = text(MAX_LONG)

# A row's id, as rows.id_from_name makes it: lowercase letters, digits and dashes, not starting with
# a dash. SlugPath is the same in a URL path, where it also keeps out "/" and "..".
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
Slug = Annotated[str, Field(pattern=SLUG_PATTERN, max_length=200)]
SlugPath = Annotated[str, PathParam(pattern=SLUG_PATTERN)]

# A PDF by its file name only: no folders, nothing hidden. PdfNamePath is the same in a URL path.
PDF_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._-]*\.pdf$"
PdfName = Annotated[str, StringConstraints(pattern=PDF_NAME_PATTERN, max_length=200)]
PdfNamePath = Annotated[str, PathParam(pattern=PDF_NAME_PATTERN)]

# A draft Claude wrote for a role, in data/drafts/<role>/: resume-1.md, cover-letter-2.md. Each
# kind has its own name so an approval cannot name the other kind. DraftNamePath is either, in a
# URL path.
RESUME_DRAFT_PATTERN = r"^resume-[1-9][0-9]{0,3}\.md$"
COVER_LETTER_PATTERN = r"^cover-letter-[1-9][0-9]{0,3}\.md$"
DRAFT_NAME_PATTERN = r"^(resume|cover-letter)-[1-9][0-9]{0,3}\.md$"
ResumeDraftName = Annotated[str, StringConstraints(pattern=RESUME_DRAFT_PATTERN)]
CoverLetterName = Annotated[str, StringConstraints(pattern=COVER_LETTER_PATTERN)]
DraftNamePath = Annotated[str, PathParam(pattern=DRAFT_NAME_PATTERN)]
# A draft's name without .md, for its PDF in a URL path: /drafts/resume-1.pdf.
DraftStemPath = Annotated[str, PathParam(pattern=DRAFT_NAME_PATTERN.removesuffix(r"\.md$") + "$")]

# The copy of an approved cover letter kept in data/sent when you apply: <role>-<date>-cover-letter.md.
SENT_LETTER_PATTERN = r"^[a-z0-9][a-z0-9-]*-cover-letter\.md$"
SentLetterPath = Annotated[str, PathParam(pattern=SENT_LETTER_PATTERN)]

# A link the page will open: https, with a host and no login in it. The page shows any other text
# as text, never as a link (web/src/shell/edits.ts isWebLink), so javascript: and the like never run.
# As typed or pasted, http:// is saved as https:// and a bare "linkedin.com/in/x" gets https:// in
# front (web/src/shell/edits.ts toWebLink does the same). Only a name with a dot in it gets one,
# so "javascript:alert(1)" stays what it is and is refused.
WEB_LINK_PATTERN = re.compile(r"^https://[^\s/?#@]+(?:[/?#]\S*)?$")
_HTTP = re.compile(r"^http://", re.IGNORECASE)
_BARE_HOST = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:[/?#]|$)")


def _as_https(value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if _HTTP.match(value):
        return "https://" + value[len("http://") :]
    if _BARE_HOST.match(value):
        return "https://" + value
    return value


def _is_web_link(value: str) -> str:
    if not WEB_LINK_PATTERN.match(value):
        raise ValueError("should be a web link, like https://www.linkedin.com/in/name")
    return value


WebLink = Annotated[str, BeforeValidator(_as_https), StringConstraints(max_length=2000), AfterValidator(_is_web_link)]
# An address to write to, and nothing a mailto: link would read as more (?cc=, spaces, a second @).
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[^\s@?&/<>\"]+@[^\s@?&/<>\"]+\.[A-Za-z]{2,}$", max_length=254),
]
# The same, in a form field where a blank is no value.
OptionalWebLink = Annotated[WebLink | None, BeforeValidator(_blank_is_none)]
OptionalEmail = Annotated[Email | None, BeforeValidator(_blank_is_none)]
