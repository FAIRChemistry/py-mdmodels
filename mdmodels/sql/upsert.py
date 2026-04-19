from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Tuple

from sqlmodel import SQLModel, Session

from mdmodels.datamodel import DataModel
from mdmodels.library import CrossConnection, Library
from mdmodels.sql.base import SQLBase
from mdmodels.sql.childref import ChildRef
from mdmodels.sql.insert import fetch_row, get_primary_key, insert_nested


def upsert_nested(
    data: DataModel | List[DataModel],
    library: Library[DataModel],
    session: Session,
    models: Library[SQLBase],
) -> List[SQLModel]:
    """Upsert one or multiple flat DataModel instances.

    Supports top-level ``row_pk`` targeting plus ChildRef-based relationship updates.
    If no matching row exists, falls back to regular nested insert.
    """
    if not isinstance(data, list):
        data = [data]

    rows: List[SQLModel] = []
    for item in data:
        rows.append(
            _upsert_single(
                data=item,
                library=library,
                session=session,
                models=models,
            )
        )

    return rows


def _upsert_single(
    *,
    data: DataModel,
    library: Library[DataModel],
    session: Session,
    models: Library[SQLBase],
) -> SQLModel:
    type_name = type(data).__name__
    table = models[type_name]
    pk_name = get_primary_key(table)

    row_pk = getattr(data, "row_pk", None)
    payload_pk = getattr(data, pk_name, None) if _model_has_field(data, pk_name) else None

    if row_pk is not None and payload_pk is not None and row_pk != payload_pk:
        raise ValueError(
            f"Conflicting primary key values for {type_name}: "
            f"row_pk={row_pk!r} vs {pk_name}={payload_pk!r}"
        )

    effective_pk = row_pk if row_pk is not None else payload_pk
    existing = session.get(table, effective_pk) if effective_pk is not None else None

    if existing is None:
        create_data = _prepare_create_payload(
            data=data,
            pk_name=pk_name,
            pk_value=effective_pk,
        )
        created = insert_nested(
            data=create_data,
            library=library,
            session=session,
            models=models,
        )
        return created[0]

    connection_map = _connection_map(type_name, library)
    scalar_fields = set(table.model_fields.keys())
    memo: Dict[Tuple[str, Any], SQLModel] = {(type_name, effective_pk): existing}

    for key, value in data:
        if key in {"row_pk", pk_name}:
            continue

        conn = connection_map.get(key)
        if conn is None:
            if key not in scalar_fields:
                # Attribute exists in the domain model but is not persisted in SQL.
                # Example: arrays of primitive fields that are intentionally skipped.
                continue
            if issubclass(type(value), Enum):
                setattr(existing, key, value.value)
            else:
                setattr(existing, key, value)
            continue

        if conn.source_attr is None:
            continue

        if conn.is_array:
            if not isinstance(value, list):
                raise ValueError(f"Value for array relation '{key}' must be a list")

            resolved_values = [
                _resolve_relation_value(
                    conn=conn,
                    value=item,
                    session=session,
                    models=models,
                    memo=memo,
                )
                for item in value
            ]

            current_values = list(getattr(existing, conn.source_attr, []) or [])
            merged_values = _merge_relation_values(current_values, resolved_values)
            setattr(existing, conn.source_attr, merged_values)
            continue

        resolved_value = _resolve_relation_value(
            conn=conn,
            value=value,
            session=session,
            models=models,
            memo=memo,
        )
        setattr(existing, conn.source_attr, resolved_value)

    return existing


def _prepare_create_payload(
    *,
    data: DataModel,
    pk_name: str,
    pk_value: Any,
) -> DataModel:
    if pk_value is None or not _model_has_field(data, pk_name):
        return data

    if getattr(data, pk_name, None) is not None:
        return data

    return data.model_copy(update={pk_name: pk_value})


def _resolve_relation_value(
    *,
    conn: CrossConnection,
    value: Any,
    session: Session,
    models: Library[SQLBase],
    memo: Dict[Tuple[str, Any], SQLModel],
) -> Any:
    if isinstance(value, ChildRef):
        return fetch_row(
            conn=conn,
            ref=value,
            session=session,
            models=models,
            memo=memo,
        )

    if isinstance(value, DataModel):
        raise ValueError(
            "Upsert expects flat payloads for connected fields. "
            "Use ChildRef(row_pk=...) for related objects."
        )

    return value


def _connection_map(type_name: str, library: Library) -> Dict[str, CrossConnection]:
    return {
        conn.source_attr: conn
        for conn in library.get_object_connections(type_name)
        if conn.source_attr is not None and conn.source_type == type_name
    }


def _merge_relation_values(
    current_values: List[Any],
    new_values: List[Any],
) -> List[Any]:
    merged = list(current_values)
    seen = {_relation_identity(item) for item in current_values}

    for item in new_values:
        item_id = _relation_identity(item)
        if item_id in seen:
            continue
        merged.append(item)
        seen.add(item_id)

    return merged


def _relation_identity(item: Any) -> tuple[str, Any]:
    if isinstance(item, SQLModel):
        table_name = type(item).__name__
        pk_name = get_primary_key(type(item))
        return (table_name, getattr(item, pk_name, None))
    return ("value", item)


def _model_has_field(value: DataModel, field_name: str) -> bool:
    return field_name in value.__class__.model_fields
