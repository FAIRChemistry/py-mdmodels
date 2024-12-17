ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY . .

RUN python3 -m pip install poetry pytest-cov pytest-httpx
RUN poetry install --extras "chat" --extras "graph" --extras "sql" --extras "dev"

CMD ["python3", "-m", "poetry", "run", "pytest", "-vv", "-m", "not expensive", "--cov=mdmodels"]
