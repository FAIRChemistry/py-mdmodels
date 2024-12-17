# Python MD-Models

![Tests](https://github.com/FairCHemistry/py-mdmodels/actions/workflows/test.yml/badge.svg)
![PyPI - Version](https://img.shields.io/pypi/v/mdmodels)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mdmodels)

This is the Python package for the [MDModels Rust crate](https://github.com/FairCHemistry/md-models) and hosts a set of tools to work with metadata models defined in markdown.

**Whats in the bag?**

- **Core** - The core functionality to work with MDModels
- **PyDantic** - Generate Pydantic models (on steroids) from MDModels
- **LLM tools** - Use LLMs to extract, transform and explore data
- **SQL tools** - Create SQL databases and query them with SQLAlchemy
- **Graph tools** - Create graph databases and query them with SPARQL

> **Note:** This package is work in progress and the API will likely change in the future. Issues and contributions are very welcome!

## Installation

To install the package, you can use the following command:

```bash
pip install mdmodels

# LLM tools
pip install mdmodels[chat]

# Graph tools
pip install mdmodels[graph]

# SQL tools
pip install mdmodels[sql]

# All tools
pip install mdmodels[all]
```

## Examples

To get you started, have a look at the [examples](./examples) folder, featuring notebooks that showcase the usage of the package. This is what is available right now:

- [Core](./examples/basic)
  - [Basic](./examples/basic) - Basic usage of the core functionality
- [LLM tools](./examples/llm)
  - [Question Answering](./examples/llm/answering) - Use LLMs to answer questions about the data
  - [Metadata Extraction](./examples/llm/extraction) - Use LLMs to extract metadata from text and to databases
  - [Metadata Mapping](./examples/llm/mapping) - Use LLMs to map metadata from one format to another
  - [Similarity Search](./examples/llm/embedding) - Use LLMs to find similar items in a database
- [SQL tools](./examples/sql)
  - [Basic](./examples/sql/basic) - Create a SQL database and interact with it
- [Graph tools](./examples/graph)
  - [Basic](./examples/graph/basic) - Create a graph database and interact with it

## Development

To run the tests for the package, use the following command:

```bash
# Execute all tests defined in the project
poetry run pytest
```

To run the tests and generate a detailed coverage report, which shows how much of your code is tested, use:

```bash
# Run tests with coverage analysis and generate an HTML report
poetry run pytest --cov=mdmodels --cov-report=html
```

If you want to run the tests within a Docker container, which can help ensure a consistent environment, use the following commands:

```bash
# Build the Docker image, specifying the Python version to use
docker build --build-arg PYTHON_VERSION=3.12 -t mdmodels .

# Run the Docker container, mounting the current directory to /app in the container
docker run -v $(pwd):/app mdmodels
```

To skip tests that are considered expensive and require additional services (like databases or external APIs), you can run:

```bash
# Execute tests while excluding those marked as expensive
poetry run pytest -m "not expensive"
```
