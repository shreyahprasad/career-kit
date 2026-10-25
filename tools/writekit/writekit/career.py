"""Where career keeps its files, shared by the career writer (tools/career) and the read API, so
the two never disagree. CAREER_DIR moves the whole folder; CAREER_DB moves only the database."""

import os
from pathlib import Path

CAREER_DIR = Path(os.environ.get("CAREER_DIR", Path(__file__).resolve().parents[3] / "data"))
CAREER_DB = Path(os.environ.get("CAREER_DB", CAREER_DIR / "career.db"))

# A draft is a page or two. The read API shows drafts up to this size, and the writer lays out
# PDFs only from drafts up to it.
MAX_DRAFT_BYTES = 200_000
