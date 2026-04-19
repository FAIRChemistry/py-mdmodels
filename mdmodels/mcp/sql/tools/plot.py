from __future__ import annotations

import inspect
import json
import numbers
from typing import Annotated, Any, List, Literal, Optional

import sqlalchemy as sa
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP, ResourcePermissions
from fastmcp.server.dependencies import get_access_token
from fastmcp.tools import ToolResult
from mcp import types
from pydantic import BaseModel, Field

from mdmodels.library import Library
from mdmodels.sql import FilterTask, select
from mdmodels.sql.base import SQLBase
from mdmodels.sql.insert import get_primary_key

from ..constants import ISS, PLOT_DESCRIPTION, SUBJECT
from ..middleware import CTX_SESSION
from ..ownership import get_owned_ids, is_scoped
from ._assets import load_html_asset

PLOT_VIEW_URI = "ui://mdmodels/plot-viewer.html"

_NUMERIC = (sa.Float, sa.Integer, sa.Numeric, sa.BigInteger, sa.SmallInteger)
_STRING = (sa.String, sa.Text, sa.Enum, sa.VARCHAR, sa.Unicode, sa.UnicodeText, sa.CHAR)
_BOOL = (sa.Boolean,)


class PlotSuggestion(BaseModel):
    x: str
    y: Optional[str] = None
    color: Optional[str] = None
    plot_type: Literal["scatter", "line", "bar", "histogram", "boxplot"] = "scatter"
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    title: Optional[str] = None
    split_by: Optional["PlotSplitBy"] = Field(
        default=None,
        description=(
            "Optional split/filter dimension for comparison across entities. "
            "Evaluate this before finalizing the chart. Use split_by only when you can "
            "identify a valid, reachable partitioning dimension (typically from the base "
            "table or a parent table) that should drive filtering/subplots."
        ),
    )


class PlotSplitBy(BaseModel):
    """Optional split/filter by table primary key."""

    table: Optional[str] = Field(
        default=None,
        description="Optional source table to discriminate by. Defaults to the queried base table. If set, it must be a parent table of the base table.",
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional output alias for the split-by key. If omitted, a table-qualified primary key alias is used.",
    )
    display_column: Optional[str] = Field(
        default=None,
        description="Optional string-like column on split_by.table used only for dropdown labels. Filtering still uses the table primary key.",
    )


class SeriesXAxis(BaseModel):
    mode: Literal["index", "column"] = "index"
    column: Optional[str] = Field(
        default=None,
        description="Required when mode='column'. Must exist on the selected `table` (or base table if omitted).",
    )
    table: Optional[str] = Field(
        default=None,
        description="Optional source table for x.column; defaults to the queried base table.",
    )
    alias: Optional[str] = Field(
        default=None, description="Optional output name for x values."
    )


class SeriesGroupBy(BaseModel):
    table: str = Field(
        description="Source table for grouping. Must be reachable from the queried base table through table relationships."
    )
    column: str = Field(
        description="Grouping column on `table`. Verify with Get_Table_Schema before using."
    )
    alias: Optional[str] = Field(
        default=None,
        description="Optional output label for this grouping dimension.",
    )


class SeriesMode(BaseModel):
    value_column: str = Field(
        description="Array-like numeric column to explode into points (for example Measurement.values)."
    )
    value_table: Optional[str] = Field(
        default=None,
        description="Table containing value_column; defaults to the queried base table.",
    )
    value_alias: str = "__value"
    x: SeriesXAxis = Field(default_factory=SeriesXAxis)
    group_by: list[SeriesGroupBy] = Field(default_factory=list)


