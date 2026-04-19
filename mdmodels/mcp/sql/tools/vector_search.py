from __future__ import annotations

import inspect

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from toon_format import encode

from mdmodels.library import Library
from mdmodels.sql import DatabaseConnector, select
from mdmodels.sql.utils import build_related_vectorsearch_query

from ..constants import ISS, SUBJECT, VECTOR_SEARCH_DESCRIPTION
from ..embedding import embed_query
from ..middleware import CTX_SESSION
from ..ownership import get_owned_ids, is_scoped


def register_vector_search_tool(
    *,
    app: FastMCP,
    db: DatabaseConnector,
    db_models: Library,
    available_tables,
    embedding_tables,
    shared_tables: set[str],
    description: str | None = None,
) -> None:
    """Register vector_search tool for direct or related-table embedding queries.

    This function registers a tool that allows performing vector similarity searches
    on database tables with embedding columns. It supports both direct searches on
    tables with embeddings and related-table searches where embeddings are stored
    in a different table but related through foreign keys.

    Args:
        app: The FastMCP application instance to register the tool with
        db: Database connector containing table configuration and embedding models
        db_models: Library containing database model classes
        available_tables: Available table names for the tool
        embedding_tables: Tables that have embedding columns available for search
        shared_tables: Set of table names that are shared (not subject to ownership scoping)
        description: Optional custom description for the tool (defaults to VECTOR_SEARCH_DESCRIPTION)
    """

    def vector_search(
        table,
        query: str,
        limit: int = 10,
        offset: int = 0,
        embedding_table=None,
        max_distance: float | None = None,
    ):
        """Perform vector similarity search on database tables with embeddings.

        This function performs semantic search by converting the query text to an embedding
        and finding the most similar records based on cosine distance. It supports both
        direct searches (where the target table has embeddings) and related searches
        (where embeddings are in a related table).

        Args:
            table: Name of the main table to search in
            query: Text query to search for semantically similar content
            limit: Maximum number of results to return (default: 10)
            offset: Number of results to skip for pagination (default: 0)
            embedding_table: Optional table name containing embeddings if different from main table
            max_distance: Optional maximum cosine distance threshold for filtering results

        Returns:
            str: Encoded JSON string containing search results with distance scores and data

        Raises:
            RuntimeError: If no active database session, embedding model not configured,
                         table not found, or embedding column missing
        """
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

        query_embedding = embed_query(embedding_model, query)
        embedding_col = getattr(target_model_class, "embedding", None)
        if embedding_col is None:
            raise RuntimeError(
                f"Model {search_table} does not have an embedding column"
            )

        cosine_distance = embedding_col.cosine_distance(query_embedding)

        token = get_access_token()
        owned_ids: set[int] | None = None
        if token is not None and is_scoped(table, shared_tables):
            owned_ids = set(
                get_owned_ids(
                    session=session,
                    table_name=table,
                    provider=token.claims[ISS],
                    subject=token.claims[SUBJECT],
                )
            )

        if search_table == table:
            stmt = select(
                main_table_class,
                cosine_distance.label("distance"),
            ).select_from(main_table_class)

            if max_distance is not None:
                stmt = stmt.where(cosine_distance <= max_distance)

            if owned_ids is not None:
                stmt = stmt.where(main_table_class.id.in_(owned_ids or [-1]))

            stmt = stmt.order_by(cosine_distance).offset(offset).limit(limit)
        else:
            try:
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

        if owned_ids is not None and search_table != table:
            results = [(obj, dist) for obj, dist in results if obj.id in owned_ids]  # pyright: ignore[reportAttributeAccessIssue]

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
        description=description or VECTOR_SEARCH_DESCRIPTION,
    )
