from typing import Generic, List, Literal

from pydantic import BaseModel, Field

from ..sql.filter import FilterTask, TEnum


class OrderSpec(BaseModel):
    """Sorting specification for search endpoints."""

    column: str
    direction: Literal["asc", "desc"] = "asc"


class SearchRequest(BaseModel, Generic[TEnum]):
    """Request body for advanced search endpoints."""

    filters: List[FilterTask[TEnum]] = Field(  # pyright: ignore[reportInvalidTypeForm]
        default_factory=list,
        description=(
            "Optional list of filter tasks to apply to the query. "
            "Each task specifies a table, list of filters, and how to combine them (and/or). "
            "Tables are validated against the generated model enum."
        ),
    )
    logic: Literal["union", "intersect"] = Field(
        default="union",
        description="The logic to apply to the filters. Default is 'union'. This is only used if filters are provided.",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of records to return (1–1000).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip before returning results.",
    )
    order_by: List[OrderSpec] = Field(
        default_factory=list,
        description="Optional list of columns to order by.",
    )
