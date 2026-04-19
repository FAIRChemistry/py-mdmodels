from pathlib import Path
from typing import TYPE_CHECKING, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, Field
from typing_extensions import Self

from mdmodels.config import AuthMethod

MCPOperation = Literal["create", "vector_search"]

if TYPE_CHECKING:
    from mdmodels.config import AppConfig


class MCPConfig(BaseModel):
    """
    Configuration for the MCP server.
    """

    description: Optional[str] = Field(default=None)
    allow_create: bool = Field(default=False)
    shared: bool = Field(default=False)

    @classmethod
    def from_config(cls, config: "AppConfig", model_name: str) -> "MCPConfig":
        """Create MCP runtime config for one model/tool from unified app config."""
        tool_cfg = config.mcp.tools.get(model_name)
        if tool_cfg is None:
            return cls()
        return cls(
            description=tool_cfg.description,
            allow_create=tool_cfg.allow_create,
            shared=tool_cfg.shared,
        )

    @classmethod
    def from_toml(cls, toml_path: str | Path, model_name: str) -> "MCPConfig":
        """Create MCP runtime config for one model/tool from TOML."""
        from mdmodels.config import AppConfig

        return cls.from_config(AppConfig.from_toml(toml_path), model_name)

    @classmethod
    def map_from_config(
        cls, config: "AppConfig"
    ) -> Tuple[
        Dict[str, Self],
        bool,
        AuthMethod | None,
    ]:
        """Create MCP runtime config mapping for all configured models/tools."""
        config_dict = {
            model_name: cls(
                description=tool_cfg.description,
                allow_create=tool_cfg.allow_create,
                shared=tool_cfg.shared,
            )
            for model_name, tool_cfg in config.mcp.tools.items()
        }

        return config_dict, config.mcp.all_create, config.mcp.auth

    @classmethod
    def map_from_toml(
        cls, toml_path: str | Path
    ) -> Tuple[
        Dict[str, Self],
        bool,
        AuthMethod | None,
    ]:
        """Create MCP runtime config mapping from TOML."""
        from mdmodels.config import AppConfig

        return cls.map_from_config(AppConfig.from_toml(toml_path))
