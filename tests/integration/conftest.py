from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlmodel import SQLModel

from mdmodels import sql
from mdmodels.datamodel import DataModel
from mdmodels.library import Library
from mdmodels.sql.base import SQLBase

_MODEL_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "model_database.md"

INTEGRATION_TABLE_CONFIG = {
    "Test": sql.TableConfig(primary_key="name"),
}

INTEGRATION_CONNECTOR_KWARGS = {
    "db_type": "sqlite",
    "database": ":memory:",
    "table_config": INTEGRATION_TABLE_CONFIG,
}


@pytest.fixture(scope="session")
def integration_db() -> tuple[sql.DatabaseConnector, Library[SQLBase], Library[DataModel]]:
    """
    One in-memory DB for the integration session.

    Only one DatabaseConnector may be built per process for this model: dynamic
    linking tables register on shared SQLModel metadata and cannot be created twice.
    """
    library = DataModel.from_markdown(str(_MODEL_PATH))
    connector = sql.DatabaseConnector(
        library=library,
        **INTEGRATION_CONNECTOR_KWARGS,
    )
    tables = connector.create_tables()
    return connector, tables, library


@pytest.fixture(autouse=True)
def _clean_integration_db_after_test(
    integration_db: tuple[sql.DatabaseConnector, Library[SQLBase], Library[DataModel]],
) -> Generator[None, None, None]:
    yield
    connector, _, _ = integration_db
    with connector as session:
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(delete(table))
