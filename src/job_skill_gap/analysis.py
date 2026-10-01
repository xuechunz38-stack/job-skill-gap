"""Pure counting, scoring and ranking. No file IO, no printing."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace

from job_skill_gap.matcher import SkillMatcher
from job_skill_gap.models import AnalysisResult, Posting, Skill, SkillStat

PCT_DECIMALS = 3


def gap_score(posting_pct: float, have_skill: bool) -> float:
    """Share of postings asking for a skill you lack; 0.0 if you have it.

    Kept as its own function so a weighted formula can replace it later.
    """
    return 0.0 if have_skill else posting_pct


def resolve_resume(
    terms: Iterable[str], matcher: SkillMatcher
) -> tuple[frozenset[str], tuple[str, ...]]:
    """Split resume terms into owned canonical skills and unknown terms."""
    owned: set[str] = set()
    unknown: list[str] = []
    for term in terms:
        canonical = matcher.resolve(term)
        if canonical is not None:
            owned.add(canonical)
        elif term not in unknown:
            unknown.append(term)
    return frozenset(owned), tuple(unknown)


def _rank_key(stat: SkillStat) -> tuple[int, bool, str, str]:
    # count desc -> missing before owned -> name asc (case-insensitive, then exact)
    return (-stat.posting_count, stat.have_skill, stat.skill.casefold(), stat.skill)


def analyze(
    postings: Sequence[Posting],
    skills: Sequence[Skill],
    resume_terms: Iterable[str],
    matcher: SkillMatcher,
) -> AnalysisResult:
    """Count, per skill, how many postings mention it, then score and rank."""
    owned, unknown = resolve_resume(resume_terms, matcher)

    counts = {skill.name: 0 for skill in skills}
    matches_by_posting: dict[str, tuple[str, ...]] = {}
    without_matches: list[str] = []
    for posting in postings:
        # Ignore matcher hits outside ``skills`` (only possible in library use).
        found = matcher.find(posting.text) & counts.keys()
        matches_by_posting[posting.name] = tuple(sorted(found))
        if not found:
            without_matches.append(posting.name)
        for name in found:
            counts[name] += 1  # a set, so at most once per posting

    total = len(postings)
    unranked = []
    for skill in skills:
        count = counts[skill.name]
        pct = round(count / total, PCT_DECIMALS) if total else 0.0
        have = skill.name in owned
        unranked.append(
            SkillStat(
                skill=skill.name,
                category=skill.category,
                posting_count=count,
                posting_pct=pct,
                have_skill=have,
                gap_score=round(gap_score(pct, have), PCT_DECIMALS),
                rank=0,
            )
        )

    ranked = tuple(
        replace(stat, rank=i)
        for i, stat in enumerate(sorted(unranked, key=_rank_key), start=1)
    )
    return AnalysisResult(
        stats=ranked,
        total_postings=total,
        matches_by_posting=matches_by_posting,
        postings_without_matches=tuple(without_matches),
        owned_skills=owned,
        unknown_resume_terms=unknown,
    )


def collect_warnings(result: AnalysisResult) -> list[str]:
    """Human-readable warnings about the run (not errors)."""
    warnings: list[str] = []
    if not result.stats:
        warnings.append("Skills dictionary is empty; nothing to match.")
    if result.postings_without_matches:
        warnings.append(
            "Postings with no recognized skills: "
            + ", ".join(result.postings_without_matches)
        )
    if result.unknown_resume_terms:
        warnings.append(
            "Resume terms not in dictionary: " + ", ".join(result.unknown_resume_terms)
        )
    if not result.missing:
        warnings.append(
            "No missing skills found: every skill the postings mention is "
            "already on your resume (or no posting mentions a dictionary skill)."
        )
    return warnings
