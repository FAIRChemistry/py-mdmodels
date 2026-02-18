from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..library import Library
from ..sql.base import SQLBase
from ..sql.connector import DatabaseConnector
from ..sql.filter import FilterTask
from ..sql.insert import get_primary_key, insert_nested
from ..sql.utils import build_related_vectorsearch_query
from .config import CrudOperation, RestApiConfig
from .search import OrderSpec, SearchRequest

if TYPE_CHECKING:
    from strawberry.fastapi import GraphQLRouter


# Type variable for the embedding tables
EmbeddingTablesType = TypeVar("EmbeddingTablesType", bound=Enum)


# Type variable for the data field in VectorSearchResult
DataType = TypeVar(
    "DataType",
    bound=Union[
        BaseModel,
        List[BaseModel],
    ],
)


class VectorSearchResult(BaseModel, Generic[DataType]):
    """Response model for vector search results containing similarity score and data."""

    distance: float
    data: DataType


class VectorSearchRequest(BaseModel, Generic[EmbeddingTablesType]):
    """Request body for vector search queries."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    table: Optional[EmbeddingTablesType] = None
    max_distance: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Maximum allowed cosine distance (0.0-2.0).",
    )


def create_rest_app(
    *,
    app: FastAPI,
    db: DatabaseConnector,
    config: Optional[Union[RestApiConfig, Path]] = None,
    graphql_router: Optional["GraphQLRouter"] = None,
):
    """
    Create a FastAPI app with CRUD routes for all models in the library.

    Iterates through all models in the database connector and registers
    appropriate CRUD endpoints based on the configuration settings.

    Args:
        app: FastAPI application instance
        db: Database connector instance containing models and database configuration
        config: REST API configuration including security and endpoint settings
        graphql_router: Optional GraphQL router to include at /graphql endpoint
    """

    if config is None:
        config = RestApiConfig()

    if isinstance(config, Path):
        if config.suffix == ".yaml" or config.suffix == ".yml":
            config = RestApiConfig.from_yaml(config)
        elif config.suffix == ".toml":
            config = RestApiConfig.from_toml(config)
        else:
            raise ValueError(f"Unsupported config file type: {config.suffix}")

    endpoints_cfg = config.endpoints

    # Include GraphQL router if provided
    if graphql_router is not None:
        app.include_router(graphql_router, prefix="/graphql")

    # Register CRUD routes for each model
    for name in db._models.keys():
        # Skip internal models (prefixed with underscore)
        if name.startswith("_"):
            continue

        assert name in db._models, f"Model {name} not found in library"

        if issubclass(db._models[name], Enum):
            continue

        # Check if any operations are allowed for this model
        allowed_ops: Optional[Set[CrudOperation]] = endpoints_cfg.allowed_operations(
            name
        )

        if allowed_ops == set():
            continue

        data_model_cls = db._models[name]
        db_model_cls = db._db_models[name]

        _register_crud_routes(
            app=app,
            db=db,
            model_name=name,
            data_model_type=data_model_cls,
            db_model_class=db_model_cls,
            db_models=db._db_models,
            model=db._models,
            allowed_endpoints=allowed_ops,
            config=config,
        )


def _register_crud_routes(
    app: FastAPI,
    db: DatabaseConnector,
    model_name: str,
    data_model_type: Type[BaseModel],
    db_model_class: Type[SQLBase],
    db_models: Library[SQLBase],
    model: Library,
    allowed_endpoints: Optional[Set[CrudOperation]],
    config: RestApiConfig,
) -> None:
    """
    Register CRUD routes for a single model with security dependencies.

    Creates an APIRouter with endpoints for create, read, update, delete operations
    based on the allowed operations configuration.
    """
    router = APIRouter(
        prefix=f"/{model_name.lower()}",
        tags=[model_name],
        dependencies=config.security.global_dependencies,
    )

    get_session = _create_session_dependency(db)
    pk_name = get_primary_key(db_model_class)
    available_models = model.to_enum()

    def deps(op: CrudOperation) -> List[Any]:
        """Get security dependencies for a specific operation."""
        return config.security.deps_for(model_name, op)

    # Register endpoints based on allowed operations
    if allowed_endpoints is not None and "create" in allowed_endpoints:
        _register_create_endpoint(
            router=router,
            model_name=model_name,
            data_model_type=data_model_type,
            db_model_class=db_model_class,
            db_models=db_models,
            model=model,
            get_session=get_session,
            extra_dependencies=deps("create"),
        )

    if allowed_endpoints is not None and "list" in allowed_endpoints:
        _register_list_endpoint(
            router=router,
            model_name=model_name,
            model_class=data_model_type,
            db_model_class=db_model_class,
            get_session=get_session,
            extra_dependencies=deps("list"),
        )

    if allowed_endpoints is not None and "search" in allowed_endpoints:
        _register_search_endpoint(
            router=router,
            model_name=model_name,
            model_class=data_model_type,
            db_model_class=db_model_class,
            db_models=db_models,
            available_models=available_models,
            get_session=get_session,
            extra_dependencies=deps("search"),
        )

    # Register vectorsearch endpoint BEFORE retrieve endpoint to avoid route conflicts
    # (/{item_id} would match /vectorsearch if registered first)
    if (
        allowed_endpoints is not None and "vectorsearch" in allowed_endpoints
    ) and hasattr(db_model_class, "embedding"):
        _register_embeddings_endpoint(
            router=router,
            model_name=model_name,
            model_class=data_model_type,
            db_model_class=db_model_class,
            get_session=get_session,
            db=db,
        )

    if allowed_endpoints is not None and "retrieve" in allowed_endpoints:
        _register_retrieve_endpoint(
            router=router,
            model_name=model_name,
            model_class=data_model_type,
            db_model_class=db_model_class,
            get_session=get_session,
            extra_dependencies=deps("retrieve"),
        )

    if allowed_endpoints is not None and "update" in allowed_endpoints:
        _register_update_endpoint(
            router=router,
            model_name=model_name,
            db_model_class=db_model_class,
            pk_name=pk_name,
            get_session=get_session,
            extra_dependencies=deps("update"),
        )

    if allowed_endpoints is not None and "delete" in allowed_endpoints:
        _register_delete_endpoint(
            router=router,
            model_name=model_name,
            db_model_class=db_model_class,
            get_session=get_session,
            extra_dependencies=deps("delete"),
        )

    app.include_router(router)


def _register_create_endpoint(
    router: APIRouter,
    model_name: str,
    data_model_type: Type[BaseModel],
    db_model_class: Type[SQLBase],
    db_models: Library,
    model: Library,
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """
    Register POST endpoint for creating new model instances.

    Handles nested object creation and returns the main created object.
    """
    deps = extra_dependencies or []

    @router.post(
        "/",
        response_model=db_model_class,
        summary=f"Create {model_name}",
        dependencies=deps,
    )
    async def create_item(
        payload: data_model_type,  # type: ignore[valid-type]
        session: Session = Depends(get_session),
    ):
        # Insert the object and any nested related objects
        to_insert = insert_nested(
            data=payload,
            library=model,
            session=session,
            models=db_models,
        )

        session.add_all(to_insert)
        session.commit()

        # Refresh all objects to get generated IDs
        for obj in to_insert:
            session.refresh(obj)

        # Find and return the main object of the requested type
        main_obj = next(
            (obj for obj in to_insert if isinstance(obj, db_model_class)), None
        )
        if main_obj is None:
            raise HTTPException(status_code=500, detail="Failed to create object")

        return main_obj


def _register_list_endpoint(
    router: APIRouter,
    model_name: str,
    db_model_class: Type[SQLBase],
    model_class: Type[BaseModel],
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """
    Register GET endpoint for listing model instances with pagination.

    Supports basic pagination and optional full object serialization.
    """
    deps = extra_dependencies or []

    @router.get(
        "/",
        response_model=List[model_class],
        summary=f"List {model_name} items",
        dependencies=deps,
    )
    def list_items(
        skip: int = 0,
        limit: int = 100,
        full: bool = False,
        session: Session = Depends(get_session),
    ):
        query = select(db_model_class).offset(skip).limit(limit)
        results = session.exec(query).all()

        if full:
            return [obj.to_dict(dtype=model_class) for obj in results]
        else:
            return [obj.model_dump() for obj in results]


def _register_search_endpoint(
    router: APIRouter,
    model_name: str,
    model_class: Type[BaseModel],
    db_model_class: Type[SQLBase],
    db_models: Library,
    available_models: Type,
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """
    Register POST endpoint for advanced search with filters and ordering.

    Supports complex filtering, ordering, and pagination through SearchRequest payload.
    """
    deps = extra_dependencies or []

    @router.post(
        "/search",
        response_model=List[model_class],
        summary=f"Advanced search for {model_name} with complex filters",
        dependencies=deps,
    )
    def search_items(
        payload: SearchRequest[available_models],  # type: ignore
        full: bool = False,
        session: Session = Depends(get_session),
    ):
        table_class = db_model_class
        table_name = model_name

        # Build ordering expressions from the request
        order_expressions = _build_order_expressions(
            table_class=table_class,
            order_specs=payload.order_by,
            table_name=table_name,
        )

        # Handle filtered search with complex query building
        if payload.filters:
            union_stmt = FilterTask.build_filtered_query(
                table_name=table_name,
                table_class=table_class,
                filters=payload.filters,
                db_models=db_models,
                logic=payload.logic,
            )
            if order_expressions:
                union_stmt = union_stmt.order_by(*order_expressions)
            if payload.offset:
                union_stmt = union_stmt.offset(payload.offset)
            if payload.limit:
                union_stmt = union_stmt.limit(payload.limit)

            query = select(table_class).from_statement(union_stmt)
            results = session.exec(query).scalars().all()  # pyright: ignore[reportCallIssue, reportArgumentType]
            return [obj.to_dict() for obj in results]

        # Handle simple search without filters
        query = select(table_class)
        if order_expressions:
            query = query.order_by(*order_expressions)

        results = session.exec(query.offset(payload.offset).limit(payload.limit)).all()

        if full:
            return [obj.to_dict(dtype=model_class) for obj in results]
        else:
            return [obj.model_dump() for obj in results]


def _register_retrieve_endpoint(
    router: APIRouter,
    model_name: str,
    model_class: Type[BaseModel],
    db_model_class: Type[SQLBase],
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """Register GET endpoint for retrieving a single model instance by ID."""
    deps = extra_dependencies or []

    @router.get(
        "/{item_id}",
        response_model=model_class,
        summary=f"Get single {model_name}",
        dependencies=deps,
    )
    def get_item(
        item_id: int,
        full: bool = False,
        session: Session = Depends(get_session),
    ):  # type: ignore[reportReturnAny]
        obj = session.get(db_model_class, item_id)
        if not obj:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")

        if full:
            return obj.to_dict(dtype=model_class)
        else:
            return obj.model_dump()


def _register_update_endpoint(
    router: APIRouter,
    model_name: str,
    db_model_class: Type[SQLBase],
    pk_name: str,
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """
    Register PUT endpoint for updating model instances.

    Updates only the fields provided in the payload, excluding the primary key.
    """
    deps = extra_dependencies or []

    @router.put(
        "/{item_id}",
        response_model=db_model_class,
        summary=f"Update {model_name}",
        dependencies=deps,
    )
    def update_item(
        item_id: int,
        payload: db_model_class,  # type: ignore
        session: Session = Depends(get_session),
    ) -> db_model_class:  # type: ignore[reportReturnAny]
        obj = session.get(db_model_class, item_id)
        if not obj:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")

        # Extract only the fields that were explicitly set
        data = payload.model_dump(exclude_unset=True)
        data.pop(pk_name, None)  # Don't allow updating the primary key

        # Update the object attributes
        for k, v in data.items():
            setattr(obj, k, v)

        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj


def _register_delete_endpoint(
    router: APIRouter,
    model_name: str,
    db_model_class: Type[SQLBase],
    get_session: Callable[[], Generator[Session, None, None]],
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """Register DELETE endpoint for removing model instances."""
    deps = extra_dependencies or []

    @router.delete(
        "/{item_id}",
        status_code=204,
        summary=f"Delete {model_name}",
        dependencies=deps,
    )
    def delete_item(
        item_id: int,
        session: Session = Depends(get_session),
    ):
        obj = session.get(db_model_class, item_id)
        if not obj:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        session.delete(obj)
        session.commit()
        return None


def _register_embeddings_endpoint(
    router: APIRouter,
    model_name: str,
    model_class: Type[BaseModel],
    db_model_class: Type[SQLBase],
    get_session: Callable[[], Generator[Session, None, None]],
    db: DatabaseConnector,
    extra_dependencies: Optional[List[Any]] = None,
) -> None:
    """
    Register POST endpoint for vector search with similarity scores.

    Performs semantic search using embeddings and returns results with cosine distance scores.
    Can search across related tables if specified.
    """

    EmbeddingTables = DatabaseConnector.embedding_tables(db.db_models, as_enum=True)

    @router.post(
        "/vectorsearch",
        response_model=List[VectorSearchResult[model_class]],
        summary=f"Vector search for {model_name}",
        description=f"Vector search for {model_name} - If `table` is not provided, the search will be performed on the model {model_name}. Otherwise, the table specified will be used for retrieval, but the model will be returned as the data.",
        dependencies=extra_dependencies,
    )
    def vector_search(
        query: str,
        payload: VectorSearchRequest[EmbeddingTables],  # pyright: ignore[reportInvalidTypeForm]
        session: Session = Depends(get_session),
    ):
        # Validate embedding configuration
        if db.table_config is None:
            raise HTTPException(
                status_code=400,
                detail="No embedding model configured for this database",
            )

        table_name = payload.table.value if payload.table is not None else model_name

        if table_name not in db.table_config:
            raise HTTPException(
                status_code=400,
                detail=f"Embedding model not configured for model {table_name}",
            )

        db_models = db._db_models

        # Ensure the models are related if searching across different tables
        if not db_models.is_related(model_name, table_name):
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_name} is not related to {table_name}",
            )

        # Generate embedding for the search query
        table_config = db.table_config[table_name]
        assert table_config.embed_model is not None, (
            "Embedding model is not defined for this table"
        )
        query_embedding = table_config.embed_model.embed(query)

        # Determine which model class to use for embedding search
        target_model_class = db_model_class
        if table_name != model_name:
            if table_name not in db_models:
                raise HTTPException(
                    status_code=400,
                    detail=f"Table {table_name} not found in database models",
                )
            target_model_class = db_models[table_name]

        # Get the embedding column (standardized as "embedding" for pgvector)
        embedding_col = getattr(target_model_class, "embedding", None)
        if embedding_col is None:
            raise HTTPException(
                status_code=400,
                detail=f"Model {table_name} does not have an embedding column",
            )

        # Calculate cosine distance using pgvector native function
        cosine_distance = embedding_col.cosine_distance(query_embedding)

        # Build the appropriate query based on whether we're searching the same table
        if table_name == model_name:
            # Simple case: searching within the same model
            stmt = select(
                db_model_class,
                cosine_distance.label("distance"),
            ).select_from(db_model_class)

            if payload.max_distance is not None:
                stmt = stmt.where(cosine_distance <= payload.max_distance)

            stmt = (
                stmt.order_by(cosine_distance)
                .offset(payload.offset)
                .limit(payload.limit)
            )
        else:
            # Complex case: searching across related tables with joins
            try:
                stmt = build_related_vectorsearch_query(
                    main_model=db_model_class,
                    related_model=target_model_class,
                    db_models=db_models,
                    cosine_distance=cosine_distance,
                    offset=payload.offset,
                    limit=payload.limit,
                    max_distance=payload.max_distance,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        results = session.exec(stmt).all()

        # Convert results to standardized format with distance scores
        # cosine_distance ranges from 0 (identical) to 2 (opposite)
        return [
            VectorSearchResult(
                distance=float(distance),
                data=obj.to_dict(dtype=model_class),
            )
            for obj, distance in results
        ]


def _create_session_dependency(
    db: DatabaseConnector,
) -> Callable[[], Generator[Session, None, None]]:
    """Create a FastAPI dependency function for database sessions."""

    def get_session() -> Generator[Session, None, None]:
        with db as session:
            yield session

    return get_session


def _build_order_expressions(
    table_class: Type[SQLBase],
    order_specs: List[OrderSpec],
    table_name: str,
) -> List[Any]:
    """
    Build SQLAlchemy order expressions from order specifications.

    Validates that the specified columns exist on the model and converts
    them to appropriate ascending or descending order expressions.
    """
    expressions = []
    for spec in order_specs:
        try:
            col = getattr(table_class, spec.column)
        except AttributeError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by column '{spec.column}' for {table_name}",
            )
        expressions.append(col.desc() if spec.direction == "desc" else col.asc())
    return expressions
