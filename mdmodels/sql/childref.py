"""
Child reference utilities for SQL models.

This module provides utilities for handling child references in SQL models,
including model reconstruction with child reference support.
"""

from typing import Any, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic_xml import BaseXmlModel, create_model, element

from mdmodels.datamodel import DataModel
from mdmodels.utils import extract_dtype


class ChildRef(BaseXmlModel, tag="ChildRef"):
    """Reference an existing row by ID instead of inlining the full object."""

    row_pk: Union[str, int] = element(tag="row_pk")


def reconstruct_model(model: Type[BaseModel], flat: bool = False) -> Type[BaseModel]:
    """
    Reconstruct a Pydantic model with child reference support.

    This function creates a new version of the given model where complex
    BaseModel fields are replaced with Union types that can accept either
    the full model or a ChildRef. This allows for flexible serialization
    where related models can be represented as either full objects or
    simple ID references.

    Args:
        model: The BaseModel class to reconstruct.

    Returns:
        A new BaseModel class with the same structure but modified field
        annotations that support child references.

    Example:
        If the original model has a field `user: User`, the reconstructed
        model will have `user: Union[User, ChildRef]`.
    """

    attrs = {}
    for name, field in model.model_fields.items():
        is_list, inner, is_complex = _field_annotation_shape(field.annotation)

        params: dict[str, Any] = {"description": field.description}

        if is_list:
            params["default_factory"] = list
        else:
            params["default"] = field.default

        if is_complex:
            if flat:
                annotation = ChildRef
            else:
                reconstructed_field = reconstruct_model(inner)
                annotation = Union[reconstructed_field, ChildRef]

            if is_list:
                annotation = list[annotation]
            elif field.default is None:
                annotation = Optional[annotation]
        else:
            annotation = field.annotation

        attrs[name] = (annotation, element(tag=name, **params))

    return create_model(
        model.__name__,
        __base__=DataModel,
        **attrs,
    )


def _field_annotation_shape(annotation: Any) -> tuple[bool, Any, bool]:
    """
    Analyze a field annotation to determine its shape and complexity.

    This function examines a type annotation and extracts information about
    whether it's a list type, what the inner type is, and whether that
    inner type is a complex BaseModel subclass.

    Args:
        annotation: The type annotation to analyze.

    Returns:
        A tuple containing:
        - is_list: True if annotation is list[...], False otherwise
        - inner: The element type (for lists) or the extracted annotation type
        - is_complex: True if inner is a concrete type subclassing BaseModel

    Example:
        >>> field_annotation_shape(list[MyModel])
        (True, MyModel, True)
        >>> field_annotation_shape(str)
        (False, str, False)
    """
    origin = get_origin(annotation)
    is_list = origin is list
    inner = (
        extract_dtype(get_args(annotation)[0])
        if is_list and get_args(annotation)
        else extract_dtype(annotation)
    )
    is_complex = isinstance(inner, type) and issubclass(inner, BaseModel)
    return is_list, inner, is_complex
