"""Skills dictionary loading and validation."""

from __future__ import annotations

import pytest

from job_skill_gap.dictionary import SkillDictionaryError, load_skills


def test_loads_valid_csv(tiny_skills_csv):
    skills = load_skills(tiny_skills_csv)
    by_name = {s.name: s for s in skills}
    assert len(skills) == 9
    assert by_name["scikit-learn"].aliases == (
        "scikit-learn",
        "sklearn",
        "scikit learn",
    )
    assert by_name["scikit-learn"].category == "ml"


def test_canonical_name_is_always_an_alias(tiny_skills_csv):
    for skill in load_skills(tiny_skills_csv):
        assert skill.aliases[0] == skill.name


def test_whitespace_stripped_and_empty_aliases_dropped(write_file):
    path = write_file(
        "s.csv",
        "skill,category,aliases\n  Python  , programming ,  py3 || python3 |\n",
    )
    (skill,) = load_skills(path)
    assert skill.name == "Python"
    assert skill.category == "programming"
    assert skill.aliases == ("Python", "py3", "python3")


def test_empty_aliases_field_ok(write_file):
    path = write_file("s.csv", "skill,category,aliases\nSQL,data,\n")
    (skill,) = load_skills(path)
    assert skill.aliases == ("SQL",)


def test_duplicate_aliases_within_skill_deduplicated(write_file):
    path = write_file("s.csv", "skill,category,aliases\nPython,p,python|PYTHON|py\n")
    (skill,) = load_skills(path)
    assert skill.aliases == ("Python", "py")


def test_alias_collision_names_both_skills(write_file):
    path = write_file(
        "s.csv",
        "skill,category,aliases\nscikit-learn,ml,sklearn\nSciKit Tools,ml,SKLearn\n",
    )
    with pytest.raises(SkillDictionaryError) as exc:
        load_skills(path)
    assert "scikit-learn" in str(exc.value)
    assert "SciKit Tools" in str(exc.value)


def test_alias_colliding_with_other_skill_name(write_file):
    path = write_file("s.csv", "skill,category,aliases\nSQL,data,\nPostgres,data,sql\n")
    with pytest.raises(SkillDictionaryError, match="SQL"):
        load_skills(path)


def test_duplicate_skill_name(write_file):
    path = write_file("s.csv", "skill,category,aliases\nPython,a,\npython,b,\n")
    with pytest.raises(SkillDictionaryError, match="duplicate skill"):
        load_skills(path)


@pytest.mark.parametrize(
    "content",
    [
        "name,category,aliases\nPython,p,\n",
        "skill,category\nPython,p\n",
        "Python,programming,\n",
        "",
    ],
)
def test_wrong_or_missing_header(write_file, content):
    path = write_file("s.csv", content)
    with pytest.raises(SkillDictionaryError, match="header"):
        load_skills(path)


def test_header_only_gives_empty_list(write_file):
    path = write_file("s.csv", "skill,category,aliases\n")
    assert load_skills(path) == []


def test_bom_and_blank_lines(write_file):
    path = write_file("s.csv", "﻿skill,category,aliases\n\nPython,p,\n,,\n")
    assert [s.name for s in load_skills(path)] == ["Python"]


def test_extra_column_is_an_error(write_file):
    path = write_file("s.csv", "skill,category,aliases\nscikit-learn,ml,sklearn,skl\n")
    with pytest.raises(SkillDictionaryError, match="too many columns"):
        load_skills(path)


def test_empty_skill_name_is_an_error(write_file):
    path = write_file("s.csv", "skill,category,aliases\n,ml,sklearn\n")
    with pytest.raises(SkillDictionaryError, match="empty skill name"):
        load_skills(path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="Skills file not found"):
        load_skills(tmp_path / "nope.csv")


def test_sample_dictionary_is_valid(sample_dir):
    skills = load_skills(sample_dir / "skills.csv")
    assert len(skills) >= 30
    assert "Go" not in {s.name for s in skills}  # risk R1: kept out on purpose
