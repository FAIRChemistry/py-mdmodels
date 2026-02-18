from __future__ import annotations

import inspect
import re
from typing import Annotated, Any, Dict, List, Literal, TypedDict

from fastmcp import FastMCP
from toon_format import encode

from mdmodels.sql.base import SQLBase

from ...library import Library
from ...sql import DatabaseConnector, FilterTask, select
from ...sql.aggregation import Aggregation
from ...sql.insert import insert_nested
from ...sql.utils import build_related_vectorsearch_query
from ...sql.vector import TextEmbedding
from ..config import MCPConfig
from .middleware import CTX_SESSION, DBSessionMiddleware

# Dynamic typing placeholders populated inside create_mcp_tools
AvailableModels: Any = Any
AvailableTables: Any = Any
EmbeddingTables: Any = Any

# Description templates (formatted with table/embed strings at runtime)
GET_SCHEMA_DESCRIPTION = (
    "Retrieve the JSON schema definition for any data model object. This tool "
    "returns the complete schema including field types, descriptions, validation "
    "rules, and structure. Use this to understand the expected format and "
    "requirements for creating or validating data objects. Essential for "
    "understanding what fields are required, optional, and their data types before "
    "creating new records."
)

GET_RELATIONSHIPS_DESCRIPTION = (
    "Retrieve database relationships and foreign key connections for any data model "
    "object. Returns detailed relationship mappings including source/target tables, "
    "columns, and connection types. Essential for understanding data dependencies, "
    "building complex queries with JOINs, and navigating the database schema "
    "structure."
)

GENERIC_CREATE_DESCRIPTION = (
    "Create and persist a new {model_name} record in the database with all related "
    "data. This tool handles complex nested data insertion including foreign key "
    "relationships. IMPORTANT: Always present the expected schema to the user and "
    "ask for confirmation before creating the {model_name}. The tool validates all "
    "data, creates database relationships, and returns the new {model_name} ID upon "
    "successful creation."
)

SELECT_DESCRIPTION = (
    "Query and retrieve records from any database table with optional filtering and "
    "result limiting. This tool performs SELECT operations with optional WHERE "
    "clause filters and returns matching records. The limit parameter controls "
    "maximum results returned (default: 20). MANDATORY: When using filters, you "
    "MUST first call 'get_table_schema' and 'get_table_relationships' to inspect the "
    "database structure before applying any filters. This ensures correct column "
    "names, data types, and operations. Each filter must specify the correct table "
    "enum, valid column name, appropriate operation, and properly typed value. "
    "Ideal for data exploration, verification, filtering, and reporting. Here are "
    "the available tables: \n{table_string}"
)

AGGREGATE_DESCRIPTION = (
    "Perform aggregation operations (count, sum, avg, min, max, stddev, variance) on "
    "database tables with optional filtering. This tool executes aggregate functions "
    "on specified columns and returns computed results. MANDATORY: When using "
    "filters, you MUST first call 'get_table_schema' and 'get_table_relationships' to "
    "inspect the database structure before applying any filters. This ensures "
    "correct column names, data types, and operations. Each filter must specify the "
    "correct table enum, valid column name, appropriate operation, and properly "
    "typed value. Here are the available tables: \n{table_string}"
)

VECTOR_SEARCH_DESCRIPTION = (
    "Perform vector search on a table, optionally using a related table's embeddings. "
    "Set `table` to the main table you want returned. Provide `embedding_table` to "
    "search via a related table's embeddings (e.g., find experiments by protein "
    "sequence). Results include cosine distance (0.0 identical, 2.0 opposite). Use "
    "`max_distance` to cap acceptable matches. The limit parameter controls maximum "
    "results returned (default: 10). If `embedding_table` is omitted, the main table "
    "is used for embeddings. Before specifying an `embedding_table`, first inspect "
    "table relationships to ensure the tables are related. Available embedding "
    "tables:\n{embed_table_string}\nAvailable tables:\n{table_string}"
)


class TableConnection(TypedDict):
    source_table: str
    source_column: str
    target_table: str
    target_column: str


