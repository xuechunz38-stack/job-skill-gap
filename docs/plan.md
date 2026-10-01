# job-skill-gap — Architecture Plan

IDS 706 · Week 4 · Option 3 (new project)
Status: **implemented** · Rev 3 — updated to match the code after review

**Revision history**
- Rev 1 — initial plan.
- Rev 2 — empty postings input is a hard error (exit 2).
- Rev 3 — brought in line with the implementation after the tester's review:
  `make test` runs plain pytest and coverage has its own `make coverage` target, kept out
  of CI on purpose (D12, D13, §6.7, §7.1); the skills CSV is parsed strictly and
  malformed rows or comma/line-break skill names are errors (F2, D6); boundary guards
  apply only to an alias's word-character edges so `C++17` / `C#10` match (D1); over-broad
  sample aliases removed (R1); `analyze()` takes resume terms and `AnalysisResult` lives in
  `models.py` (§3.1); test plan extended (§6).

---

## 1. Goal

A Python 3.11 command-line tool that compares a set of job postings against my resume and tells me which skills I'm missing, ranked by how often employers ask for them.

```
postings/*.txt  ─┐
skills.csv      ─┼─► job-skill-gap ─► skill_gap.csv        (every skill, ranked)
resume.txt      ─┘                 ─► top_missing.png      (top 10 missing skills)
                                   ─► summary on stdout
```

---

## 2. Requirements

### 2.1 Functional

| ID | Requirement |
|----|-------------|
| F1 | Read every `*.txt` file in a postings folder (non-recursive). Other file types are ignored. If the folder contains **no `.txt` files** (empty, or only other file types), the CLI fails with a non-zero exit code and the error `No .txt postings found in <path>`, and writes no output files. |
| F2 | Read a skills dictionary CSV with header `skill,category,aliases`; `aliases` is a `|`-separated list (may be empty). The canonical `skill` name always counts as its own alias. The CSV is parsed strictly: malformed CSV (unterminated quote, oversized field, stray quote) and skill names containing a comma or line break are errors (exit 1), never a traceback or a silently wrong skill. |
| F3 | Read a resume skills file: one skill per line; blank lines and lines starting with `#` are ignored. Resume entries are resolved through the **same alias table** (so `sklearn` on the resume = `scikit-learn`). |
| F4 | Matching is case-insensitive and respects word boundaries (`R` must not match `React`, `Java` must not match `JavaScript`, `SQL` must not match `NoSQL`). |
| F5 | A skill is counted **at most once per posting**, no matter how many times or via how many aliases it appears. |
| F6 | Output CSV contains **every** dictionary skill (including 0-count skills) with columns: `rank, skill, category, posting_count, posting_pct, have_skill, gap_score`. |
| F7 | Output PNG: horizontal bar chart of the top 10 missing skills (`have_skill = False`, `posting_count > 0`) by posting count. |
| F8 | Print a short terminal summary: postings analyzed, skills matched, how many in-demand skills I already have, top 5 gaps, paths of written files, and any warnings. If postings exist but **no missing skills** are found, exit 0 with a warning (this is a legitimate result, not an input mistake). |
| F9 | Ship ~8 sample postings (data-science / AI-product internships), a sample skills CSV and a sample resume so `make run` works out of the box. |

### 2.2 Non-functional

| ID | Requirement |
|----|-------------|
| N1 | Python 3.11; `src/` layout; installable with `pip install -e .`; exposes a `job-skill-gap` console command and `python -m job_skill_gap`. |
| N2 | Deterministic output: same inputs → byte-identical CSV (stable sort order, fixed float rounding). |
| N3 | Code formatted with **black**, lint-clean under **flake8**. |
| N4 | **pytest** suite covering typical and edge cases (§6). |
| N5 | **Makefile** wrapping install / format / lint / test / run / docker tasks. |
| N6 | **Dockerfile** + **docker-compose.yml** that run the CLI with an input folder mounted read-only and an output folder mounted read-write. |
| N7 | **GitHub Actions** CI running format check, lint, tests, and a Docker smoke run; status badge in README. |
| N8 | Minimal dependencies: runtime = `matplotlib` only (CSV via stdlib `csv`, CLI via stdlib `argparse`). |

### 2.3 Out of scope (v1)

