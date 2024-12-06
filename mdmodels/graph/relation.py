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

from __future__ import annotations

from typing import Any
from uuid import uuid4

import neomodel as nm
from neomodel import (
    StructuredNode,
    Relationship,
    StructuredRel,
    RelationshipTo,
    RelationshipFrom,
)
from neomodel import db


class DynRelationship(Relationship):
    """
    A dynamic relationship class that allows setting properties when connecting nodes.
    """

    def connect(self, node, properties: dict | None = None):
        """
        Connects the relationship to a node with optional properties.

        Args:
            node: The node to connect to.
            properties (dict, optional): Properties to set on the relationship. Defaults to None.
        """
        if properties:
            self.definition["model"] = _create_dyn_body(properties)
        super().connect(node)


class DynRelationshipTo(RelationshipTo):
    """
    A dynamic relationship class for outgoing relationships that allows setting properties when connecting nodes.
    """

    def connect(self, node, properties: dict | None = None):
        """
        Connects the relationship to a node with optional properties.

        Args:
            node: The node to connect to.
            properties (dict, optional): Properties to set on the relationship. Defaults to None.
        """
        if properties:
            self.definition["model"] = _create_dyn_body(properties)
        super().connect(node)


class DynRelationshipFrom(RelationshipFrom):
    """
    A dynamic relationship class for incoming relationships that allows setting properties when connecting nodes.
    """

    def connect(self, node, properties: dict | None = None):
        """
        Connects the relationship to a node with optional properties.

        Args:
            node: The node to connect to.
            properties (dict, optional): Properties to set on the relationship. Defaults to None.
        """
        if properties:
            self.definition["model"] = _create_dyn_body(properties)

        super().connect(node)


def add_structured_rel_properties(
    properties: dict[str, Any],
    rel,
):
    """
    Adds structured relationship properties to a relationship.

    Args:
        properties (dict[str, Any]): The properties to add.
        rel: The relationship to which the properties will be added.
    """
    rel.definition["model"] = _create_dyn_body(properties)


def _create_dyn_body(properties: dict[str, Any]):
    """
    Creates a dynamic body for a relationship based on the given properties.

    Args:
        properties (dict[str, Any]): The properties to include in the dynamic body.

    Returns:
        type: A dynamically created StructuredRel class with the given properties.
    """
    body = {}

    for key, value in properties.items():
        match value:
            case str():
                body[key] = nm.StringProperty(default=value)
            case int():
                body[key] = nm.IntegerProperty(default=value)
            case float():
                body[key] = nm.FloatProperty(default=value)
            case bool():
                body[key] = nm.BooleanProperty(default=value)
            case list():
                body[key] = nm.ArrayProperty(nm.StringProperty(), default=value)
            case dict():
                body[key] = nm.JSONProperty(default=value)
            case _:
                raise ValueError(f"Unsupported type: {type(value)}")

    return type(f"DynamicStructuredRelation-{uuid4()}", (StructuredRel,), body)


def create_dynamic_relationship(
    from_node: StructuredNode,
    to_node: StructuredNode,
    relationship_type: str,
    properties: dict | None = None,
):
    """
    Creates a relationship between two nodes with a dynamic relationship type and optional properties.

    Args:
        from_node (StructuredNode): The node from which the relationship originates.
        to_node (StructuredNode): The node to which the relationship points.
        relationship_type (str): The type of the relationship.
        properties (dict, optional): Properties to set on the relationship. Defaults to None.

    Raises:
        ValueError: If the relationship type is not a valid identifier.
    """

    if not relationship_type.isidentifier():
        raise ValueError("Invalid relationship type provided.")

    query = f"""
    MATCH (a), (b)
    WHERE elementId(a) = $from_id AND elementId(b) = $to_id
    MERGE (a)-[r:{relationship_type}]->(b)
    """

    if properties:
        set_statements = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
        query += f" SET {set_statements}"

    params = {"from_id": from_node.element_id, "to_id": to_node.element_id}
    if properties:
        params.update(properties)

    db.cypher_query(query, params)
