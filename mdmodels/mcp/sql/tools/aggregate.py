from __future__ import annotations

import inspect
from typing import Annotated, List

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from toon_format import encode

from mdmodels.library import Library
from mdmodels.sql import FilterTask, select
from mdmodels.sql.aggregation import Aggregation

from ..constants import AGGREGATE_DESCRIPTION, ISS, SUBJECT
from ..middleware import CTX_SESSION
from ..ownership import get_owned_ids, is_scoped


def register_aggregate_tool(
    *,
    app: FastMCP,
    db_models: Library,
    available_tables,
    available_models,
    shared_tables: set[str],
) -> None:
    """Register aggregate_from_table tool supporting Aggregation plus filters.

    This function registers a tool that allows aggregating data from database tables
    with optional filtering and ownership scoping. The tool supports various aggregation
    operations (count, sum, avg, etc.) and can apply complex filters to the data.

    Args:
        app: The FastMCP application instance to register the tool with
        db_models: Library containing database model classes
        available_tables: Available table names for the tool
        available_models: Available model types for filtering
        shared_tables: Set of table names that are shared (not subject to ownership scoping)
    """

    def aggregate_from_table(
        table,
        aggregations: List[Aggregation],
        filters: Annotated[
            List,
            "List of filter tasks to apply to the query. Each task specifies a table, "
            "list of filters, and how to combine them (and/or). It is required to "
            "first check the database schema and table relationships to ensure "
            "correct column names, data types, and filter operations are used. Use "
            "tools like 'get_table_schema' and 'get_table_relationships' to inspect "
            "the database structure before applying filters.",
        ] = [],
    ):
        """Aggregate data from a database table with optional filtering and ownership scoping.

        This function performs aggregation operations on a specified table, applying
        any provided filters and respecting ownership boundaries for scoped tables.

        Args:
            table: Name of the table to aggregate from
            aggregations: List of aggregation operations to perform (count, sum, avg, etc.)
            filters: Optional list of filter tasks to apply before aggregation

        Returns:
            str: Encoded JSON string containing the aggregation results

        Raises:
            RuntimeError: If no active database session is found in context
        """
        from sqlmodel import intersect

        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]
        subqueries = []

        # Apply filters if provided
        if filters:
            subqueries.append(
                FilterTask.build_filtered_query(
                    table_name=table,
                    table_class=table_class,
                    filters=filters,
                    db_models=db_models,
                )
            )

        # Apply ownership scoping for non-shared tables
        token = get_access_token()
        if token is not None and is_scoped(table, shared_tables):
            owned_ids = get_owned_ids(
                session=session,
                table_name=table,
                provider=token.claims[ISS],
                subject=token.claims[SUBJECT],
            )
            subqueries.append(
                select(table_class).where(table_class.id.in_(owned_ids or [-1]))
            )

        # Combine subqueries using intersection
        union_stmt = (
            intersect(*subqueries)
            if len(subqueries) > 1
            else (subqueries[0] if subqueries else None)
        )

        # Build and execute the aggregation query
        query = Aggregation.build_query_with_filters(
            table_name=table,
            table_class=table_class,
            aggregations=aggregations,
            db_models=db_models,
            union_stmt=union_stmt,
        )

        result = session.exec(
            query,  # pyright: ignore[reportCallIssue, reportArgumentType]
        ).first()
        formatted = Aggregation.format_results(result, aggregations)
        return encode([item.model_dump() for item in formatted])

    # Set up function annotations for tool registration
    aggregate_from_table.__annotations__ = {
        "table": available_tables,
        "aggregations": List[Aggregation],
        "filters": List[FilterTask[available_models]],
        "return": str,
    }  # type: ignore[assignment]

    aggregate_from_table.__signature__ = inspect.signature(aggregate_from_table)  # type: ignore[attr-defined]

    # Register the tool with the FastMCP application
    app.tool(
        aggregate_from_table,
        name="Aggregate_Table",
        description=AGGREGATE_DESCRIPTION,
    )
