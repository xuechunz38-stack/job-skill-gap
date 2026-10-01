"""Command-line entry point: parse args, wire modules, map errors to exit codes.

Exit codes: 0 success, 1 invalid input data, 2 bad path or arguments.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from job_skill_gap import __version__
from job_skill_gap.analysis import analyze, collect_warnings
from job_skill_gap.dictionary import SkillDictionaryError, load_skills
from job_skill_gap.loader import NoPostingsError, load_postings, load_resume
from job_skill_gap.matcher import SkillMatcher
from job_skill_gap.report import (
    CSV_NAME,
    PNG_NAME,
    format_summary,
    plot_top_missing,
    write_csv,
)

EXIT_OK = 0
EXIT_BAD_DATA = 1
EXIT_BAD_PATH = 2


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {number}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-skill-gap",
        description=(
            "Compare job postings against your resume skills and rank the "
            "skills you are missing by how many postings ask for them."
        ),
    )
    parser.add_argument(
        "--postings",
        required=True,
        help="folder of job-posting .txt files (non-recursive)",
    )
    parser.add_argument(
        "--skills", required=True, help="skills CSV: skill,category,aliases"
    )
    parser.add_argument(
        "--resume", required=True, help="resume skills file, one skill per line"
    )
    parser.add_argument(
        "--out-dir", default="output", help="output folder (default: output)"
    )
    parser.add_argument(
        "--top",
        type=_positive_int,
        default=10,
        help="number of bars in the chart (default: 10)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="do not print the summary (files are still written)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _error(message: object) -> None:
    print(f"error: {message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # usage errors (2), --help / --version (0)
        return int(exc.code or 0)

    # 1. Load and validate every input before touching the output folder.
    try:
        skills = load_skills(args.skills)
        matcher = SkillMatcher(skills)
        postings = load_postings(args.postings)
        resume_terms = load_resume(args.resume)
    except SkillDictionaryError as exc:
        _error(exc)
        return EXIT_BAD_DATA
    except (NoPostingsError, OSError) as exc:
        _error(exc)
        return EXIT_BAD_PATH

    # 2. Pure analysis.
    result = analyze(postings, skills, resume_terms, matcher)

    # 3. Write outputs.
    out_dir = Path(args.out_dir)
    csv_path = out_dir / CSV_NAME
    png_path = out_dir / PNG_NAME
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        write_csv(result.stats, csv_path)
        plot_top_missing(
            result.stats, png_path, n=args.top, total_postings=result.total_postings
        )
    except OSError as exc:
        _error(f"cannot write outputs to {out_dir}: {exc}")
        return EXIT_BAD_PATH

    # 4. Report.
    if args.quiet:
        for warning in collect_warnings(result):
            print(f"warning: {warning}", file=sys.stderr)
    else:
        print(format_summary(result, {"CSV": csv_path, "Chart": png_path}))
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
