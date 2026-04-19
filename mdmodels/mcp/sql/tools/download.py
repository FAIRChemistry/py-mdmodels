from __future__ import annotations

import inspect
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP, ResourcePermissions
from fastmcp.tools import ToolResult
from mcp import types

from mdmodels.library import Library
from mdmodels.sql.base import SQLBase

from ..constants import DOWNLOAD_DESCRIPTION
from ..middleware import CTX_SESSION
from ._assets import load_html_asset

VIEW_URI = "ui://mdmodels/json-viewer.html"


def _load_download_html() -> str:
    return load_html_asset("json_viewer.html")


DOWNLOAD_HTML = _load_download_html()


def register_download_tool(
    *,
    app: FastMCP,
    db_models: Library[SQLBase],
    available_tables,
) -> None:
    """Register a download tool that renders an interactive JSON tree viewer.

    The tool fetches a full (nested) record from any table and returns it as a
    rich MCP App — an interactive, collapsible JSON tree with a "Copy to Clipboard"
    button rendered inside the host client.

    The viewer resource is registered once at ``ui://mdmodels/json-viewer.html``
    and shared across all tool calls.

    Args:
        app: FastMCP application instance to register the tool with
        db_models: Library containing the database model classes
        available_tables: Annotated Literal type enumerating valid table names
    """

    @app.resource(
        VIEW_URI,
        app=AppConfig(
            csp=ResourceCSP(resourceDomains=["https://unpkg.com"]),
            permissions=ResourcePermissions(clipboardWrite={}),
        ),
    )
    def _json_viewer_resource() -> str:
        return DOWNLOAD_HTML

    def download_entry(
        table,
        id: Annotated[int, "Primary key of the record to download."],
    ) -> ToolResult:
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]
        row = session.get(table_class, id)

        if row is None:
            raise ValueError(f"No entry found in '{table}' with id={id}.")

        import json as _json

        payload = {
            "_meta": {"table": table, "id": id},
            "data": row.to_dict(),  # type: ignore[attr-defined]
        }

        return ToolResult(
            content=[types.TextContent(type="text", text=_json.dumps(payload))]
        )

    download_entry.__annotations__ = {
        "table": available_tables,
        "id": int,
        "return": ToolResult,
    }  # type: ignore[assignment]
    download_entry.__signature__ = inspect.signature(download_entry)  # type: ignore[attr-defined]

    app.tool(
        download_entry,
        name="Download_Entry",
        description=DOWNLOAD_DESCRIPTION,
        app=AppConfig(resourceUri=VIEW_URI),
    )
