"""Immutable data containers shared by every module."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    """One dictionary entry. ``aliases`` always includes ``name`` itself."""

    name: str
    category: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Posting:
    """One job posting: its file name and full text."""

    name: str
    text: str


@dataclass(frozen=True)
class SkillStat:
    """Demand statistics for one skill across all postings."""

    skill: str
    category: str
    posting_count: int
    posting_pct: float
    have_skill: bool
    gap_score: float
    rank: int


@dataclass(frozen=True)
class AnalysisResult:
    """Everything the report layer needs; produced by ``analysis.analyze``."""

    stats: tuple[SkillStat, ...]
    total_postings: int
    matches_by_posting: dict[str, tuple[str, ...]] = field(default_factory=dict)
    postings_without_matches: tuple[str, ...] = ()
    owned_skills: frozenset[str] = frozenset()
    unknown_resume_terms: tuple[str, ...] = ()

    @property
    def matched_stats(self) -> tuple[SkillStat, ...]:
        """Skills mentioned by at least one posting, in rank order."""
        return tuple(s for s in self.stats if s.posting_count > 0)

    @property
    def missing(self) -> tuple[SkillStat, ...]:
        """In-demand skills not on the resume, in rank order."""
        return tuple(s for s in self.matched_stats if not s.have_skill)

    @property
    def owned_in_demand(self) -> tuple[SkillStat, ...]:
        """In-demand skills already on the resume, in rank order."""
        return tuple(s for s in self.matched_stats if s.have_skill)
