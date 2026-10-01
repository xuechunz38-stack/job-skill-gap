"""Read the postings folder and the resume skills file."""

from __future__ import annotations

from pathlib import Path

from job_skill_gap.models import Posting

ENCODING = "utf-8-sig"  # transparently strips a UTF-8 BOM


class NoPostingsError(ValueError):
    """The postings folder exists but holds no ``.txt`` files."""


def _read_text(path: Path) -> str:
    return path.read_text(encoding=ENCODING, errors="replace")


def load_postings(folder: str | Path) -> list[Posting]:
    """Load every ``*.txt`` file directly inside ``folder``, sorted by name.

    Sub-folders, other extensions and hidden files (``.DS_Store``,
    ``._foo.txt``) are ignored.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Postings folder not found: {folder}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Postings path is not a directory: {folder}")

    files = sorted(
        (
            p
            for p in folder_path.iterdir()
            if p.is_file() and p.suffix.lower() == ".txt" and not p.name.startswith(".")
        ),
        key=lambda p: p.name,
    )
    if not files:
        raise NoPostingsError(f"No .txt postings found in {folder}")
    return [Posting(name=p.name, text=_read_text(p)) for p in files]


def load_resume(path: str | Path) -> list[str]:
    """One skill per line; blank lines and ``#`` comments are skipped."""
    resume_path = Path(path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")
    if not resume_path.is_file():
        raise IsADirectoryError(f"Resume path is not a file: {path}")

    terms: list[str] = []
    for line in _read_text(resume_path).splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term)
    return terms
