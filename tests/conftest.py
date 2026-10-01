"""Shared fixtures: a tiny in-memory dictionary and temp-folder helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from job_skill_gap.matcher import SkillMatcher
from job_skill_gap.models import Posting, Skill

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"

TINY_SKILLS_CSV = """skill,category,aliases
Python,programming,
R,programming,RStudio|R programming
React,web,React.js
Java,programming,
JavaScript,programming,
SQL,data,
scikit-learn,ml,sklearn|scikit learn
C++,programming,
machine learning,ml,ML
"""


def _skill(name: str, category: str, *aliases: str) -> Skill:
    return Skill(name=name, category=category, aliases=(name, *aliases))


@pytest.fixture
def tiny_skills() -> list[Skill]:
    return [
        _skill("Python", "programming"),
        _skill("R", "programming", "RStudio", "R programming"),
        _skill("React", "web", "React.js"),
        _skill("Java", "programming"),
        _skill("JavaScript", "programming"),
        _skill("SQL", "data"),
        _skill("scikit-learn", "ml", "sklearn", "scikit learn"),
        _skill("C++", "programming"),
        _skill("machine learning", "ml", "ML"),
    ]


@pytest.fixture
def matcher(tiny_skills: list[Skill]) -> SkillMatcher:
    return SkillMatcher(tiny_skills)


@pytest.fixture
def make_postings():
    def _make(*texts: str) -> list[Posting]:
        return [Posting(name=f"p{i}.txt", text=t) for i, t in enumerate(texts, 1)]

    return _make


@pytest.fixture
def write_file(tmp_path: Path):
    """Write ``content`` to ``tmp_path / relative`` (creating folders)."""

    def _write(relative: str, content: str | bytes = "") -> Path:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def tiny_skills_csv(write_file) -> Path:
    return write_file("skills.csv", TINY_SKILLS_CSV)


@pytest.fixture
def sample_dir() -> Path:
    return SAMPLE_DIR
