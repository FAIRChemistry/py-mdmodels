from __future__ import annotations

import inspect
from typing import List

from fastmcp import FastMCP
from toon_format import encode

from mdmodels.library import Library

from ..constants import GET_RELATIONSHIPS_DESCRIPTION
from ..relationships_types import TableConnection


def register_relationships_tool(
    *,
    app: FastMCP,
    model: Library,
    available_tables,
) -> None:
    """Register relationship inspection tool returning source/target column mappings.

    This function registers a tool that allows inspection of table relationships
    within a database model. It provides information about foreign key relationships
    between tables, including source and target table/column mappings.

    Args:
        app: The FastMCP application instance to register the tool with
        model: The Library instance containing the database model
        available_tables: Type annotation for available table names

    Returns:
        None
    """

    def get_relationships(table):
        """Get relationship information for a specific table.

        Retrieves all foreign key relationships for the specified table,
        returning detailed information about source and target connections.

        Args:
            table: The name of the table to inspect relationships for

        Returns:
            str: Encoded JSON string containing list of TableConnection objects

        Raises:
            AssertionError: If source or target attributes are missing from connections
        """
        connections = model.get_relations(table)
        table_conns: List[TableConnection] = []
        for _, connection in connections.values():
            assert connection.source_attr is not None, "Source attribute is required"
            assert connection.target_attr is not None, "Target attribute is required"
            table_conns.append(
                TableConnection(
                    source_table=connection.source_type,
                    source_column=connection.source_attr,
                    target_table=connection.target_type,
                    target_column=connection.target_attr,
                )
            )
        return encode(table_conns)

    get_relationships.__annotations__ = {"table": available_tables, "return": str}  # type: ignore[assignment]
    get_relationships.__signature__ = inspect.signature(get_relationships)  # type: ignore[attr-defined]

    app.tool(
        get_relationships,
        name="Get_Table_Relationships",
        description=GET_RELATIONSHIPS_DESCRIPTION,
    )