PDF/DOCX parsing, web scraping, NLP/embedding-based fuzzy matching, skill-level weighting by seniority, a web UI.

---

## 3. Proposed file layout

```
job-skill-gap/
├── .github/
│   └── workflows/
│       └── ci.yml                 # format + lint + test + docker smoke
├── src/
│   └── job_skill_gap/
│       ├── __init__.py            # __version__
│       ├── __main__.py            # `python -m job_skill_gap` → cli.main()
│       ├── cli.py                 # argparse, orchestration, exit codes
│       ├── models.py              # dataclasses: Skill, Posting, SkillStat
│       ├── dictionary.py          # load + validate skills CSV → list[Skill]
│       ├── matcher.py             # compile alias regexes; text → set[skill]
│       ├── loader.py              # read postings folder + resume file
│       ├── analysis.py            # counts, gap score, ranking (pure)
│       └── report.py              # write CSV, render PNG, format summary
├── tests/
│   ├── conftest.py                # shared fixtures (tiny dictionary, tmp folders)
│   ├── test_dictionary.py
│   ├── test_matcher.py
│   ├── test_loader.py
│   ├── test_analysis.py
│   ├── test_report.py
│   └── test_cli.py                # end-to-end on tmp_path + on data/sample
├── data/
│   └── sample/
│       ├── postings/              # 8 hand-written .txt postings
│       │   ├── 01_ds_intern_fintech.txt
│       │   ├── 02_ml_intern_ecommerce.txt
│       │   ├── 03_ai_product_intern_consumer.txt
│       │   ├── 04_data_analyst_intern_health.txt
│       │   ├── 05_llm_apps_intern_startup.txt
│       │   ├── 06_product_analytics_intern_social.txt
│       │   ├── 07_ai_pm_intern_enterprise.txt
│       │   └── 08_mle_intern_recsys.txt
│       ├── skills.csv             # ~35 skills across 5–6 categories
│       └── resume_skills.txt      # my current skills
├── docs/
│   └── plan.md                    # this file
├── output/                        # generated; git-ignored (keep .gitkeep)
├── .flake8                        # max-line-length 88, ignore E203/W503
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml                 # metadata, deps, console script, black + pytest config
├── requirements-dev.txt           # black, flake8, pytest, pytest-cov
└── README.md                      # badge, usage, sample output, design notes
```

### 3.1 Module responsibilities

| Module | Responsibility | Pure? |
|--------|----------------|-------|
| `models.py` | Frozen dataclasses. `Skill(name, category, aliases: tuple[str, ...])`, `Posting(name, text)`, `SkillStat(skill, category, posting_count, posting_pct, have_skill, gap_score, rank)`, `AnalysisResult` (stats plus per-posting matches, postings without matches, owned skills, unknown resume terms; `matched_stats` / `missing` / `owned_in_demand` views). | yes |
| `dictionary.py` | `load_skills(path) -> list[Skill]`. Parses with `csv.DictReader(strict=True)`, validates header, strips whitespace, drops empty aliases, adds canonical name as alias, de-dupes aliases, **raises `SkillDictionaryError`** for malformed CSV (`csv.Error` is caught and re-raised), an empty skill name, a skill name containing a comma or line break, too many columns, a repeated skill name, or the same alias mapping to two different skills. | IO at edge |
| `matcher.py` | `SkillMatcher(skills)` compiles one regex per skill (alternation of escaped, individually guarded aliases, longest first; a skill with no aliases never matches). `find(text) -> set[str]` returns canonical names. `resolve(term) -> str \| None` maps a single resume term to a canonical skill. | yes |
| `loader.py` | `load_postings(folder) -> list[Posting]` (sorted by filename, UTF-8 with BOM handling, `errors="replace"`); `load_resume(path) -> list[str]`. Raises `FileNotFoundError` / `NotADirectoryError` with clear messages, and `NoPostingsError("No .txt postings found in <path>")` when the folder has zero `.txt` files. | IO |
| `analysis.py` | `analyze(postings, skills, resume_terms, matcher) -> AnalysisResult`: resolves resume terms through the matcher (`resolve_resume`), then counts, scores and ranks. Also `gap_score()` and `collect_warnings(result)`. No file IO, no printing. | yes |
| `report.py` | `write_csv(stats, path)`, `plot_top_missing(stats, path, n=10)`, `format_summary(result, paths) -> str`. Uses matplotlib `Agg` backend. | IO |
| `cli.py` | Parse args, wire modules together, print summary, map exceptions → exit codes. Thin; no business logic. | IO |

