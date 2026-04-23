from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional

import toml
from pydantic import BaseModel, Field, model_validator

RestOperation = Literal[
    "create",
    "list",
    "retrieve",
    "update",
    "delete",
    "search",
    "vectorsearch",
]
SQLDatabaseType = Literal[
    "postgres",
    "postgresql",
    "pgvector",
    "sqlite",
]
EmbeddingProvider = Literal[
    "openai",
    "huggingface",
]
AuthMethod = Literal["oidc"]


class ModelConfig(BaseModel):
    """Top-level model source configuration."""

    path: Path = Field(
        description="The path to the model file",
    )

    repo: Optional[str] = Field(
        default=None,
        description="The GitHub repository in the format 'owner/repo'",
    )

    branch: Optional[str] = Field(
        default=None,
        description="The branch name",
    )

    tag: Optional[str] = Field(
        default=None,
        description="The tag name",
    )


class OpenAIEmbeddingConfig(BaseModel):
    """Provider-specific OpenAI embedding settings."""

    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None


class HuggingFaceEmbeddingConfig(BaseModel):
    """Provider-specific Hugging Face embedding settings."""

    device: Optional[str] = None
    batch_size: int = 32
    normalize_embeddings: bool = True


class SQLEmbeddingConfig(BaseModel):
    """Single embedding configuration for one SQL table."""

    column: str
    model: str
    provider: EmbeddingProvider
    dimension: Optional[int] = None
    openai: Optional[OpenAIEmbeddingConfig] = None
    huggingface: Optional[HuggingFaceEmbeddingConfig] = None

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "SQLEmbeddingConfig":
        if self.provider == "openai" and self.huggingface is not None:
            raise ValueError(
                "embedding.huggingface is not allowed when embedding.provider='openai'"
            )
        if self.provider == "huggingface" and self.openai is not None:
            raise ValueError(
                "embedding.openai is not allowed when embedding.provider='huggingface'"
            )
        return self


class SQLTableConfig(BaseModel):
    """Configuration for a single SQL table."""

    primary_key: Optional[str] = None
    indexed_columns: List[str] = Field(default_factory=list)
    deduplicate_on: List[str] = Field(default_factory=list)
    conflict_policy: Literal["error", "upsert", "ignore"] = "error"
    mutability_policy: Literal["mutable", "append_only"] = "mutable"
    embedding: Optional[SQLEmbeddingConfig] = None


class SQLConfig(BaseModel):
    """Database connection and table-level SQL configuration."""

    type: SQLDatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    tables: Dict[str, SQLTableConfig] = Field(default_factory=dict)


class RestConfig(BaseModel):
    """REST endpoint enablement by model/table name."""

    endpoints: Dict[str, List[RestOperation]] = Field(default_factory=dict)


class MCPToolConfig(BaseModel):
    """MCP tool exposure/configuration for a model/table."""

    description: Optional[str] = None
    allow_create: bool = False
    shared: bool = False


class MCPConfig(BaseModel):
    """MCP section containing tool configuration per table/model."""

    all_create: bool = False
    auth: Optional[AuthMethod] = None
    tools: Dict[str, MCPToolConfig] = Field(default_factory=dict)


class AppConfig(BaseModel):
    """Unified TOML configuration model for model/sql/rest/mcp sections."""

    model: ModelConfig
    sql: SQLConfig
    rest: RestConfig = Field(default_factory=RestConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    @classmethod
    def from_toml(cls, toml_path: str | Path) -> "AppConfig":
        with open(toml_path, "r", encoding="utf-8") as handle:
            raw = toml.load(handle)
        return cls.model_validate(raw or {})


# Ensure forward references are resolved when this module is loaded directly.
SQLEmbeddingConfig.model_rebuild()
SQLTableConfig.model_rebuild()
SQLConfig.model_rebuild()
RestConfig.model_rebuild()
MCPToolConfig.model_rebuild()
MCPConfig.model_rebuild()
AppConfig.model_rebuild()
