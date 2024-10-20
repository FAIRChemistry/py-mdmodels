from __future__ import annotations

import types
from pathlib import Path
from typing import get_args

from bigtree import nested_dict_to_tree
from pydantic_xml import BaseXmlModel
from typing_inspect import get_origin


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
        branch: str | None,
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