def register_plot_tool(
    *,
    app: FastMCP,
    db_models: Library[SQLBase],
    available_tables,
    available_models,
    shared_tables: set[str],
) -> None:
    """Register the interactive plot tool backed by ECharts.

    It reuses table filtering/ownership rules and returns query results plus
    LLM-provided defaults to the sandboxed plot viewer app.
    """

    @app.resource(
        PLOT_VIEW_URI,
        app=AppConfig(
            csp=ResourceCSP(
                resourceDomains=["https://cdn.jsdelivr.net", "https://unpkg.com"]
            ),
            permissions=ResourcePermissions(clipboardWrite={}),
        ),
    )
    def _plot_viewer_resource() -> str:
        return PLOT_HTML

    def plot_from_table(
        table,
        suggested: Annotated[
            PlotSuggestion,
            "LLM-supplied plot defaults. Infer x/y from numeric columns, "
            "color from string/boolean columns. Set plot_type based on the "
            "user's intent: 'scatter' or 'line' for two numeric axes, "
            "'histogram' for a single numeric axis, 'bar' or 'boxplot' for "
            "categorical x + numeric y. Optionally set x_label, y_label, "
            "title, and split_by ({table?, alias?, display_column?}) to expose an "
            "optional dropdown filter in the UI. Before suggesting any cross-table "
            "column (for x.table, group_by.table, or split_by.table), first call "
            "Get_Table_Relationships and ensure the table is reachable from the base "
            "query table. split_by always uses the selected table primary key and "
            "is restricted to base table or parent tables. If useful, set "
            "split_by.display_column to a readable string field for dropdown labels. "
            "Before finalizing any chart, explicitly decide whether a valid split_by "
            "dimension exists. Distinguish split_by from color/grouping: split_by "
            "creates a filter/subplot partition across entities, while color/grouping "
            "only encodes series within the currently selected partition. Prefer "
            "split_by when comparisons across partitions are central, when a parent "
            "table naturally segments records, or when a single combined chart would "
            "hide structure due to overlap. If no valid partition is available, leave "
            "split_by unset instead of forcing it.",
        ],
        limit: int = 500,
        filters: Annotated[
            List,
            "List of filter tasks identical to Select_Table. Before any filter task, "
            "you MUST call Get_Table_Schema and Get_Table_Relationships to verify "
            "column names, types, and join reachability.",
        ] = [],
        filter_logic: Annotated[
            Literal["and", "or"],
            "Logic to combine top-level filters.",
        ] = "and",
        subplots: Annotated[
            bool,
            "If true and split_by is set, render one subplot per split group. "
            "Use this for side-by-side/stacked comparison instead of a single combined chart.",
        ] = False,
        series_mode: Annotated[
            Optional[SeriesMode],
            "Optional special mode for time-series/replicate visualization from array values. "
            "Set value_column to an array-like numeric field (for example Measurement.values). "
            "Use x.mode='index' or x.mode='column', and optionally add group_by fields from "
            "related tables (joins are resolved automatically). Always validate each "
            "group_by.table/group_by.column with Get_Table_Relationships + Get_Table_Schema "
            "before sending the request.",
        ] = None,
    ) -> ToolResult:
        """Query a table and display the results as an interactive ECharts plot.

        The chart renders in a sandboxed UI with live-editable controls for
        axis selection, color grouping, and plot type. The LLM pre-fills
        sensible defaults via ``suggested``; the user can override everything
        interactively.
        """
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        table_class = db_models[table]
        rows = _fetch_rows(
            session=session,
            db_models=db_models,
            table=table,
            table_class=table_class,
            filters=filters,
            filter_logic=filter_logic,
            limit=limit,
            shared_tables=shared_tables,
        )

        split_by_cfg = suggested.split_by

        if series_mode is None:
            payload = _build_flat_payload(
                session=session,
                db_models=db_models,
                table=table,
                table_class=table_class,
                rows=rows,
                suggested=suggested,
                split_by_cfg=split_by_cfg,
                subplots=subplots,
            )
        else:
            payload = _build_series_payload(
                session=session,
                db_models=db_models,
                table=table,
                table_class=table_class,
                rows=rows,
                suggested=suggested,
                split_by_cfg=split_by_cfg,
                subplots=subplots,
                series_mode=series_mode,
            )

        return ToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))]
        )

    plot_from_table.__annotations__ = {
        "table": available_tables,
        "suggested": PlotSuggestion,
        "limit": int,
        "filters": List[FilterTask[available_models]],
        "filter_logic": Literal["and", "or"],
        "subplots": bool,
        "series_mode": Optional[SeriesMode],
        "return": ToolResult,
    }  # type: ignore[assignment]
    plot_from_table.__signature__ = inspect.signature(plot_from_table)  # type: ignore[attr-defined]

    app.tool(
        plot_from_table,
        name="Plot_Table",
        description=PLOT_DESCRIPTION,
        app=AppConfig(resourceUri=PLOT_VIEW_URI),
    )