### 3.2 CLI contract

```
job-skill-gap \
  --postings  data/sample/postings \
  --skills    data/sample/skills.csv \
  --resume    data/sample/resume_skills.txt \
  --out-dir   output \
  [--top 10]                # bars in the chart
  [--quiet]                 # suppress summary (files still written)
```

Outputs: `<out-dir>/skill_gap.csv`, `<out-dir>/top_missing_skills.png` (out-dir created if missing).

Exit codes:

| Code | Meaning | Examples |
|------|---------|----------|
| `0` | Success | Normal run; also postings found but **no missing skills** (warning printed, outputs written). |
| `1` | Invalid input data | Malformed skills CSV, bad header, comma/line break in a skill name, duplicate skill, alias collision between skills. |
| `2` | Bad input path or arguments | Postings path missing / not a directory; **no `.txt` postings found in the folder**; argparse usage errors. |

All errors go to stderr as one readable line (`error: No .txt postings found in data/postings`), never a traceback. Inputs are fully loaded and validated **before** the output directory is created, so a failed run leaves no partial or empty outputs behind.

---

## 4. Key design decisions

### D1 — Word-boundary matching with custom lookarounds, not `\b`
`\b` breaks on skills that start or end in non-word characters (`C++`, `C#`, `.NET`). Each alias is compiled as:

```
[(?<![A-Za-z0-9_])]  <re.escape(alias) with spaces → \s+>  [(?![A-Za-z0-9_])]
```
with `re.IGNORECASE`, where each bracketed guard is added **only if the alias's first / last character is a word character** (ASCII letter, digit or `_`). A word-character edge is where gluing creates a different word, so it is guarded: `R` ✗ `React`, `Java` ✗ `JavaScript`, `SQL` ✗ `NoSQL`/`MySQL`, `Spark` ✗ `PySpark`, `C` ✗ `C99`. A symbol edge is already a boundary, so it is not: `C++17` → `C++`, `C#10` → `C#` (Rev 2 guarded both sides, which missed version suffixes). Trade-off: with a `.NET` skill, `ASP.NET` counts as `.NET`. Each alias carries its own guards inside the alternation. Multi-word aliases (`machine learning`) tolerate line breaks/multiple spaces between words.

### D2 — Count presence per posting, not occurrences
`find()` returns a `set` of canonical names, so "Python, Python, python" or "sklearn … scikit-learn" in one posting = 1. This is the "document frequency" — what we actually want to know is *how many employers* ask for a skill.

### D3 — Gap score definition
```
posting_pct = posting_count / total_postings          (0.0 when total_postings == 0)
gap_score   = posting_pct  if not have_skill  else 0.0
```
Rounded to 3 decimals. Simple, explainable, bounded in [0, 1], and directly "how much of the market am I missing by not having this." Kept in one function (`gap_score()`) so it's easy to swap later (e.g., category weights).

### D4 — Ranking and determinism
CSV sorted by `posting_count` desc → `have_skill` (missing first) → `skill` name asc. `rank` is 1-based dense position in that order. Postings read in sorted filename order. Floats formatted with fixed precision.

### D5 — One alias table for postings *and* resume
The resume goes through `matcher.resolve()`. Unrecognized resume terms are **not** an error: they're collected and listed as a warning in the summary ("not in dictionary: Tableau Prep"), because the user's resume may contain skills the dictionary doesn't track.

### D6 — Fail fast on dictionary ambiguity and malformed CSV
Two skills sharing an alias makes results order-dependent and silently wrong, so `load_skills` raises with both skill names in the message. Duplicate aliases *within* one skill are silently de-duplicated.

The same reasoning applies to malformed CSV. With default (non-strict) parsing, an unterminated quote silently swallows the rest of the file into one skill named e.g. `Python,p,`, and an oversized field raises a raw `csv.Error` traceback. So the CSV is read with `strict=True`, every `csv.Error` becomes `SkillDictionaryError` (`<path>: malformed CSV after line N (<reason>)`, exit 1), and a skill name containing a comma or line break, which is almost always a misplaced quote, is rejected. Quoted aliases may still contain commas.

