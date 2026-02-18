from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Set, Union

import toml
import yaml
from pydantic import BaseModel, Field, RootModel

if TYPE_CHECKING:
    from mdmodels.config import AppConfig

# CrudOperation is a literal type for the CRUD operations
CrudOperation = Literal[
    "create",
    "list",
    "retrieve",
    "update",
    "delete",
    "search",
    "vectorsearch",
]

# Predefined sets of operations
READ_OPERATIONS: List[CrudOperation] = ["list", "retrieve"]
WRITE_OPERATIONS: List[CrudOperation] = ["create", "update", "delete"]
SEARCH_OPERATIONS: List[CrudOperation] = ["search", "vectorsearch"]
ALL_OPERATIONS: List[CrudOperation] = (
    READ_OPERATIONS + WRITE_OPERATIONS + SEARCH_OPERATIONS
)


class SecurityConfig(BaseModel):
    """
    Security configuration for generated REST endpoints.

    - global_dependencies:
        Dependencies applied to every router for every model.
        Example: [Depends(require_login)]

    - per_model:
        A mapping of model_name -> operation -> dependencies.
        Example:
            {
                "Experiment": {
                    "delete": [Depends(only_admin)],
                    "create": [Depends(only_admin)],
                }
            }
    """

    global_dependencies: List[Any] = Field(default_factory=list)
    per_model: Dict[str, Dict[CrudOperation, List[Any]]] = Field(default_factory=dict)

    def deps_for(self, model_name: str, operation: CrudOperation) -> List[Any]:
        return self.per_model.get(model_name, {}).get(operation, [])


EndpointRule = Union[Literal["disable"], List[CrudOperation]]


class EndpointConfig(RootModel[Dict[str, EndpointRule]]):
    """
    Endpoint enable/disable configuration.

    Per-model configuration values:
      - None (missing model): all operations enabled
      - "disable": model skipped entirely
      - List[CrudOperation]: only these operations enabled
    """

    root: Dict[str, EndpointRule] = Field(default_factory=dict)

    def allowed_operations(self, model_name: str) -> Optional[Set[CrudOperation]]:
        value = self.root.get(model_name)
        if value is None:
            # Missing model means all operations are enabled.
            return None
        if value == "disable":
            # Explicit disable means the model is skipped entirely.
            return set()
        return set(value)


class RestApiConfig(BaseModel):
    """
    Root config object for the REST generator.
    Extend this later with pagination, versioning, logging, etc.
    """

    security: SecurityConfig = Field(default_factory=SecurityConfig)
    endpoints: EndpointConfig = Field(default_factory=lambda: EndpointConfig(root={}))

    @classmethod
    def from_config(cls, config: "AppConfig") -> "RestApiConfig":
        """Create REST runtime config from unified app config."""
        return cls.model_validate({"endpoints": config.rest.endpoints})

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> RestApiConfig:
        with open(yaml_path, "r") as f:
            yaml_data = yaml.safe_load(f)
        return cls.model_validate(yaml_data or {})

    @classmethod
    def from_toml(cls, toml_path: Path) -> RestApiConfig:
        with open(toml_path, "r") as f:
            toml_data = toml.load(f)
        # Support unified app config files ([rest.*]) and legacy REST-only files.
        if "rest" in toml_data:
            from mdmodels.config import AppConfig

            return cls.from_config(AppConfig.model_validate(toml_data or {}))
        return cls.model_validate(toml_data or {})
