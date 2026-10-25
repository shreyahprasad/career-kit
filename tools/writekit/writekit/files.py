"""Files in data/ that a request names: the read API and the writers find them the same way."""

from pathlib import Path


def file_in(folder: Path, name: str) -> Path | None:
    """The file by that name right in folder, or None. A link that leads out of folder is not
    followed, so a link put in data/ cannot make a writer read, or the read API serve, a file
    from anywhere else."""
    path = folder / name
    if not path.is_file() or path.resolve().parent != folder.resolve():
        return None
    return path
