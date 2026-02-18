#  -----------------------------------------------------------------------------
#   Copyright \(c\) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files \(the "Software"\), to deal
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
from typing import Optional, Type

from sqlalchemy import func
from sqlmodel import select

from mdmodels.create import TYPE_MAPPING
from mdmodels.library import Library
from mdmodels.relations import apply_join_chain
from mdmodels.sql.base import SQLBase
from mdmodels.sql.insert import get_primary_key

PK_KEYS = ["pk", "primary_key", "primary key", "primarykey"]
FK_KEYS = ["fk", "foreign_key", "foreign key", "foreignkey", "references"]


def extract_foreign_keys(library: Library):
    """
    Extract foreign keys from the data model.

    Args:
        library: The data model library.

    Returns:
        dict: A dictionary of foreign keys.
    """

    library.resolve_target_primary_keys(overwrite=True)

    foreign_keys = dict()

    if library._rust_model is None:
        raise ValueError("Rust model not found in library.")

    model = library._rust_model.model
    for obj in model.objects:
        connections = library.get_object_connections(obj.name)
        foreign_keys[obj.name] = {
            conn.source_attr: (conn.target_type, conn.target_attr)
            for conn in connections
            if conn.is_identifier
        }

    return foreign_keys


def extract_primary_keys(model, primary_keys):
    """
    Extract primary keys from the data model.

    Args:
        model: The data model.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary of primary keys.
    """
    primary_keys = dict()
    for obj in model.objects:
        pk_fields = [
            (attr.name, TYPE_MAPPING[attr.dtypes[0]])
            for attr in obj.attributes
            if any(opt.k().lower() in PK_KEYS for opt in attr.options)
            or attr.name == "id"
        ]

        assert len(pk_fields) <= 1, (
            f"Multiple primary keys found for object '{obj.name}'."
        )

        if pk_fields:
            primary_keys[obj.name] = pk_fields[0]

    return primary_keys


def map_pk_types(model, primary_keys) -> dict[str, tuple[str, type]]:
    """
    Map primary key types from the data model.

    Args:
        model: The data model.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary of typed primary keys.
    """
    typed_pks = {}
    for obj_name, attr_name in primary_keys.items():
        obj = next((o for o in model.objects if o.name == obj_name), None)

        if obj is None:
            raise ValueError(f"Primary key object '{obj_name}' not found in model.")

        attr = next((a for a in obj.attributes if a.name == attr_name), None)
        if attr is None:
            raise ValueError(
                f"Primary key attribute '{attr_name}' not found in object '{obj_name}'."
            )

        if attr.dtypes[0] not in TYPE_MAPPING:
            raise ValueError(
                f"Type '{attr.dtypes[0]}' of primary key attribute '{attr_name}' not found in TYPE_MAPPING."
            )

        typed_pks[obj.name] = (attr.name, TYPE_MAPPING[attr.dtypes[0]])

    return typed_pks


def build_related_vectorsearch_query(
    *,
    main_model: Type[SQLBase],
    related_model: Type[SQLBase],
    db_models: Library[SQLBase],
    cosine_distance,
    offset: int,
    limit: int,
    max_distance: Optional[float] = None,
):
    """
    Build a vector-search query that joins a related table providing embeddings.

    The query returns rows from ``main_model`` ordered by the best (minimum)
    cosine distance from rows in ``related_model``.

    Args:
        main_model: The table whose rows should be returned.
        related_model: The table that owns the embedding column used for search.
        db_models: Library of SQLModel classes (used to inspect relations).
        cosine_distance: SQL expression for cosine distance.
        offset: Pagination offset.
        limit: Pagination limit.
        max_distance: Optional maximum cosine distance; results exceeding it are
            excluded.

    Returns:
        A selectable statement yielding (main_model, distance).

    Raises:
        ValueError: If the tables are not related or required relation metadata
            is missing.
    """

    related_name = related_model.__name__

    join_chain = db_models.find_join_chain(
        source=main_model.__name__,
        target=related_name,
    )
    if not join_chain:
        raise ValueError(
            f"No join path between {main_model.__name__} and {related_name}"
        )

    pk_name = get_primary_key(main_model)
    pk_column = getattr(main_model, pk_name)
    min_distance = func.min(cosine_distance).label("distance")

    stmt = select(
        pk_column.label("pk"),
        min_distance,
    ).select_from(main_model)

    stmt = apply_join_chain(
        stmt,
        start_cls=main_model,
        join_chain=join_chain,
        db_models=db_models,
    )

    if max_distance is not None:
        stmt = stmt.where(cosine_distance <= max_distance)

    distance_subquery = (
        stmt.group_by(pk_column)
        .order_by(min_distance)
        .offset(offset)
        .limit(limit)
        .subquery()
    )

    return (
        select(
            main_model,
            distance_subquery.c.distance.label("distance"),
        )
        .join(
            distance_subquery,
            pk_column == distance_subquery.c.pk,
        )
        .order_by(distance_subquery.c.distance)
    )
