# Python MD-Models

![Tests](https://github.com/FairCHemistry/py-mdmodels/actions/workflows/test.yml/badge.svg)
![PyPI - Version](https://img.shields.io/pypi/v/mdmodels)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mdmodels)

Build metadata-first Python apps from Markdown-defined models. `mdmodels` is the Python package for the [MDModels Rust crate](https://github.com/FairCHemistry/md-models), with batteries included for data modeling, AI workflows, SQL/graph backends, and API generation. 🚀

## Why MD-Models?

- 🧩 **Model once** in Markdown, then generate strongly typed Python models
- 🤖 **Work with AI** for extraction, mapping, Q&A, and similarity search
- 🗃️ **Persist and query** with SQL, vectors, and graph databases
- 🌐 **Ship interfaces fast** via REST, GraphQL, and MCP helpers

## What's in the bag? 🎒

- 🧱 **Core model tooling** - Load, inspect, and work with metadata models
- 🐍 **Pydantic generation** - Generate rich Python model classes from MD-Models
- 🤖 **LLM workflows** - Extract, map, search, and answer questions over metadata
- 🗄️ **SQL and vector search** - Build SQL-backed stores and pgvector-style embedding workflows
- 🕸️ **Graph databases** - Build and query graph representations of your models
- 🌐 **API generation** - Expose model-backed services through REST and GraphQL helpers
- 🔌 **MCP integrations** - Create MCP-compatible interfaces for model and SQL workflows

> **Note:** This package is actively evolving and APIs may change. Feedback and contributions are welcome. 🙌

## Installation

We recommend using `uv` for a fast, reproducible Python workflow.

Install `uv` (if needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install the base package:

```bash
uv pip install mdmodels
```

Install optional feature sets:

```bash
# LLM tools
uv pip install "mdmodels[chat]"

# Graph database tools
uv pip install "mdmodels[graph]"

# SQL tools
uv pip install "mdmodels[sql]"

# All available extras
uv pip install "mdmodels[all]"
```

## Documentation 📚

Guides, tutorials, and API usage:

- https://py-mdmodels.vercel.app/

## Development

Run all tests:

```bash
uv run pytest
```

Run tests with coverage report:

```bash
uv run pytest --cov=mdmodels --cov-report=html
```

Run tests in Docker:

```bash
docker build --build-arg PYTHON_VERSION=3.12 -t mdmodels .
docker run -v $(pwd):/app mdmodels
```

Use the helper script:

```bash
./run-tests.sh --python=3.12
```

Skip expensive tests:

```bash
uv run pytest -m "not expensive"
```
