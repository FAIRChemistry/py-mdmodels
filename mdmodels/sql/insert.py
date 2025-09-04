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
import asyncio
from typing import Any, Dict, List, Optional, Type

from sqlmodel import Session, SQLModel
from mdmodels.datamodel import DataModel
from mdmodels.library import CrossConnection, Library
from mdmodels.sql.base import SQLBase


def insert_nested(
    data: DataModel | List[DataModel],
    library: Library,
    session: Session,
    models: Library,
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
    return asyncio.run(insert_nested_async(data, library, session, models))


async def insert_nested_async(
    data: DataModel | List[DataModel],
    library: Library,
    session: Session,
    models: Library,
) -> List[SQLModel]:
    """
    Insert one or multiple DataModel instances into the database asynchronously.

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

    tasks = [_to_sqlmodel(item, library, session, models) for item in data]

    return await asyncio.gather(*tasks)  # type: ignore


async def _to_sqlmodel(
    data: DataModel | str | float | int | bool,
    library: Library,
    session: Session,
    models: Library,
) -> SQLModel | str | float | int | bool:
    """
    Convert a DataModel instance to a SQLModel instance.

    Args:
        data (DataModel): The data model instance to convert.
        library (Library): The library providing object connections.
        session (Session): The active database session.
        models (Library): A library containing model classes.

    Returns:
        SQLModel: A SQLModel instance representing the data, or the original data if it is a string.
    """
    if not isinstance(data, DataModel):
        return data

    connections = library.get_object_connections(type(data).__name__)
    delayed_attrs: Dict[str, Any] = {}
    primitives: Dict[str, Any] = {}

    tasks: List[asyncio.Task] = []

    for key, value in data:
        conn = attr_connected_to(key, connections)
        if conn:
            tasks.append(
                _process_connected_attr(
                    conn=conn,
                    value=value,
                    delayed_attrs=delayed_attrs,
                    library=library,
                    session=session,
                    models=models,
                )  # type: ignore
            )
        else:
            primitives[key] = value

    await asyncio.gather(*tasks)

    row = models[type(data).__name__](**primitives)
    _set_delayed_attributes(row, delayed_attrs)

    return row


async def _process_connected_attr(
    conn: CrossConnection,
    value: DataModel | str | float | int | bool,
    delayed_attrs: Dict[str, Any],
    library: Library,
    session: Session,
    models: Library,
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
    if conn.is_array:
        tasks = []
        delayed_attrs[conn.source_attr] = []  # type: ignore

        for item in value:
            if isinstance(item, DataModel):
                tasks.append(_create_or_fetch_object(item, library, session, models))
            else:
                delayed_attrs[conn.source_attr].append(item)  # type: ignore

        delayed_attrs[conn.source_attr] = await asyncio.gather(*tasks)  # type: ignore
    else:
        if isinstance(value, DataModel):
            processed_value = await _to_sqlmodel(value, library, session, models)
            delayed_attrs[conn.source_attr] = processed_value  # type: ignore
        else:
            delayed_attrs[conn.source_attr] = value  # type: ignore


async def _create_or_fetch_object(
    value: DataModel,
    library: Library,
    session: Session,
    models: Library,
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
        return await _to_sqlmodel(value, library, session, models)  # type: ignore

    table = models[type(value).__name__]

    for instance in session:
        if isinstance(instance, table) and getattr(instance, pk) == getattr(value, pk):
            return instance

    result = session.get(table, getattr(value, pk))

    if result:
        return result

    row = await _to_sqlmodel(value, library, session, models)  # type: ignore
    session.add(row)
    return row


def _set_delayed_attributes(row: Any, delayed_attrs: Dict[str, Any]) -> None:
    """
    Assign delayed attributes to a SQLModel row.

    Args:
        row (Any): The SQLModel row to update.
        delayed_attrs (Dict[str, Any]): A dictionary of attributes to set on the row.
    """
    for key, value in delayed_attrs.items():
        setattr(row, key, value)


def attr_connected_to(attr: str, connections: List[Any]) -> Optional[Any]:
    """
    Retrieve the connection for a specified attribute.

    Args:
        attr (str): The attribute name to find a connection for.
        connections (List[Any]): A list of potential connections.

    Returns:
        Optional[Any]: The connection object if found, otherwise None.
    """
    return next((c for c in connections if c.source_attr == attr), None)


def get_primary_key(table: Type[SQLBase]) -> str:
    """
    Get the primary key of a SQLModel table.
    """
    return list(table.__table__.primary_key.columns.keys())[0]  # type: ignore


def _pk_exists(value: DataModel, pk: str) -> bool:
    """
    Check if a primary key exists in a DataModel instance.
    """
    return pk in value.__class__.model_fields
