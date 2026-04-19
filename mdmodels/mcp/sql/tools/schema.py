from __future__ import annotations

from fastmcp import FastMCP

from mdmodels.library import Library
from mdmodels.templates import Templates

from ..constants import GET_SCHEMA_DESCRIPTION


def register_schema_tool(*, app: FastMCP, model: Library) -> None:
    """Register markdown schema tool for the loaded model library.

    This function registers a tool that allows clients to retrieve the database
    schema in markdown format. The tool provides a structured view of all tables,
    columns, and their relationships in the loaded model library.

    Args:
        app: The FastMCP application instance to register the tool with
        model: The Library instance containing the database model definitions
    """

    def get_schema():
        """Get the database schema in markdown format.

        Returns:
            str: A markdown-formatted string containing the complete database schema,
                including table definitions, column types, and relationships.
        """
        return model.convert_to(Templates.MARKDOWN)

    app.tool(
        get_schema,
        name="Get_Table_Schema",
        description=GET_SCHEMA_DESCRIPTION,
    )