def create_sql_mcp_tools(
    *,
    app: FastMCP,
    db: DatabaseConnector,
    config: Dict[str, MCPConfig],
) -> None:
    """Attach MCP tools for schema, create, select, aggregate, and vector search.

    Mirrors the style of the REST/GraphQL builders: consumes an already-configured
    `DatabaseConnector` plus the paired pydantic/sqlmodel libraries, registers all
    tools on the provided FastMCP app, and keeps dynamic Literals/enums aligned with
    the live model set.
    """

    # Ensure DB sessions are managed for every tool invocation.
    app.add_middleware(DBSessionMiddleware(db))

    model = db._pydantic_library
    db_models = db._db_models

    # Build runtime Literals/enums from the current library so tool signatures stay in sync.
    available_models = model.to_enum()
    available_tables = Literal[*available_models.__members__.keys()]  # type: ignore[misc]

    embedding_tables = DatabaseConnector.embedding_tables(db_models)

    embed_table_literal = (
        Literal[*embedding_tables]  # type: ignore[misc]
        if embedding_tables
        else Literal["__no_embedding_tables__"]  # type: ignore[misc]
    )

    # Expose dynamic types in module globals so FastMCP/Pydantic can resolve them.
    globals()["AvailableModels"] = available_models
    globals()["AvailableTables"] = available_tables
    globals()["EmbeddingTables"] = embed_table_literal

    embed_table_string = (
        "\n".join([f"- {table}" for table in embedding_tables])
        if embedding_tables
        else "None configured"
    )
    table_string = "\n".join(
        [f"- {table}" for table in model.keys() if not str(table).startswith("_")]
    )

    # Informational tools
    _register_schema_tool(app=app, model=model, available_models=available_models)
    _register_relationships_tool(
        app=app,
        model=model,
        description=GET_RELATIONSHIPS_DESCRIPTION,
        available_tables=available_tables,
    )

    # Per-model create tools share the same nested insert logic.
    _register_create_tools(
        app=app,
        model=model,
        db_models=db_models,
        config=config,
    )
    # Table-level query/aggregation tools reuse shared FilterTask/Aggregation helpers.
    _register_select_tool(
        app=app,
        db_models=db_models,
        description=SELECT_DESCRIPTION.format(table_string=table_string),
        available_tables=available_tables,
        available_models=available_models,
    )
    _register_aggregate_tool(
        app=app,
        db_models=db_models,
        description=AGGREGATE_DESCRIPTION.format(table_string=table_string),
        available_tables=available_tables,
        available_models=available_models,
    )

    if embedding_tables:
        _register_vector_search_tool(
            app=app,
            db=db,
            db_models=db_models,
            available_tables=available_tables,
            embedding_tables=embed_table_literal,
            description=VECTOR_SEARCH_DESCRIPTION.format(
                embed_table_string=embed_table_string,
                table_string=table_string,
            ),
        )


def _register_schema_tool(app: FastMCP, model: Library, available_models) -> None:
    """Register JSON-schema tool for any model in the library."""

    def get_schema(object: AvailableModels):  # pyright: ignore[reportInvalidTypeForm]
        return model[object.name].model_json_schema()

    # Align annotations/signature before FastMCP inspects them (rest/create style).
    get_schema.__annotations__ = {"object": available_models, "return": dict}  # type: ignore[assignment]
    get_schema.__signature__ = inspect.signature(get_schema)  # type: ignore[attr-defined]

    app.tool(
        get_schema,
        name="Get_Table_Schema",
        description=GET_SCHEMA_DESCRIPTION,
    )


def _register_relationships_tool(
    *,
    app: FastMCP,
    model: Library,
    description: str,
    available_tables,
) -> None:
    """Register relationship inspection tool returning source/target column mappings."""

    def get_relationships(table: AvailableTables):  # pyright: ignore[reportInvalidTypeForm]
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
        description=description,
    )


def _register_create_tools(
    *,
    app: FastMCP,
    model: Library,
    db_models: Library,
    config: Dict[str, MCPConfig],
) -> None:
    """Register one create tool per model, with optional per-model descriptions."""
    for model_name in model.keys():
        table_config = config.get(model_name, MCPConfig())

        if not table_config.allow_create:
            continue

        if str(model_name).startswith("_"):
            continue

        data_model_type = model[model_name]
        db_model_class = db_models[model_name]
        snake_model_name = _camel_to_snake(str(model_name))

        description = table_config.description or GENERIC_CREATE_DESCRIPTION.format(
            model_name=snake_model_name
        )

        tool_func = _create_insert_tool(
            model_name=str(model_name),
            data_model_type=data_model_type,
            db_model_class=db_model_class,
            model=model,
            db_models=db_models,
        )

        app.tool(
            tool_func,
            name=f"create_{snake_model_name}",
            description=description,
        )


