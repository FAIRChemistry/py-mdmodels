from __future__ import annotations

import inspect
from typing import Annotated, List, Literal

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from toon_format import encode

from mdmodels.library import Library
from mdmodels.sql import FilterTask, select
from mdmodels.sql.base import SQLBase

from ..constants import ISS, SELECT_DESCRIPTION, SUBJECT
from ..middleware import CTX_SESSION
from ..ownership import get_owned_ids, is_scoped


def register_select_tool(
    *,
    app: FastMCP,
    db_models: Library[SQLBase],
    available_tables,
    available_models,
    shared_tables: set[str],
) -> None:
    """Register select_from_table tool with optional filters and limits.

    This function registers a tool that allows querying data from database tables
    with optional filtering, ownership scoping, and result limiting. The tool supports
    complex filtering operations and respects ownership boundaries for scoped tables.

    Args:
        app: The FastMCP application instance to register the tool with
        db_models: Library containing database model classes
        available_tables: Available table names for the tool
        available_models: Available model types for filtering
        shared_tables: Set of table names that are shared (not subject to ownership scoping)
    """

    def select_from_table(
        table,
        limit: int = 20,
        full: bool = False,
        filters: Annotated[
            List,
            "List of filter tasks to apply to the query. Each task specifies a table, "
            "list of filters, and how to combine them (and/or). It is required to "
            "first check the database schema and table relationships to ensure "
            "correct column names, data types, and filter operations are used. Use "
            "tools like 'get_table_schema' and 'get_table_relationships' to inspect "
            "the database structure before applying filters.",
        ] = [],
        filter_logic: Annotated[
            Literal["and", "or"],
            "The logic to apply to the filters, either 'and' (logical AND) or 'or' (logical OR). Default is 'and'. This is only used if filters are provided.",
        ] = "and",
    ):
        """Select data from a database table with optional filtering and ownership scoping.

        This function queries data from a specified table, applying any provided filters
        and respecting ownership boundaries for scoped tables. It supports both full
        object serialization and column-only output.

        Args:
            table: Name of the table to select from
            limit: Maximum number of rows to return (default: 20)
            full: If True, returns full object serialization; if False, returns only table columns
            filters: Optional list of filter tasks to apply to the query
            filter_logic: Logic to combine filters - 'and' for intersection, 'or' for union

        Returns:
            str: Encoded JSON string containing the query results

        Raises:
            RuntimeError: If no active database session is found in context
        """
        from sqlmodel import intersect

        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]
        subqueries = []

        if filters:
            subqueries.append(
                FilterTask.build_filtered_query(
                    table_name=table,
                    table_class=table_class,
                    filters=filters,
                    db_models=db_models,
                    logic="intersect" if filter_logic == "and" else "union",
                )
            )

        token = get_access_token()
        if token is not None and is_scoped(table, shared_tables):
            owned_ids = get_owned_ids(
                session=session,
                table_name=table,
                provider=token.claims[ISS],
                subject=token.claims[SUBJECT],
            )
            subqueries.append(
                select(table_class).where(table_class.id.in_(owned_ids or [-1]))  # pyright: ignore[reportAttributeAccessIssue]
            )

        if subqueries:
            final_stmt = (
                intersect(*subqueries) if len(subqueries) > 1 else subqueries[0]
            )
            result = (
                session.exec(
                    select(table_class).from_statement(final_stmt),  # pyright: ignore[reportCallIssue, reportArgumentType]
                )
                .scalars()
                .all()
            )
        else:
            result = session.exec(
                select(table_class).limit(limit),  # pyright: ignore[reportCallIssue, reportArgumentType]
            ).all()

        if full:
            return encode([row.to_dict() for row in result])  # pyright: ignore[reportAttributeAccessIssue]
        return encode(
            [
                {col: getattr(row, col) for col in row.__table__.columns.keys()}  # pyright: ignore[reportAttributeAccessIssue]
                for row in result
            ]
        )

    select_from_table.__annotations__ = {
        "table": available_tables,
        "limit": int,
        "filters": List[FilterTask[available_models]],
        "return": str,
        "filter_logic": Literal["and", "or"],
        "full": bool,
    }  # type: ignore[assignment]
    select_from_table.__signature__ = inspect.signature(select_from_table)  # type: ignore[attr-defined]

    app.tool(
        select_from_table,
        name="Select_Table",
        description=SELECT_DESCRIPTION,
    )
