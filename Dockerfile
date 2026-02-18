ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential pkg-config && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY mdmodels /app/mdmodels
COPY tests /app/tests

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install uv && \
    uv sync --all-extras --group dev --python ${PYTHON_VERSION}

# Run tests by default.
CMD ["uv", "run", "pytest", "-v", "-m", "not expensive"]