### D7 — Empty postings input is an error; "no gaps" is not
- **No `.txt` postings in the folder** (empty folder, or only `.md`/`.DS_Store`/etc.) almost always means the wrong path was passed. Writing a zero-filled CSV and exiting 0 would hide that mistake — especially in Docker, where a wrong volume mount silently yields an empty `/data/input/postings`. So `load_postings` raises `NoPostingsError`, the CLI prints `error: No .txt postings found in <path>` and exits **2**, and no output files are written.
- **Postings exist but every demanded skill is already on the resume** (or no posting mentions a dictionary skill) is a valid, if unusual, result. The CLI exits **0**, writes the full CSV, writes the PNG as a placeholder figure with a centered "No missing skills found" message, and prints a warning. Output shape stays stable for successful runs.
- `analysis.analyze()` still guards against `total_postings == 0` (pct = 0.0) so the pure function is safe if called directly as a library, but the CLI never reaches that path.

### D8 — Pure core, thin IO shell
`matcher` and `analysis` take strings/dataclasses and return dataclasses — no filesystem, no printing. 80%+ of tests run without touching disk; only `loader`, `report`, `cli` tests use `tmp_path`.

### D9 — Minimal dependencies
No pandas: stdlib `csv` is enough for ~50 rows and keeps the Docker image small and install fast in CI. matplotlib is the only runtime dependency; it's forced to the `Agg` backend so it works headless (Docker, CI).

### D10 — Packaging via `pyproject.toml` (setuptools, src layout)
The src layout guarantees tests run against the installed package, not stray files in the repo root. Console script entry point: `job-skill-gap = job_skill_gap.cli:main`.

### D11 — Docker
- Base `python:3.11-slim`; install with `pip install --no-cache-dir .`.
- `ENV MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl` (matplotlib needs a writable config dir).
- `ENTRYPOINT ["job-skill-gap"]`, default `CMD` points at `/data/input/...` and `/data/output`.
- `docker-compose.yml` mounts `./data/sample:/data/input:ro` and `./output:/data/output`.
- Sample data is **not** baked into the image (`.dockerignore` excludes `data/`, `output/`, `tests/`) so the image is reusable with any input.

### D12 — CI
`.github/workflows/ci.yml`, triggered on push and pull_request:
1. **quality** job: checkout → setup-python 3.11 (pip cache) → `make install` → `make format-check` → `make lint` → `make test` (plain pytest, **no coverage**).
2. **docker** job (needs quality): `docker compose build` → `docker compose run --rm job-skill-gap` → assert both output files exist → wrong-mount check (empty postings mount exits 2 with the expected message and writes nothing).

Coverage is deliberately **not** run in CI, not even as an optional step: the `--cov` path was never verified in CI, and an optional step would add noise without changing what CI checks. Coverage is measured locally with `make coverage` (§6.7).

README badge: `![CI](https://github.com/xuechunz38-stack/job-skill-gap/actions/workflows/ci.yml/badge.svg)` (adjust if the repo name differs).

### D13 — Makefile targets
`install` (pip install -e . + dev reqs) · `format` (black) · `format-check` (black --check --diff) · `lint` (flake8) · `test` (plain `pytest -v`, no plugins needed) · `coverage` (`pytest -v --cov=job_skill_gap --cov-report=term-missing`; needs pytest-cov from requirements-dev.txt; not part of `all` or CI) · `run` (CLI on sample data) · `docker-build` · `docker-run` (compose) · `clean` · `all` = format-check lint test.

---

