from __future__ import annotations

from collections import deque
from functools import lru_cache
from typing import Any, Iterable, Literal, Type, TypedDict, get_origin

from pydantic import BaseModel

from mdmodels.utils import extract_dtype

PK_FLAG_KEYS = {"primary_key", "pk"}

__all__ = ["JoinEdge", "apply_join_chain", "find_join_chain"]


class JoinEdge(TypedDict):
    """Represents one hop in a join chain between data models."""

    from_type: str
    from_field: str
    to_type: str
    to_field: str
    is_many: bool
    direction: Literal["down", "up"]


def find_join_chain(
    source: str | Type[BaseModel],
    target: str | Type[BaseModel],
    models: Iterable[Type[BaseModel]],
) -> list[JoinEdge]:
    """
    Return the join chain between source and target using provided models.

    Args:
        source: Name or type of the source model.
        target: Name or type of the target model.
        models: Iterable of model types to inspect for relations.

    Returns:
        List of JoinEdge entries in traversal order. Empty if no path exists.
    """

    def norm(t: str | Type[BaseModel]) -> str:
        if isinstance(t, str):
            return t
        # Support Enum or other objects with a .name attribute (e.g., Table enums)
        if hasattr(t, "name"):
            return str(getattr(t, "name"))
        return t.__name__

    relations = _collect_relations(models)
    edge_keys = tuple(_edge_key(edge) for edge in relations)
    chain = _find_join_chain_cached(norm(source), norm(target), edge_keys)
    # Return a list view without copying inner dicts (cache holds immutable tuples)
    return list(chain)


def apply_join_chain(
    stmt: Any,
    *,
    start_cls: Type,
    join_chain: Iterable[JoinEdge],
    db_models: Any,
) -> Any:
    """
    Apply a computed join chain to a SQLAlchemy/SQLModel statement.

    Prefers relationship attributes if present; otherwise falls back to
    explicit column equality joins. Raises if required join attributes are
    missing.
    """

    current_cls = start_cls
    for edge in join_chain:
        next_cls = db_models[edge["to_type"]]

        rel_attr = getattr(current_cls, edge["from_field"], None)
        if rel_attr is not None:
            stmt = stmt.join(rel_attr)
        else:
            left_col = getattr(current_cls, edge["from_field"], None)
            right_col = getattr(next_cls, edge["to_field"], None)
            if left_col is None or right_col is None:
                raise ValueError(
                    f"Join attribute not found for edge {edge['from_type']} -> {edge['to_type']}"
                )
            stmt = stmt.join(next_cls, left_col == right_col)

        current_cls = next_cls

    return stmt


def _collect_relations(models: Iterable[Type[BaseModel]]) -> tuple[JoinEdge, ...]:
    """Collect complex (BaseModel) relations from model fields."""
    edges: list[JoinEdge] = []
    for model in models:
        for field_name, field in model.model_fields.items():  # type: ignore[attr-defined]
            outer = get_origin(field.annotation)
            is_many = outer in (list, set, tuple)
            dtype = extract_dtype(field.annotation)
            if isinstance(dtype, type) and issubclass(dtype, BaseModel):
                target_pk = _find_primary_key(dtype)
                edges.append(
                    {
                        "from_type": model.__name__,
                        "to_type": dtype.__name__,
                        "from_field": field_name,
                        "to_field": target_pk,
                        "is_many": is_many,
                        "direction": "down",
                    }
                )
    return tuple(edges)


def _edge_key(edge: JoinEdge) -> tuple:
    return (
        edge["from_type"],
        edge["to_type"],
        edge["from_field"],
        edge["to_field"],
        edge["is_many"],
        edge["direction"],
    )


@lru_cache(maxsize=512)
def _build_graph(edge_keys: tuple[tuple, ...]) -> dict[str, list[JoinEdge]]:
    graph: dict[str, list[JoinEdge]] = {}
    for from_type, to_type, from_field, to_field, is_many, _ in edge_keys:
        down_edge: JoinEdge = {
            "from_type": from_type,
            "to_type": to_type,
            "from_field": from_field,
            "to_field": to_field,
            "is_many": is_many,
            "direction": "down",
        }
        graph.setdefault(from_type, []).append(down_edge)

        up_edge: JoinEdge = {
            "from_type": to_type,
            "to_type": from_type,
            "from_field": to_field,
            "to_field": from_field,
            "is_many": is_many,
            "direction": "up",
        }
        graph.setdefault(to_type, []).append(up_edge)
    return graph


def _find_primary_key(model: Type[BaseModel]) -> str:
    """
    Detect the primary key field on a Pydantic model.

    Prefer an explicit json_schema_extra flag (primary_key/pk). If none is found,
    fall back to the conventional 'id' used by sql/create.py.
    """

    for name, field in model.model_fields.items():  # type: ignore[attr-defined]
        extra = getattr(field, "json_schema_extra", None) or {}
        if any(extra.get(flag, False) for flag in PK_FLAG_KEYS):
            return name

    return "id"


@lru_cache(maxsize=512)
def _find_join_chain_cached(
    source: str,
    target: str,
    edge_keys: tuple[tuple, ...],
) -> tuple[JoinEdge, ...]:
    graph = _build_graph(edge_keys)
    if source not in graph or target not in graph:
        return tuple()

    queue = deque([source])
    visited = {source}
    parent: dict[str, tuple[str, JoinEdge]] = {}

    while queue:
        node = queue.popleft()
        if node == target:
            break
        for edge in graph.get(node, []):
            nxt = edge["to_type"]
            if nxt in visited:
                continue
            visited.add(nxt)
            parent[nxt] = (node, edge)
            queue.append(nxt)

    if target not in visited:
        return tuple()

    path: list[JoinEdge] = []
    cur = target
    while cur != source:
        prev, edge = parent[cur]
        path.append(edge)
        cur = prev

    path.reverse()
    return tuple(path)
