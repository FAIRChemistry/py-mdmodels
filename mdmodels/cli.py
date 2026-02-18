"""MDModels CLI - Command line interface for managing MDModels applications.

This module provides CLI commands for running MDModels applications in different modes
(REST API, MCP server) and installing them in various clients like Claude Desktop.
"""

import os
import sys
from pathlib import Path
from typing import Literal, Optional, cast

import dotenv
import typer
from fastmcp.mcp_config import StdioMCPServer, update_config_file
from rich import print

from mdmodels.config import AppConfig

app = typer.Typer(
    help="MDModels CLI - Manage and run MDModels applications",
    add_completion=False,
)


def _load_app_config(config: Path) -> AppConfig:
    """Load config and normalize contained paths to absolute.

    Args:
        config: Path to the configuration file

    Returns:
        AppConfig: Loaded and normalized configuration
    """
    config_path = config if config.is_absolute() else (Path.cwd() / config)
    config_path = config_path.resolve()

    app_config = AppConfig.from_toml(config_path)
    if not app_config.model.path.is_absolute():
        app_config.model.path = (config_path.parent / app_config.model.path).resolve()

    return app_config


@app.command()
def rest(
    config: Path = typer.Option(..., help="Path to the configuration TOML file"),
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to"),
    port: int = typer.Option(8800, help="Port to bind the server to"),
    name: Optional[str] = typer.Option(
        default=None, help="API name (defaults to model name)"
    ),
    graphql: bool = typer.Option(default=False, help="Enable GraphQL endpoint"),
    env: Path = typer.Option(
        default=None, help="Path to .env file for environment variables"
    ),
    create_tables: bool = typer.Option(
        default=True, help="Create database tables on startup"
    ),
):
    """Run MDModels as a REST API server.

    Starts a FastAPI server that exposes your MDModels configuration as REST endpoints.
    Optionally includes GraphQL support for more flexible querying.
    """
    import uvicorn
    from fastapi import FastAPI

    from mdmodels.rest import RestApiConfig, create_rest_app
    from mdmodels.sql.connector import DatabaseConnector

    if env is not None:
        dotenv.load_dotenv(dotenv_path=env)

    app_config = _load_app_config(config)

    rest_config = RestApiConfig.from_config(app_config)
    db = DatabaseConnector.from_config(app_config)

    if create_tables:
        db.create_tables()

    if name is None:
        name = cast(str, db.db_models._rust_model.model.name)  # pyright: ignore[reportOptionalMemberAccess]

    fastapi_app = FastAPI(title=name)
    graphql_router = None

    if graphql:
        from mdmodels.graphql import create_graphql_app

        graphql_router = create_graphql_app(db=db, as_router=True)

    create_rest_app(
        app=fastapi_app,
        db=db,
        config=rest_config,
        graphql_router=graphql_router,
    )

    uvicorn.run(fastapi_app, host=host, port=port)


@app.command()
def mcp(
    config: Path = typer.Option(..., help="Path to the configuration TOML file"),
    host: str = typer.Option(
        "127.0.0.1", help="Host to bind the server to (for non-stdio transports)"
    ),
    port: int = typer.Option(
        7000, help="Port to bind the server to (for non-stdio transports)"
    ),
    env: Path = typer.Option(
        default=None, help="Path to .env file for environment variables"
    ),
    transport: Literal["stdio", "sse", "streamable-http"] = typer.Option(
        "stdio", help="Transport protocol for MCP communication"
    ),
):
    """Run MDModels as an MCP (Model Context Protocol) server.

    Starts an MCP server that exposes your MDModels configuration as MCP tools
    for use with AI assistants like Claude Desktop, Cursor, and others.

    Transport options:
    - stdio: Standard input/output (default, for desktop clients)
    - sse: Server-sent events over HTTP
    - streamable-http: HTTP with streaming support
    """
    from fastmcp import FastMCP

    from mdmodels.mcp import create_mcp_tools
    from mdmodels.mcp.config import MCPConfig
    from mdmodels.sql.connector import DatabaseConnector

    if env is not None:
        dotenv.load_dotenv(dotenv_path=env)

    app_config = _load_app_config(config)

    app = FastMCP(name="mdmodels")
    db = DatabaseConnector.from_config(app_config)
    mcp_config = MCPConfig.map_from_config(app_config)
    create_mcp_tools(app=app, db=db, config=mcp_config)

    match transport:
        case "stdio":
            app.run("stdio")
        case "sse":
            app.run("sse", host=host, port=port)
        case "streamable-http":
            app.run("streamable-http", host=host, port=port)
        case _:
            raise ValueError(f"Invalid transport: {transport}")


def get_claude_config_path() -> Path | None:
    """Get Claude Desktop config directory based on platform.

    Returns:
        Path to Claude Desktop config directory, or None if not found
    """
    if sys.platform == "win32":
        path = Path(Path.home(), "AppData", "Roaming", "Claude")
    elif sys.platform == "darwin":
        path = Path(Path.home(), "Library", "Application Support", "Claude")
    elif sys.platform.startswith("linux"):
        path = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"), "Claude"
        )
    else:
        return None

    if path.exists():
        return path
    return None


@app.command()
def install(
    client: Literal["claude-desktop"] = typer.Argument(
        ..., help="Client to install the MCP server for"
    ),
    config: Path = typer.Option(
        ..., help="Path to the MDModels configuration TOML file"
    ),
    name: str = typer.Option(
        "mdmodels", help="Name for the server in the client's configuration"
    ),
    project: Path = typer.Option(
        Path.cwd(), help="Project directory for uv to use as working directory"
    ),
):
    """Install MDModels MCP server in a supported AI client.

    Currently supports:
    - claude-desktop: Installs in Claude Desktop's MCP server configuration

    The installation creates a configuration entry that runs MDModels via uv
    in the specified project directory, making it available to the AI client.
    """
    if client != "claude-desktop":
        raise typer.BadParameter(f"Unsupported client: {client}")

    config_dir = get_claude_config_path()
    if config_dir is None:
        print(
            "[red]Claude Desktop config directory not found.[/red]\n"
            "[blue]Please run Claude Desktop at least once first.[/blue]"
        )
        raise typer.Exit(code=1)

    config_path = config.resolve()
    project_path = project.resolve()
    config_file = config_dir / "claude_desktop_config.json"

    server_config = StdioMCPServer(
        command="uv",
        args=[
            "--project",
            str(project_path),
            "run",
            "mdmodels",
            "mcp",
            "--config",
            str(config_path),
        ],
        env={},
    )

    try:
        update_config_file(config_file, name, server_config)
    except Exception as e:
        print(f"[red]Failed to install server: {e}[/red]")
        raise typer.Exit(code=1) from e

    print(f"[green]Successfully installed '{name}' in Claude Desktop[/green]")


if __name__ == "__main__":
    app()