## 5. Risks and design concerns

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | **Short / common-word skills and broad aliases** — case-insensitive `R` matches "R&D" and "R-squared"; `Go` matches the verb "go"; `Excel` matches "excel at"; `statistics` matches a degree field; broad aliases ("containers", "forecasting", "BigQuery"…) count postings that don't ask for the skill. | False positives inflate counts. | Keep `Go` out of the sample dictionary; for `R`, rely on boundaries and add aliases like `R programming`, `RStudio`. Rev 3: removed the over-broad sample aliases (containers, experimentation, forecasting, spreadsheets, GitHub, BigQuery, LlamaIndex). Remaining false positives documented in README Known limitations. Possible v2: optional `case_sensitive` column in the CSV. |
| R2 | **Overlapping skills** — `machine learning` vs `deep learning`; `SQL` vs `PostgreSQL`. | Both counted (correct), but a posting saying "PostgreSQL" won't count generic `SQL` unless listed as alias. | Explicit design choice: dictionary owns semantics. Document; the user adds `postgresql` as alias of `SQL` if desired. |
| R3 | **Alias collisions** between skills. | Wrong attribution. | D6 — validation error at load time + test. |
| R4 | **Regex special characters** in aliases (`C++`, `C#`, `.NET`), including version suffixes (`C++17`, `C#10`). | Crashes, missed or wrong matches. | `re.escape` + edge-dependent lookarounds (D1) + dedicated tests. |
| R5 | **Hyphen / spacing variants** (`scikit learn`, `scikit-learn`, `large language models` across a line break). | Missed matches. | Whitespace → `\s+` in patterns; hyphen variants are listed as aliases rather than auto-normalized (keeps behavior predictable). |
| R6 | **File encoding** (BOM, Windows-1252 smart quotes). | `UnicodeDecodeError`. | Read as `utf-8-sig` with `errors="replace"`. Test with a BOM file. |
| R7 | **Wrong or empty postings path** (typo, wrong Docker volume mount). | Silently empty results that look like "no skills in demand". | D7 — hard error with exit 2 and the offending path in the message; outputs not written. Defensive pct = 0.0 guard kept in `analysis`. |
| R8 | **Docker volume permissions** — container writes to a host-mounted `output/` as root (Linux hosts may get root-owned files). | Annoying cleanup on Linux; fine on macOS Docker Desktop. | Document; optional `user: "${UID}:${GID}"` in compose. |
| R9 | **matplotlib headless issues** in CI/Docker. | Test or run failures. | Force `Agg`, set `MPLCONFIGDIR`. Tests check the PNG exists and starts with PNG magic bytes — no pixel comparison. |
| R10 | **Sample data bias** — I wrote the postings myself, so counts reflect my assumptions, not the market. | Misleading conclusions if presented as real data. | README states clearly that samples are synthetic and for demonstrating the pipeline; the tool is meant to be pointed at real postings. |
| R11 | **Scope creep** (fuzzy matching, scraping, LLM extraction). | Missing the Week 4 deadline. | v1 scope frozen in §2.3; ideas go to a "Future work" section in README. |

---

## 6. Testing plan

All tests use pytest; fixtures in `conftest.py` provide a small in-memory dictionary (≈8 skills incl. `R`, `React`, `Java`, `JavaScript`, `SQL`, `scikit-learn|sklearn`, `C++`, `machine learning`).

### 6.1 `test_matcher.py` (core, most important)

| Case | Input | Expected |
|------|-------|----------|
| Typical | "Experience with Python and SQL" | `{Python, SQL}` |
| Alias | "Familiar with sklearn" | `{scikit-learn}` |
| Alias + canonical in same text | "sklearn / scikit-learn" | `{scikit-learn}` (once) |
| Word boundary R/React | "Build UIs in React" | `{React}` — **not** `R` |
| R standalone | "Statistics in R, Python" | contains `R` |
| Java vs JavaScript | "JavaScript developer" | `{JavaScript}` only |
| SQL vs NoSQL | "NoSQL stores" | no `SQL` |
| Special chars | "C++ and C#" | `C++` matched |
| Case insensitive | "PYTHON", "python", "PyThOn" | `Python` each |
| Multi-word over line break | "machine\nlearning" | `machine learning` |
| Duplicates | "Python Python python" | `{Python}` (set of size 1) |
| No known skill | "We value teamwork and curiosity." | `set()` |
| Empty string | "" | `set()` |
| Punctuation adjacency | "(Python), SQL." | both matched |
| `resolve()` | "sklearn" / "SKLEARN" / "Tableau Prep" | `scikit-learn` / `scikit-learn` / `None` |
| Version suffix | "C++17", "C++20 or newer", "C#10" | `C++` / `C#` matched |
| Word edge still guarded | "Embedded C99" (skill `C`), "ObjC++" | no match |
| Symbol edge trade-off | "ASP.NET" (skill `.NET`) | `.NET` matched (documented) |
| Guard construction | `R`, `C++`, `.NET`, `C#` | guards only on word-character edges |
| No aliases | skill with empty alias tuple | never matches |

