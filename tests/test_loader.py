"""Reading postings folders and resume files."""

from __future__ import annotations

import pytest

from job_skill_gap.loader import NoPostingsError, load_postings, load_resume


def test_reads_only_txt_sorted_by_filename(tmp_path, write_file):
    write_file("postings/b.txt", "second")
    write_file("postings/a.txt", "first")
    write_file("postings/notes.md", "ignored")
    write_file("postings/.DS_Store", b"\x00\x01")
    write_file("postings/sub/c.txt", "not recursive")
    postings = load_postings(tmp_path / "postings")
    assert [p.name for p in postings] == ["a.txt", "b.txt"]
    assert [p.text for p in postings] == ["first", "second"]


def test_uppercase_extension_and_hidden_txt(tmp_path, write_file):
    write_file("postings/A.TXT", "upper")
    write_file("postings/._a.txt", b"\x00\x05\x16\x07")  # macOS resource fork
    assert [p.name for p in load_postings(tmp_path / "postings")] == ["A.TXT"]


def test_empty_folder_raises_with_path(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    with pytest.raises(NoPostingsError) as exc:
        load_postings(folder)
    assert str(exc.value) == f"No .txt postings found in {folder}"


def test_folder_with_only_non_txt_files_raises(tmp_path, write_file):
    write_file("postings/notes.md", "# notes")
    write_file("postings/.DS_Store", b"\x00")
    with pytest.raises(NoPostingsError, match="No .txt postings found in"):
        load_postings(tmp_path / "postings")


def test_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_postings(tmp_path / "does-not-exist")


def test_path_is_a_file(write_file):
    path = write_file("posting.txt", "hello")
    with pytest.raises(NotADirectoryError):
        load_postings(path)


def test_bom_is_stripped(tmp_path, write_file):
    write_file("postings/bom.txt", "﻿Python required".encode("utf-8"))
    (posting,) = load_postings(tmp_path / "postings")
    assert posting.text == "Python required"


def test_invalid_utf8_is_replaced_not_fatal(tmp_path, write_file):
    write_file("postings/cp1252.txt", "“SQL”".encode("cp1252"))
    (posting,) = load_postings(tmp_path / "postings")
    assert "SQL" in posting.text


def test_resume_skips_blanks_and_comments(write_file):
    path = write_file(
        "resume.txt",
        "# my skills\n\n  Python  \nsklearn\n   \n  # indented comment\nSQL\n",
    )
    assert load_resume(path) == ["Python", "sklearn", "SQL"]


def test_resume_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Resume file not found"):
        load_resume(tmp_path / "nope.txt")


def test_resume_is_a_directory(tmp_path):
    with pytest.raises(IsADirectoryError):
        load_resume(tmp_path)
