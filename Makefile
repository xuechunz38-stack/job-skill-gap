PYTHON  ?= python3
SRC     := src tests
SAMPLE  := data/sample
OUT_DIR ?= output
IMAGE   ?= job-skill-gap:latest

.PHONY: help install format format-check lint test coverage run docker-build docker-run clean all

help:
	@echo "Targets: install format format-check lint test coverage run docker-build docker-run clean all"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -r requirements-dev.txt

format:
	$(PYTHON) -m black $(SRC)

format-check:
	$(PYTHON) -m black --check --diff $(SRC)

lint:
	$(PYTHON) -m flake8 $(SRC)

test:
	$(PYTHON) -m pytest -v

# Optional: needs pytest-cov (in requirements-dev.txt). Not part of `all` or CI.
coverage:
	$(PYTHON) -m pytest -v --cov=job_skill_gap --cov-report=term-missing

run:
	$(PYTHON) -m job_skill_gap \
		--postings $(SAMPLE)/postings \
		--skills $(SAMPLE)/skills.csv \
		--resume $(SAMPLE)/resume_skills.txt \
		--out-dir $(OUT_DIR)

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker compose run --rm job-skill-gap

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .coverage htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find $(OUT_DIR) -mindepth 1 ! -name .gitkeep -delete

all: format-check lint test