### 6.2 `test_dictionary.py`
- Loads valid CSV; canonical name included in aliases; whitespace stripped; empty `aliases` field OK.
- Alias collision across two skills → `SkillDictionaryError` naming both.
- Duplicate skill name → error.
- Missing/wrong header → error.
- Empty file (header only) → empty list (CLI then warns).
- Malformed CSV → `SkillDictionaryError` ("malformed CSV"), not `csv.Error`: unterminated quote, stray quote after a quoted field, field over the csv size limit.
- Skill name containing a comma, `\n` or `\r\n` → error; a quoted *alias* containing a comma is still allowed.

### 6.3 `test_loader.py`
- Reads only `.txt`, ignores `.md` / `.DS_Store`, sorted by filename.
- **Empty folder** → raises `NoPostingsError`; message contains the folder path.
- Folder containing only non-`.txt` files (`notes.md`, `.DS_Store`) → raises `NoPostingsError`.
- Non-existent folder → `FileNotFoundError`; path is a file → `NotADirectoryError`.
- BOM-prefixed file decoded correctly.
- Resume: blank lines and `#` comments skipped; whitespace trimmed.

### 6.4 `test_analysis.py`
- 3 postings, hand-computed expected counts, pct, gap scores, ranks.
- Duplicate mentions in one posting count once toward `posting_count`.
- Owned skill → `gap_score == 0.0` even if most frequent.
- 0 postings passed directly to `analyze()` (library use) → all counts 0, pct 0.0, no `ZeroDivisionError`.
- All demanded skills owned → every `gap_score == 0.0`, missing list empty.
- Posting with no known skill → appears in `postings_without_matches`, does not affect counts.
- Unknown resume term → listed in `unknown_resume_terms`.
- Deterministic tie-breaking (equal counts → alphabetical).
- Every dictionary skill present in output, including 0-count ones.

### 6.5 `test_report.py`
- CSV has exact header and one row per skill; values round-trip via `csv.DictReader`; `have_skill` written as `true/false`.
- PNG created, non-empty, begins with `\x89PNG`.
- Fewer than 10 missing skills → chart still created; 0 missing → placeholder chart created.
- `format_summary` contains posting count, top gaps, output paths, warnings.

### 6.6 `test_cli.py` (end-to-end)
- Run `main([...])` on `data/sample` into `tmp_path` → exit 0, both files exist, CSV row count = dictionary size, stdout contains "postings analyzed".
- **Empty postings folder** → exit code 2; stderr contains `No .txt postings found in` + the path; stdout has no summary; `out-dir` does not exist / contains no `skill_gap.csv` or PNG.
- **Folder with only non-`.txt` files** → same as above (exit 2, same message).
- **No missing skills** (resume covers every skill that appears in the postings) → exit 0; warning `No missing skills found` in output; CSV written with all `gap_score = 0`; placeholder PNG written.
- Missing postings folder → exit 2, error on stderr.
- Bad skills CSV (alias collision) → exit 1.
- Malformed skills CSV (unterminated quote, oversized field, comma in skill name) → exit 1, one-line `error:` on stderr, no traceback, no outputs.
- `--postings` pointing at a file → exit 2 (`Postings path is not a directory`), no outputs.
- Installed `job-skill-gap` console script (subprocess): sample run exits 0; empty postings folder exits 2 with the exact error line. Skipped if the command is not on PATH.
- `--top 3` → chart produced (smoke).
- Sanity on sample data: `scikit-learn` count includes the posting that only says "sklearn"; `R` count excludes the posting that only says "React"; `Python` count is exactly 6 even though posting 01 says it many times.

### 6.7 Coverage target
≥ 90% line coverage on `matcher`, `dictionary`, `analysis`; overall ≥ 85%. Measured **locally** with `make coverage`; not run in CI and not a gate (see D12).

---

## 7. Verification steps

### 7.1 Local quality gate
```bash
make install          # pip install -e . + dev deps
make format-check     # black --check src tests
make lint             # flake8 src tests
make test             # pytest -v (no coverage)
make coverage         # optional, local only: pytest --cov report (needs pytest-cov)
```
`install`, `format-check`, `lint` and `test` must pass before every commit (same as CI). `make coverage` is for checking §6.7 by hand.

