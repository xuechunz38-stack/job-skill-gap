"""Counting, gap score and ranking (pure functions, no disk)."""

from __future__ import annotations

import pytest

from job_skill_gap.analysis import analyze, collect_warnings, gap_score
from job_skill_gap.matcher import SkillMatcher


@pytest.fixture
def three_postings(make_postings):
    return make_postings(
        "Python and SQL. Python again, python everywhere.",
        "We use sklearn and R.",
        "Python services with a React front end.",
    )


@pytest.fixture
def result(three_postings, tiny_skills, matcher):
    return analyze(
        three_postings, tiny_skills, ["SQL", "sklearn", "Tableau Prep"], matcher
    )


def _by_name(result):
    return {s.skill: s for s in result.stats}


def test_hand_computed_counts_pct_and_gap(result):
    stats = _by_name(result)
    assert result.total_postings == 3
    assert stats["Python"].posting_count == 2
    assert stats["Python"].posting_pct == 0.667
    assert stats["Python"].gap_score == 0.667
    assert stats["R"].posting_count == 1
    assert stats["R"].gap_score == 0.333
    assert stats["React"].posting_count == 1
    assert stats["Java"].posting_count == 0
    assert stats["Java"].posting_pct == 0.0


def test_hand_computed_rank_order(result):
    assert [s.skill for s in result.stats] == [
        "Python",  # 2 postings
        "R",  # 1, missing, alphabetical
        "React",
        "scikit-learn",  # 1, owned -> after missing
        "SQL",
        "C++",  # 0 postings, alphabetical (case-insensitive)
        "Java",
        "JavaScript",
        "machine learning",
    ]
    assert [s.rank for s in result.stats] == list(range(1, 10))


def test_duplicate_mentions_count_once(result):
    # posting 1 says Python three times
    assert _by_name(result)["Python"].posting_count == 2


def test_owned_skill_has_zero_gap_even_if_most_frequent(
    three_postings, tiny_skills, matcher
):
    res = analyze(three_postings, tiny_skills, ["python"], matcher)
    python = _by_name(res)["Python"]
    assert python.have_skill is True
    assert python.posting_count == 2
    assert python.gap_score == 0.0
    assert python.rank == 1


def test_resume_alias_resolves(result):
    stats = _by_name(result)
    assert stats["scikit-learn"].have_skill is True
    assert stats["scikit-learn"].gap_score == 0.0
    assert result.owned_skills == frozenset({"SQL", "scikit-learn"})


def test_unknown_resume_term_listed(result):
    assert result.unknown_resume_terms == ("Tableau Prep",)


def test_zero_postings_library_use_no_zero_division(tiny_skills, matcher):
    res = analyze([], tiny_skills, ["Python"], matcher)
    assert res.total_postings == 0
    assert all(s.posting_count == 0 and s.posting_pct == 0.0 for s in res.stats)
    assert all(s.gap_score == 0.0 for s in res.stats)
    assert len(res.stats) == len(tiny_skills)


def test_all_demanded_skills_owned(three_postings, tiny_skills, matcher):
    res = analyze(
        three_postings, tiny_skills, ["Python", "SQL", "sklearn", "R", "React"], matcher
    )
    assert all(s.gap_score == 0.0 for s in res.stats)
    assert res.missing == ()
    assert any("No missing skills found" in w for w in collect_warnings(res))


def test_posting_without_known_skill(make_postings, tiny_skills, matcher):
    postings = make_postings("Python and SQL", "We like curious people.")
    res = analyze(postings, tiny_skills, [], matcher)
    assert res.postings_without_matches == ("p2.txt",)
    assert res.matches_by_posting["p2.txt"] == ()
    assert _by_name(res)["Python"].posting_count == 1
    assert _by_name(res)["Python"].posting_pct == 0.5  # denominator includes p2


def test_tie_breaking_is_alphabetical_and_deterministic(
    make_postings, tiny_skills, matcher
):
    postings = make_postings("SQL, Java, C++")
    first = analyze(postings, tiny_skills, [], matcher)
    second = analyze(list(reversed(postings)), list(reversed(tiny_skills)), [], matcher)
    assert [s.skill for s in first.stats][:3] == ["C++", "Java", "SQL"]
    assert first.stats == second.stats


def test_every_dictionary_skill_present(result, tiny_skills):
    assert sorted(s.skill for s in result.stats) == sorted(s.name for s in tiny_skills)


def test_result_views(result):
    assert [s.skill for s in result.missing] == ["Python", "R", "React"]
    assert [s.skill for s in result.owned_in_demand] == ["scikit-learn", "SQL"]
    assert len(result.matched_stats) == 5


def test_warnings_for_typical_run(result):
    warnings = collect_warnings(result)
    assert warnings == ["Resume terms not in dictionary: Tableau Prep"]


def test_warning_for_empty_dictionary(make_postings):
    res = analyze(make_postings("Python"), [], [], SkillMatcher([]))
    assert res.stats == ()
    assert "Skills dictionary is empty" in collect_warnings(res)[0]


@pytest.mark.parametrize(
    "pct, have, expected", [(0.5, False, 0.5), (0.5, True, 0.0), (0.0, False, 0.0)]
)
def test_gap_score_formula(pct, have, expected):
    assert gap_score(pct, have) == expected