def _create_insert_tool(
    *,
    model_name: str,
    data_model_type,
    db_model_class,
    model: Library,
    db_models: Library,
):
    """Factory building a single create_<model> coroutine with nested insert support."""
    snake_model_name = _camel_to_snake(model_name)

    async def insert_function(**kwargs: Any):  # pyright: ignore[reportInvalidTypeForm]
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        data = data_model_type(**kwargs)
        # Convert pydantic payload into SQLModel objects (handles nested relations).
        to_insert = insert_nested(
            data=data,
            library=model,
            models=db_models,
            session=session,
        )

        try:
            session.add_all(to_insert)
            session.commit()

            for obj in to_insert:
                session.refresh(obj)

            main_obj = next(
                (obj for obj in to_insert if isinstance(obj, db_model_class)), None
            )
            if main_obj:
                obj_id = getattr(main_obj, "id", None)
                if obj_id is not None:
                    return f"Successfully created {snake_model_name} with ID: {obj_id}"
            return f"Successfully created {snake_model_name}"
        except Exception as exc:  # pragma: no cover - defensive rollback
            session.rollback()
            raise RuntimeError(f"Failed to create {snake_model_name}: {exc}") from exc

    insert_function.__name__ = f"Create_{snake_model_name}"
    insert_function.__annotations__ = data_model_type.__annotations__
    insert_function.__signature__ = inspect.signature(data_model_type)

    return insert_function


def _register_select_tool(
    *,
    app: FastMCP,
    db_models: Library[SQLBase],
    description: str,
    available_tables,
    available_models,
) -> None:
    """Register select_from_table tool with optional filters and limits."""

    def select_from_table(
        table: AvailableTables,  # pyright: ignore[reportInvalidTypeForm]
        limit: int = 20,
        filters: Annotated[
            List[FilterTask[AvailableModels]],  # pyright: ignore[reportInvalidTypeForm]
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
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]

        if filters:
            # Build a union statement that already applies join-aware filters.
            union_stmt = FilterTask.build_filtered_query(
                table_name=table,
                table_class=table_class,
                filters=filters,
                db_models=db_models,
                logic="intersect" if filter_logic == "and" else "union",
            )
            query = select(table_class).from_statement(union_stmt)
            result = (
                session.exec(
                    query,  # pyright: ignore[reportCallIssue, reportArgumentType]
                )
                .scalars()
                .all()
            )
        else:
            query = select(table_class)
            result = session.exec(
                query.limit(limit),  # pyright: ignore[reportCallIssue, reportArgumentType]
            ).all()

        return encode([row.to_dict() for row in result])  # pyright: ignore[reportAttributeAccessIssue]

    select_from_table.__annotations__ = {
        "table": available_tables,
        "limit": int,
        "filters": List[FilterTask[available_models]],
        "return": str,
        "filter_logic": Literal["and", "or"],
    }  # type: ignore[assignment]
    select_from_table.__signature__ = inspect.signature(select_from_table)  # type: ignore[attr-defined]

    app.tool(
        select_from_table,
        name="Select_Table",
        description=description,
    )


def _register_aggregate_tool(
    *,
    app: FastMCP,
    db_models: Library,
    description: str,
    available_tables,
    available_models,
) -> None:
    """Register aggregate_from_table tool supporting Aggregation plus filters."""

    def aggregate_from_table(
        table: AvailableTables,  # pyright: ignore[reportInvalidTypeForm]
        aggregations: List[Aggregation],
        filters: Annotated[
            List[FilterTask[AvailableModels]],  # pyright: ignore[reportInvalidTypeForm]
            "List of filter tasks to apply to the query. Each task specifies a table, "
            "list of filters, and how to combine them (and/or). It is required to "
            "first check the database schema and table relationships to ensure "
            "correct column names, data types, and filter operations are used. Use "
            "tools like 'get_table_schema' and 'get_table_relationships' to inspect "
            "the database structure before applying filters.",
        ] = [],
    ):
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]

        union_stmt = None
        if filters:
            union_stmt = FilterTask.build_filtered_query(
                table_name=table,
                table_class=table_class,
                filters=filters,
                db_models=db_models,
            )

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

    aggregate_from_table.__annotations__ = {
        "table": available_tables,
        "aggregations": List[Aggregation],
        "filters": List[FilterTask[available_models]],
        "return": str,
    }  # type: ignore[assignment]

    aggregate_from_table.__signature__ = inspect.signature(aggregate_from_table)  # type: ignore[attr-defined]

    app.tool(
        aggregate_from_table,
        name="Aggregate_Table",
        description=description,
    )


