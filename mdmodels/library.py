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
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import pandas as pd
from dotted_dict import DottedDict
from mdmodels_core import DataModel as RSDataModel  # type: ignore
from pydantic import BaseModel

from mdmodels.path import PathFactory
from mdmodels.relations import JoinEdge, apply_join_chain, find_join_chain
from mdmodels.templates import Templates
from mdmodels.utils import extract_object, extract_option

if TYPE_CHECKING:
    from sqlmodel import SQLModel

    from mdmodels.datamodel import DataModel
    from mdmodels.graph.basenode import BaseNode
    from mdmodels.sql.config import TableConfig
    from mdmodels.sql.connector import DatabaseType, DatabaseTypeLiteral

# Primary key identifiers used in model definitions
PK_KEYS = ["pk", "primary_key", "primary key", "primarykey"]

# Mapping from mdmodels types to SQL types
SQL_TYPE_MAPPING = {
    "integer": "INTEGER",
    "float": "REAL",
    "string": "VARCHAR",
    "boolean": "INTEGER",
    "number": "REAL",
}

# Type variable for Library generic type
T = TypeVar("T")


class RelationType(Enum):
    """
    Enumeration of possible relationship types between data models.

    Attributes:
        MANY_TO_MANY: Many-to-many relationship
        MANY_TO_ONE: Many-to-one relationship
        ONE_TO_MANY: One-to-many relationship
        ONE_TO_ONE: One-to-one relationship
    """

    MANY_TO_MANY = "many_to_many"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_MANY = "one_to_many"
    ONE_TO_ONE = "one_to_one"


class CrossConnection(BaseModel):
    """
    Represents a connection between two data model objects.

    This class defines relationships between different objects in the data model,
    including the source and target types, their attributes, and relationship properties.

    Attributes:
        source_type (str): The name of the source object type
        source_attr (str | None): The attribute name in the source object
        target_type (str): The name of the target object type
        target_attr (str | None): The attribute name in the target object
        is_array (bool): Whether the relationship involves an array/collection
        is_identifier (bool): Whether the attribute serves as an identifier
    """

    source_type: str
    source_attr: str | None = None
    target_type: str
    target_attr: str | None = None
    is_array: bool = False
    is_identifier: bool = False

    def to_nested_dict(self):
        """
        Convert the cross connection to a nested dictionary format.

        Returns:
            dict: A dictionary mapping source attribute to target type and attribute
        """
        return {self.source_attr: (self.target_type, self.target_attr)}

    def reverse(self):
        """
        Create a reversed version of this cross connection.

        Returns:
            CrossConnection: A new CrossConnection with source and target swapped
        """
        return CrossConnection(
            source_type=self.target_type,
            source_attr=self.target_attr,
            target_type=self.source_type,
            target_attr=self.source_attr,
            is_array=self.is_array,
            is_identifier=self.is_identifier,
        )


