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

import neomodel as nm

from ..create import TYPE_MAPPING
from ..datamodel import DataModel as DataModelType
from ..library import Library
from .basenode import BaseNode


def generate_neomodel(
    *,
    data_model: Library[DataModelType],
) -> Library[BaseNode]:
    """
    Create neomodel classes dynamically from a schema.

    This function takes a data model library and generates corresponding neomodel
    classes that can be used for graph database operations with Neo4j. Each object
    in the data model is converted to a BaseNode subclass with appropriate
    properties and relationships.

    Args:
        data_model (Library[DataModel]): The library containing the data model
            with objects to be converted to neomodel classes.

    Returns:
        Library[BaseNode]: A library containing BaseNode classes that correspond
            to the objects in the input data model.

    Raises:
        AssertionError: If the data model does not have a rust model provided.

    Example:
        >>> from mdmodels import DataModel, graph
        >>> model = DataModel.from_markdown("model.md")
        >>> graph_models = graph.generate_neomodel(data_model=model)
        >>> # Use the generated graph models for Neo4j operations
    """
    assert data_model._rust_model, "Rust model not provided."
    model = data_model._rust_model.model  # type: ignore

    global enums

    library = Library(rust_model=data_model._rust_model)
    library._cross_connections = data_model._cross_connections
    enums = [enum.name for enum in model.enums]

    for obj in model.objects:
        # Create attributes and relationship
        attributes = _create_attributes(obj.attributes)
        relationships = _create_relationships(obj.attributes)

        # Combine attributes and relationship.py for the class
        class_body = {**attributes, **relationships}

        # Dynamically create the class using type()
        new_class = type(obj.name, (BaseNode,), class_body)
        library[obj.name] = new_class

        # Add to sys modules
        sys.modules[__name__].__dict__[obj.name] = new_class

    return library


def _create_attributes(obj_attributes):
    """
    Create a dictionary of attributes for a neomodel class based on schema attributes.

    This function processes object attributes from the schema and converts them
    to appropriate neomodel property types. It handles various data types including
    strings, numbers, identifiers, and arrays.

    Args:
        obj_attributes (list): A list of attribute objects from the schema,
            each containing name, dtypes, required status, and array information.

    Returns:
        dict: A dictionary where keys are attribute names and values are neomodel
            property instances (StringProperty, IntegerProperty, etc.).

    Note:
        - The 'id' attribute is renamed to 'id_' to avoid conflicts with neomodel's
          built-in id handling.
        - Complex data types that cannot be mapped are skipped.
        - Array attributes are wrapped in ArrayProperty.
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
    """
    Map schema data types to neomodel property types.

    This function converts string representations of data types from the schema
    to the corresponding neomodel property class.

    Args:
        dtype (str): The data type string from the schema (e.g., "string",
            "integer", "float", "Identifier").

    Returns:
        type or None: The corresponding neomodel property class, or None if
            the data type cannot be mapped.

    Supported mappings:
        - "Identifier" -> UniqueIdProperty
        - "string" or enum types -> StringProperty
        - "float", "number" -> FloatProperty
        - "integer" -> IntegerProperty
    """
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
    Create a dictionary of relationships for a neomodel class based on schema attributes.

    This function processes schema attributes to identify relationships between
    objects and creates appropriate neomodel relationship definitions. Only
    array attributes that reference other objects (not primitive types) are
    converted to relationships.

    Args:
        schema_attributes (list): A list of attribute objects from the schema,
            each containing name, dtypes, array status, and relationship terms.

    Returns:
        dict: A dictionary where keys are relationship names and values are
            neomodel RelationshipTo instances.

    Note:
        - Only array attributes are considered for relationships.
        - Attributes with data types that exist in TYPE_MAPPING (primitive types)
          are skipped.
        - The relationship type defaults to "HAS" if no specific term is provided.
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
