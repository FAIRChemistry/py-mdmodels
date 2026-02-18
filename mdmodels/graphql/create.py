from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
    cast,
    overload,
)

import strawberry
from pydantic import BaseModel
from sqlmodel import SQLModel, select
from strawberry.asgi import GraphQL
from strawberry.experimental import pydantic as strawberry_pydantic
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig

from ..library import Library
from ..sql import DatabaseConnector
from ..sql.base import SQLBase
from ..sql.config import TableConfig
from ..sql.utils import build_related_vectorsearch_query


@overload
def create_graphql_app(
    *,
    db: DatabaseConnector,
    as_router: Literal[False] = False,
    **router_kwargs: Dict[str, Any],
) -> GraphQL:
    pass


@overload
def create_graphql_app(
    *,
    db: DatabaseConnector,
    as_router: Literal[True] = True,
    **router_kwargs: Dict[str, Any],
) -> GraphQLRouter:
    pass


def create_graphql_app(
    *,
    db: DatabaseConnector,
    as_router: bool = False,
    **router_kwargs: Dict[str, Any],
) -> Union[GraphQL, GraphQLRouter]:
    """
    Build a Strawberry GraphQL ASGI app from an mdmodels Library and a SQL DatabaseConnector.

    Creates one GraphQL type per mdmodels object (using strawberry-pydantic) and one query
    field per object: `<name>s(limit, offset)`. Each field returns a list of that object's
    type, including nested relations, because the underlying Pydantic models already encode
    relationships.

    Args:
        model (Library): The mdmodels Library containing DataModel (pydantic) classes
            generated from markdown.
        db_models (Library): The corresponding Library of SQLModel classes generated via
            `sql.generate_sqlmodel`.
        db (DatabaseConnector): A DatabaseConnector providing a SQLAlchemy engine and
            context-managed Sessions.

    Returns:
        GraphQL: A Strawberry ASGI app ready to be mounted or served with uvicorn.
    """
    pydantic_types: Dict[str, Type[BaseModel]] = {}
    sqlmodel_types: Dict[str, Type[SQLModel]] = {}
    gql_types: Dict[str, type] = {}

    _collect_types(
        db._models,
        db._db_models,
        pydantic_types,
        sqlmodel_types,
        gql_types,
    )

    query_fields = _build_query_fields(pydantic_types, sqlmodel_types, gql_types, db)

    QueryBase = type("Query", (), query_fields)
    Query = strawberry.type(QueryBase)

    schema = strawberry.Schema(
        query=Query,
        config=StrawberryConfig(auto_camel_case=False),
    )

    if as_router:
        return GraphQLRouter(
            schema,
            **router_kwargs,  # pyright: ignore[reportArgumentType]
        )
    else:
        return GraphQL(schema)


def _collect_types(
    model: Library,
    db_models: Library,
    pydantic_types: Dict[str, Type[BaseModel]],
    sqlmodel_types: Dict[str, Type[SQLModel]],
    gql_types: Dict[str, type],
) -> None:
    """
    Collect Pydantic & SQLModel classes for each top-level object.

    Args:
        model (Library): The mdmodels Library containing DataModel classes.
        db_models (Library): The Library of SQLModel classes.
        pydantic_types (Dict): Dictionary to store Pydantic types.
        sqlmodel_types (Dict): Dictionary to store SQLModel types.
        gql_types (Dict): Dictionary to store GraphQL types.
    """
    for name, dm_cls in model.models():
        if name.startswith("_"):
            continue
        if name not in db_models:
            continue

        sql_cls = db_models[name]
        if not isinstance(sql_cls, type) or not issubclass(sql_cls, SQLModel):
            continue

        @strawberry_pydantic.type(dm_cls, all_fields=True, name=name)
        class GQLType:  # type: ignore[valid-type]
            pass

        pydantic_types[name] = dm_cls
        sqlmodel_types[name] = sql_cls
        gql_types[name] = GQLType


def _build_query_fields(
    pydantic_types: Dict[str, Type[BaseModel]],
    sqlmodel_types: Dict[str, Type[SQLModel]],
    gql_types: Dict[str, type],
    db: DatabaseConnector,
) -> Dict[str, Any]:
    """
    Build Query type dynamically: one field per model.

    Args:
        pydantic_types (Dict): Dictionary of Pydantic types.
        sqlmodel_types (Dict): Dictionary of SQLModel types.
        gql_types (Dict): Dictionary of GraphQL types.
        db (DatabaseConnector): Database connector for querying.

    Returns:
        Dict: Dictionary of query fields.
    """
    query_fields: Dict[str, Any] = {}

    for name, gql_type in gql_types.items():
        dm_cls = pydantic_types[name]
        sql_cls = sqlmodel_types[name]
        field_name = name[0].lower() + name[1:] if name else name

        has_embedding = hasattr(sql_cls, "embedding")
        resolver_fn = _make_resolver(sql_cls, dm_cls, gql_type, db, has_embedding)

        # Mirror the original per-table query structure from `graphql_app.py`,
        # letting Strawberry infer the GraphQL return type from the resolver.
        query_fields[field_name] = strawberry.field(
            resolver_fn,
            description=f"Query {name} objects",
        )

    return query_fields


