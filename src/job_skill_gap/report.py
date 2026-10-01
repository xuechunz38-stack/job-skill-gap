"""Write the CSV, render the PNG chart and format the terminal summary."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: Docker, CI, SSH sessions

import matplotlib.pyplot as plt  # noqa: E402

from job_skill_gap.analysis import collect_warnings  # noqa: E402
from job_skill_gap.models import AnalysisResult, SkillStat  # noqa: E402

CSV_COLUMNS = (
    "rank",
    "skill",
    "category",
    "posting_count",
    "posting_pct",
    "have_skill",
    "gap_score",
)
CSV_NAME = "skill_gap.csv"
PNG_NAME = "top_missing_skills.png"

# Chart styling: one series -> one hue, recessive chrome.
_BAR = "#2a78d6"
_SURFACE = "#fcfcfb"
_INK = "#0b0b0b"
_INK_2 = "#52514e"
_MUTED = "#898781"
_GRID = "#e1e0d9"


def write_csv(stats: Sequence[SkillStat], path: str | Path) -> Path:
    """Write every skill, in rank order, with fixed formatting (deterministic)."""
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for s in stats:
            writer.writerow(
                [
                    s.rank,
                    s.skill,
                    s.category,
                    s.posting_count,
                    f"{s.posting_pct:.3f}",
                    "true" if s.have_skill else "false",
                    f"{s.gap_score:.3f}",
                ]
            )
    return path


def _style_axes(ax) -> None:
    ax.set_facecolor(_SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(_GRID)
    ax.tick_params(axis="x", colors=_MUTED, labelsize=9)
    ax.tick_params(axis="y", colors=_INK_2, labelsize=10, length=0)
    ax.grid(axis="x", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_top_missing(
    stats: Sequence[SkillStat],
    path: str | Path,
    n: int = 10,
    total_postings: int | None = None,
) -> Path:
    """Horizontal bar chart of the top ``n`` missing in-demand skills.

    With no missing skills, a placeholder figure is written instead so a
    successful run always produces the same set of files.
    """
    path = Path(path)
    missing = [s for s in stats if not s.have_skill and s.posting_count > 0][:n]

    height = 1.6 + 0.42 * max(len(missing), 3)
    fig, ax = plt.subplots(figsize=(8, height), dpi=120)
    fig.patch.set_facecolor(_SURFACE)
    try:
        if not missing:
            ax.set_axis_off()
            ax.text(
                0.5,
                0.5,
                "No missing skills found",
                ha="center",
                va="center",
                fontsize=14,
                color=_INK_2,
                transform=ax.transAxes,
            )
            ax.set_title("Top missing skills", loc="left", color=_INK, fontsize=13)
        else:
            _style_axes(ax)
            ordered = list(reversed(missing))  # largest bar at the top
            labels = [s.skill for s in ordered]
            counts = [s.posting_count for s in ordered]
            bars = ax.barh(labels, counts, color=_BAR, height=0.6)
            ax.bar_label(bars, padding=4, color=_INK_2, fontsize=9)
            ax.set_xlim(0, max(counts) * 1.15)
            ax.xaxis.get_major_locator().set_params(integer=True)
            ax.set_title(
                f"Top {len(missing)} missing skills by posting count",
                loc="left",
                color=_INK,
                fontsize=13,
            )
            of_total = f" (of {total_postings})" if total_postings else ""
            ax.set_xlabel(f"Postings mentioning the skill{of_total}", color=_MUTED)
        fig.tight_layout()
        fig.savefig(path, format="png", facecolor=fig.get_facecolor())
    finally:
        plt.close(fig)
    return path


def format_summary(
    result: AnalysisResult,
    paths: Mapping[str, str | Path],
    top: int = 5,
) -> str:
    """Short plain-text report for the terminal."""
    matched = result.matched_stats
    lines = [
        f"job-skill-gap: {result.total_postings} postings analyzed",
        f"  Skills matched:  {len(matched)} of {len(result.stats)} "
        "dictionary skills appear in at least one posting",
        f"  Already have:    {len(result.owned_in_demand)} of "
        f"{len(matched)} in-demand skills are on your resume",
        "",
        f"Top {top} gaps:",
    ]
    gaps = result.missing[:top]
    if gaps:
        width = max(len(s.skill) for s in gaps)
        for i, s in enumerate(gaps, start=1):
            lines.append(
                f"  {i}. {s.skill:<{width}}  {s.posting_count}/{result.total_postings}"
                f" postings ({s.posting_pct * 100:.1f}%)"
            )
    else:
        lines.append("  (none)")

    lines += ["", "Output files:"]
    lines += [f"  {label}: {p}" for label, p in paths.items()]

    warnings = collect_warnings(result)
    if warnings:
        lines += ["", "Warnings:"]
        lines += [f"  - {w}" for w in warnings]
    return "\n".join(lines)
