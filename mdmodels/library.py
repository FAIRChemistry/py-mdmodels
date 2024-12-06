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
from enum import Enum

import pandas as pd
from dotted_dict import DottedDict
from mdmodels_core import DataModel as RSDataModel  # type: ignore
from pydantic import BaseModel

from mdmodels.path import PathFactory
from mdmodels.utils import extract_object, extract_option

PK_KEYS = ["pk", "primary_key", "primary key", "primarykey"]
SQL_TYPE_MAPPING = {
    "integer": "INTEGER",
    "float": "REAL",
    "string": "VARCHAR",
    "boolean": "INTEGER",
    "number": "REAL",
}


class CrossConnection(BaseModel):
    source_type: str
    source_attr: str | None = None
    target_type: str
    target_attr: str | None = None
    is_array: bool = False
    is_identifier: bool = False

    def to_nested_dict(self):
        return {self.source_attr: (self.target_type, self.target_attr)}


class Library(DottedDict):
    """
    A class to represent a data_model that extends DottedDict.

    Methods:
        info(): Display information about each item in the data_model.
    """

    def __init__(
        self,
        rust_model: RSDataModel | None = None,
        path_factory: PathFactory | None = None,
    ):
        """
        Initialize the data_model.
        """
        super().__init__()
        self._rust_model = rust_model
        self._path_factory = path_factory
        self._cross_connections: list[CrossConnection] = []

    def __repr__(self):
        rep_str = ""
        for key in self:
            if key.startswith("_"):
                continue
            rep_str += f"{key}\n"

        return rep_str

    def __str__(self):
        return self.__repr__()

    def info(self):
        """
        Display information about each item in the data_model.
        Calls the `info` method on each item if it exists.
        """
        for cls in self.values():
            if hasattr(cls, "info"):
                cls.info()

    def to_enum(self) -> Enum:
        """
        Convert the data_model to an Enum.
        """
        return Enum(
            "Library",
            {key: key for key in self.keys() if key != "_rust_model"},
        )

    def add_cross_connection(
        self,
        source_type: str,
        source_attr: str,
        target_type: str,
        target_attr: str | None = None,
        is_array: bool = False,
        is_identifier: bool = False,
    ):
        """Add a cross connection to the data_model.

        Internally used to store cross connections between objects in the data_model. Used to
        generate SQL and Neo4J schemes.

        Args:
            source_type (str): The source type.
            source_attr (str): The source attribute.
            target_type (str): The target type.
            target_attr (str): The target attribute.
            is_array (bool): Whether the attribute is an array.
            is_identifier (bool): Whether the attribute is an identifier.
        """
        enums = [en.name for en in self._rust_model.model.enums] # type: ignore

        if source_type in enums or target_type in enums:
            return

        self._cross_connections.append(
            CrossConnection(
                source_type=source_type,
                source_attr=source_attr,
                target_type=target_type,
                target_attr=target_attr,
                is_array=is_array,
                is_identifier=is_identifier,
            )
        )

    def get_object_connections(self, obj_name: str):
        """
        Get the cross connections for an object.

        Args:
            obj_name (str): The object name.

        Returns:
            list: A list of cross connections.
        """
        return [
            connection
            for connection in self._cross_connections
            if connection.source_type == obj_name
        ]

    def resolve_target_primary_keys(self, overwrite: bool = False):
        """
        Resolve the primary keys for target attributes in cross connections.

        Iterates over the cross connections and assigns the primary key attribute
        to the target attribute if it is not already set. The primary key is determined
        by checking the attributes of the target object.

        Args:
            overwrite (bool): Whether to overwrite the target attribute if it is already set.
        """

        for connection in self._cross_connections:
            if connection.target_attr and not overwrite:
                continue

            obj = extract_object(connection.target_type, self._rust_model)
            pk_attr = "id"

            for attr in obj.attributes:
                if extract_option(attr, PK_KEYS):
                    pk_attr = attr.name
                    break
            connection.target_attr = pk_attr

    def sql_schema(self, mode="tabular"):
        """
        Return the schema for the data_model.

        Args:
            mode (str): The mode for the schema. Only 'tabular' mode is supported.

        Raises:
            NotImplementedError: If the mode is not 'tabular'.
            ValueError: If the _rust_model is not provided.

        Returns:
            dict: A dictionary containing the schema tables.
        """
        if mode != "tabular":
            raise NotImplementedError("Only tabular mode is supported.")

        if not self._rust_model:
            raise ValueError("Rust model not provided.")

        return self._tabular_schema()

    def _tabular_schema(self):
        """
        Generate the tabular schema for the data_model.

        Returns:
            dict: A dictionary where keys are table names and values are markdown representations of the tables.
        """
        tables = {}
        for obj in self._rust_model.model.objects: # type: ignore
            table = [
                {
                    "name": attr.name,
                    "type": SQL_TYPE_MAPPING.get(attr.dtypes[0]),
                    "nullable": not attr.required,
                    "primary_key": attr.name == "id",
                }
                for attr in obj.attributes
                if SQL_TYPE_MAPPING.get(attr.dtypes[0])
            ]
            tables[obj.name] = pd.DataFrame(table).to_markdown(index=False)
        return tables