def _register_vector_search_tool(
    *,
    app: FastMCP,
    db: DatabaseConnector,
    db_models: Library,
    description: str,
    available_tables,
    embedding_tables,
) -> None:
    """Register vector_search tool for direct or related-table embedding queries."""

    def vector_search(
        table: AvailableTables,  # pyright: ignore[reportInvalidTypeForm]
        query: str,
        limit: int = 10,
        offset: int = 0,
        embedding_table: EmbeddingTables | None = None,  # type: ignore[reportInvalidTypeForm]
        max_distance: float | None = None,
    ):
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        search_table = embedding_table or table
        if db.table_config is None or search_table not in db.table_config:
            raise RuntimeError(
                f"Embedding model not configured for table {search_table}"
            )

        if search_table not in db_models:
            raise RuntimeError(f"Table {search_table} not found in database models")

        main_table_class = db_models[table]
        target_model_class = (
            main_table_class if search_table == table else db_models[search_table]
        )

        table_config = db.table_config[search_table]
        embedding_model = table_config.embed_model
        if embedding_model is None:
            raise RuntimeError(f"Embedding model not defined for table {search_table}")

        query_embedding = _embed_query(embedding_model, query)
        embedding_col = getattr(target_model_class, "embedding", None)
        if embedding_col is None:
            raise RuntimeError(
                f"Model {search_table} does not have an embedding column"
            )

        cosine_distance = embedding_col.cosine_distance(query_embedding)

        if search_table == table:
            # Same-table search: order by distance directly on main model.
            stmt = select(
                main_table_class,
                cosine_distance.label("distance"),
            ).select_from(main_table_class)

            if max_distance is not None:
                stmt = stmt.where(cosine_distance <= max_distance)

            stmt = stmt.order_by(cosine_distance).offset(offset).limit(limit)
        else:
            try:
                # Cross-table search: join via relations while preserving ordering.
                stmt = build_related_vectorsearch_query(
                    main_model=main_table_class,
                    related_model=target_model_class,
                    db_models=db_models,
                    cosine_distance=cosine_distance,
                    offset=offset,
                    limit=limit,
                    max_distance=max_distance,
                )
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc

        results = session.exec(
            stmt,  # pyright: ignore[reportCallIssue, reportArgumentType]
        ).all()

        objects = []

        for obj, distance in results:
            if isinstance(obj, list):
                objects.append(
                    {
                        "distance": float(distance),
                        "data": [
                            sub_obj.to_dict(dtype=target_model_class).model_dump()  # pyright: ignore[reportAttributeAccessIssue]
                            for sub_obj in obj
                        ],
                    }
                )
            else:
                objects.append(
                    {
                        "distance": float(distance),
                        "data": obj.to_dict(dtype=target_model_class).model_dump(),  # pyright: ignore[reportAttributeAccessIssue]
                    }
                )

        return encode(objects)

    vector_search.__annotations__ = {
        "table": available_tables,
        "query": str,
        "limit": int,
        "offset": int,
        "embedding_table": embedding_tables | None,  # type: ignore[operator]
        "max_distance": float | None,
        "return": str,
    }  # type: ignore[assignment]
    vector_search.__signature__ = inspect.signature(vector_search)  # type: ignore[attr-defined]

    app.tool(
        vector_search,
        name="Vector_Search",
        description=description,
    )


def _camel_to_snake(name: str, capitalize: bool = True) -> str:
    """Convert Camel/Pascal to snake_case (predictable tool names)."""
    step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    step2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1)
    result = step2.lower()
    if capitalize:
        return "_".join(word.capitalize() for word in result.split("_"))
    return result


def _embed_query(embedding_model: TextEmbedding, query: str):
    """Embed a query string with the configured text embedding model."""
    return embedding_model.embed(query)
