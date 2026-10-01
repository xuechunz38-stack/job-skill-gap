"""Find dictionary skills in free text with word-boundary-safe regexes."""

from __future__ import annotations

import re
from collections.abc import Iterable

from job_skill_gap.dictionary import normalize_term
from job_skill_gap.models import Skill

# ``\b`` fails for aliases that start or end with a non-word character
# (C++, C#, .NET), so we use explicit "not next to a letter/digit/_" guards.
_LEFT = r"(?<![A-Za-z0-9_])"
_RIGHT = r"(?![A-Za-z0-9_])"


def alias_to_pattern(alias: str) -> str:
    """Escape an alias; any run of whitespace in it matches ``\\s+``."""
    return r"\s+".join(re.escape(part) for part in alias.split())


def compile_skill_pattern(aliases: Iterable[str]) -> re.Pattern[str]:
    """One case-insensitive pattern per skill: guarded alternation of aliases."""
    ordered = sorted(set(aliases), key=lambda a: (-len(a), a))
    body = "|".join(alias_to_pattern(a) for a in ordered)
    return re.compile(f"{_LEFT}(?:{body}){_RIGHT}", re.IGNORECASE)


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
