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
    """Create and register MCP tools for database operations.

    This function serves as the main entry point for adding database interaction
    tools to a FastMCP application. It automatically detects the connector type
    and registers the appropriate set of tools.

    For SQL databases (DatabaseConnector), the following tools are registered:

    **Schema & Relationship Tools:**
    - `get_schema`: Retrieve JSON schema for any data model, including field types,
      validation rules, and structure requirements
    - `get_relationships`: Get database relationships and foreign key connections
      between tables, essential for understanding data dependencies

    **Data Creation Tools:**
    - `create_<model_name>`: One tool per model for creating new records with
      nested data insertion and foreign key relationship handling. Always presents
      expected schema and asks for confirmation before creation.

    **Query & Retrieval Tools:**
    - `select_from_table`: Query and retrieve records with optional filtering and
      result limiting. Supports complex WHERE clause filters with mandatory
      schema inspection before filtering.
    - `aggregate_from_table`: Perform aggregation operations (count, sum, avg, min,
      max, stddev, variance) on database tables with optional filtering support.

    **Vector Search Tools:**
    - `vector_search`: Perform semantic vector search on tables with embeddings,
      supporting both direct table search and cross-table search via related
      embeddings. Returns results with cosine distance scores.

    All tools include comprehensive validation, error handling, and automatic
    database session management via middleware. Filter-based tools require
    mandatory schema inspection to ensure correct column names and data types.

    Args:
        app: FastMCP application instance to register tools on
        db: Database connector (SQL or Graph) - determines which tools are created
        model_descriptions: Optional custom descriptions for create tools, keyed
            by model name. If not provided, generic descriptions are used.

    Raises:
        NotImplementedError: If a GraphConnector is provided (not yet supported)

    Example:
        ```python
        from fastmcp import FastMCP
        from mdmodels.sql import DatabaseConnector
        from mdmodels.mcp import create_mcp_tools

        app = FastMCP("my-database-tools")
        db = DatabaseConnector(database_url="sqlite:///example.db")

        # Register all database tools
        create_mcp_tools(app=app, db=db)

        # Or with custom descriptions
        descriptions = {
            "User": "Create a new user account with profile information",
            "Project": "Create a new research project with metadata"
        }
        create_mcp_tools(app=app, db=db, model_descriptions=descriptions)
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
