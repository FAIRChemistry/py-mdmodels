from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from mdmodels.library import Library
from mdmodels.sql.connector import DatabaseConnector


@dataclass(frozen=True)
class RuntimeToolMetadata:
    """Metadata container for runtime tool configuration.

    This dataclass holds all the metadata needed to configure MCP tools at runtime,
    including available models, tables, and embedding-specific information.

    Attributes:
        available_models: Enum of all available database models
        available_tables: Literal type containing all available table names
        embedding_tables: List of table names that have embedding capabilities
        embedding_tables_literal: Literal type for embedding table names
        embed_table_string: Formatted string listing embedding tables for display
        table_string: Formatted string listing all non-internal tables for display
    """

    available_models: Any
    available_tables: Any
    embedding_tables: list[str]
    embedding_tables_literal: Any
    embed_table_string: str
    table_string: str


def build_runtime_tool_metadata(
    *,
    model: Library,
    db_models: Library,
) -> RuntimeToolMetadata:
    """Build runtime metadata for MCP tool configuration.

    This function analyzes the provided model libraries to extract metadata
    needed for configuring MCP tools at runtime. It identifies available models,
    tables with embedding capabilities, and generates formatted strings for
    display purposes.

    Args:
        model: Library containing the domain models/tables
        db_models: Library containing database-specific models

    Returns:
        RuntimeToolMetadata: Container with all runtime configuration metadata
    """
    available_models = model.to_enum()
    available_tables = Literal[*available_models.__members__.keys()]  # type: ignore[misc]

    embedding_tables = DatabaseConnector.embedding_tables(db_models)

    embedding_tables_literal = (
        Literal[*embedding_tables]  # type: ignore[misc]
        if embedding_tables
        else Literal["__no_embedding_tables__"]  # type: ignore[misc]
    )

    embed_table_string = (
        "\n".join([f"- {table}" for table in embedding_tables])
        if embedding_tables
        else "None configured"
    )
    table_string = "\n".join(
        [f"- {table}" for table in model.keys() if not str(table).startswith("_")]
    )

    return RuntimeToolMetadata(
        available_models=available_models,
        available_tables=available_tables,
        embedding_tables=embedding_tables,
        embedding_tables_literal=embedding_tables_literal,
        embed_table_string=embed_table_string,
        table_string=table_string,
    )
