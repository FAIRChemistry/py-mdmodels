from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from sqlalchemy.engine import URL
from sqlmodel import SQLModel

from mdmodels.config import AppConfig
from mdmodels.datamodel import DataModel
from mdmodels.sql.config import TableConfig
from mdmodels.sql.connector import DatabaseType
from mdmodels.sql.vector import BatchEmbedding, EmbeddingVector, TextEmbedding


class MigrationTextEmbedding(TextEmbedding):
    """Placeholder embedding model used only for migration metadata generation."""

    def embed(self, text: str) -> EmbeddingVector:
        raise NotImplementedError(
            "MigrationTextEmbedding is metadata-only and cannot embed text."
        )

    def embed_batch(self, texts) -> BatchEmbedding:
        raise NotImplementedError(
            "MigrationTextEmbedding is metadata-only and cannot embed text."
        )


def load_app_config(config_path: Path) -> AppConfig:
    """Load AppConfig and resolve local model paths relative to config file."""
    resolved_config = config_path.resolve()
    app_config = AppConfig.from_toml(resolved_config)

    if app_config.model.repo is None and not app_config.model.path.is_absolute():
        app_config.model.path = (
            resolved_config.parent / app_config.model.path
        ).resolve()

    return app_config


def build_database_url(config_path: Path) -> str:
    """Build a SQLAlchemy URL string from config.toml and environment overrides."""
    app_config = load_app_config(config_path)
    sql_cfg = app_config.sql

    db_type = sql_cfg.type
    if db_type == "sqlite":
        database = os.getenv("DB_DATABASE", sql_cfg.database or ":memory:")
        return str(URL.create("sqlite", database=database))

    if db_type == "postgres":
        drivername = "postgresql+psycopg2"
    elif db_type == "postgresql":
        drivername = "postgresql+psycopg2"
    elif db_type == "pgvector":
        drivername = "postgresql+psycopg2"
    else:
        raise ValueError(f"Unsupported SQL type for migrations: {db_type}")

    username = os.getenv("DB_USERNAME", sql_cfg.username)
    password = os.getenv("DB_PASSWORD", sql_cfg.password)
    host = os.getenv("DB_HOST", sql_cfg.host or "localhost")
    port = int(os.getenv("DB_PORT", str(sql_cfg.port or 5432)))
    database = os.getenv("DB_DATABASE", sql_cfg.database)

    if database is None:
        raise ValueError("DB_DATABASE (or sql.database) must be set for migrations.")

    return str(
        URL.create(
            drivername=drivername,
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )
    )


def build_target_metadata(config_path: Path):
    """Build SQLModel metadata from config.toml + model source."""
    app_config = load_app_config(config_path)

    if app_config.model.repo is not None:
        library = DataModel.from_github(
            repo=app_config.model.repo,
            spec_path=app_config.model.path.as_posix(),
            branch=app_config.model.branch,
            tag=app_config.model.tag,
        )
    else:
        library = DataModel.from_markdown(app_config.model.path)

    table_config = _table_config_map_for_migrations(app_config)
    database_type = _database_type_for_migrations(app_config.sql.type)

    library.to_sqlmodel(
        database_type=database_type,
        table_config=table_config,
    )

    return SQLModel.metadata


def _database_type_for_migrations(sql_type: str) -> DatabaseType:
    if sql_type == "sqlite":
        return DatabaseType.SQLITE
    if sql_type == "postgres":
        return DatabaseType.POSTGRESQL
    if sql_type == "pgvector":
        return DatabaseType.PGVECTOR
    raise ValueError(f"Unsupported SQL database type in config: {sql_type}")


def _table_config_map_for_migrations(app_config: AppConfig) -> Dict[str, TableConfig]:
    mapped: Dict[str, TableConfig] = {}

    for table_name, table_cfg in app_config.sql.tables.items():
        embed_column = None
        embed_model = None

        if table_cfg.embedding is not None:
            embed_column = table_cfg.embedding.column
            embed_model = MigrationTextEmbedding(
                dimension=_infer_embedding_dimension(table_name, table_cfg.embedding)
            )

        mapped[table_name] = TableConfig(
            primary_key=table_cfg.primary_key,
            embed_column=embed_column,
            embed_model=embed_model,
            indexed_columns=list(table_cfg.indexed_columns),
            deduplicate_on=list(table_cfg.deduplicate_on),
            conflict_policy=table_cfg.conflict_policy,
            mutability_policy=table_cfg.mutability_policy,
        )

    return mapped


def _infer_embedding_dimension(table_name: str, embedding_cfg) -> int:
    if embedding_cfg.dimension is not None:
        return embedding_cfg.dimension

    if embedding_cfg.provider == "openai":
        if embedding_cfg.model == "text-embedding-3-small":
            return 1536
        if embedding_cfg.model == "text-embedding-3-large":
            return 3072

    raise ValueError(
        "embedding.dimension must be set in config.toml for migrations "
        f"(table='{table_name}', provider='{embedding_cfg.provider}', "
        f"model='{embedding_cfg.model}')."
    )