# ── HTML (ECharts) ────────────────────────────────────────────────────────────
def _load_plot_html() -> str:
    return load_html_asset("plot_viewer.html")


PLOT_HTML = _load_plot_html()


def _collapse_values(values: list[Any]) -> Any:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


def _infer_dtype_from_values(values: list[Any]) -> str:
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "other"

    if all(isinstance(v, bool) for v in non_null):
        return "boolean"
    if all(isinstance(v, str) for v in non_null):
        return "string"
    if all(isinstance(v, numbers.Real) and not isinstance(v, bool) for v in non_null):
        return "numeric"
    return "other"


def _normalize_group_value(value: Any) -> Any:
    if isinstance(value, list):
        compact = [v for v in value if v is not None]
        if not compact:
            return None
        return " | ".join(dict.fromkeys(str(v) for v in compact))
    return value


def _resolve_named_column_map(
    *,
    session,
    db_models: Library[SQLBase],
    base_table: str,
    base_table_class,
    base_pk_name: str,
    row_ids: list[Any],
    rows,
    source_table: str,
    source_column: str,
    alias: Optional[str] = None,
    require_parent_path: bool = False,
) -> tuple[str, dict[Any, Any]]:
    if source_table not in db_models:
        raise ValueError(f"Table '{source_table}' is not available.")

    source_cls = db_models[source_table]
    if not hasattr(source_cls, source_column):
        raise ValueError(
            f"Column '{source_column}' not found in table '{source_table}'."
        )

    if source_table != base_table:
        join_chain = db_models.find_join_chain(base_table, source_table)
        if not join_chain:
            raise ValueError(
                f"No join path exists from '{base_table}' to '{source_table}'. "
                "Call Get_Table_Relationships before choosing cross-table columns."
            )
        if require_parent_path and any(
            edge["direction"] != "up" for edge in join_chain
        ):
            raise ValueError(
                "Discriminator must come from a parent table of the base table. "
                f"'{source_table}' is not a parent of '{base_table}'."
            )

    resolved_alias = alias or (
        source_column
        if source_table == base_table
        else f"{source_table}.{source_column}"
    )
    column_map = _resolve_column_map(
        session=session,
        db_models=db_models,
        base_table=base_table,
        base_table_class=base_table_class,
        base_pk_name=base_pk_name,
        row_ids=row_ids,
        rows=rows,
        source_table=source_table,
        source_column=source_column,
    )
    return resolved_alias, column_map


def _resolve_column_map(
    *,
    session,
    db_models: Library[SQLBase],
    base_table: str,
    base_table_class,
    base_pk_name: str,
    row_ids: list[Any],
    rows,
    source_table: str,
    source_column: str,
) -> dict[Any, Any]:
    values_by_id: dict[Any, list[Any]] = {row_id: [] for row_id in row_ids}

    if source_table == base_table:
        for row in rows:
            row_id = getattr(row, base_pk_name)
            values_by_id[row_id].append(getattr(row, source_column, None))
        return {row_id: _collapse_values(vals) for row_id, vals in values_by_id.items()}

    source_cls = db_models[source_table]
    if not hasattr(source_cls, source_column):
        raise ValueError(
            f"Column '{source_column}' not found in table '{source_table}'."
        )

    base_pk_col = getattr(base_table_class, base_pk_name)
    source_col = getattr(source_cls, source_column)

    stmt = select(base_pk_col, source_col).select_from(base_table_class)
    stmt = db_models.apply_join_chain(stmt, source=base_table, target=source_table)
    stmt = stmt.where(base_pk_col.in_(row_ids))

    for base_id, value in session.exec(stmt).all():
        if base_id not in values_by_id:
            continue
        if value not in values_by_id[base_id]:
            values_by_id[base_id].append(value)

    return {row_id: _collapse_values(vals) for row_id, vals in values_by_id.items()}


