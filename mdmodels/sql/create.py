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
import warnings
from pathlib import Path
from typing import Optional, List

from mdmodels_core import DataModel
from pydantic import create_model
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship

from mdmodels.create import TYPE_MAPPING
from mdmodels.sql.base import SQLBase
from mdmodels.sql.linked_type import LinkedType

PK_KEYS = ["pk", "primary_key", "primary key", "primarykey"]


def generate_sqlmodel(
    *,
    path: Path | str | None = None,
    content: str | None = None,
    base_classes=None,
    primary_keys: dict[str, str] = None,
) -> dict[str, SQLBase]:
    """
    Convert a DataModel to a dictionary of SQLModel classes.

    Args:
        path (Path | str | None): Path to the markdown file.
        content (str | None): The content of the markdown file.
        base_classes (List[type]): A list of base classes to inherit from.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary where keys are model names and values are SQLModel classes.
    """

    global enums

    if base_classes is None:
        base_classes = []
    if primary_keys is None:
        primary_keys = {}

    assert path or content, "Either path or content must be provided."

    if content:
        model = DataModel.from_markdown_string(content).model
    elif path:
        model = DataModel.from_markdown(str(path)).model
    else:
        raise ValueError("Either path or content must be provided.")

    enums = [enum.name for enum in model.enums]
    typed_pks = {
        **_map_pk_types(model, primary_keys),
        **_extract_primary_keys(model, primary_keys),
    }

    linking_tables = _extract_linking_tables(model, typed_pks)
    models = dict()

    for obj in model.objects:
        pk_name, _ = typed_pks.get(obj.name, (None, None))
        _process_object(
            linking_tables,
            models,
            obj,
            base_classes,
            pk_name,
        )

    for model in models.values():
        model.model_rebuild()

    return models


def _extract_primary_keys(model, primary_keys):
    primary_keys = dict()
    for obj in model.objects:
        pk_fields = [
            (attr.name, TYPE_MAPPING[attr.dtypes[0]])
            for attr in obj.attributes
            if any(opt.key.lower() in PK_KEYS for opt in attr.options)
            or attr.name == "id"
        ]

        assert (
            len(pk_fields) <= 1
        ), f"Multiple primary keys found for object '{obj.name}'."

        if pk_fields:
            primary_keys[obj.name] = pk_fields[0]

    return primary_keys


def _map_pk_types(model, primary_keys) -> dict[str, tuple[str, type]]:
    typed_pks = dict()
    for obj, attr in primary_keys.items():
        try:
            obj = next(o for o in model.objects if o.name == obj)
        except StopIteration:
            raise ValueError(f"Primary key object '{obj}' not found in model.")

        try:
            try:
                attr = next(a for a in obj.attributes if a.name == attr)
            except StopIteration:
                raise ValueError(
                    f"Primary key attribute '{attr}' not found in object '{obj}'."
                )

            typed_pks[obj.name] = (attr.name, TYPE_MAPPING[attr.dtypes[0]])
        except KeyError:
            raise ValueError(
                f"Type '' of primary key attribute '{attr}' not found in TYPE_MAPPING."
            )

    return typed_pks


def _process_object(
    linking_tables: dict[str, SQLModel],
    models: dict,
    obj: DataModel,
    base_classes: List[type],
    primary_key: str | None,
) -> None:
    """
    Process an object and add it to the models dictionary.

    Args:
        linking_tables (dict): A dictionary of linking tables.
        models (dict): A dictionary to store the processed models.
        obj: The object to process.
        base_classes (List[type]): A list of base classes to inherit from.
        primary_key (str | None): The primary key attribute
    """

    field_definitions = dict()

    if primary_key is None:
        field_definitions["id"] = (int, Field(default=None, primary_key=True))

    for attr in obj.attributes:  # noqa
        is_primary_key = attr.name == primary_key
        _process_attribute(
            attr,
            field_definitions,
            linking_tables,
            obj,  # noqa
            is_primary_key,
        )

    model = create_model(  # noqa
        obj.name,  # noqa
        __base__=tuple([SQLBase, *base_classes]),  # noqa
        __cls_kwargs__={"table": True},
        **field_definitions,
    )

    model.__table_args__ = UniqueConstraint(
        *[field for field in field_definitions.keys() if field != "id"],
        name=f"unique_{obj.name}_constraints",  # noqa
    )

    models[obj.name] = model  # noqa