### 7.2 Manual smoke test (local)
1. `make run` → terminal shows summary; `output/skill_gap.csv` and `output/top_missing_skills.png` exist.
2. Open the CSV: one row per dictionary skill; sorted by `posting_count` desc; owned skills have `gap_score = 0`; `posting_pct` ≤ 1.
3. Spot-check **alias**: posting `02_*` uses only "sklearn" → `scikit-learn` count includes it.
4. Spot-check **boundary**: posting `03_*` mentions "React" but not R → `R` count does not include it.
5. Spot-check **duplicates**: pick a posting that says "Python" several times → contributes 1.
6. Open the PNG: ≤ 10 bars, all skills not on my resume, sorted, labels readable, title/axis labels present.
7. Edge — empty folder: `mkdir /tmp/empty && job-skill-gap --postings /tmp/empty --out-dir /tmp/out ...` → `error: No .txt postings found in /tmp/empty`, `echo $?` prints 2, `/tmp/out` not created.
   Repeat after `touch /tmp/empty/notes.md` → same error.
7b. Edge — no missing skills: copy every skill name from `skills.csv` into a temporary resume file and run against the sample postings → exit 0, warning "No missing skills found", CSV with all `gap_score = 0`, placeholder PNG.
8. Edge — no-skill posting: add a `.txt` with "We like curious people." → summary lists it under postings with no recognized skills; other counts unchanged, `posting_pct` denominator +1.
9. Edge — bad path: `--postings does/not/exist` → readable error, `echo $?` prints 2.
10. Edit `resume_skills.txt` to add a top missing skill → re-run → that skill moves to `have_skill = true`, `gap_score = 0`, drops off the chart.

### 7.3 Docker smoke test
```bash
make docker-build
docker compose run --rm job-skill-gap
ls output/            # skill_gap.csv, top_missing_skills.png
```
Also run once with a custom mount to prove the image isn't tied to sample data:
`docker run --rm -v "$PWD/my_postings:/data/input/postings:ro" ... job-skill-gap`.
Wrong-mount check: mount an empty host folder as `/data/input/postings` → container exits with code 2 and prints `No .txt postings found in /data/input/postings`; nothing new appears in `output/`.

### 7.4 CI
Push a branch → Actions tab shows both jobs green → README badge renders "passing". Deliberately push a black-violating change once on a branch to confirm the gate fails, then revert.

---

## 8. Implementation order (milestones)

1. Scaffold: `pyproject.toml`, `.flake8`, `.gitignore`, Makefile, empty package, one trivial test → `make all` green. Commit.
2. `models` + `dictionary` + tests.
3. `matcher` + full matcher test table (the riskiest logic — do it early).
4. `loader` + tests.
5. `analysis` + tests.
6. Sample data (8 postings, skills.csv, resume) — deliberately include the sklearn-only, React-only, repeated-Python, and no-skill cases.
7. `report` + `cli` + end-to-end tests; `make run` works.
8. Dockerfile + docker-compose + `.dockerignore`; docker smoke test.
9. GitHub Actions + badge; README (usage, sample output screenshot, design decisions summary, limitations, future work).
10. Run full §7 checklist; tag `v0.1.0`.

---

## 9. Definition of done

- [ ] `make all` passes locally; CI green; badge visible in README.
- [ ] `make run` and `docker compose run --rm job-skill-gap` both produce the CSV + PNG from sample data.
- [ ] Every edge case listed in the assignment has at least one named test: empty folder (non-zero exit + message, no outputs), no-missing-skills (exit 0 + warning), no-known-skill posting, alias (`sklearn`), word boundary (`R`/`React`), case insensitivity, duplicate mentions.
- [ ] README explains install, usage, input formats, gap-score formula, limitations (R1, R10).
- [ ] Manual smoke test (§7.2) completed and noted in README or PR description.

---

## 10. Assumptions / open questions

- GitHub repo is `xuechunz38-stack/job-skill-gap` (confirmed; badge URL uses this).
- Resume input is a skills list, not a full resume — no parsing of free-form resume text in v1.
- "Gap score" uses the simple frequency-if-missing formula (D3); if the course expects a weighted score (e.g., by category), only `analysis.gap_score()` changes.
- Postings are English plain text.