def _expand_series_rows(
    *,
    rows,
    base_pk_name: str,
    value_map: dict[Any, Any],
    x_mode: SeriesXAxis,
    x_map: dict[Any, Any] | None,
    x_name: str,
    y_name: str,
    group_maps: list[tuple[str, dict[Any, Any]]],
    extra_maps: list[tuple[str, dict[Any, Any]]] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    extra_maps = extra_maps or []

    for row in rows:
        row_id = getattr(row, base_pk_name)
        y_raw = value_map.get(row_id)
        if y_raw is None:
            continue

        y_values = list(y_raw) if isinstance(y_raw, (list, tuple)) else [y_raw]
        if not y_values:
            continue

        points: list[tuple[Any, Any]] = []
        if x_mode.mode == "index":
            points = [(idx, y) for idx, y in enumerate(y_values)]
        else:
            x_raw = x_map.get(row_id) if x_map is not None else None
            if isinstance(x_raw, (list, tuple)):
                x_values = list(x_raw)
                if len(y_values) > 1:
                    n = min(len(x_values), len(y_values))
                    points = [(x_values[i], y_values[i]) for i in range(n)]
                elif len(y_values) == 1:
                    points = [(xv, y_values[0]) for xv in x_values]
            else:
                if len(y_values) > 1 and x_raw is None:
                    points = [(idx, y) for idx, y in enumerate(y_values)]
                elif len(y_values) > 1:
                    points = [(x_raw, y) for y in y_values]
                else:
                    points = [(x_raw, y_values[0])]

        for x_value, y_value in points:
            if y_value is None:
                continue
            row_out: dict[str, Any] = {x_name: x_value, y_name: y_value}
            for alias, gmap in group_maps:
                row_out[alias] = _normalize_group_value(gmap.get(row_id))
            for alias, emap in extra_maps:
                row_out[alias] = _normalize_group_value(emap.get(row_id))
            out.append(row_out)

    return out


def _build_suggested_payload(
    suggested: PlotSuggestion, split_control: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    payload = suggested.model_dump()
    payload.pop("discriminator", None)
    if split_control:
        payload["split_by"] = split_control
    return payload


def _resolve_split_by(
    *,
    split_by_cfg: Optional[PlotSplitBy],
    session,
    db_models: Library[SQLBase],
    table: str,
    table_class,
    rows,
) -> Optional[dict[str, Any]]:
    if split_by_cfg is None:
        return None

    base_pk_name = get_primary_key(table_class)
    row_ids = [getattr(row, base_pk_name) for row in rows]
    split_table = split_by_cfg.table or table
    split_pk = get_primary_key(db_models[split_table])

    def _named_map(source_column: str, alias: Optional[str]):
        return _resolve_named_column_map(
            session=session,
            db_models=db_models,
            base_table=table,
            base_table_class=table_class,
            base_pk_name=base_pk_name,
            row_ids=row_ids,
            rows=rows,
            source_table=split_table,
            source_column=source_column,
            alias=alias,
            require_parent_path=True,
        )

    split_alias, split_map = _named_map(split_pk, split_by_cfg.alias)

    display_alias: Optional[str] = None
    display_map: dict[Any, Any] | None = None
    if split_by_cfg.display_column:
        display_alias = f"{split_alias}__display"
        _, display_map = _named_map(split_by_cfg.display_column, display_alias)

    control = {"column": split_alias, "table": split_table, "label": split_table}
    if display_alias:
        control["display_column"] = display_alias

    return {
        "base_pk_name": base_pk_name,
        "table": split_table,
        "alias": split_alias,
        "map": split_map,
        "display_alias": display_alias,
        "display_map": display_map,
        "control": control,
    }


def _fetch_rows(
    *,
    session,
    db_models: Library[SQLBase],
    table: str,
    table_class,
    filters: list,
    filter_logic: Literal["and", "or"],
    limit: int,
    shared_tables: set[str],
):
    from sqlmodel import intersect

    subqueries = []
    if filters:
        subqueries.append(
            FilterTask.build_filtered_query(
                table_name=table,
                table_class=table_class,
                filters=filters,
                db_models=db_models,
                logic="intersect" if filter_logic == "and" else "union",
            )
        )

    token = get_access_token()
    if token is not None and is_scoped(table, shared_tables):
        owned_ids = get_owned_ids(
            session=session,
            table_name=table,
            provider=token.claims[ISS],
            subject=token.claims[SUBJECT],
        )
        pk_col = getattr(table_class, get_primary_key(table_class))
        subqueries.append(select(table_class).where(pk_col.in_(owned_ids or [-1])))

    if not subqueries:
        return session.exec(
            select(table_class).limit(limit)  # pyright: ignore[reportCallIssue, reportArgumentType]
        ).all()

    final_stmt = intersect(*subqueries) if len(subqueries) > 1 else subqueries[0]
    return (
        session.exec(
            select(table_class).from_statement(final_stmt),  # pyright: ignore[reportCallIssue, reportArgumentType]
        )
        .scalars()
        .all()
    )


def _build_flat_payload(
    *,
    session,
    db_models: Library[SQLBase],
    table: str,
    table_class,
    rows,
    suggested: PlotSuggestion,
    split_by_cfg: Optional[PlotSplitBy],
    subplots: bool,
) -> dict[str, Any]:
    flat_rows = [
        {col: getattr(row, col) for col in row.__table__.columns.keys()}  # pyright: ignore[reportAttributeAccessIssue]
        for row in rows
    ]
    columns = _classify_columns(table_class)
    controls: dict[str, Any] = {}

    split = _resolve_split_by(
        split_by_cfg=split_by_cfg,
        session=session,
        db_models=db_models,
        table=table,
        table_class=table_class,
        rows=rows,
    )
    if split:
        split_alias = split["alias"]
        split_map = split["map"]
        display_alias = split["display_alias"]
        display_map = split["display_map"]
        base_pk_name = split["base_pk_name"]
        for row, row_payload in zip(rows, flat_rows):
            row_id = getattr(row, base_pk_name)
            row_payload[split_alias] = _normalize_group_value(split_map.get(row_id))
            if display_alias and display_map is not None:
                row_payload[display_alias] = _normalize_group_value(
                    display_map.get(row_id)
                )
        if split_alias not in {col["name"] for col in columns}:
            columns.append(
                {
                    "name": split_alias,
                    "dtype": _infer_dtype_from_values(
                        [row.get(split_alias) for row in flat_rows]
                    ),
                }
            )
        controls["split_by"] = split["control"]

    payload = {
        "_meta": {"table": table, "subplots": bool(subplots and split_by_cfg)},
        "columns": columns,
        "suggested": _build_suggested_payload(suggested, controls.get("split_by")),
        "data": flat_rows,
    }
    if controls:
        payload["controls"] = controls
    return payload


def _build_series_payload(
    *,
    session,
    db_models: Library[SQLBase],
    table: str,
    table_class,
    rows,
    suggested: PlotSuggestion,
    split_by_cfg: Optional[PlotSplitBy],
    subplots: bool,
    series_mode: SeriesMode,
) -> dict[str, Any]:
    base_pk_name = get_primary_key(table_class)
    row_ids = [getattr(row, base_pk_name) for row in rows]

    value_table = series_mode.value_table or table
    if value_table not in db_models:
        raise ValueError(f"Series value table '{value_table}' is not available.")
    value_cls = db_models[value_table]
    if not hasattr(value_cls, series_mode.value_column):
        raise ValueError(
            f"Column '{series_mode.value_column}' not found in table '{value_table}'."
        )

    def _col_map(source_table: str, source_column: str):
        return _resolve_column_map(
            session=session,
            db_models=db_models,
            base_table=table,
            base_table_class=table_class,
            base_pk_name=base_pk_name,
            row_ids=row_ids,
            rows=rows,
            source_table=source_table,
            source_column=source_column,
        )

    value_map = _col_map(value_table, series_mode.value_column)

    x_mode = series_mode.x
    x_name = (
        x_mode.alias
        or x_mode.column
        or ("__point_index" if x_mode.mode == "index" else "__x")
    )
    y_name = series_mode.value_alias or "__value"
    x_map = None
    if x_mode.mode == "column":
        x_table = x_mode.table or table
        if not x_mode.column:
            raise ValueError("series_mode.x.column is required when x.mode='column'.")
        if x_table not in db_models:
            raise ValueError(f"Series x table '{x_table}' is not available.")
        x_cls = db_models[x_table]
        if not hasattr(x_cls, x_mode.column):
            raise ValueError(
                f"Column '{x_mode.column}' not found in table '{x_table}'."
            )
        x_map = _col_map(x_table, x_mode.column)

    group_maps: list[tuple[str, dict[Any, Any]]] = []
    for group in series_mode.group_by:
        if group.table not in db_models:
            raise ValueError(f"Group-by table '{group.table}' is not available.")
        group_cls = db_models[group.table]
        if not hasattr(group_cls, group.column):
            raise ValueError(
                f"Group-by column '{group.column}' not found in table '{group.table}'."
            )
        alias = group.alias or f"{group.table}.{group.column}"
        group_maps.append(
            (
                alias,
                _col_map(group.table, group.column),
            )
        )

    split = _resolve_split_by(
        split_by_cfg=split_by_cfg,
        session=session,
        db_models=db_models,
        table=table,
        table_class=table_class,
        rows=rows,
    )
    extra_maps: list[tuple[str, dict[Any, Any]]] = []
    if split:
        split_alias = split["alias"]
        if split_alias not in {alias for alias, _ in group_maps}:
            group_maps.append((split_alias, split["map"]))
        if split["display_alias"] and split["display_map"] is not None:
            extra_maps.append((split["display_alias"], split["display_map"]))

    series_rows = _expand_series_rows(
        rows=rows,
        base_pk_name=base_pk_name,
        value_map=value_map,
        x_mode=x_mode,
        x_map=x_map,
        x_name=x_name,
        y_name=y_name,
        group_maps=group_maps,
        extra_maps=extra_maps,
    )

    columns = [
        {
            "name": x_name,
            "dtype": (
                "numeric"
                if x_mode.mode == "index"
                else _infer_dtype_from_values([r.get(x_name) for r in series_rows])
            ),
        },
        {"name": y_name, "dtype": "numeric"},
    ] + [
        {
            "name": alias,
            "dtype": _infer_dtype_from_values([r.get(alias) for r in series_rows]),
        }
        for alias, _ in group_maps
    ]
    available_names = {col["name"] for col in columns}
    split_control = (
        split["control"] if split and split["alias"] in available_names else None
    )
    suggested_payload = _build_suggested_payload(suggested, split_control)
    if suggested_payload.get("x") not in available_names:
        suggested_payload["x"] = x_name
    if (
        suggested_payload.get("y") not in available_names
        and suggested_payload.get("plot_type") != "histogram"
    ):
        suggested_payload["y"] = y_name
    if suggested_payload.get("color") not in available_names:
        suggested_payload["color"] = group_maps[0][0] if group_maps else None

    payload = {
        "_meta": {
            "table": table,
            "series_mode": True,
            "subplots": bool(subplots and split_by_cfg),
        },
        "columns": columns,
        "suggested": suggested_payload,
        "data": series_rows,
    }
    if split_control:
        payload["controls"] = {"split_by": split_control}
    return payload


def _infer_dtype(col: sa.Column) -> Literal["numeric", "string", "boolean"] | None:
    col_type = col.type
    affinity = getattr(col_type, "_type_affinity", None)

    def _matches(candidates: tuple[type, ...]) -> bool:
        if affinity is not None:
            try:
                if any(issubclass(affinity, candidate) for candidate in candidates):
                    return True
            except TypeError:
                pass
        return isinstance(col_type, candidates)

    if _matches(_NUMERIC):
        return "numeric"
    if _matches(_BOOL):
        return "boolean"
    if _matches(_STRING):
        return "string"

    try:
        py_type = col_type.python_type
    except (AttributeError, NotImplementedError):
        py_type = None

    if isinstance(py_type, type):
        if py_type is bool:
            return "boolean"
        if issubclass(py_type, str):
            return "string"
        if issubclass(py_type, numbers.Real):
            return "numeric"

    return None


def _classify_columns(table_class) -> list[dict]:
    """Return [{name, dtype}] for all non-internal columns.

    Every column is included so the UI can populate the X axis fully.
    Columns whose type cannot be mapped (e.g. JSON, vectors) get dtype
    'other' and are excluded from numeric-only dropdowns client-side.
    """
    result, skip = [], {"id", "embedding"}
    for col in table_class.__table__.columns:
        if col.name in skip:
            continue
        dtype = _infer_dtype(col) or "other"
        result.append({"name": col.name, "dtype": dtype})
    return result
