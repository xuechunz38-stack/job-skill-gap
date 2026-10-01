"""End-to-end CLI runs: exit codes, outputs, stdout/stderr."""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys

import pytest

from job_skill_gap.cli import main
from job_skill_gap.dictionary import load_skills
from job_skill_gap.report import CSV_NAME, PNG_NAME


def _args(postings, skills, resume, out_dir, *extra):
    return [
        "--postings",
        str(postings),
        "--skills",
        str(skills),
        "--resume",
        str(resume),
        "--out-dir",
        str(out_dir),
        *map(str, extra),
    ]


def _sample_args(sample_dir, out_dir, *extra):
    return _args(
        sample_dir / "postings",
        sample_dir / "skills.csv",
        sample_dir / "resume_skills.txt",
        out_dir,
        *extra,
    )


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _assert_no_outputs(out_dir):
    assert not (out_dir / CSV_NAME).exists()
    assert not (out_dir / PNG_NAME).exists()
    assert not out_dir.exists()


# --- typical run on the shipped sample data --------------------------------


def test_sample_run_succeeds(sample_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(_sample_args(sample_dir, out)) == 0
    stdout = capsys.readouterr().out
    assert "postings analyzed" in stdout
    assert (out / CSV_NAME).is_file()
    assert (out / PNG_NAME).read_bytes().startswith(b"\x89PNG")
    rows = _read_csv(out / CSV_NAME)
    assert len(rows) == len(load_skills(sample_dir / "skills.csv"))


def test_sample_alias_and_boundary_sanity(sample_dir, tmp_path, capsys):
    out = tmp_path / "out"
    main(_sample_args(sample_dir, out, "--quiet"))
    rows = {r["skill"]: r for r in _read_csv(out / CSV_NAME)}
    postings = sample_dir / "postings"

    # 02_* only says "sklearn"; it must still count toward scikit-learn.
    p02 = (postings / "02_ml_intern_ecommerce.txt").read_text(encoding="utf-8")
    assert "sklearn" in p02 and "scikit-learn" not in p02
    p01 = (postings / "01_ds_intern_fintech.txt").read_text(encoding="utf-8")
    assert "scikit-learn" in p01
    assert rows["scikit-learn"]["posting_count"] == "2"
    assert rows["scikit-learn"]["have_skill"] == "true"  # resume says "sklearn"

    # 03_* mentions React but not R; R count comes only from 04_* and 06_*.
    assert rows["R"]["posting_count"] == "2"
    assert rows["React"]["posting_count"] == "1"

    # 01_* says Python many times but contributes once: 6 of the 8 postings
    # mention Python (01, 02, 04, 05, 06, 08).
    assert p01.count("Python") > 3
    assert rows["Python"]["posting_count"] == "6"


def test_sample_run_is_deterministic(sample_dir, tmp_path, capsys):
    main(_sample_args(sample_dir, tmp_path / "a", "--quiet"))
    main(_sample_args(sample_dir, tmp_path / "b", "--quiet"))
    a = (tmp_path / "a" / CSV_NAME).read_bytes()
    b = (tmp_path / "b" / CSV_NAME).read_bytes()
    assert a == b


def test_top_option(sample_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(_sample_args(sample_dir, out, "--top", 3)) == 0
    assert (out / PNG_NAME).read_bytes().startswith(b"\x89PNG")


def test_quiet_suppresses_summary(sample_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(_sample_args(sample_dir, out, "--quiet")) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "warning:" in captured.err  # sample includes a no-skill posting
    assert (out / CSV_NAME).exists()


# --- empty postings input: hard error (D7) ---------------------------------


def test_empty_postings_folder_exits_2(tiny_skills_csv, write_file, tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    resume = write_file("resume.txt", "Python\n")
    out = tmp_path / "out"
    assert main(_args(empty, tiny_skills_csv, resume, out)) == 2
    captured = capsys.readouterr()
    assert f"No .txt postings found in {empty}" in captured.err
    assert captured.err.startswith("error: ")
    assert captured.out == ""
    _assert_no_outputs(out)


def test_only_non_txt_postings_exits_2(tiny_skills_csv, write_file, tmp_path, capsys):
    write_file("postings/notes.md", "Python")
    write_file("postings/.DS_Store", b"\x00")
    resume = write_file("resume.txt", "Python\n")
    out = tmp_path / "out"
    assert main(_args(tmp_path / "postings", tiny_skills_csv, resume, out)) == 2
    captured = capsys.readouterr()
    assert "No .txt postings found in" in captured.err
    assert str(tmp_path / "postings") in captured.err
    assert captured.out == ""
    _assert_no_outputs(out)


# --- no missing skills: valid result (exit 0 + warning) --------------------


def test_no_missing_skills_exits_0_with_warning(
    tiny_skills_csv, write_file, tmp_path, capsys
):
    write_file("postings/a.txt", "Python and SQL")
    write_file("postings/b.txt", "sklearn, Python")
    resume = write_file("resume.txt", "Python\nSQL\nscikit-learn\n")
    out = tmp_path / "out"
    assert main(_args(tmp_path / "postings", tiny_skills_csv, resume, out)) == 0
    stdout = capsys.readouterr().out
    assert "No missing skills found" in stdout
    rows = _read_csv(out / CSV_NAME)
    assert len(rows) == 9
    assert all(r["gap_score"] == "0.000" for r in rows)
    assert (out / PNG_NAME).read_bytes().startswith(b"\x89PNG")


def test_every_dictionary_skill_on_resume(sample_dir, tmp_path, write_file, capsys):
    """§7.2 step 7b: resume lists every dictionary skill."""
    names = [s.name for s in load_skills(sample_dir / "skills.csv")]
    resume = write_file("all.txt", "\n".join(names))
    out = tmp_path / "out"
    args = _args(sample_dir / "postings", sample_dir / "skills.csv", resume, out)
    assert main(args) == 0
    assert "No missing skills found" in capsys.readouterr().out
    assert all(r["gap_score"] == "0.000" for r in _read_csv(out / CSV_NAME))


# --- other error paths ------------------------------------------------------


def test_missing_postings_folder_exits_2(tiny_skills_csv, write_file, tmp_path, capsys):
    resume = write_file("resume.txt", "Python\n")
    out = tmp_path / "out"
    code = main(_args(tmp_path / "does/not/exist", tiny_skills_csv, resume, out))
    assert code == 2
    assert "error: Postings folder not found" in capsys.readouterr().err
    _assert_no_outputs(out)


def test_missing_resume_exits_2(sample_dir, tmp_path, capsys):
    args = _args(
        sample_dir / "postings",
        sample_dir / "skills.csv",
        tmp_path / "nope.txt",
        tmp_path / "out",
    )
    assert main(args) == 2
    assert "Resume file not found" in capsys.readouterr().err


def test_alias_collision_exits_1(write_file, sample_dir, tmp_path, capsys):
    skills = write_file("bad.csv", "skill,category,aliases\nA,x,shared\nB,x,shared\n")
    resume = write_file("resume.txt", "A\n")
    out = tmp_path / "out"
    assert main(_args(sample_dir / "postings", skills, resume, out)) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "'A'" in err and "'B'" in err
    assert "Traceback" not in err
    _assert_no_outputs(out)


def test_bad_header_exits_1(write_file, sample_dir, tmp_path, capsys):
    skills = write_file("bad.csv", "name,type\nPython,lang\n")
    resume = write_file("resume.txt", "Python\n")
    assert main(_args(sample_dir / "postings", skills, resume, tmp_path / "o")) == 1


@pytest.mark.parametrize("extra", [[], ["--top", "0"], ["--top", "abc"]])
def test_usage_errors_exit_2(sample_dir, tmp_path, capsys, extra):
    args = _sample_args(sample_dir, tmp_path / "out", *extra) if extra else []
    assert main(args) == 2
    assert "usage:" in capsys.readouterr().err


def test_python_dash_m_entry_point(sample_dir, tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "job_skill_gap", *_sample_args(sample_dir, tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "postings analyzed" in proc.stdout


def test_out_dir_is_a_file_exits_2(sample_dir, tmp_path, write_file, capsys):
    blocker = write_file("out", "I am a file, not a folder")
    assert main(_sample_args(sample_dir, blocker, "--quiet")) == 2
    assert "error: cannot write outputs to" in capsys.readouterr().err


def test_postings_path_is_a_file_exits_2(sample_dir, tmp_path, capsys):
    a_file = sample_dir / "postings" / "01_ds_intern_fintech.txt"
    args = _sample_args(sample_dir, tmp_path / "out")
    args[args.index("--postings") + 1] = str(a_file)
    assert main(args) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: Postings path is not a directory")
    _assert_no_outputs(tmp_path / "out")


@pytest.mark.parametrize(
    "content",
    [
        'skill,category,aliases\n"Python,p,\n',  # unterminated quote
        "skill,category,aliases\nPython,p," + "a" * 200_000 + "\n",  # huge field
        'skill,category,aliases\n"Python, SQL",p,\n',  # comma in skill name
    ],
    ids=["unterminated-quote", "oversized-field", "comma-in-name"],
)
def test_malformed_skills_csv_exits_1_without_traceback(
    write_file, sample_dir, tmp_path, capsys, content
):
    skills = write_file("bad.csv", content)
    resume = write_file("resume.txt", "Python\n")
    out = tmp_path / "out"
    assert main(_args(sample_dir / "postings", skills, resume, out)) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert err.count("\n") == 1  # one line
    assert "Traceback" not in err
    _assert_no_outputs(out)


def test_installed_console_script(sample_dir, tmp_path):
    exe = shutil.which("job-skill-gap")
    if exe is None:
        pytest.skip("job-skill-gap is not on PATH; run `make install` first")
    proc = subprocess.run(
        [exe, *_sample_args(sample_dir, tmp_path / "out")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "8 postings analyzed" in proc.stdout
    assert (tmp_path / "out" / CSV_NAME).is_file()


def test_installed_console_script_error_exit_code(sample_dir, tmp_path):
    exe = shutil.which("job-skill-gap")
    if exe is None:
        pytest.skip("job-skill-gap is not on PATH; run `make install` first")
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "out"
    args = _sample_args(sample_dir, out)
    args[args.index("--postings") + 1] = str(empty)
    proc = subprocess.run([exe, *args], capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    assert proc.stderr == f"error: No .txt postings found in {empty}\n"
    assert not out.exists()