def _pluralize(name: str) -> str:
    """
    Simple, predictable pluralization: "Experiment" -> "experiments".

    Args:
        name (str): The singular name to pluralize.

    Returns:
        str: The pluralized name.
    """
    return name[0].lower() + name[1:] + "s"


def _make_resolver(
    sql_cls: Type[SQLModel],
    dm_cls: Type[BaseModel],
    gql_type: type,
    db: DatabaseConnector,
    has_embedding: bool,
) -> Callable[..., List[Any]]:
    """
    Create a resolver function for a GraphQL query field.

    Args:
        sql_cls (Type[SQLModel]): The SQLModel class to query.
        dm_cls (Type[BaseModel]): The Pydantic model class.
        gql_type (type): The GraphQL type.
        db (DatabaseConnector): Database connector for querying.
        has_embedding (bool): True when the SQLModel exposes an embedding column.

    Returns:
        Callable: The resolver function.
    """

    if has_embedding:

        def resolver(  # type: ignore[return-value]
            self: Any,
            semantic_query: Optional[str] = None,
            embedding_table: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
            max_distance: Optional[float] = None,
        ) -> List[Any]:
            instances = _list_rows(
                sql_cls=sql_cls,
                dm_cls=dm_cls,
                limit=limit,
                offset=offset,
                db=db,
                semantic_query=semantic_query,
                embedding_table=embedding_table,
                max_distance=max_distance,
                has_embedding=has_embedding,
            )
            return [gql_type.from_pydantic(obj) for obj in instances]

        resolver.__annotations__["semantic_query"] = Optional[str]  # type: ignore[index]
        resolver.__annotations__["embedding_table"] = Optional[str]  # type: ignore[index]
    else:

        def resolver(self: Any, limit: int = 100, offset: int = 0) -> List[Any]:
            instances = _list_rows(
                sql_cls=sql_cls,
                dm_cls=dm_cls,
                limit=limit,
                offset=offset,
                db=db,
                semantic_query=None,
                embedding_table=None,
                max_distance=None,
                has_embedding=has_embedding,
            )
            return [gql_type.from_pydantic(obj) for obj in instances]

    # Let Strawberry infer the GraphQL type from the resolver's return annotation.
    # We override it dynamically so each resolver returns List[gql_type].
    resolver.__annotations__["return"] = List[gql_type]  # type: ignore[assignment]

    return resolver


def _list_rows(
    sql_cls: Type[SQLModel],
    dm_cls: Type[BaseModel],
    limit: int,
    offset: int,
    db: DatabaseConnector,
    semantic_query: Optional[str],
    embedding_table: Optional[str],
    max_distance: Optional[float],
    has_embedding: bool,
) -> List[BaseModel]:
    """
    Run a simple SELECT with pagination and map to Pydantic.

    Args:
        sql_cls (Type[SQLModel]): The SQLModel class to query.
        dm_cls (Type[BaseModel]): The Pydantic model class.
        limit (int): Maximum number of rows to return.
        offset (int): Number of rows to skip.
        db (DatabaseConnector): Database connector for querying.
        semantic_query (Optional[str]): Text to run a semantic similarity search on.
        has_embedding (bool): True when the SQLModel exposes an embedding column.

    Returns:
        List[BaseModel]: List of Pydantic model instances.
    """
    with db as session:  # type: ignore[attr-defined]
        if semantic_query:
            _ensure_semantic_supported(sql_cls, db, has_embedding)
            search_table, target_model = _resolve_search_table(
                sql_cls, db, embedding_table
            )
            table_config, embedding_col = _resolve_embedding_config(
                search_table, target_model, db
            )
            cosine_distance = _build_cosine_distance(
                semantic_query, table_config, embedding_col
            )
            rows = (
                _run_semantic_query_same_table(
                    session=session,
                    sql_cls=sql_cls,
                    cosine_distance=cosine_distance,
                    limit=limit,
                    offset=offset,
                    max_distance=max_distance,
                )
                if search_table == sql_cls.__name__
                else _run_semantic_query_related(
                    session=session,
                    sql_cls=sql_cls,
                    target_model=target_model,
                    cosine_distance=cosine_distance,
                    db=db,
                    limit=limit,
                    offset=offset,
                    max_distance=max_distance,
                )
            )
        else:
            rows = _run_basic_query(
                session=session, sql_cls=sql_cls, limit=limit, offset=offset
            )

        return _rows_to_models(rows, dm_cls)


