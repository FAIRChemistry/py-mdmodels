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
from functools import partial
from typing import Iterable, Any

from bigtree import Node, findall, BaseNode
from dotted_dict import DottedDict
from mdmodels_core import DataModel
from pydantic import computed_field, BaseModel, ConfigDict


class PathFactory(BaseModel):
    """
    A factory class to create and manage paths for a data model.

    This is a utility class used to generate reference paths that are used
    to cross-reference data between objects in a data model.

    Attributes:
        model (DataModel): The data model to create paths for.
        object_trees (DottedDict[str, Node]): A dictionary of object trees.
    """

    model: DataModel

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @computed_field(return_type=DottedDict[str, Node])
    def object_trees(self):
        """
        Compute the object trees for the data model.

        Returns:
            DottedDict[str, Node]: A dictionary where keys are object names and values are root nodes of the object trees.
        """
        type_mapping = _extract_type_mapping(self.model)
        object_trees = DottedDict()

        for obj in self.model.model.objects:
            root = Node(obj.name, is_type=True)
            _build_type_tree(root, type_mapping[obj.name], type_mapping)
            object_trees[obj.name] = root

        return object_trees

    def dot_to_json_path(self, dot_path: str) -> str:
        """
        Convert a dot path to a JSON path.

        Args:
            dot_path (str): The dot path to convert.

        Returns:
            str: The JSON path as a string.
        """
        node = self._traverse_by_dot_path(dot_path)
        return self._node_path_to_json_path(node.node_path)

    def get_attr_type_by_dot(self, dot_path: str) -> tuple[str, str]:
        """
        Get the attribute type by traversing the dot path.

        Args:
            dot_path (str): The dot path to traverse.

        Returns:
            tuple[str, str]: A tuple containing the parent object name and the attribute name.

        Raises:
            ValueError: If the path is a type path.
        """
        node = self._traverse_by_dot_path(dot_path)

        if node.is_type:  # noqa
            raise ValueError(f"Path '{dot_path}' is a type path.")

        return node.parent.name, node.name

    def get_all_paths(
        self,
        root: str,
        leafs: bool = True,
    ) -> list[str]:
        """
        Get all paths for an object in the object tree.

        Args:
            root (str): The root object name.
            leafs (bool, optional): Whether to return only leaf nodes. Defaults to True.

        Returns:
            list[str]: A list of all paths for the object.
        """
        if root not in self.object_trees:
            raise ValueError(
                f"Object '{root}' not found in model. "
                f"Available objects: {list(self.object_trees.keys())}"
            )

        root = self.object_trees[root]

        if leafs:
            return [
                self._node_path_to_json_path(node.node_path)
                for node in findall(root, lambda n: not n.children)
            ]
        else:
            return [
                self._node_path_to_json_path(node.node_path)
                for node in findall(root, lambda n: True)
            ]

    def get_type_paths(
        self,
        root: str,
        dtype: str,
        attr: str | None = None,
    ) -> list[str]:
        """
        Get the paths for a specific type in the object tree.

        Args:
            root (str): The root object name.
            dtype (str): The data type to find.
            attr (str, optional): The attribute name to find. Defaults to None.

        Returns:
            list[str]: A list of paths for the specified type.

        Raises:
            ValueError: If the root object is not found in the model.
        """
        if root not in self.object_trees:
            raise ValueError(
                f"Object '{root}' not found in model. "
                f"Available objects: {list(self.object_trees.keys())}"
            )

        root = self.object_trees[root]

        if attr:
            nodes = findall(
                root,
                partial(self._find_node_attribute, name=dtype, attr=attr),
            )
        else:
            nodes = findall(root, partial(self._find_node, name=dtype))

        return [self._node_path_to_json_path(node.node_path) for node in nodes]

    @staticmethod
    def _find_node(node, name):
        """
        Find a node by name.

        Args:
            node (Node): The node to check.
            name (str): The name to match.

        Returns:
            bool: True if the node name matches, False otherwise.
        """
        return node.name == name

    @staticmethod
    def _find_node_attribute(node, name, attr):
        """
        Find a node by attribute name and parent name.

        Args:
            node (Node): The node to check.
            name (str): The parent name to match.
            attr (str): The attribute name to match.

        Returns:
            bool: True if the node name matches the attribute and the parent name matches, False otherwise.
        """
        return node.name == attr and node.parent.name == name

    @staticmethod
    def _node_path_to_json_path(nodes: Iterable[BaseNode | Any]):
        """
        Convert a node path to a JSON path.

        Args:
            nodes (Iterable[BaseNode | Any]): The nodes to convert.

        Returns:
            str: The JSON path as a string.
        """
        path = []

        for node in nodes:
            if node.is_type:
                continue
            name = node.name + "[*]" if node.is_array else node.name
            path.append(name)

        return "$." + ".".join(path)

    def _traverse_by_dot_path(self, dot_path):
        """
        Traverse the object tree using a dot path.

        Args:
            dot_path (str): The dot path to traverse.

        Returns:
            Node: The node found at the end of the dot path.

        Raises:
            ValueError: If the root object or any part of the path is not found in the model.
        """
        root, *parts = dot_path.split(".")
        if root not in self.object_trees:
            raise ValueError(
                f"Object '{root}' not found in model. "
                f"Available objects: {list(self.object_trees.keys())}"
            )
        node = self.object_trees[root]
        for part in parts[:-1]:
            node = next((n for n in node.children if n.name == part), None)

            if node is None:
                raise ValueError(f"Path '{dot_path}' not found in model.")

            node = node.children[0]

        node = next((n for n in node.children if n.name == parts[-1]), None)

        if node is None:
            raise ValueError(f"Path '{dot_path}' not found in model.")

        return node


def _extract_type_mapping(dm: DataModel):
    """
    Extract the type mapping from the data model.

    Args:
        dm (DataModel): The data model to extract from.

    Returns:
        dict: A dictionary where keys are object names and values are dictionaries of attribute type mappings.
    """

    from mdmodels.create import TYPE_MAPPING

    type_mapping = {}
    enums = [e.name for e in dm.model.enums]

    for obj in dm.model.objects:
        local_types = {
            attr.name: {
                "complex": [
                    t for t in attr.dtypes if t not in TYPE_MAPPING and t not in enums
                ],
                "simple": [t for t in attr.dtypes if t in TYPE_MAPPING],
                "multiple": attr.is_array,
            }
            for attr in obj.attributes
        }
        type_mapping[obj.name] = local_types

    return type_mapping


def _build_type_tree(root: Node, obj: dict, type_mapping: dict) -> None:
    """
    Build the type tree for an object.

    Args:
        root (Node): The root node of the tree.
        obj (dict): The object to build the tree for.
        type_mapping (dict): The type mapping dictionary.
    """
    for name, types in obj.items():
        attr_node = Node(name, is_array=types["multiple"], is_type=False)
        root.append(attr_node)

        for complex_type in types["complex"]:
            node = Node(complex_type, is_type=True)
            _build_type_tree(node, type_mapping[complex_type], type_mapping)
            attr_node.append(node)
