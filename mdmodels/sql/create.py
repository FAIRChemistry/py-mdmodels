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
from typing import Optional, List

from mdmodels_core import DataModel # type: ignore
from pydantic import create_model
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship

from .base import SQLBase
from .linked_type import LinkedType
from .utils import extract_foreign_keys, map_pk_types, extract_primary_keys
from ..create import TYPE_MAPPING
from ..library import Library


def generate_sqlmodel(
    *,
    data_model: Library,
    base_classes=None,
) -> Library:
    """
    Convert a DataModel to a dictionary of SQLModel classes.

    Args:
        data_model (Library): The library containing the data model.
        base_classes (List[type]): A list of base classes to inherit from.

    Returns:
        dict: A dictionary where keys are model names and values are SQLModel classes.
    """
    global enums

    if base_classes is None:
        base_classes = []

    primary_keys = {}
    model = data_model._rust_model.model  # noqa
    enums = [enum.name for enum in model.enums]

    foreign_keys = extract_foreign_keys(data_model)

    typed_pks = {
        **map_pk_types(model, primary_keys),
        **extract_primary_keys(model, primary_keys),
    }

    linking_tables = _extract_linking_tables(model, typed_pks)
    models = Library(rust_model=data_model._rust_model)
    models._cross_connections = data_model._cross_connections

    for obj in model.objects:
        pk_name, _ = typed_pks.get(obj.name, (None, None))
        obj_fks = foreign_keys.get(obj.name, {})
        _process_object(
            linking_tables,
            models,
            obj,
            base_classes,
            pk_name,
            obj_fks,
        )

    for name, model in models.items():
        if name.startswith("_"):
            continue

        model.model_rebuild()

    return models


def _init_model(content, data_model, path):
    """
    Initialize the data model from content, data_model, or path.

    Args:
        content (str | None): The content of the markdown file.
        data_model (DataModel | Library | None): The data model.
        path (Path | str | None): Path to the markdown file.

    Returns:
        tuple: A tuple containing the data model and rust model.
    """
    if content:
        data_model = DataModel.from_markdown_string(content)
    elif path:
        data_model = DataModel.from_markdown_file(path)
    elif data_model and isinstance(data_model, Library):
        data_model = data_model._rust_model
    elif data_model and isinstance(data_model, DataModel):
        data_model = data_model

    return data_model.model, data_model


def _process_object(
    linking_tables: dict[str, SQLModel],
    models: dict,
    obj: DataModel,
    base_classes: List[type],
    primary_key: str | None,
    foreign_keys: dict[str, (str, str)],
) -> None:
    """
    Process an object and add it to the models dictionary.

    Args:
        linking_tables (dict): A dictionary of linking tables.
        models (dict): A dictionary to store the processed models.
        obj: The object to process.
        base_classes (List[type]): A list of base classes to inherit from.
        primary_key (str | None): The primary key attribute.
        foreign_keys (dict): A dictionary of foreign keys.
    """
    field_definitions = dict()

    use_id = primary_key is None
    has_id = any(attr.name == "id" for attr in obj.attributes)

    if use_id and not has_id:
        field_definitions["id"] = (Optional[int], Field(default=None, primary_key=True))
    elif use_id and has_id:
        primary_key = "id"

    for attr in obj.attributes:
        is_primary_key = attr.name == primary_key
        fk = foreign_keys.get(attr.name)
        _process_attribute(
            attr,
            field_definitions,
            linking_tables,
            obj,
            is_primary_key,
            fk,
        )

    model = create_model(
        obj.name,
        __base__=tuple([SQLBase, *base_classes]),
        __cls_kwargs__={"table": True},
        **field_definitions,
    )

    model.__table_args__ = UniqueConstraint(
        *[field for field in field_definitions.keys() if field != "id"],
        name=f"unique_{obj.name}_constraints",
    )

    models[obj.name] = model


def _process_attribute(
    attr,
    field_definitions,
    linking_tables,
    obj,
    is_primary_key: bool,
    fk: tuple[str, str] | None = None,
):
    """
    Process an attribute and add it to the field definitions.

    Args:
        attr: The attribute to process.
        field_definitions (dict): A dictionary to store the field definitions.
        linking_tables (dict): A dictionary of linking tables.
        obj: The object containing the attribute.
        is_primary_key (bool): Whether the attribute is a primary key.
        fk (tuple): A tuple of foreign key mappings.
    """
    join_name = _link_table_name(obj.name, attr.name, attr.dtypes[0])
    if TYPE_MAPPING.get(attr.dtypes[0]):
        _create_simple_attr(
            attr,
            TYPE_MAPPING.get(attr.dtypes[0]),
            field_definitions,
            is_primary_key,
            fk,
        )
    elif attr.dtypes[0] in enums:
        _create_simple_attr(
            attr,
            str,
            field_definitions,
            is_primary_key,
            fk,
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
    fk: tuple[str, str] | None = None,
):
    """
    Create a simple attribute and add it to the field definitions.

    Args:
        attr: The attribute to process.
        dtype: The data type of the attribute.
        field_definitions (dict): A dictionary to store the field definitions.
        is_primary_key (bool): Whether the attribute is a primary key.
        fk (tuple): A tuple of foreign key mappings.
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

    if fk:
        table_name, column = fk
        field_params["foreign_key"] = f"{table_name.lower()}.{column}"
        field_definitions[f"{attr.name}__ref"] = (
            table_name,
            Relationship(
                sa_relationship_kwargs={
                    "cascade": "all",
                }
            ),
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
    dtypes = _all_types(model.objects)
    links = []

    for obj in model.objects:
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