def _ensure_semantic_supported(
    sql_cls: Type[SQLModel],
    db: DatabaseConnector,
    has_embedding: bool,
) -> None:
    """
    Validate semantic search prerequisites for a given model.

    Raises a ValueError if the model or database configuration does not support
    semantic search.
    """
    if not has_embedding:
        raise ValueError(f"Model {sql_cls.__name__} does not support semantic search")
    if db.table_config is None:
        raise ValueError("Embedding model is not configured for semantic search")


def _resolve_search_table(
    sql_cls: Type[SQLModel],
    db: DatabaseConnector,
    embedding_table: Optional[str],
) -> tuple[str, Type[SQLModel]]:
    """
    Determine which table to search against and return its SQLModel.

    Returns:
        (search_table, target_model)
    """
    search_table = embedding_table or sql_cls.__name__
    assert db.table_config is not None  # type narrowing for static checkers
    table_config = db.table_config

    if search_table not in table_config:
        raise ValueError(f"Embedding model not configured for table {search_table}")
    if search_table not in db._db_models:
        raise ValueError(f"Table {search_table} not found in database models")

    target_model: Type[SQLModel] = (
        sql_cls if search_table == sql_cls.__name__ else db._db_models[search_table]
    )
    return search_table, target_model


def _resolve_embedding_config(
    search_table: str,
    target_model: Type[SQLModel],
    db: DatabaseConnector,
) -> tuple[TableConfig, Any]:
    """
    Fetch the embedding config and column for the selected table.

    Returns:
        (table_config, embedding_column)
    """
    embedding_col = getattr(target_model, "embedding", None)
    if embedding_col is None:
        raise ValueError(f"Model {search_table} does not have an embedding column")

    assert db.table_config is not None  # narrow type for mypy/pyright
    table_config = db.table_config[search_table]
    assert table_config.embed_model is not None, (
        "Embedding model is not defined for this table"
    )
    return table_config, embedding_col


def _build_cosine_distance(
    semantic_query: str,
    table_config: TableConfig,
    embedding_col: Any,
):
    """
    Create a cosine distance expression for the query embedding.
    """
    embedding_model = table_config.embed_model

    assert embedding_model is not None, "Embedding model is not defined for this table"

    query_embedding = embedding_model.embed(semantic_query)
    return embedding_col.cosine_distance(query_embedding)


def _run_semantic_query_same_table(
    session: Any,
    sql_cls: Type[SQLModel],
    cosine_distance: Any,
    limit: int,
    offset: int,
    max_distance: Optional[float],
) -> List[Any]:
    """
    Execute a semantic similarity query against the main table.
    """
    stmt = select(sql_cls, cosine_distance.label("distance")).select_from(sql_cls)

    if max_distance is not None:
        stmt = stmt.where(cosine_distance <= max_distance)

    stmt = stmt.order_by(cosine_distance.asc()).offset(offset).limit(limit)
    rows_with_distance = session.exec(stmt).all()
    return [row for row, _ in rows_with_distance]


def _run_semantic_query_related(
    session: Any,
    sql_cls: Type[SQLModel],
    target_model: Type[SQLModel],
    cosine_distance: Any,
    db: DatabaseConnector,
    limit: int,
    offset: int,
    max_distance: Optional[float],
) -> List[Any]:
    """
    Execute a semantic similarity query joining to a related embedding table.
    """
    try:
        stmt = build_related_vectorsearch_query(
            main_model=cast(Type[SQLBase], sql_cls),
            related_model=cast(Type[SQLBase], target_model),
            db_models=db._db_models,
            cosine_distance=cosine_distance,
            offset=offset,
            limit=limit,
            max_distance=max_distance,
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    rows_with_distance = session.exec(stmt).all()
    return [row for row, _ in rows_with_distance]


def _run_basic_query(
    session: Any,
    sql_cls: Type[SQLModel],
    limit: int,
    offset: int,
) -> List[Any]:
    """
    Execute a simple paginated select without semantic search.
    """
    stmt = select(sql_cls).offset(offset).limit(limit)
    return session.exec(stmt).all()


def _rows_to_models(rows: List[Any], dm_cls: Type[BaseModel]) -> List[BaseModel]:
    """
    Convert SQLModel rows to their corresponding Pydantic models.
    """
    results: List[BaseModel] = []
    for row in rows:
        to_dict_fn = getattr(row, "to_dict", None)
        if callable(to_dict_fn):
            data = cast(Dict[str, Any], to_dict_fn())
        else:
            data = cast(Dict[str, Any], row.model_dump())
        results.append(dm_cls(**data))
    return results
