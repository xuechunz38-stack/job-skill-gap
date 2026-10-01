"""CSV writer, PNG chart and terminal summary."""

from __future__ import annotations

import csv

import pytest

from job_skill_gap.analysis import analyze
from job_skill_gap.report import (
    CSV_COLUMNS,
    format_summary,
    plot_top_missing,
    write_csv,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def result(make_postings, tiny_skills, matcher):
    postings = make_postings(
        "Python and SQL", "Python, sklearn and R", "React and Java", "Nothing here."
    )
    return analyze(postings, tiny_skills, ["SQL", "Tableau Prep"], matcher)


def test_csv_header_and_one_row_per_skill(result, tmp_path, tiny_skills):
    path = write_csv(result.stats, tmp_path / "out.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        handle.seek(0)
        header = handle.readline().strip()
    assert header == ",".join(CSV_COLUMNS)
    assert len(rows) == len(tiny_skills)


def test_csv_values_round_trip(result, tmp_path):
    path = write_csv(result.stats, tmp_path / "out.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = {r["skill"]: r for r in csv.DictReader(handle)}
    python = rows["Python"]
    assert python["rank"] == "1"
    assert python["posting_count"] == "2"
    assert python["posting_pct"] == "0.500"
    assert python["have_skill"] == "false"
    assert python["gap_score"] == "0.500"
    assert rows["SQL"]["have_skill"] == "true"
    assert rows["SQL"]["gap_score"] == "0.000"
    assert rows["C++"]["posting_count"] == "0"


def test_csv_is_byte_identical_across_runs(result, tmp_path):
    a = write_csv(result.stats, tmp_path / "a.csv").read_bytes()
    b = write_csv(result.stats, tmp_path / "b.csv").read_bytes()
    assert a == b
    assert b"\r\n" not in a


def _assert_png(path):
    data = path.read_bytes()
    assert len(data) > 1000
    assert data.startswith(PNG_MAGIC)


def test_png_created(result, tmp_path):
    path = plot_top_missing(result.stats, tmp_path / "chart.png", total_postings=4)
    _assert_png(path)


def test_png_with_fewer_than_n_missing(result, tmp_path):
    assert len(result.missing) < 10
    _assert_png(plot_top_missing(result.stats, tmp_path / "chart.png", n=10))


def test_png_placeholder_when_nothing_missing(
    tmp_path, make_postings, tiny_skills, matcher
):
    res = analyze(make_postings("Python"), tiny_skills, ["Python"], matcher)
    assert res.missing == ()
    _assert_png(plot_top_missing(res.stats, tmp_path / "chart.png"))


def test_summary_contents(result):
    text = format_summary(result, {"CSV": "out/skill_gap.csv", "Chart": "out/c.png"})
    assert "4 postings analyzed" in text
    assert "1. Python" in text
    assert "2/4 postings (50.0%)" in text
    assert "out/skill_gap.csv" in text
    assert "out/c.png" in text
    assert "Warnings:" in text
    assert "p4.txt" in text  # posting with no recognized skills
    assert "Tableau Prep" in text  # unknown resume term


def test_summary_limits_to_top_five(make_postings, tiny_skills, matcher):
    res = analyze(
        make_postings("Python R React Java JavaScript C++ ML"), tiny_skills, [], matcher
    )
    text = format_summary(res, {})
    assert "5. " in text and "6. " not in text


def test_summary_when_no_gaps(make_postings, tiny_skills, matcher):
    res = analyze(make_postings("Python"), tiny_skills, ["Python"], matcher)
    text = format_summary(res, {})
    assert "(none)" in text
    assert "No missing skills found" in text
