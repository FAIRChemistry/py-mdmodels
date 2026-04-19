#  -----------------------------------------------------------------------------
#   Copyright (c) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#  #
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#  #
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#   THE SOFTWARE.
#  -----------------------------------------------------------------------------
from enum import Enum
from typing import Any, Dict, List, Tuple, Type

from sqlmodel import Session, SQLModel, select

from mdmodels.datamodel import DataModel
from mdmodels.library import CrossConnection, Library
from mdmodels.sql.base import SQLBase
from mdmodels.sql.childref import ChildRef


def insert_nested(
    data: DataModel | List[DataModel],
    library: Library[DataModel],
    session: Session,
    models: Library[SQLBase],
) -> List[SQLModel]:
    """
    Insert one or multiple DataModel instances into the database.

    Args:
        data (DataModel | List[DataModel]): The data model instance(s) to insert.
        library (Library): The library providing object connections.
        session (Session): The active database session.
        models (Library): A library containing model classes.

    Returns:
        List[SQLModel]: A list of SQLModel instances representing the inserted data.
    """
    if not isinstance(data, list):
        data = [data]

    connection_cache: Dict[str, Dict[str, CrossConnection]] = {}
    memo: Dict[Tuple[str, Any], SQLModel] = {}
    created_rows: List[SQLModel] = []

    rows: List[SQLModel] = []
    for item in data:
        rows.append(
            _to_sqlmodel(
                item,
                library=library,
                session=session,
                models=models,
                connection_cache=connection_cache,
                memo=memo,
                created_rows=created_rows,
            )
        )

    if created_rows:
        session.add_all(created_rows)

    return rows


def _to_sqlmodel(
    data: DataModel,
    library: Library,
    session: Session,
    models: Library,
    connection_cache: Dict[str, Dict[str, CrossConnection]],
    memo: Dict[Tuple[str, Any], SQLModel],
    created_rows: List[SQLModel],
) -> SQLModel:
    """
    Convert a DataModel instance to a SQLModel instance.

    Args:
        data (DataModel): The data model instance to convert.
        library (Library): The library providing object connections.
        session (Session): The active database session.
        models (Library): A library containing model classes.

    Returns:
        SQLModel: A SQLModel instance representing the data, or the original data if it is a primitive.
    """
    type_name = type(data).__name__
    connections = _connection_map(type_name, library, connection_cache)
    delayed_attrs: Dict[str, Any] = {}
    primitives: Dict[str, Any] = {}

    table = models[type_name]
    pk = get_primary_key(table)

    pk_val = getattr(data, pk, None) if _pk_exists(data, pk) else None
    memo_key = (type_name, pk_val)

    if pk_val is not None and memo_key in memo:
        return memo[memo_key]

    if pk_val is not None:
        existing = session.get(table, pk_val)
        if existing:
            memo[memo_key] = existing
            return existing

    for key, value in data:
        if key == "row_pk":
            # Technical upsert routing key, not a persisted domain column.
            continue

        conn = connections.get(key)
        if conn:
            _process_connected_attr(
                conn=conn,
                value=value,
                delayed_attrs=delayed_attrs,
                library=library,
                session=session,
                models=models,
                connection_cache=connection_cache,
                memo=memo,
                created_rows=created_rows,
            )
        else:
            if key not in table.model_fields:
                # Attribute exists in the domain model but is not persisted in SQL.
                continue
            if issubclass(type(value), Enum):
                # Handle enum values
                primitives[key] = value.value
            else:
                # Handle primitive values (not connected to other models)
                primitives[key] = value

    row = table(**primitives)
    _set_delayed_attributes(row, delayed_attrs)

    if pk_val is not None:
        memo[memo_key] = row

    created_rows.append(row)
    return row