def _process_attribute(
    attr,
    field_definitions,
    linking_tables,
    obj,
    is_primary_key: bool,
):
    """
    Process an attribute and add it to the field definitions.

    Args:
        attr: The attribute to process.
        field_definitions (dict): A dictionary to store the field definitions.
        linking_tables (dict): A dictionary of linking tables.
        obj: The object containing the attribute.
        is_primary_key (bool): Whether the attribute is a primary key.
    """
    join_name = _link_table_name(obj.name, attr.name, attr.dtypes[0])
    if TYPE_MAPPING.get(attr.dtypes[0]):
        _create_simple_attr(
            attr,
            TYPE_MAPPING.get(attr.dtypes[0]),
            field_definitions,
            is_primary_key,
        )
    elif attr.dtypes[0] in enums:
        _create_simple_attr(
            attr,
            str,
            field_definitions,
            is_primary_key,
        )
    elif linking_tables.get(join_name):
        _create_complex_attr(
            attr,
            field_definitions,
            join_name,
            linking_tables,
        )
    else:
        raise ValueError(
            f"Type '{attr.dtypes[0]}' not found in TYPE_MAPPING and '{join_name}' linking tables."
        )


def _create_complex_attr(attr, field_definitions, join_name, linking_tables):
    """
    Create a complex attribute and add it to the field definitions.

    Args:
        attr: The attribute to process.
        field_definitions (dict): A dictionary to store the field definitions.
        join_name (str): The name of the join table.
        linking_tables (dict): A dictionary of linking tables.
    """
    if attr.is_array:
        dtype = List[attr.dtypes[0]]
    else:
        dtype = attr.dtypes[0]

    if not attr.required:
        dtype = _wrap_optional(dtype)

    field_definitions[attr.name] = (
        dtype,
        Relationship(link_model=linking_tables[join_name]),
    )


def _create_simple_attr(
    attr,
    dtype,
    field_definitions,
    is_primary_key,
):
    """
    Create a simple attribute and add it to the field definitions.

    Args:
        attr: The attribute to process.
        field_definitions (dict): A dictionary to store the field definitions.
    """
    if attr.is_array:
        warnings.warn(
            f"Array of simple units not supported."
            f"Skipping attribute '{attr.name}'.",
        )

        return

    field_params = {
        "default": ...,
        "primary_key": is_primary_key,
        "index": is_primary_key,
    }

    if not attr.required:
        dtype = _wrap_optional(dtype)
        field_params.update(
            {
                "default": None,
                "nullable": True,
            }
        )

    if attr.docstring:
        field_params["description"] = attr.docstring

    field_definitions[attr.name] = (dtype, Field(**field_params))


def _wrap_optional(dtype):
    """
    Wrap a data type in Optional.

    Args:
        dtype: The data type to wrap.

    Returns:
        Optional: The wrapped data type.
    """
    return Optional[dtype]


def _link_table_name(
    source_type: str,
    source_field: str,
    target_type,
) -> str:
    """
    Generate a name for the link table.

    Args:
        source_type (str): The source type.
        source_field (str): The source field.
        target_type: The target type.

    Returns:
        str: The generated link table name.
    """
    return f"{source_type}__{source_field}__{target_type}__Link"


def _extract_linking_tables(
    model: DataModel,
    primary_keys: dict[str, tuple[str, type]],
) -> dict[str, SQLModel]:
    """
    Extract linking tables from the data model.

    Args:
        model (DataModel): The data model to extract linking tables from.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary of linking tables.
    """
    dtypes = _all_types(model.objects)  # noqa
    links = []

    for obj in model.objects:  # noqa
        links += _extract_links(dtypes, obj, primary_keys)

    tables = {}

    for link in set(links):
        model = link.get_sql_model()
        tables[model.__name__] = model

    return tables


def _extract_links(
    dtypes: list[str],
    obj,
    primary_keys: dict[str, tuple[str, type]],
) -> list[LinkedType]:
    """
    Extract links from an object.

    Args:
        dtypes (list[str]): A list of data units.
        obj: The object to extract links from.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        list: A list of extracted links.
    """
    to_link = []
    extra_params = {"source_pk": primary_keys.get(obj.name)}

    for attr in obj.attributes:
        complex_types = _filter_complex_types(attr.dtypes, dtypes)
        for dtype in complex_types:
            local_extra_params = extra_params.copy()
            local_extra_params["target_pk"] = primary_keys.get(dtype)
            to_link.append(
                LinkedType(
                    source_type=obj.name,
                    source_field=attr.name,
                    target_type=dtype,
                    **local_extra_params,
                )
            )

    return to_link


def _filter_complex_types(dtypes: list[str], all_types: list[str]) -> list[str]:
    """
    Filter complex units from a list of data units.

    Args:
        dtypes (list[str]): A list of data units.
        all_types (list[str]): A list of all units.

    Returns:
        list: A list of complex units.
    """
    return [t for t in dtypes if t in all_types]


def _all_types(objects):
    """
    Get all units from a list of objects.

    Args:
        objects: A list of objects.

    Returns:
        list: A list of all units.
    """
    return [obj.name for obj in objects]
