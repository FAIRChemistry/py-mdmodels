from typing import Any, Dict, List, Optional, Type, Union, overload

from pydantic import BaseModel
from sqlmodel import SQLModel
from sqlmodel.main import SQLModelMetaclass

from mdmodels.sql.config import TableConfig


class SQLModelMeta(SQLModelMetaclass):
    """Metaclass for SQL models that stores embedding column info."""

    def __new__(cls, name, bases, namespace, **kwargs):
        table_config = kwargs.pop("__table_config__", None)
        new_class = super().__new__(cls, name, bases, namespace, **kwargs)
        annotations = getattr(new_class, "__annotations__", {})
        model_fields = getattr(new_class, "model_fields", {})

        new_class._relation_fields = tuple(
            name for name in annotations.keys() if name not in model_fields
        )
        new_class._table_config = table_config
        return new_class


class SQLBase(SQLModel, metaclass=SQLModelMeta):
    """Base class for SQL models."""

    _table_config: Optional[TableConfig] = None
    _relation_fields: tuple[str, ...] = ()

    @property
    def table_config(self) -> Optional[TableConfig]:
        """The table configuration for the model."""
        return self.__class__._table_config

    @property
    def embedding_column(self) -> Optional[str]:
        """The column name for the embedding source column."""
        if self.__class__._table_config is None:
            return None
        return self.__class__._table_config.embed_column

    @overload
    def to_dict(self, dtype: Type[BaseModel]) -> Union[BaseModel, List[BaseModel]]: ...

    @overload
    def to_dict(
        self, dtype: None = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]: ...

    def to_dict(
        self, dtype: Optional[Type[BaseModel]] = None
    ) -> Union[
        Dict[str, Any],
        List[Dict[str, Any]],
        BaseModel,
        List[BaseModel],
    ]:
        """
        Convert the SQLModel object to a dictionary.

        Returns:
            dict: The dictionary representation of the SQLModel object.
        """
        serialized = self._to_dict_with_relationships(self)
        if dtype is not None:
            return dtype.model_construct(**serialized)  # pyright: ignore[reportCallIssue]
        return serialized

    @classmethod
    def _to_dict_with_relationships(cls, obj):
        """
        Recursively serialize SQLModel objects including relationships.

        Args:
            obj: The SQLModel object or list of objects to serialize.

        Returns:
            dict or list: The serialized dictionary or list of dictionaries.
        """
        if isinstance(obj, (list, tuple)):
            return [cls._to_dict_with_relationships(o) for o in obj]

        if not isinstance(obj, SQLModel):
            raise ValueError(f"Invalid object type: {type(obj)}")

        relation_fields = obj.__class__._relation_fields  # pyright: ignore[reportAttributeAccessIssue]

        # Early exit if no relationships to process
        if not relation_fields:
            return obj.model_dump(mode="python")

        # Exclude relationship fields from initial dump to avoid lazy loading triggers
        data = obj.model_dump(mode="python", exclude=set(relation_fields))

        # Process relationships
        to_dict = cls._to_dict_with_relationships
        for relation_name in relation_fields:
            if relation_name == "embedding":
                continue

            value = getattr(obj, relation_name, None)
            if value is None:
                continue

            data[relation_name] = to_dict(value)

        return data
