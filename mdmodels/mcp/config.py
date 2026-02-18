from pathlib import Path
from typing import TYPE_CHECKING, Dict, Literal, Optional

from pydantic import BaseModel, Field

MCPOperation = Literal["create", "vector_search"]

if TYPE_CHECKING:
    from mdmodels.config import AppConfig


class MCPConfig(BaseModel):
    """
    Configuration for the MCP server.
    """

    description: Optional[str] = Field(default=None)
    allow_create: bool = Field(default=False)

    @classmethod
    def from_config(cls, config: "AppConfig", model_name: str) -> "MCPConfig":
        """Create MCP runtime config for one model/tool from unified app config."""
        tool_cfg = config.mcp.tools.get(model_name)
        if tool_cfg is None:
            return cls()
        return cls(description=tool_cfg.description, allow_create=tool_cfg.allow_create)

    @classmethod
    def from_toml(cls, toml_path: str | Path, model_name: str) -> "MCPConfig":
        """Create MCP runtime config for one model/tool from TOML."""
        from mdmodels.config import AppConfig

        return cls.from_config(AppConfig.from_toml(toml_path), model_name)

    @classmethod
    def map_from_config(cls, config: "AppConfig") -> Dict[str, "MCPConfig"]:
        """Create MCP runtime config mapping for all configured models/tools."""
        return {
            model_name: cls(
                description=tool_cfg.description,
                allow_create=tool_cfg.allow_create,
            )
            for model_name, tool_cfg in config.mcp.tools.items()
        }

    @classmethod
    def map_from_toml(cls, toml_path: str | Path) -> Dict[str, "MCPConfig"]:
        """Create MCP runtime config mapping from TOML."""
        from mdmodels.config import AppConfig

        return cls.map_from_config(AppConfig.from_toml(toml_path))
