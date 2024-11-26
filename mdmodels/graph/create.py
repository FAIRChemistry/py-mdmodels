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


import sys
import warnings
from pathlib import Path

import neomodel as nm
from mdmodels_core import DataModel

from .basenode import BaseNode
from ..create import TYPE_MAPPING


def generate_neomodel(
    *,
    path: Path | str | None = None,
    content: str | None = None,
) -> dict[str, type[BaseNode]]:
    """
    Create neomodel classes dynamically from a schema.

    Args:
        path (Path | str | None): Path to the markdown file.
        content (str | None): The content of the markdown file.

    Returns:
        dict: A dictionary where keys are class names and values are dynamically created neomodel classes.
    """

    assert path or content, "Either path or content must be provided."

    if content:
        model = DataModel.from_markdown_string(content).model
    elif path:
        model = DataModel.from_markdown(str(path)).model
    else:
        raise ValueError("Either path or content must be provided.")

    global enums

    classes = {}
    enums = [enum.name for enum in model.enums]

    for obj in model.objects:
        # Create attributes and relationship
        attributes = _create_attributes(obj.attributes)
        relationships = _create_relationships(obj.attributes)

        # Combine attributes and relationship.py for the class
        class_body = {**attributes, **relationships}

        # Dynamically create the class using type()
        new_class = type(obj.name, (BaseNode,), class_body)
        classes[obj.name] = new_class

        # Add to sys modules
        sys.modules[__name__].__dict__[obj.name] = new_class

    return classes


def _create_attributes(obj_attributes):
    """
    Create a dictionary of attributes for a neomodel class based on schema attributes.

    Args:
        schema_attributes (list): A list of dictionaries, each representing an attribute with its properties.

    Returns:
        dict: A dictionary where keys are attribute names and values are neomodel properties.
    """
    attributes = {}
    for attr in obj_attributes:
        if attr.name == "id":
            warnings.warn(
                "Attribute 'id' is reserved and will be renamed to 'id_' to avoid conflicts."
            )

            name = "id_"
        else:
            name = attr.name

        wrapped_type = _get_dtype(attr.dtypes[0])

        if wrapped_type is None:
            # Skip complex units for now
            continue

        if attr.is_array:
            attributes[name] = nm.ArrayProperty(wrapped_type(required=attr.required))
        else:
            attributes[name] = wrapped_type(required=attr.required)

    return attributes


def _get_dtype(dtype):
    if dtype == "Identifier":
        return nm.UniqueIdProperty
    elif dtype == "string" or dtype in enums:
        return nm.StringProperty
    elif dtype in ["float", "number"]:
        return nm.FloatProperty
    elif dtype == "integer":
        return nm.IntegerProperty
    else:
        return None


def _create_relationships(schema_attributes):
    """
    Create a dictionary of relationship.py for a neomodel class based on schema attributes.

    Args:
        schema_attributes (list): A list of dictionaries, each representing an attribute with its properties.

    Returns:
        dict: A dictionary where keys are relationship names and values are neomodel relationship.py.
    """
    relationships = {}
    for attr in schema_attributes:
        if not attr.is_array or all(dt in TYPE_MAPPING for dt in attr.dtypes):
            continue

        relationships[attr.name] = nm.RelationshipTo(
            attr.dtypes[0],
            attr.term if attr.term else "HAS",
        )

    return relationships
