import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from mdmodels.sql.vector import (
    FastembedTextEmbedding,
    OpenAITextEmbedding,
    SentenceTransformerEmbedding,
    TextEmbedding,
)

if TYPE_CHECKING:
    from mdmodels.config import AppConfig, SQLTableConfig as FileSQLTableConfig

# Type aliases for conflict and mutability policies.
ConflictPolicy = Literal["error", "upsert", "ignore"]
MutabilityPolicy = Literal["mutable", "append_only"]


class TableConfig(BaseModel):
    """Configuration for database table behavior and constraints.

    This class defines how a table should be created and managed in the database,
    including primary key configuration, embedding settings, indexing, deduplication
    rules, and conflict resolution policies.

    Attributes:
        primary_key: The name of the primary key column (default: "id").
        embed_column: The column name to use for generating embeddings. Must be
                     paired with embed_model.
        embed_model: The embedding model to use for generating vector embeddings.
                    Must be paired with embed_column.
        indexed_columns: List of column names to create database indexes on for
                        improved query performance.
        deduplicate_on: List of column names to use for deduplication. Records
                       with matching values in these columns are considered duplicates.
        conflict_policy: How to handle conflicts when inserting duplicate records:
                        - "error": Raise an error on conflicts (default)
                        - "upsert": Update existing records with new values
                        - "ignore": Skip duplicate records silently
        mutability_policy: Whether records can be modified after insertion:
                          - "mutable": Records can be updated (default)
                          - "append_only": Records cannot be modified once inserted
    """

    primary_key: Optional[str] = Field(
        default=None,
        description="Name of the primary key column, otherwise an id column will be added",
    )
    embed_column: Optional[str] = Field(
        default=None,
        description="Column name to use for generating embeddings",
    )
    embed_model: Optional[TextEmbedding] = Field(
        default=None,
        description="Embedding model for generating vector embeddings",
    )
    indexed_columns: List[str] = Field(
        default_factory=list,
        description="Column names to create database indexes on",
    )
    deduplicate_on: List[str] = Field(
        default_factory=list,
        description="Column names to use for identifying duplicate records",
    )
    conflict_policy: ConflictPolicy = Field(
        default="error",
        description="Policy for handling duplicate record conflicts",
    )
    mutability_policy: MutabilityPolicy = Field(
        default="mutable",
        description="Whether records can be modified after insertion",
    )

    @model_validator(mode="after")
    def validate_embedding_config(self) -> "TableConfig":
        """Validate embedding column and model configuration.

        Ensures that embed_column and embed_model are either both provided
        or both None. Having one without the other is invalid.

        Returns:
            The validated TableConfig instance.

        Raises:
            ValueError: If only one of embed_column or embed_model is provided.
        """
        if self.embed_column is None and self.embed_model is not None:
            raise ValueError("Embed column is required when embed model is provided")
        elif self.embed_column is not None and self.embed_model is None:
            raise ValueError("Embed model is required when embed column is provided")
        return self

    @model_validator(mode="after")
    def validate_deduplication_config(self) -> "TableConfig":
        """Validate deduplication configuration.

        Ensures that the primary key is not included in the deduplication
        columns, as this would be redundant and potentially problematic.

        Returns:
            The validated TableConfig instance.

        Raises:
            ValueError: If primary_key is included in deduplicate_on.
        """
        if self.primary_key in self.deduplicate_on:
            raise ValueError("Primary key cannot be in deduplicate on list")
        return self

    @model_validator(mode="after")
    def validate_conflict_policy(self) -> "TableConfig":
        """Validate conflict policy configuration.

        Ensures that the "upsert" conflict policy is only used when
        deduplication columns are specified, as upserts require a way
        to identify which records to update.

        Returns:
            The validated TableConfig instance.

        Raises:
            ValueError: If conflict_policy is "upsert" but deduplicate_on is empty.
        """
        if self.conflict_policy == "upsert" and not self.deduplicate_on:
            raise ValueError(
                "conflict_policy='upsert' requires deduplicate_on to be set"
            )
        return self

    @model_validator(mode="after")
    def validate_mutability_policy(self) -> "TableConfig":
        """Validate mutability policy configuration.

        Ensures that append-only tables don't use upsert conflict policy,
        as this would contradict the immutability constraint.

        Returns:
            The validated TableConfig instance.

        Raises:
            ValueError: If mutability_policy is "append_only" and conflict_policy is "upsert".
        """
        if self.mutability_policy == "append_only" and self.conflict_policy == "upsert":
            raise ValueError("append_only tables cannot use conflict_policy='upsert'")
        return self

    @model_validator(mode="after")
    def validate_indexed_columns(self) -> "TableConfig":
        """Validate indexed columns configuration.

        Ensures that indexed_columns contains no duplicates and no empty
        or whitespace-only column names.

        Returns:
            The validated TableConfig instance.

        Raises:
            ValueError: If indexed_columns contains duplicates or empty column names.
        """
        if len(self.indexed_columns) != len(set(self.indexed_columns)):
            raise ValueError("indexed_columns contains duplicates")

        if any(not col.strip() for col in self.indexed_columns):
            raise ValueError("indexed_columns must contain non-empty column names")
        return self

    @classmethod
    def from_config(cls, config: "AppConfig", table_name: str) -> "TableConfig":
        """Create SQL runtime table config for a single table."""
        if table_name not in config.sql.tables:
            raise KeyError(f"Table '{table_name}' not found in config.sql.tables")
        return cls._from_file_table_config(config.sql.tables[table_name])

    @classmethod
    def from_toml(cls, toml_path: str | Path, table_name: str) -> "TableConfig":
        """Create SQL runtime table config for one table from TOML."""
        from mdmodels.config import AppConfig

        return cls.from_config(AppConfig.from_toml(toml_path), table_name)

    @classmethod
    def map_from_config(cls, config: "AppConfig") -> Dict[str, "TableConfig"]:
        """Create SQL runtime table config mapping for all configured tables."""
        return {
            table_name: cls._from_file_table_config(table_cfg)
            for table_name, table_cfg in config.sql.tables.items()
        }

    @classmethod
    def map_from_toml(cls, toml_path: str | Path) -> Dict[str, "TableConfig"]:
        """Create SQL runtime table config mapping from TOML."""
        from mdmodels.config import AppConfig

        return cls.map_from_config(AppConfig.from_toml(toml_path))

    @classmethod
    def _from_file_table_config(cls, table_cfg: "FileSQLTableConfig") -> "TableConfig":
        embed_column: Optional[str] = None
        embed_model: Optional[TextEmbedding] = None

        if table_cfg.embedding is not None:
            embed_column = table_cfg.embedding.column
            embed_model = cls._build_embedding_model(table_cfg)

        return cls(
            primary_key=table_cfg.primary_key,
            embed_column=embed_column,
            embed_model=embed_model,
            indexed_columns=list(table_cfg.indexed_columns),
            deduplicate_on=list(table_cfg.deduplicate_on),
            conflict_policy=table_cfg.conflict_policy,
            mutability_policy=table_cfg.mutability_policy,
        )

    @staticmethod
    def _build_embedding_model(table_cfg: "FileSQLTableConfig") -> TextEmbedding:
        embedding = table_cfg.embedding
        if embedding is None:
            raise ValueError("No embedding section configured for table")

        if embedding.provider == "openai":
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError(
                    "OpenAI embeddings require the 'openai' package."
                ) from exc

            openai_cfg = embedding.openai
            api_key = None
            base_url = None
            if openai_cfg is not None:
                api_key = os.getenv(openai_cfg.api_key_env)
                base_url = openai_cfg.base_url

            client_kwargs = {}
            if api_key:
                client_kwargs["api_key"] = api_key
            if base_url:
                client_kwargs["base_url"] = base_url

            return OpenAITextEmbedding(
                client=OpenAI(**client_kwargs),
                model=embedding.model,
                dimension=embedding.dimension or 1536,
            )

        if embedding.provider == "huggingface":
            huggingface_cfg = embedding.huggingface
            model = SentenceTransformerEmbedding(
                model_name=embedding.model,
                device=huggingface_cfg.device if huggingface_cfg else None,
                batch_size=huggingface_cfg.batch_size if huggingface_cfg else 32,
                normalize_embeddings=(
                    huggingface_cfg.normalize_embeddings if huggingface_cfg else True
                ),
                trust_remote_code=(
                    huggingface_cfg.trust_remote_code if huggingface_cfg else False
                ),
            )

            if embedding.dimension is not None and embedding.dimension != model.dimension:
                raise ValueError(
                    f"Configured embedding.dimension={embedding.dimension} does not "
                    f"match model dimension={model.dimension} for '{embedding.model}'"
                )
            return model

        if embedding.provider == "fastembed":
            fastembed_cfg = embedding.fastembed
            model = FastembedTextEmbedding(
                model_name=embedding.model,
                cache_dir=fastembed_cfg.cache_dir if fastembed_cfg else None,
                batch_size=fastembed_cfg.batch_size if fastembed_cfg else None,
            )

            if embedding.dimension is not None and embedding.dimension != model.dimension:
                raise ValueError(
                    f"Configured embedding.dimension={embedding.dimension} does not "
                    f"match model dimension={model.dimension} for '{embedding.model}'"
                )
            return model

        raise ValueError(f"Unsupported embedding provider: {embedding.provider}")
