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
import types
from pathlib import Path
from typing import get_args, Any
from xml.dom import minidom

import jsonpath
from bigtree import nested_dict_to_tree
from pydantic_xml import BaseXmlModel


class DataModel(BaseXmlModel):
    @classmethod
    def meta_tree(cls):
        """
        Generate and display a tree representation of the data model's metadata.

        Returns:
            str: An empty string (the tree is displayed using the `show` method).
        """
        tree = nested_dict_to_tree(cls._construct_tree())
        tree.show(attr_list=["type"])
        return ""

    @classmethod
    def _construct_tree(cls):
        """
        Construct a nested dictionary representing the data model's structure.

        Returns:
            dict: A dictionary representing the data model's structure.
        """
        children = list()

        for key, field in cls.model_fields.items():
            if dtypes := get_args(field.annotation):
                dtype = dtypes[0]
            else:
                dtype = field.annotation

            is_multiple = get_origin(field.annotation) is list
            is_optional = field.default is None

            attr_name = key

            if is_multiple:
                attr_name = attr_name + "[]"
            elif not is_optional:
                attr_name = attr_name + "*"

            child = {
                "name": attr_name,
                "type": dtype.__name__,
                "multiple": is_multiple,
                "optional": is_optional,
            }

            if issubclass(dtype, BaseXmlModel):
                child["children"] = [dtype.construct_tree()]
                del [child["type"]]

            children.append(child)

        return {"name": cls.__name__, "children": children}

    @classmethod
    def from_markdown(cls, path: Path | str) -> types.ModuleType:
        """
        Create a data model from a markdown file.

        Args:
            path (Path | str): Path to the markdown file.

        Returns:
            types.ModuleType: A module containing the generated data model.
        """
        from .create import build_module

        if isinstance(path, Path):
            path = str(path)

        return build_module(path)

    @classmethod
    def from_github(
        cls,
        repo: str,
        spec_path: str,
        branch: str | None = None,
        tag: str | None = None,
    ) -> types.ModuleType:
        """
        Create a data model from a markdown file hosted on GitHub.

        Args:
            repo (str): The GitHub repository in the format 'owner/repo'.
            spec_path (str): The path to the markdown file in the repository.
            branch (str | None): The branch name (if applicable).
            tag (str | None, optional): The tag name (if applicable). Defaults to None.

        Returns:
            types.ModuleType: A module containing the generated data model.
        """
        from .create import build_module

        assert (
            branch is not None or tag is not None
        ), "Either branch or tag must be provided"
        assert (
            branch is None or tag is None
        ), "Either branch or tag must be provided, not both"

        if branch:
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{spec_path}"
        elif tag:
            url = f"https://raw.githubusercontent.com/{repo}/tags/{tag}/{spec_path}"
        else:
            url = f"https://raw.githubusercontent.com/{repo}/{spec_path}"

        return build_module(url)

    def find(self, json_path: str) -> Any | None:
        """
        Find the value of a field using a JSON path.

        Args:
            json_path (str): The JSON path to the field.

        Returns:
            Any: The value of the field.
        """

        try:
            result = asyncio.run(jsonpath.findall_async(json_path, self.model_dump()))
            return result
        except StopIteration:
            print(f"Could not find data using JSON path: {json_path}")
            return None

    def xml(
        self,
        encoding: str = "unicode",
        skip_empty: bool = True,
    ) -> str | bytes:
        """
        Converts the object to an XML string.

        Args:
            encoding (str, optional): The encoding to use. If set to "bytes", will return a bytes string.
                                      Defaults to "unicode".
            skip_empty (bool, optional): Whether to skip empty fields. Defaults to True.

        Returns:
            str | bytes: The XML representation of the object.
        """
        if encoding == "bytes":
            return self.to_xml()

        raw_xml = self.to_xml(encoding=None, skip_empty=skip_empty)
        parsed_xml = minidom.parseString(raw_xml)
        return parsed_xml.toprettyxml(indent="  ")
