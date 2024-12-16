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
import builtins
from typing import Union, get_origin, get_args, Annotated
import warnings

import forge

from forge import FParameter, sign, FSignature

from mdmodels import DataModel
from mdmodels.units.unit_definition import UnitDefinition, BaseUnit
from mdmodels.utils import extract_dtype


def apply_adder_methods(cls: type[DataModel]):
    """
    Apply adder methods to the given DataModel class.

    Args:
        cls (type[DataModel]): The DataModel class to which adder methods will be applied.
    """
    for name, field in cls.model_fields.items():
        if get_origin(field.annotation) is not list:
            continue

        method_name = f"add_to_{name}"
        underlying_type = get_args(field.annotation)

        if len(underlying_type) != 1 or get_origin(underlying_type[0]) is Union:
            warnings.warn(
                f"Only one type is supported for adder methods. {cls.__name__}.{name} has multiple types. Skipping.",
            )
            continue
        else:
            underlying_type = underlying_type[0]

        if underlying_type in [UnitDefinition, BaseUnit] or is_builtin_type(
            underlying_type
        ):
            continue

        add_method = _create_add_method(underlying_type, name)
        setattr(cls, method_name, add_method)


def is_builtin_type(obj):
    """
    Check if the given object is a built-in type.

    Args:
        obj: The object to check.

    Returns:
        bool: True if the object is a built-in type, False otherwise.
    """
    return obj.__name__ in dir(builtins)


def _create_add_method(
    coll_cls: type[DataModel],
    field: str,
):
    """
    Create an adder method for the given collection class and field.

    Args:
        coll_cls (type[DataModel]): The collection class for which the adder method is created.
        field (str): The field to which the adder method will be applied.

    Returns:
        function: The created adder method.
    """

    @sign(*_create_signature(coll_cls))
    def add_method(self, **kwargs):
        coll = getattr(self, field)
        coll.append(coll_cls(**kwargs))
        return coll[-1]

    return add_method


def _create_signature(coll_cls: type[DataModel]):
    """
    Create a signature for the adder method.

    Args:
        coll_cls (type[DataModel]): The collection class for which the signature is created.

    Returns:
        FSignature: The created signature.
    """
    if get_origin(coll_cls) is Annotated:
        coll_cls = extract_dtype(coll_cls)

    annotations = coll_cls.__annotations__
    parameters = [
        FParameter(
            kind=FParameter.KEYWORD_ONLY,
            name=name,
            type=annotations[name],
            default=None if get_origin(annotations[name]) is not list else [],
        )
        for name in annotations
        if name != "return"
    ]

    return FSignature(
        [forge.self] + parameters,
    )
