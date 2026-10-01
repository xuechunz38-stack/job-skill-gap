"""Load and validate the skills dictionary CSV (``skill,category,aliases``)."""

from __future__ import annotations

import csv
from pathlib import Path

from job_skill_gap.models import Skill

EXPECTED_HEADER = ("skill", "category", "aliases")
ALIAS_SEPARATOR = "|"
INVALID_NAME_CHARS = (",", "\n", "\r")


class SkillDictionaryError(ValueError):
    """The skills CSV is malformed or ambiguous."""


def normalize_term(term: str) -> str:
    """Lower-case and collapse internal whitespace: the alias lookup key."""
    return " ".join(term.split()).casefold()


def _parse_aliases(name: str, raw: str | None) -> tuple[str, ...]:
    """Canonical name first, then the listed aliases, de-duplicated."""
    candidates = [name]
    if raw:
        candidates.extend(raw.split(ALIAS_SEPARATOR))
    seen: set[str] = set()
    aliases: list[str] = []
    for alias in candidates:
        cleaned = " ".join(alias.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            aliases.append(cleaned)
    return tuple(aliases)


def load_skills(path: str | Path) -> list[Skill]:
    """Read the skills CSV and return validated skills in file order.

    Raises ``FileNotFoundError`` if the file is missing and
    ``SkillDictionaryError`` for malformed CSV (e.g. an unterminated quote or
    an oversized field), a bad header, an empty skill name, a skill name
    containing a comma or line break, a repeated skill name, or one alias
    claimed by two different skills.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Skills file not found: {path}")

    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        # strict=True turns bad quoting (e.g. a missing closing quote) into an
        # error instead of silently swallowing the rest of the file.
        reader = csv.DictReader(handle, strict=True)
        try:
            return _parse_rows(path, reader)
        except csv.Error as exc:
            # line_num is the last line read cleanly; the bad one follows it.
            raise SkillDictionaryError(
                f"{path}: malformed CSV after line {reader.line_num} ({exc})"
            ) from None


def _parse_rows(path: Path, reader: csv.DictReader) -> list[Skill]:
    header = tuple((name or "").strip().lower() for name in reader.fieldnames or [])
    if header != EXPECTED_HEADER:
        raise SkillDictionaryError(
            f"{path}: expected header 'skill,category,aliases', "
            f"got '{','.join(header)}'"
        )
    # DictReader keys are the raw header names; map them to the clean ones.
    raw_names = dict(zip(EXPECTED_HEADER, reader.fieldnames or []))

    skills: list[Skill] = []
    skill_keys: dict[str, int] = {}
    alias_owner: dict[str, str] = {}
    for row in reader:
        line = reader.line_num
        if None in row:
            raise SkillDictionaryError(
                f"{path}, line {line}: too many columns "
                f"(separate aliases with '|', not ',')"
            )
        values = {key: (row.get(raw) or "") for key, raw in raw_names.items()}
        if not any(v.strip() for v in values.values()):
            continue  # blank line
        raw_name = values["skill"].strip()
        if any(ch in raw_name for ch in INVALID_NAME_CHARS):
            raise SkillDictionaryError(
                f"{path}, line {line}: skill name {raw_name!r} contains a comma "
                "or line break (check for a missing or misplaced quote)"
            )
        name = " ".join(raw_name.split())
        if not name:
            raise SkillDictionaryError(f"{path}, line {line}: empty skill name")
        key = normalize_term(name)
        if key in skill_keys:
            raise SkillDictionaryError(
                f"{path}, line {line}: duplicate skill '{name}' "
                f"(first defined on line {skill_keys[key]})"
            )
        skill_keys[key] = line

        aliases = _parse_aliases(name, values["aliases"])
        for alias in aliases:
            alias_key = normalize_term(alias)
            owner = alias_owner.get(alias_key)
            if owner is not None and owner != name:
                raise SkillDictionaryError(
                    f"{path}, line {line}: alias '{alias}' is used by both "
                    f"'{owner}' and '{name}'"
                )
            alias_owner[alias_key] = name

        category = values["category"].strip() or "uncategorized"
        skills.append(Skill(name=name, category=category, aliases=aliases))
    return skills
