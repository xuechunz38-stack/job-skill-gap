# job-skill-gap

![CI](https://github.com/xuechunz38-stack/job-skill-gap/actions/workflows/ci.yml/badge.svg)

A small Python 3.11 command-line tool that compares a folder of job postings against
your resume skills and ranks the skills you are missing by how many postings ask for
them.

```
postings/*.txt  ─┐
skills.csv      ─┼─► job-skill-gap ─► skill_gap.csv            (every skill, ranked)
resume.txt      ─┘                 ─► top_missing_skills.png   (top 10 missing skills)
                                   ─► summary on stdout
```

IDS 706 · Week 4 · Option 3. The architecture plan is in [`docs/plan.md`](docs/plan.md).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate   # any Python 3.11+
make install        # pip install -e . + black, flake8, pytest, pytest-cov
make coverage       # optional: pytest with a coverage report
make run            # analyze the sample data into ./output
make all            # format-check + lint + test (same gate as CI)
```

Or with Docker (no local Python needed):

```bash
docker compose run --rm job-skill-gap     # sample data -> ./output
```

## Usage

```bash
job-skill-gap \
  --postings  data/sample/postings \
  --skills    data/sample/skills.csv \
  --resume    data/sample/resume_skills.txt \
  --out-dir   output \
  [--top 10]      # bars in the chart
  [--quiet]       # no summary; warnings still go to stderr
```

`python -m job_skill_gap ...` works the same way.

| Exit code | Meaning |
|-----------|---------|
| `0` | Success, including "no missing skills found" (a warning is printed) |
| `1` | Invalid input data: malformed skills CSV (e.g. a missing closing quote), bad header, comma or line break in a skill name, duplicate skill, alias shared by two skills |
| `2` | Bad path or arguments: missing folder/file, **no `.txt` postings in the folder**, usage errors |

Errors are one line on stderr (`error: No .txt postings found in data/postings`), never
a traceback. All inputs are loaded and validated before the output folder is created,
so a failed run writes nothing.

### Analyze your own postings with Docker

```bash
docker build -t job-skill-gap .
docker run --rm \
  -v "$PWD/my_input:/data/input:ro" \
  -v "$PWD/output:/data/output" \
  job-skill-gap
```

`my_input/` must contain `postings/`, `skills.csv` and `resume_skills.txt`. Sample
data is not baked into the image. If the mount is wrong and the container sees an
empty `/data/input/postings`, it exits with code 2 instead of writing empty results.

## Input formats

**Postings** — every `*.txt` file directly inside the folder (not sub-folders). Other
extensions and hidden files such as `.DS_Store` are ignored. Files are read as UTF-8
(a BOM is fine; undecodable bytes are replaced, not fatal).

**Skills dictionary** — CSV with header `skill,category,aliases`. Aliases are
`|`-separated and may be empty. The skill name always counts as its own alias.
The file is parsed strictly: a malformed row (for example a missing closing quote)
or a skill name containing a comma or line break stops the run with exit code 1
instead of silently producing a wrong skill.

```csv
skill,category,aliases
scikit-learn,data & ml,sklearn|scikit learn
R,programming,R programming|RStudio|R language
SQL,programming,
```

**Resume** — one skill per line; blank lines and `#` comments are ignored. Resume lines
go through the same alias table, so `sklearn` counts as `scikit-learn`. Lines that are
not in the dictionary are listed as a warning, not an error.

## How matching and scoring work

- **Case-insensitive, word-boundary-safe matching.** Instead of `\b`, each alias gets
  a "not next to a letter/digit/`_`" guard (`(?<![A-Za-z0-9_])` / `(?![A-Za-z0-9_])`)
  only on the sides where the alias itself starts or ends with a letter, digit or `_`.
  So `R` does not match `React`, `Java` does not match `JavaScript`, `SQL` does not
  match `NoSQL`, and `Spark` does not match `PySpark`; but a symbol edge is already a
  boundary, so `C++17` counts as `C++` and `C#10` as `C#`. Spaces inside an alias
  match any whitespace, including line breaks.
- **Counted once per posting.** A posting that says "Python" five times, or both
  "sklearn" and "scikit-learn", adds 1 to that skill.
- **Gap score** = `posting_count / total_postings` if the skill is **not** on your
  resume, otherwise `0`. Rounded to 3 decimals, always in `[0, 1]`. The formula lives
  in one function, `analysis.gap_score()`.
- **Ranking** = `posting_count` desc → missing before owned → skill name A–Z. Same
  inputs always give a byte-identical CSV.

## Output

`skill_gap.csv` — one row per dictionary skill, including skills no posting mentions:

```csv
rank,skill,category,posting_count,posting_pct,have_skill,gap_score
1,Python,programming,6,0.750,true,0.000
2,SQL,programming,6,0.750,true,0.000
3,A/B testing,data & ml,4,0.500,true,0.000
4,statistics,data & ml,4,0.500,true,0.000
5,data visualization,analytics & bi,3,0.375,false,0.375
6,Docker,engineering,3,0.375,false,0.375
...
```

`top_missing_skills.png` — the top 10 missing skills (`have_skill = false`,
`posting_count > 0`). When nothing is missing, a placeholder chart saying
"No missing skills found" is written so a successful run always produces both files.

![Top missing skills on the sample data](docs/sample_top_missing_skills.png)

Terminal summary on the sample data:

```text
job-skill-gap: 8 postings analyzed
  Skills matched:  42 of 44 dictionary skills appear in at least one posting
  Already have:    16 of 42 in-demand skills are on your resume

Top 5 gaps:
  1. data visualization  3/8 postings (37.5%)
  2. Docker              3/8 postings (37.5%)
  3. Airflow             2/8 postings (25.0%)
  4. causal inference    2/8 postings (25.0%)
  5. deep learning       2/8 postings (25.0%)

Output files:
  CSV: output/skill_gap.csv
  Chart: output/top_missing_skills.png

Warnings:
  - Postings with no recognized skills: 07_ai_pm_intern_enterprise.txt
  - Resume terms not in dictionary: Wind API
```

## Sample data

`data/sample/` holds 8 data-science / AI-product internship postings, a 44-skill
dictionary and a resume. **The postings are synthetic — I wrote them to exercise the
pipeline, so the counts reflect my assumptions, not the job market.** They
deliberately include the edge cases the tests rely on:

| Posting | Edge case |
|---------|-----------|
| `01_ds_intern_fintech.txt` | says "Python" many times → counts once |
| `02_ml_intern_ecommerce.txt` | says only "sklearn" → counts as `scikit-learn` |
| `03_ai_product_intern_consumer.txt` | mentions React, not R → `R` not counted |
| `07_ai_pm_intern_enterprise.txt` | no dictionary skill at all → warning |

## Project layout

```
src/job_skill_gap/
  models.py      frozen dataclasses (Skill, Posting, SkillStat, AnalysisResult)
  dictionary.py  load + validate skills CSV
  matcher.py     alias regexes; text -> set of skills; resolve one term
  loader.py      postings folder + resume file
  analysis.py    counts, gap score, ranking, warnings (pure)
  report.py      CSV, PNG (matplotlib Agg), summary text
  cli.py         argparse, wiring, exit codes
tests/           pytest suite (one file per module + end-to-end CLI)
data/sample/     sample postings, skills.csv, resume_skills.txt
```

`matcher` and `analysis` do no file IO, so most tests run without touching disk.

## Development

| Command | What it does |
|---------|--------------|
| `make install` | `pip install -e .` + dev requirements |
| `make format` / `make format-check` | black |
| `make lint` | flake8 (max line 88, E203/W503 ignored) |
| `make test` | pytest (no plugins needed) |
| `make coverage` | pytest with a pytest-cov line-coverage report |
| `make run` | CLI on the sample data |
| `make docker-build` / `make docker-run` | build image / `docker compose run` |
| `make clean` | remove caches and generated output |
| `make all` | format-check + lint + test |

CI (`.github/workflows/ci.yml`) runs on every push and pull request: a **quality** job
(black check, flake8, pytest) and a **docker** job that builds the image,
runs it on the sample data, checks both output files exist, and checks that an empty
postings mount fails with exit code 2.

## Known limitations

- **Short or common-word skills can false-positive.** Matching is case-insensitive and
  `&`, `-` and `/` count as boundaries, so with the sample dictionary:
  - "R&D" and "R-squared" both count as `R`;
  - "you excel at communication" counts as `Excel`;
  - "BS/MS in CS, statistics" (a degree field, not a skill) counts as `statistics`.

  `Go` is left out of the sample dictionary for the same reason.
- **Aliases are kept deliberately narrow.** Broad aliases such as "containers"
  (Docker), "experimentation" (A/B testing), "forecasting" (time series),
  "spreadsheets" (Excel), "GitHub" (Git), "BigQuery" (GCP) and "LlamaIndex"
  (LangChain) were removed because they counted postings that do not ask for the
  skill. Add them back in your own dictionary only if you accept that trade-off.
- **The dictionary owns the semantics.** "PostgreSQL" does not count as `SQL` unless
  you list it as an alias. Overlapping skills are all counted: "LLM evaluation" counts
  as both `LLM` and `model evaluation`, and "Spark SQL" as both `Spark` and `SQL`.
- **Symbol edges are not guarded.** An alias that starts or ends with a symbol has no
  boundary check on that side, which is what lets "C++17" count as `C++`. The
  trade-off: with a `.NET` skill, "ASP.NET" also counts as `.NET`.
- **Hyphen/spacing variants are aliases, not automatic.** `scikit learn` matches only
  because it is listed. Whitespace inside an alias is flexible; hyphens are not.
- **Plain English text only.** No PDF/DOCX parsing, no scraping.
- **Symlinked postings are counted twice.** A `.txt` symlink to another posting in the
  same folder is read as a separate posting and adds to every count again.
- **An empty dictionary is not an error.** A skills CSV with only the header exits 0;
  the summary then says "No missing skills found" and lists every posting as having no
  recognized skills, which is misleading.
- **Smaller rough edges:**
  - passing a folder to `--skills` reports "Skills file not found" rather than
    "not a file";
  - unknown resume terms are de-duplicated case-sensitively ("Wind API, wind api");
  - the summary heading always reads "Top 5 gaps:" even when fewer are listed;
  - `make clean` fails if `output/` does not exist;
  - a failed run leaves earlier outputs in the output folder untouched, so they can
    be mistaken for fresh results;
  - letters with accents count as a boundary, so "Pythonés" matches `Python`.
- On Linux hosts, Docker writes `./output` files as root; see the commented `user:` line
  in `docker-compose.yml`. With that line enabled, matplotlib prints a cache-directory
  warning because `/tmp/mpl` in the image is owned by root.

## Future work

- Optional `case_sensitive` column for short skills like `R`.
- Category weights in the gap score.
- PDF/DOCX posting input; fuzzy or embedding-based matching.
- Skip symlinked postings, or de-duplicate them by resolved path.
- Treat a dictionary with no skills as invalid input (exit 1).
- Fix the rough edges above: a "not a file" message for `--skills`, case-insensitive
  de-duplication of unknown resume terms, a "Top N gaps" heading that matches what is
  listed, a `make clean` that tolerates a missing `output/`, clearing stale outputs
  before a run, Unicode-aware boundaries, and a world-writable `/tmp/mpl` in the
  Docker image.

## IDS 706 Week 4: AI-assisted workflow

**Option 3 — new project.** I picked a problem I actually have: I'm applying for
data-science and AI-product internships, and I wanted a repeatable way to see which
skills keep showing up in postings that I can't yet claim.

### Install, run, test

See [Quick start](#quick-start). Any Python 3.11+ works (I used a conda env:
`conda create -n jsg python=3.11`). `make install && make all && make run`, or
`docker compose build && docker compose run --rm job-skill-gap`.

### Manual smoke test (run by me on macOS, before the Tester stage)

| Check | Result |
|---|---|
| `make install` in a fresh Python 3.11 env | ✅ installed |
| `make test` | ✅ 101 passed |
| `make run` on sample data | ✅ 8 postings; top gaps data visualization, Docker (3/8); CSV + PNG written to `output/` |
| Alias / word boundary in output | ✅ posting 02 ("sklearn") counts as scikit-learn; "React" in 03 does not count as R |
| Empty postings folder | ✅ `error: No .txt postings found in /tmp/empty`, `exit=2`, no output folder |
| `docker compose build && docker compose run --rm job-skill-gap` | ✅ image built, same summary as the local run |

Screenshots: [local run](docs/smoke/smoke_local.png) · [Docker run](docs/smoke/smoke_docker.png) ·
[re-check after Tester fixes](docs/smoke/retest_after_tester.png) (125 passed, malformed CSV → exit 1).

### How each AI role contributed

Three fresh conversations with Claude (Cowork); transcripts in
[`docs/transcripts/`](docs/transcripts/).

- **Architect** wrote [`docs/plan.md`](docs/plan.md): requirements, module layout,
  custom word-boundary matching, gap score = share of postings for missing skills,
  exit codes, and a test + smoke-test plan.
- **Builder** implemented the plan (package, 8 sample postings, 101 tests, Docker,
  CI) and listed nine deviations from the plan with reasons.
- **Tester** reviewed the repo independently against the plan and found ten issues,
  ranked. The important ones were real bugs the Builder's 101 tests missed: a
  malformed skills CSV could crash with a traceback or silently create a skill named
  `Python,p,`, and "C++17" did not match `C++`.

### AI recommendations I accepted

- Custom boundary checks instead of `\b`, so `C++`/`C#` work and `R` doesn't match
  "React" (Architect).
- Gap score = share of postings that mention a skill I don't have: simple and
  explainable (Architect). Confirmed "postings with no known skills" should exit 0
  with a warning.
- Strict CSV parsing, symbol-aware boundary guards and removing over-broad aliases
  such as "containers" → Docker (Tester #1–#4); fixed and re-tested.

### Recommendations I changed or rejected

- **Changed (Architect):** the plan exited 0 and wrote empty outputs when the postings
  folder was empty. That almost always means a wrong path or Docker mount, so I made it
  a hard error (exit 2, no outputs).
- **Changed (Builder):** `make test` ran pytest with `--cov`, which the Builder never
  managed to run. I moved coverage to a separate `make coverage` so tests and CI don't
  fail for a reason unrelated to the code.
- **Rejected (Tester #5):** adding a coverage step to CI, for the same reason.
- **Deferred (Tester #8–#10):** symlinked postings, empty dictionary, small message
  issues. They are edge cases for a personal tool, so they are documented under
  [Known limitations](#known-limitations) instead.

### How I verified the result myself

Neither the Builder's nor the Tester's sandbox could install pytest/black/flake8 or
pull Docker images, so their "all checks pass" claims were not enough on their own.
I ran everything on my Mac: `make format-check`, `make lint`, `make test`
(**125 passed** after the fixes), `make run`, the empty-folder and malformed-CSV error
paths, and the Docker build + run. GitHub Actions runs the same checks plus the
Docker job on every push.
