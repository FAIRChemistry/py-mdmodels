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
from pathlib import Path
from typing import Any, get_origin, Coroutine
from xml.dom import minidom

import jsonpath
from pydantic import model_validator, ValidationError
from pydantic_core import InitErrorDetails
from pydantic_xml import BaseXmlModel
from rich.console import Console
from rich.table import Table

from mdmodels.utils import extract_dtype

from .git_utils import create_github_url
from .library import Library
from .meta import DataModelMeta
from .reference import ReferenceContext


class DataModel(
    BaseXmlModel,
    metaclass=DataModelMeta,
    search_mode="unordered",
):
    """
    A class to represent a data model with various utility methods.
    """

    def validate(self):  # noqa
        """
        Revalidate the dataset.

        This is mainly useful to revalidate the dataset after it has been modified.

        Returns:
            self: The revalidated data model instance.
        """
        type(self).model_validate(self)

    @model_validator(mode="after")
    def validate_references(self):
        """
        Validate references in the data model after initialization.

        This method checks the reference paths defined in the model's metadata
        and validates them against the JSON representation of the model.

        Returns:
            self: The validated data model instance.

        Raises:
            ValidationError: If any validation errors are found.
        """
        ctx = self.__class__.__mdmodels__.reference_paths  # type: ignore

        if not ctx:
            return self

        json_rep = self.model_dump()

        validation_errors: list[InitErrorDetails] = [
            error
            for error in asyncio.run(self._validate_batch(ctx, json_rep))
            if error is not None
        ]

        if validation_errors:
            raise ValidationError.from_exception_data(
                title=self.__class__.__name__,
                line_errors=validation_errors,
            )

        return self

    @staticmethod
    async def _validate_batch(
        ctx: list[ReferenceContext],
        json_rep: dict,
    ):
        """
        Validate a batch of reference contexts asynchronously.

        This method prepares and validates each reference context in the given
        context list against the JSON representation of the model.

        Args:
            ctx (list): The list of reference contexts to validate.
            json_rep (dict): The JSON representation of the data model.

        Returns:
            list: A list of validation errors, if any.
        """
        await asyncio.gather(*[c.prepare(json_rep) for c in ctx])

        tasks = []
        for c in ctx:
            tasks += c.validate_references()

        return await asyncio.gather(*tasks)

    @classmethod
    def info(cls):
        """
        Display information about the data model.

        Returns:
            str: The data model's name.
        """
        console = Console()
        table = Table(
            title=cls.__name__,
            title_style="bold magenta",
            caption_justify="left",
        )

        table.add_column("Field", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Adder", style="green")

        for name, field in cls.model_fields.items():
            dtype = extract_dtype(field.annotation)

            if get_origin(field.annotation) is list:
                dtype = list[dtype]
                annot = (
                    repr(dtype).replace("pydantic_xml.model.", "").replace("[", r"\[")
                )
            elif hasattr(dtype, "__name__"):
                annot = dtype.__name__
            else:
                annot = repr(dtype)

            adder = cls._find_adder_method(list(cls.__dict__.keys()), name)

            table.add_row(name, annot, adder)

        console.print(table)

    @staticmethod
    def _find_adder_method(keys: list[str], field: str):
        """
        Find the adder method for a field.

        Args:
            keys (list[str]): The keys to search for.
            field (str): The field to search for.

        Returns:
            str: The adder method name.
        """
        for key in keys:
            if key.startswith(f"add_to_{field}"):
                return key

        return ""

    @classmethod
    def from_markdown(
        cls,
        path: Path | str,
        ignore_attributes: list[str] = [],
    ) -> Library:
        """
        Create a data model from a markdown file.

        Args:
            path (Path | str): Path to the markdown file.

        Returns:
            Library: A dotted dict containing the generated modules
        """
        from .create import build_module

        if isinstance(path, Path):
            path = str(path)

        return build_module(path, ignore_attributes=ignore_attributes)

    @classmethod
    def from_github(
        cls,
        repo: str,
        spec_path: str,
        branch: str | None = None,
        tag: str | None = None,
        ignore_attributes: list[str] = [],
    ) -> Library:
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

        return build_module(
            create_github_url(branch, repo, spec_path, tag),
            ignore_attributes=ignore_attributes,
        )

    def find(self, json_path: str) -> Any | None:
        """
        Find the value of a field using a JSON path.

        Args:
            json_path (str): The JSON path to the field.

        Returns:
            Any: The value of the field.
        """
        try:
            result = asyncio.run(self._query_by_path(json_path))
            return result
        except StopIteration:
            print(f"Could not find data using JSON path: {json_path}")
            return None

    def find_multiple(self, json_paths: list[str]) -> dict[str, Any]:
        """
        Find the values of multiple fields using JSON paths.

        Args:
            json_paths (list[str]): A list of JSON paths to the fields.

        Returns:
            list: A list of values for each field.
        """

        tasks = [self._query_by_path(path) for path in json_paths]
        results = asyncio.run(asyncio.gather(*tasks))  # noqa

        return {path: res for path, res in zip(json_paths, results)}

    def _query_by_path(self, path: str) -> Coroutine[Any, Any, list[object]]:
        """
        Query the data model by path.

        Args:
            path (str): The path to query.

        Returns:
            Any: The result of the query.
        """
        return jsonpath.findall_async(path, self.model_dump())

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

    @classmethod
    def json_paths(cls, leafs: bool = True) -> list[str]:
        """Get all JSON paths for the data model.

        Returns:
            list[str]: A list of JSON paths for the data model.
        """
        assert cls.__mdmodels__.path_factory, "Path factory not found for data model"

        path_factory = cls.__mdmodels__.path_factory

        return path_factory.get_all_paths(cls.__name__, leafs=leafs)
