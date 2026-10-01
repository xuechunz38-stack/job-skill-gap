"""Matcher: aliases, word boundaries, case, special characters, duplicates."""

from __future__ import annotations

import pytest

from job_skill_gap.matcher import SkillMatcher, alias_to_pattern
from job_skill_gap.models import Skill


def test_typical_text(matcher):
    assert matcher.find("Experience with Python and SQL") == {"Python", "SQL"}


def test_alias_maps_to_canonical(matcher):
    assert matcher.find("Familiar with sklearn") == {"scikit-learn"}


def test_alias_and_canonical_in_same_text_count_once(matcher):
    found = matcher.find("sklearn / scikit-learn")
    assert found == {"scikit-learn"}
    assert len(found) == 1


def test_word_boundary_r_not_in_react(matcher):
    assert matcher.find("Build UIs in React") == {"React"}


def test_standalone_r_matches(matcher):
    assert "R" in matcher.find("Statistics in R, Python")


def test_java_not_in_javascript(matcher):
    assert matcher.find("JavaScript developer") == {"JavaScript"}


def test_sql_not_in_nosql_or_mysql(matcher):
    assert "SQL" not in matcher.find("NoSQL stores and MySQL replicas")


def test_special_characters(matcher):
    assert "C++" in matcher.find("C++ and C#")


def test_special_characters_at_end_of_sentence(matcher):
    assert matcher.find("Low-latency code in C++.") == {"C++"}


@pytest.mark.parametrize("text", ["PYTHON", "python", "PyThOn"])
def test_case_insensitive(matcher, text):
    assert matcher.find(text) == {"Python"}


def test_multi_word_alias_across_line_break(matcher):
    assert matcher.find("experience in machine\nlearning") == {"machine learning"}


def test_multi_word_alias_with_extra_spaces(matcher):
    assert matcher.find("machine    learning") == {"machine learning"}


def test_duplicate_mentions_return_a_set_of_one(matcher):
    found = matcher.find("Python Python python")
    assert found == {"Python"}


def test_no_known_skill(matcher):
    assert matcher.find("We value teamwork and curiosity.") == set()


def test_empty_string(matcher):
    assert matcher.find("") == set()


def test_punctuation_adjacency(matcher):
    assert matcher.find("(Python), SQL.") == {"Python", "SQL"}


def test_short_alias_ml(matcher):
    assert matcher.find("Our ML team") == {"machine learning"}
    assert matcher.find("HTML and XML") == set()


@pytest.mark.parametrize(
    "term, expected",
    [
        ("sklearn", "scikit-learn"),
        ("SKLEARN", "scikit-learn"),
        ("  scikit   learn ", "scikit-learn"),
        ("Python", "Python"),
        ("Tableau Prep", None),
        ("", None),
    ],
)
def test_resolve(matcher, term, expected):
    assert matcher.resolve(term) == expected


def test_spark_not_in_pyspark():
    m = SkillMatcher(
        [
            Skill("Spark", "eng", ("Spark",)),
            Skill("PySpark", "eng", ("PySpark",)),
        ]
    )
    assert m.find("pipelines in PySpark") == {"PySpark"}
    assert m.find("Apache Spark and PySpark") == {"Spark", "PySpark"}


def test_dotted_aliases():
    m = SkillMatcher(
        [Skill(".NET", "eng", (".NET",)), Skill("Node.js", "eng", ("Node.js",))]
    )
    assert m.find("Services in .NET and Node.js.") == {".NET", "Node.js"}
    assert m.find("ASP.NET only") == set()


def test_alias_to_pattern_escapes_and_joins_whitespace():
    assert alias_to_pattern("C++") == r"C\+\+"
    assert alias_to_pattern("machine learning") == r"machine\s+learning"
