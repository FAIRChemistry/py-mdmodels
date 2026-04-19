from __future__ import annotations

import inspect
from typing import Dict, Type, cast

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from pydantic import BaseModel
from toon_format import encode

from mdmodels.datamodel import DataModel
from mdmodels.library import Library
from mdmodels.mcp.config import MCPConfig
from mdmodels.sql.childref import reconstruct_model
from mdmodels.sql.upsert import upsert_nested

from ..constants import GENERIC_UPSERT_DESCRIPTION, ISS, SUBJECT
from ..middleware import CTX_SESSION
from ..naming import camel_to_snake
from ..ownership import track_ownership


def register_upsert_tools(
    *,
    app: FastMCP,
    model: Library,
    db_models: Library,
    config: Dict[str, MCPConfig],
    all_create: bool = False,
    shared_tables: set[str],
) -> None:
    """Register one upsert tool per model, with optional per-model descriptions.

    Creates MCP tools for upserting data into database tables based on the provided
    data models. Each tool handles flat payload upserts and ownership tracking.

    Args:
        app: FastMCP application instance to register tools with
        model: Library containing the data model definitions
        db_models: Library containing the database model definitions
        config: Configuration mapping for each model, controlling creation permissions
        all_create: If True, allows creation for all models regardless of config
        shared_tables: Set of table names that are shared across tenants
    """
    for model_name, _ in model.models():
        table_config = config.get(model_name, MCPConfig())

        if not table_config.allow_create and not all_create:
            continue

        if str(model_name).startswith("_"):
            continue

        data_model_type = model[model_name]
        snake_model_name = camel_to_snake(str(model_name))
        description = table_config.description or GENERIC_UPSERT_DESCRIPTION.format(
            model_name=snake_model_name
        )

        tool_func = _create_upsert_tool(
            model_name=str(model_name),
            data_model_type=data_model_type,
            model=model,
            db_models=db_models,
            shared_tables=shared_tables,
        )

        app.tool(
            tool_func,
            name=f"Upsert_{snake_model_name}",
            description=description,
        )


def _create_upsert_tool(
    *,
    model_name: str,
    data_model_type,
    model: Library,
    db_models: Library,
    shared_tables: set[str],
):
    """Factory building a single Upsert_<model> coroutine with flat upsert support.

    Creates a dynamic upsert function for a specific model that handles:
    - Create-or-update behavior using optional top-level row_pk
    - ChildRef-based relationship updates for flat payloads
    - Database transaction management with rollback on errors
    - Ownership tracking for newly created objects
    - Proper session management and object refresh

    Args:
        model_name: Name of the model to create insert tool for
        data_model_type: The actual data model class
        model: Library containing data model definitions
        db_models: Library containing database model definitions
        shared_tables: Set of table names that are shared across tenants

    Returns:
        Async function that performs the insert operation
    """
    snake_model_name = camel_to_snake(model_name)
    childref_model = reconstruct_model(
        data_model_type,
        flat=True,
        include_row_pk=True,
    )

    async def upsert_function(data: list[childref_model]):  # pyright: ignore[reportInvalidTypeForm]
        """Upsert one or more instances of the model into the database.

        Args:
            data: List of model instances to insert

        Returns:
            JSON-encoded string of upserted objects

        Raises:
            RuntimeError: If no database session is available or upsert fails
        """
        session = CTX_SESSION.get()

        if session is None:
            raise RuntimeError("No active DB session in context")

        to_upsert = upsert_nested(
            data=cast(list[DataModel], data),
            library=model,
            models=db_models,
            session=session,
        )

        try:
            session.add_all(to_upsert)
            session.commit()

            upserted = []

            for obj in to_upsert:
                session.refresh(obj)
                upserted.append(obj)

            token = get_access_token()
            if token is not None:
                track_ownership(
                    session=session,
                    model_name=model_name,
                    inserted_objects=upserted,
                    provider=token.claims[ISS],
                    subject=token.claims[SUBJECT],
                    shared_tables=shared_tables,
                )
                session.commit()

            return encode([upserted_row.model_dump() for upserted_row in upserted])
        except Exception as exc:  # pragma: no cover - defensive rollback
            session.rollback()
            raise RuntimeError(f"Failed to upsert {snake_model_name}: {exc}") from exc

    upsert_function.__name__ = f"Upsert_{snake_model_name}"
    upsert_function.__signature__ = _build_signature_from_model(childref_model)
    upsert_function.__annotations__ = {
        "data": list[childref_model],
        "return": str,
    }

    return upsert_function


def _build_signature_from_model(model: Type[BaseModel]) -> inspect.Signature:
    """Build a function signature for the insert tool based on the model.

    Creates an inspect.Signature object that defines the expected parameters
    for the dynamically generated insert function.

    Args:
        model: Pydantic model class to build signature from

    Returns:
        Function signature with a single 'data' parameter expecting a list of the model
    """
    return inspect.Signature(
        parameters=[
            inspect.Parameter(
                name="data",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty,
                annotation=list[model],
            ),
        ],
        return_annotation=str,
    )
