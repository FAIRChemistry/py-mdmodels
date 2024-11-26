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

import pathlib
import types
from enum import Enum

import httpx
import validators
from dotted_dict import DottedDict
from mdmodels_core import DataModel as RSDataModel
from pydantic_xml import create_model, attr, element

from mdmodels.datamodel import DataModel
from mdmodels.units.annotation import UnitDefinitionAnnot

# Mapping of string type names to Python units
TYPE_MAPPING = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
    "number": float,
    "date": str,
}


def build_module(
    path: pathlib.Path | str,
    mod_name: str = "model",
):
    """
    Create a data model module from a markdown file.

    Args:
        path (pathlib.Path | str): Path to the markdown file.
        mod_name (str): The name of the module.

    Returns:
        types.ModuleType: A module containing the generated data model.
    """
    dm = init_data_model(path)
    config = dm.model.config

    module = DottedDict()

    for rs_type in dm.model.objects:
        build_type(dm, rs_type, module, module)

    if dm.model.name:
        mod_name = dm.model.name

    return module


def init_data_model(path):
    """
    Initialize the data model from a path or URL.

    Args:
        path (str | pathlib.Path): Path or URL to the markdown file.

    Returns:
        RSDataModel: The initialized data model.
    """
    if validators.url(path):
        content = httpx.get(path).text
        return RSDataModel.from_markdown_string(content)
    else:
        if isinstance(path, str):
            path = pathlib.Path(path)

        assert path.exists(), f"Path '{path}' does not exist"
        return RSDataModel.from_markdown(str(path))


def build_type(
    dm: RSDataModel,
    rs_type,
    py_types: dict,
    py_enums: dict | None = None,
):
    """
    Build a Python type from a data model type.

    Args:
        dm (RSDataModel): The data model.
        rs_type: The data model type.
        py_types (dict): Dictionary of Python units.
        py_enums (dict, optional): Dictionary of Python enums. Defaults to None.
    """
    if py_enums is None:
        py_enums = {}

    attrs = {}

    for attribute in rs_type.attributes:
        params = {}
        dtype = get_dtype(attribute, dm, py_types, py_enums)

        if attribute.is_array:
            dtype = list[dtype]

        if description := attribute.docstring:
            params["description"] = description

        if not attribute.required and not attribute.is_array:
            params["default"] = None
            dtype = dtype | None
        elif not attribute.required and attribute.is_array:
            params["default_factory"] = list

        if attribute.xml.is_attr:
            attrs[attribute.name] = (dtype, attr(name=attribute.xml.name, **params))
        else:
            attrs[attribute.name] = (dtype, element(tag=attribute.xml.name, **params))

    py_types[rs_type.name] = create_model(
        rs_type.name,
        __base__=DataModel,
        **attrs,
    )

    return py_types[rs_type.name]


def get_dtype(
    attribute,
    dm: RSDataModel,
    py_types: dict,
    py_enums: dict,
):
    """
    Get the Python data type for an attribute.

    Args:
        attribute: The attribute.
        dm (RSDataModel): The data model.
        py_types (dict): Dictionary of Python units.
        py_enums (dict): Dictionary of Python enums.

    Returns:
        type: The Python data type.
    """
    dtype = attribute.dtypes[0]

    if dtype in TYPE_MAPPING:
        return TYPE_MAPPING[dtype]
    elif dtype == "UnitDefinition":
        return UnitDefinitionAnnot
    elif dtype in py_types:
        return py_types[dtype]
    elif sub_obj := next((o for o in dm.model.objects if o.name == dtype), None):
        return build_type(dm, sub_obj, py_types)
    elif enum_obj := next((o for o in dm.model.enums if o.name == dtype), None):
        return build_enum(enum_obj, py_types)
    else:
        raise ValueError(f"Unknown type {dtype}")


def build_enum(
    enum_obj,
    py_enums: dict,
):
    """
    Create a Python Enum from a data model Enum object.

    Args:
        enum_obj: The Enum object.
        py_enums (dict): Dictionary of Python enums.

    Returns:
        Enum: The created Python Enum.
    """
    py_enums[enum_obj.name] = Enum(enum_obj.name, enum_obj.mappings)

    return py_enums[enum_obj.name]
