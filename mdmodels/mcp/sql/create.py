from __future__ import annotations

from typing import Dict, Optional

from fastmcp import FastMCP

from ...config import AuthMethod
from ...sql import DatabaseConnector
from ..config import MCPConfig
from ..sql.ownership import create_ownership_tables
from .annotation import create_annotation_tables
from .constants import SERVER_INSTRUCTIONS, VECTOR_SEARCH_DESCRIPTION
from .middleware import DBSessionMiddleware
from .runtime import build_runtime_tool_metadata
from .tools.aggregate import register_aggregate_tool
from .tools.annotate import register_annotate_tool
from .tools.download import register_download_tool
from .tools.plot import register_plot_tool
from .tools.relationships import register_relationships_tool
from .tools.schema import register_schema_tool
from .tools.select import register_select_tool
from .tools.upsert import register_upsert_tools
from .tools.vector_search import register_vector_search_tool


def create_sql_mcp_tools(
    *,
    app: FastMCP,
    db: DatabaseConnector,
    config: Dict[str, MCPConfig],
    all_create: bool = False,
    auth: Optional[AuthMethod] = None,
) -> None:
    """Attach MCP SQL tools for schema, create, select, aggregate, and vector search.

    This function sets up a complete suite of SQL-based MCP (Model Context Protocol) tools
    for database interaction. It registers tools for schema inspection, data creation,
    selection, aggregation, and vector similarity search operations.

    The function configures the FastMCP application with:
    - Database session middleware for connection management
    - Schema inspection tools for understanding table structure
    - CRUD operations with ownership scoping and access control
    - Aggregation tools for statistical queries
    - Vector search capabilities for semantic similarity queries

    Args:
        app: The FastMCP application instance to register tools with
        db: Database connector containing model definitions and connection details
        config: Dictionary mapping table names to their MCP configuration settings,
               including sharing permissions and access controls
        all_create: If True, registers create tools for all tables; if False, only
                   registers create tools for tables specified in config

    Note:
        The function automatically determines which tables support vector search based
        on the presence of embedding columns in the database models. Vector search
        tools are only registered if embedding-capable tables are found.

        Ownership scoping is applied to non-shared tables, restricting access to
        records owned by the authenticated user based on JWT token claims.
    """

    if auth is not None:
        create_ownership_tables(db.engine)

    create_annotation_tables(db.engine)

    if app.instructions is None:
        app.instructions = SERVER_INSTRUCTIONS

    app.add_middleware(DBSessionMiddleware(db))

    model = db._pydantic_library
    db_models = db._db_models
    shared_tables = set(table for table, config in config.items() if config.shared)
    runtime = build_runtime_tool_metadata(model=model, db_models=db_models)

    register_schema_tool(app=app, model=model)
    register_annotate_tool(app=app, available_tables=runtime.available_tables)
    register_relationships_tool(
        app=app,
        model=model,
        available_tables=runtime.available_tables,
    )
    register_upsert_tools(
        app=app,
        model=model,
        db_models=db_models,
        config=config,
        all_create=all_create,
        shared_tables=shared_tables,
    )
    register_select_tool(
        app=app,
        db_models=db_models,
        available_tables=runtime.available_tables,
        available_models=runtime.available_models,
        shared_tables=shared_tables,
    )
    register_aggregate_tool(
        app=app,
        db_models=db_models,
        available_tables=runtime.available_tables,
        available_models=runtime.available_models,
        shared_tables=shared_tables,
    )
    register_download_tool(
        app=app,
        db_models=db_models,
        available_tables=runtime.available_tables,
    )
    register_plot_tool(
        app=app,
        db_models=db_models,
        available_tables=runtime.available_tables,
        available_models=runtime.available_models,
        shared_tables=shared_tables,
    )

    if runtime.embedding_tables:
        register_vector_search_tool(
            app=app,
            db=db,
            db_models=db_models,
            available_tables=runtime.available_tables,
            embedding_tables=runtime.embedding_tables_literal,
            shared_tables=shared_tables,
            description=VECTOR_SEARCH_DESCRIPTION.format(
                embed_table_string=runtime.embed_table_string,
                table_string=runtime.table_string,
            ),
        )