def _process_connected_attr(
    conn: CrossConnection,
    value: DataModel | str | float | int | bool,
    delayed_attrs: Dict[str, Any],
    library: Library,
    session: Session,
    models: Library,
    connection_cache: Dict[str, Dict[str, CrossConnection]],
    memo: Dict[Tuple[str, Any], SQLModel],
    created_rows: List[SQLModel],
) -> None:
    """
    Process an attribute that is linked to another model and update delayed attributes.

    Args:
        conn (CrossConnection): The connection information for the attribute.
        value (DataModel | str | float | int | bool): The value of the attribute to process.
        delayed_attrs (Dict[str, Any]): A dictionary to store attributes that need delayed processing.
        library (Library): The library providing object connections.
        session (Session): The active database session.
        models (Library): A library containing model classes.
    """
    if conn.source_attr is None:
        return

    if conn.is_array:
        delayed_attrs[conn.source_attr] = []

        if not isinstance(value, list):
            raise ValueError(f"Value {value} is not a list")

        for item in value:
            if isinstance(item, DataModel):
                delayed_attrs[conn.source_attr].append(
                    _create_or_fetch_object(
                        item,
                        library,
                        session,
                        models,
                        connection_cache,
                        memo,
                        created_rows,
                    )
                )  # type: ignore
            elif isinstance(item, ChildRef):
                delayed_attrs[conn.source_attr].append(
                    fetch_row(
                        conn=conn,
                        ref=item,
                        session=session,
                        models=models,
                        memo=memo,
                    )
                )  # type: ignore
            else:
                delayed_attrs[conn.source_attr].append(item)  # type: ignore
    else:
        if isinstance(value, DataModel):
            processed_value = _to_sqlmodel(
                value,
                library=library,
                session=session,
                models=models,
                connection_cache=connection_cache,
                memo=memo,
                created_rows=created_rows,
            )
            delayed_attrs[conn.source_attr] = processed_value  # type: ignore
        elif isinstance(value, ChildRef):
            delayed_attrs[conn.source_attr] = fetch_row(
                conn=conn,
                ref=value,
                session=session,
                models=models,
                memo=memo,
            )  # type: ignore
        else:
            delayed_attrs[conn.source_attr] = value  # type: ignore


def fetch_row(
    conn: CrossConnection,
    ref: ChildRef,
    session: Session,
    models: Library,
    memo: Dict[Tuple[str, Any], SQLModel],
) -> SQLModel:
    """
    Fetch an existing relationship row from the database using a ChildRef.
    """
    table = models[conn.target_type]
    target_key = conn.target_attr or get_primary_key(table)
    memo_key = (conn.target_type, ref.row_pk)

    if memo_key in memo:
        return memo[memo_key]

    if target_key == get_primary_key(table):
        row = session.get(table, ref.row_pk)
    else:
        stmt = select(table).where(getattr(table, target_key) == ref.row_pk).limit(1)
        row = session.exec(stmt).first()

    if row is None:
        raise ValueError(
            f"Could not resolve ChildRef(row_pk_={ref.row_pk}) for {conn.target_type}"
        )

    memo[memo_key] = row
    return row


def _create_or_fetch_object(
    value: DataModel,
    library: Library,
    session: Session,
    models: Library,
    connection_cache: Dict[str, Dict[str, CrossConnection]],
    memo: Dict[Tuple[str, Any], SQLModel],
    created_rows: List[SQLModel],
) -> SQLModel:
    """
    Create or fetch an object from the database.

    Args:
        value (DataModel): The data model instance to create or fetch.
        library (Library): The library providing object connections.
        session (Session): The active database session.
        models (Library): A library containing model classes.
    """
    pk = get_primary_key(models[type(value).__name__])

    if not _pk_exists(value, pk):
        return _to_sqlmodel(
            value,
            library,
            session,
            models,
            connection_cache,
            memo,
            created_rows,
        )  # type: ignore

    table = models[type(value).__name__]
    pk_val = getattr(value, pk, None)
    memo_key = (type(value).__name__, pk_val)

    if pk_val is None:
        return _to_sqlmodel(
            value,
            library,
            session,
            models,
            connection_cache,
            memo,
            created_rows,
        )  # type: ignore

    if memo_key in memo:
        return memo[memo_key]

    result = session.get(table, pk_val)

    if result:
        memo[memo_key] = result
        return result

    row = _to_sqlmodel(
        value,
        library,
        session,
        models,
        connection_cache,
        memo,
        created_rows,
    )  # type: ignore
    memo[memo_key] = row
    return row  # type: ignore


def _set_delayed_attributes(row: Any, delayed_attrs: Dict[str, Any]) -> None:
    """
    Assign delayed attributes to a SQLModel row.

    Args:
        row (Any): The SQLModel row to update.
        delayed_attrs (Dict[str, Any]): A dictionary of attributes to set on the row.
    """
    for key, value in delayed_attrs.items():
        setattr(row, key, value)


def _connection_map(
    type_name: str, library: Library, cache: Dict[str, Dict[str, CrossConnection]]
) -> Dict[str, CrossConnection]:
    if type_name not in cache:
        connections = library.get_object_connections(type_name)
        # Explicitly filter to only outgoing relationships (source_type == type_name)
        # This prevents processing backlinks during hierarchical traversal
        # get_object_connections already filters to source_type == type_name, but
        # this explicit check makes the behavior clear and robust
        cache[type_name] = {
            conn.source_attr: conn
            for conn in connections
            if conn.source_attr is not None and conn.source_type == type_name
        }
    return cache[type_name]


def get_primary_key(table: Type[SQLModel]) -> str:
    """
    Get the primary key of a SQLModel table.
    """
    return list(table.__table__.primary_key.columns.keys())[0]  # type: ignore


def _pk_exists(value: DataModel, pk: str) -> bool:
    """
    Check if a primary key exists in a DataModel instance.
    """
    return pk in value.__class__.model_fields
