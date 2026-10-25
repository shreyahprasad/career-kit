"""career.db, written only through db (writekit.Database). Its schema is schema.sql. Beside it,
resumes/ holds the PDFs you export, drafts/<role>/ the drafts Claude writes for each role, and sent/
the copies kept when you apply."""

from pathlib import Path

from writekit.career import CAREER_DB, CAREER_DIR
from writekit.db import Database

db = Database(CAREER_DB, Path(__file__).with_name("migrations"))


# Read when called, so a test can move CAREER_DIR.
def resumes() -> Path:
    return CAREER_DIR / "resumes"


def sent() -> Path:
    return CAREER_DIR / "sent"


def drafts(role_id: str) -> Path:
    return CAREER_DIR / "drafts" / role_id
