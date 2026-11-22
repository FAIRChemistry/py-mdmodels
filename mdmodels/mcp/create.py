from __future__ import annotations

from typing import Dict, Optional

from fastmcp import FastMCP

from mdmodels.config import AuthMethod
from mdmodels.mcp.config import MCPConfig
from mdmodels.sql.connector import DatabaseConnector

from .sql import create_sql_mcp_tools


def create_mcp_tools(
    *,
    app: FastMCP,
    db: DatabaseConnector,
    config: Optional[Dict[str, MCPConfig]] = None,
    all_create: bool = False,
    auth: Optional[AuthMethod] = None,
) -> None:
    """Register the MCP tools for a model on a FastMCP application.

    Main entry point for exposing a database built from an MD-Models model to
    LLM agents. Only SQL databases (`DatabaseConnector`) are supported. The tools
    are implemented in `mdmodels/mcp/sql/tools/` and registered by
    `mdmodels.mcp.sql.create.create_sql_mcp_tools`.

    Registered tools:

    **Schema**
    - `Get_Table_Schema`: return the Markdown data model with all fields, types,
      relationships and nesting.
    - `Get_Table_Relationships`: return the foreign-key mappings of a table.

    **Writing**
    - `Upsert_<Object>`: one tool per object, for every object if `all_create`
      is True and otherwise for the tables with `allow_create` in `config`.
      Writes a nested record across the corresponding tables in one
      transaction, or updates an existing record when its `row_pk` is given.
      Nested fields may reference existing rows by key. Attributes are checked
      for their declared types.
    - `Annotate_Entries`, `Get_Annotations`: free-text annotations on rows of
      any table.

    **Reading**
    - `Select_Table`: select rows from one table with optional filters and a
      row limit.
    - `Aggregate_Table`: count, sum, avg, min, max, stddev or variance over a
      table, with optional filters.
    - `Download_Entry`: fetch one entry by primary key as a JSON tree that can
      be copied or downloaded.
    - `Vector_Search`: semantic search over tables with embeddings. Registered
      only when a table has an embedding column.

    **Interactive apps**
    - `Plot_Table`: query a table with optional filters, optionally grouped by
      a column of a related table, and render the rows as an interactive chart.
    - `Data_Entry`: render a typed form whose fields, labels, types and bounds
      are specified by the agent. The form is not derived from the schema; the
      agent maps the submitted values to columns when it calls an
      `Upsert_<Object>` tool.
    - `Submit_Data_Entry`: callback of the form. Checks the submitted values
      against the form specification and returns them to the agent.

    For the four-object `Experiment` model with `all_create=True` and no
    embeddings, this registers 14 tools.

    Args:
        app: FastMCP application to register the tools on.
        db: Database connector built from the model.
        config: Per-table settings keyed by table name (`MCPConfig`):
            `allow_create` registers the upsert tool for that table,
            `description` replaces the upsert tool's description, and `shared`
            exempts the table from ownership scoping.
        all_create: Register an `Upsert_<Object>` tool for every object,
            regardless of `allow_create`.
        auth: Authentication method. With `"oidc"`, ownership tables are
            created and tables not marked `shared` are scoped to the
            authenticated user.

    Raises:
        ValueError: If `db` is not a `DatabaseConnector`.

    Example:
        ```python
        from fastmcp import FastMCP
        from mdmodels import DataModel
        from mdmodels.mcp import create_mcp_tools
        from mdmodels.sql import DatabaseConnector

        library = DataModel.from_markdown("model.md")
        db = DatabaseConnector(library=library, database="example.db")
        db.create_tables()

        app = FastMCP("my-database-tools")
        create_mcp_tools(app=app, db=db, all_create=True)
        ```
    """

    config = config or {}

    if isinstance(db, DatabaseConnector):
        create_sql_mcp_tools(
            app=app,
            db=db,
            config=config,
            all_create=all_create,
            auth=auth,
        )
    else:
        raise ValueError(
            f"{type(db)} is not supported yet. Please use 'DatabaseConnector' instead."
        )
