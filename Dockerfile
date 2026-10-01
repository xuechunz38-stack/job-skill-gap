# job-skill-gap — run the CLI against any mounted input folder.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/mpl

WORKDIR /app

# Only what the package needs; sample data and tests are excluded via .dockerignore.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && mkdir -p /data/input /data/output "$MPLCONFIGDIR"

ENTRYPOINT ["job-skill-gap"]
CMD ["--postings", "/data/input/postings", \
     "--skills", "/data/input/skills.csv", \
     "--resume", "/data/input/resume_skills.txt", \
     "--out-dir", "/data/output"]