class Library(DottedDict, Generic[T]):
    """
    A generic container class for managing collections of data models.

    The Library class extends DottedDict to provide a convenient interface for storing
    and managing collections of data models. It supports generic typing to specify
    what type of models the library contains.

    The type parameter T specifies what type of models this library contains:
    - Library[DataModel] for Pydantic data models
    - Library[SQLModel] for SQLModel classes
    - Library[Any] for mixed or unspecified model types

    Attributes:
        _rust_model (RSDataModel | None): The underlying Rust data model
        _path_factory (PathFactory | None): Factory for generating file paths
        _cross_connections (list[CrossConnection]): List of connections between objects

    Example:
        >>> library = Library[DataModel]()
        >>> library['User'] = UserDataModel()
        >>> library['Post'] = PostDataModel()
        >>> print(library.type)  # 'DataModel'
        >>> library.info()  # Display info about all models
    """

    def __init__(
        self,
        rust_model: RSDataModel | None = None,
        path_factory: PathFactory | None = None,
    ):
        """
        Initialize the Library.

        Args:
            rust_model (RSDataModel | None): The underlying Rust data model instance
            path_factory (PathFactory | None): Factory for generating file paths
        """
        super().__init__()
        self._rust_model = rust_model
        self._path_factory = path_factory
        self._cross_connections: list[CrossConnection] = []
        self._pydantic_library: Optional[Library[DataModel]] = None

    @property
    def type(self) -> str:
        """
        Get the type name of models stored in this library.

        This property ensures that all models in the library are of the same type
        and returns the name of that type. Libraries are expected to be homogeneous,
        containing only one type of model (e.g., all DataModel instances or all SQLModel instances).

        Returns:
            str: The class name of the model type stored in this library.

        Raises:
            ValueError: If the library contains models of different types (not homogeneous).

        Example:
            >>> library = Library[DataModel]()
            >>> library['User'] = UserDataModel()
            >>> library.type
            'DataModel'
        """
        types = {
            type(value).__name__
            for key, value in self.items()
            if not key.startswith("_")
        }

        types = []
        for key, value in self.items():
            t_name = type(value).__name__
            if not key.startswith("_") and t_name not in types:
                types.append(t_name)

        return set(types).pop().replace("Metaclass", "").replace("Meta", "")

    def __repr__(self):
        """
        Return a string representation of the Library.

        Returns:
            str: A formatted string showing the library type and contained models
        """
        rep_str = ""
        rep_str += f"Library[{self.type}]\n"
        for key in self:
            if key.startswith("_"):
                continue
            rep_str += f"  - {key}\n"

        return rep_str

    def __str__(self):
        """
        Return a string representation of the Library.

        Returns:
            str: Same as __repr__
        """
        return self.__repr__()

    def __iter__(self):
        """
        Iterate over the keys in the Library.

        Returns:
            Iterator: An iterator over the library keys
        """
        return iter(self.keys())

    def __getattr__(
        self,
        attr,
    ) -> Type[T]:
        """
        Get an attribute from the Library.

        Args:
            attr: The attribute name to retrieve

        Returns:
            Type[T]: The model type associated with the attribute
        """
        return super().__getattr__(attr)

    def __getitem__(self, key) -> Type[T]:
        """
        Get an item from the Library by key.

        Args:
            key: The key to retrieve from the library

        Returns:
            Type[T]: The model type associated with the key

        Raises:
            KeyError: If the key is not found in the library
        """
        return super().__getitem__(key)

    def info(self):
        """
        Display information about each item in the Library.

        Calls the `info` method on each model if it exists, providing
        detailed information about the structure and properties of each model.
        """
        for cls in self.values():
            if hasattr(cls, "info"):
                cls.info()

    def convert_to(self, template: Templates, features: Optional[List[str]] = None):
        """
        Convert the Library to a specified template format.

        Args:
            template (Templates): The target template format
            features (Optional[List[str]]): List of features to enable during conversion

        Returns:
            The converted representation in the specified template format

        Raises:
            AssertionError: If the Rust model is not provided
        """
        if features is None:
            features = []

        assert self._rust_model, "Rust model not provided."

        return self._rust_model.convert_to(
            template.value,
            {feature: "true" for feature in features},
        )  # type: ignore

    def to_sqlmodel(
        self,
        database_type: Union[DatabaseTypeLiteral, DatabaseType],
        table_config: Optional[Dict[str, TableConfig]] = None,
    ) -> Library[SQLModel]:
        """
        Convert the Library to a SQLModel library.

        Returns:
            Library[SQLModel]: A library containing SQLModel classes
        """
        from sqlmodel import SQLModel

        from .sql import generate_sqlmodel

        # assert self.type == "DataModel", "Library must contain DataModel instances"

        return cast(
            Library[SQLModel],
            generate_sqlmodel(
                data_model=cast(Library[DataModel], self),
                database_type=database_type,
                table_config=table_config,
            ),
        )

    def to_neomodel(self) -> Library[BaseNode]:
        """
        Convert the Library to a NeoModel library.

        Returns:
            Library[BaseNode]: A library containing BaseNode classes
        """
        from .datamodel import DataModel
        from .graph import generate_neomodel

        assert self.type == "DataModel", "Library must contain DataModel instances"

        return generate_neomodel(data_model=cast(Library[DataModel], self))

    def to_enum(self) -> type[Enum]:
        """
        Convert the Library keys to an Enum type.

        Args:
            model_values (bool): Whether to use model values (currently unused)

        Returns:
            type[Enum]: An Enum class with library keys as enum values
        """

        return Enum(  # pyright: ignore[reportReturnType]
            "Library",
            {key: key for key in self.keys() if not key.startswith("_")},
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
        """
        Add a cross connection between two objects in the Library.

        Cross connections define relationships between different objects in the data model.
        They are used internally to generate SQL schemas, Neo4J schemas, and other
        relationship-aware representations.

        Args:
            source_type (str): The name of the source object type
            source_attr (str): The attribute name in the source object
            target_type (str): The name of the target object type
            target_attr (str | None): The attribute name in the target object
            is_array (bool): Whether the attribute represents an array/collection
            is_identifier (bool): Whether the attribute serves as an identifier

        Note:
            Connections involving enum types are automatically filtered out.
        """
        enums = [en.name for en in self._rust_model.model.enums]  # type: ignore

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

    def get_object_connections(self, obj_name: str | Type[BaseModel]):
        """
        Get all cross connections originating from a specific object.

        Args:
            obj_name (str | Type[BaseModel]): The object name or type to get connections for

        Returns:
            list[CrossConnection]: A list of cross connections where the specified object is the source
        """
        if not isinstance(obj_name, str) and hasattr(obj_name, "__name__"):
            obj_name = obj_name.__name__

        return [
            connection
            for connection in self._cross_connections
            if connection.source_type == obj_name
        ]

    def get_relations(
        self,
        obj_name: str | Type[BaseModel],
    ) -> Dict[str, Tuple[RelationType, CrossConnection]]:
        """
        Get relationship types for all objects connected to the specified object.

        Analyzes cross connections to determine the type of relationship (one-to-one,
        one-to-many, many-to-one, many-to-many) between the specified object and
        all related objects.

        Args:
            obj_name (str | Type[BaseModel]): The object name or type to analyze

        Returns:
            Dict[str, Tuple[RelationType, CrossConnection]]: A dictionary mapping
            related object names to tuples of (relation_type, connection)
        """
        obj_name = self._resolve_obj_name(obj_name)
        relations = {}

        for connection in self._cross_connections:
            if connection.source_type == obj_name:
                relation_type = (
                    RelationType.ONE_TO_MANY
                    if connection.is_array
                    else RelationType.ONE_TO_ONE
                )
                relations[connection.target_type] = (relation_type, connection)
            elif connection.target_type == obj_name:
                relation_type = (
                    RelationType.MANY_TO_ONE
                    if connection.is_array
                    else RelationType.ONE_TO_ONE
                )
                relations[connection.source_type] = (
                    relation_type,
                    connection.reverse(),
                )

        return relations

    def is_related(
        self,
        obj_name: str | Type[BaseModel],
        target_obj_name: str | Type[BaseModel],
    ) -> bool:
        """
        Check if two objects are connected through any cross connection.

        Args:
            obj_name (str | Type[BaseModel]): The first object name or type
            target_obj_name (str | Type[BaseModel]): The second object name or type

        Returns:
            bool: True if the objects are connected, False otherwise

        Note:
            Objects are considered related if they are the same object or if there
            exists a cross connection between them in either direction.
        """
        if obj_name == target_obj_name:
            return True

        return len(self.find_join_chain(obj_name, target_obj_name)) > 0

    def _resolve_obj_name(self, obj_name: str | Type[BaseModel]) -> str:
        """
        Resolve an object name or type to a string representation.

        Args:
            obj_name (str | Type[BaseModel]): The object name or type to resolve

        Returns:
            str: The string representation of the object name
        """
        if not isinstance(obj_name, str) and hasattr(obj_name, "__name__"):
            obj_name = obj_name.__name__
        return str(obj_name)

    def resolve_target_primary_keys(self, overwrite: bool = False):
        """
        Resolve primary key attributes for target objects in cross connections.

        Iterates through all cross connections and automatically assigns the primary key
        attribute to the target attribute if it is not already set. The primary key is
        determined by checking the attributes of the target object for primary key indicators.

        Args:
            overwrite (bool): Whether to overwrite existing target attributes.
                            If False, only connections without target_attr will be updated.

        Note:
            Primary keys are identified using the PK_KEYS constant, which includes
            common primary key identifiers like 'pk', 'primary_key', etc.
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
        Generate SQL schema representation for the Library.

        Args:
            mode (str): The schema generation mode. Currently only 'tabular' is supported.

        Returns:
            dict: A dictionary containing schema tables in the specified format

        Raises:
            NotImplementedError: If a mode other than 'tabular' is specified
            ValueError: If the Rust model is not provided
        """
        if mode != "tabular":
            raise NotImplementedError("Only tabular mode is supported.")

        if not self._rust_model:
            raise ValueError("Rust model not provided.")

        return self._tabular_schema()

    def find_join_chain(
        self,
        source: str | Type[BaseModel],
        target: str | Type[BaseModel],
    ) -> list[JoinEdge]:
        """
        Return the complex join path between two types.
        Thin wrapper around mdmodels.relations.find_join_chain.
        """

        if self._pydantic_library is not None:
            models = list(self._pydantic_library.models())
            return find_join_chain(
                source,
                target,
                (m for _, m in models),
            )

        return find_join_chain(
            cast(str | Type[BaseModel], source),
            cast(str | Type[BaseModel], target),
            cast(Iterable[Type[BaseModel]], (m for _, m in self.models())),
        )

    def apply_join_chain(
        self,
        stmt: Any,
        *,
        source: str | Type[BaseModel],
        target: str | Type[BaseModel],
    ) -> Any:
        """
        Apply a join chain to a SQLAlchemy/SQLModel statement.

        Computes the join path from source to target and applies it to the statement.
        This method respects the hierarchical structure of MD models, joining "down"
        from parent to child when following forward relationships.

        Args:
            stmt: The SQLAlchemy/SQLModel statement to apply joins to.
            source: The source model type (name or class) to start the join from.
            target: The target model type (name or class) to join to.

        Returns:
            The statement with joins applied.

        Raises:
            ValueError: If no join path exists between source and target.
        """
        # Find the join chain from source to target
        join_chain = self.find_join_chain(source, target)

        if not join_chain:
            source_name = source if isinstance(source, str) else source.__name__
            target_name = target if isinstance(target, str) else target.__name__
            raise ValueError(
                f"No join path exists between {source_name} and {target_name}"
            )

        # Verify that forward relationships use "down" direction
        # This ensures we follow the hierarchical structure (parent -> child)
        for edge in join_chain:
            # For forward relationships (as defined in MD model), prefer "down" direction
            # The edge direction indicates whether it's a forward (down) or reverse (up) relationship
            if edge["direction"] == "up" and edge["from_type"] != edge["to_type"]:
                # This is a reverse relationship - validate it's intentional
                # (e.g., querying from child to parent)
                pass

        # Get the actual class for start_cls
        if isinstance(source, str):
            start_cls = self[source]
        else:
            start_cls = source

        return apply_join_chain(
            stmt,
            start_cls=start_cls,
            join_chain=join_chain,
            db_models=self,
        )

    def _tabular_schema(self):
        """
        Generate tabular schema representation for all objects in the Library.

        Creates a table schema for each object, including column names, types,
        nullability, and primary key information.

        Returns:
            dict: A dictionary where keys are table names and values are markdown
                 representations of the table schemas
        """
        tables = {}
        for obj in self._rust_model.model.objects:  # type: ignore
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

    def models(self) -> Generator[tuple[str, Type[T]], None, None]:
        """
        Iterate over all models in the Library.

        Yields tuples of model names and their corresponding model classes,
        filtering out internal attributes (those starting with underscore).

        Yields:
            tuple[str, Type[T]]: Tuples containing the model name and model class

        Example:
            >>> for name, model_class in library.models():
            ...     print(f"Model: {name}, Type: {type(model_class)}")
        """
        for name, module in self.items():
            if name.startswith("_"):
                continue
            if hasattr(module, "model_fields"):
                yield name, module  # type: ignore
