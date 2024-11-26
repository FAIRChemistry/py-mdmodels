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

from enum import Enum
from typing import Optional

from neomodel import (
    StructuredNode,
    db,
    StringProperty,
    IntegerProperty,
    FloatProperty,
    UniqueIdProperty,
    ArrayProperty,
)
from pydantic import Field, create_model, BaseModel

from .relation import add_structured_rel_properties

TYPE_MAPPING = {
    StringProperty: str,
    IntegerProperty: int,
    FloatProperty: float,
    UniqueIdProperty: str,
}


class Direction(Enum):
    """
    Enumeration for relationship directions.
    """

    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    BOTH = "BOTH"


class BaseNode(StructuredNode):
    """
    Base node that adds extended functionality to the neomodel StructuredNode class.
    """

    __abstract_node__ = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._validate()

    def _validate(self):
        """
        Validate the node properties.
        """
        field_definitions = dict()

        for name, prop in self.__all_properties__:
            is_array = isinstance(prop, ArrayProperty)

            if is_array:
                dtype = list[TYPE_MAPPING[prop.base_property.__class__]]
            else:
                dtype = TYPE_MAPPING[prop.__class__]

            field_definitions[name] = (Optional[dtype], Field(default=None))

        cls = create_model(
            self.__class__.__name__,
            __base__=BaseModel,
            **field_definitions,
        )

        cls(**self.__properties__)

    def get_relationships(self):
        """
        Get all relationships for the current node.

        Returns:
            list: A list of relationships.
        """
        # Cypher query to get all relationships for the current node
        query = """
            MATCH (a)-[r]-(b)
            WHERE elementId(a) = $id
            RETURN r, b
        """

        # Execute the query
        relationships = []
        result, _ = db.cypher_query(query, {"id": self.element_id})

        for res, tgt_node in result:
            if self.element_id == res.start_node.element_id:
                relationships.append((self, res, tgt_node))
            else:
                relationships.append((tgt_node, res, self))

        return relationships

    def prop_connect(
        self,
        rel_name: str,
        node,
        properties: dict,
    ):
        """
        Connect a property to a node with given properties.

        The relationship property must exist on the node, otherwise an AssertionError is raised.
        If you'd like to connect a node with a dynamic relationship type, use the dyn_connect method,
        which allows you to specify the relationship type as a string and properties.

        Args:
            rel_name (str): The name of the property to connect.
            node: The node to connect to.
            properties (dict): The properties to set on the relationship.

        Raises:
            AssertionError: If properties are not provided or the property does not exist on the node.


        Example:
            >>> node_a.prop_connect("likes", node_b, {"since": "2022-01-01"})
        """
        assert len(properties) > 0, "Properties must be provided."
        assert hasattr(self, rel_name), f"Property {rel_name} does not exist on node."

        # Get the relationship property and add the properties
        rel = getattr(self, rel_name)
        add_structured_rel_properties(properties, rel)
        rel.connect(node, properties=properties)

        # Reset the model definition to avoid side effects
        rel.definition["model"] = None

    def dyn_connect(
        self,
        target: BaseNode,
        relationship_type: str,
        properties: dict | None = None,
    ):
        """
        Creates a relationship between two nodes with a dynamic relationship type and optional properties.

        Args:
            target (BaseNode): The node to which the relationship points.
            relationship_type (str): The type of the relationship.
            properties (dict, optional): Properties to set on the relationship. Defaults to None.

        Raises:
            ValueError: If the relationship type is not a valid identifier.

        Example:
            >>> node_a.dyn_connect(node_b, "LIKES", {"since": "2022-01-01"})
        """
        assert isinstance(target, BaseNode), "Target must be a BaseNode instance."

        if not relationship_type.isidentifier():
            raise ValueError("Invalid relationship type provided.")

        query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $from_id AND elementId(b) = $to_id
            MERGE (a)-[r:{relationship_type}]->(b)
        """

        # Combine the parameters for the query
        params = {"from_id": self.element_id, "to_id": target.element_id}
        if properties:
            # Add SET statements to the query if properties are provided
            set_statements = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
            query += f" SET {set_statements}"
            params.update(properties)

        # Execute the query
        db.cypher_query(query, params)
