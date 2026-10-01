"""Find dictionary skills in free text with word-boundary-safe regexes."""

from __future__ import annotations

import re
from collections.abc import Iterable

from job_skill_gap.dictionary import normalize_term
from job_skill_gap.models import Skill

# ``\b`` fails for aliases that start or end with a non-word character
# (C++, C#, .NET), so we use explicit "not next to a letter/digit/_" guards.
# A guard is only added on a side where the alias itself has a word character:
# that is where gluing would create a different word (R in React, Java in
# JavaScript). An edge like the "++" in C++ is already a boundary, so C++17 and
# C#10 still match C++ / C#.
_LEFT = r"(?<![A-Za-z0-9_])"
_RIGHT = r"(?![A-Za-z0-9_])"


def _is_word_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char == "_")


def alias_to_pattern(alias: str) -> str:
    """Escape an alias; any run of whitespace in it matches ``\\s+``."""
    return r"\s+".join(re.escape(part) for part in alias.split())


def guarded_alias_pattern(alias: str) -> str:
    """``alias_to_pattern`` plus boundary guards on its word-character edges."""
    alias = alias.strip()
    left = _LEFT if _is_word_char(alias[0]) else ""
    right = _RIGHT if _is_word_char(alias[-1]) else ""
    return f"{left}{alias_to_pattern(alias)}{right}"


def compile_skill_pattern(aliases: Iterable[str]) -> re.Pattern[str]:
    """One case-insensitive pattern per skill: alternation of guarded aliases."""
    ordered = sorted({a for a in aliases if a.strip()}, key=lambda a: (-len(a), a))
    if not ordered:
        return re.compile(r"(?!)")  # no aliases: never match (not "always")
    body = "|".join(guarded_alias_pattern(a) for a in ordered)
    return re.compile(f"(?:{body})", re.IGNORECASE)


class SkillMatcher:
    """Maps text or single terms to canonical skill names."""

    def __init__(self, skills: Iterable[Skill]) -> None:
        self._patterns: list[tuple[str, re.Pattern[str]]] = []
        self._lookup: dict[str, str] = {}
        for skill in skills:
            self._patterns.append((skill.name, compile_skill_pattern(skill.aliases)))
            for alias in skill.aliases:
                self._lookup.setdefault(normalize_term(alias), skill.name)

    def find(self, text: str) -> set[str]:
        """Canonical names of every skill mentioned at least once in ``text``."""
        if not text:
            return set()
        return {name for name, pattern in self._patterns if pattern.search(text)}

    def resolve(self, term: str) -> str | None:
        """Canonical name for a single term (e.g. a resume line), else ``None``."""
        return self._lookup.get(normalize_term(term))
