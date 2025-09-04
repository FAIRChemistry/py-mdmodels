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

import copy
import pathlib
from enum import Enum
from functools import partial
from typing import Any, Annotated, ForwardRef, Union

import httpx
import validators
from mdmodels_core import DataModel as RSDataModel  # type: ignore
from pydantic import BeforeValidator
from pydantic_core.core_schema import ValidationInfo
from pydantic_xml import RootXmlModel, create_model, attr, element, wrapped

from mdmodels.adder_method import apply_adder_methods
from mdmodels.datamodel import DataModel
from mdmodels.library import Library
from mdmodels.path import PathFactory
from mdmodels.reference import ReferenceContext
from mdmodels.units.annotation import UnitDefinitionAnnot
from mdmodels.utils import extract_option

# Mapping of string type names to Python units
TYPE_MAPPING = {
    "string": str,
    "integer": int,
    "float": float,
    "boolean": bool,
    "number": float,
    "date": str,
    "bytes": bytes,
}


class StringElement(RootXmlModel):
    root: str


class FloatElement(RootXmlModel):
    root: float


class BooleanElement(RootXmlModel):
    root: bool


class IntegerElement(RootXmlModel):
    root: int


class BytesElement(RootXmlModel):
    root: bytes


BASIC_TYPE_ELEMENTS = {
    str: StringElement,
    float: FloatElement,
    bool: BooleanElement,
    int: IntegerElement,
    bytes: BytesElement,
}


def build_module(
    path: pathlib.Path | str | None = None,
    data_model: RSDataModel | None = None,
    ignore_attributes: list[str] = [],
) -> Library:
    """
    Create a data model module from a markdown file.

    Args:
        path (pathlib.Path | str): Path to the markdown file.
        data_model (RSDataModel | None): The data model. If None, it will be initialized from the path.

    Returns:
        Library: A module containing the generated data model.
    """

    if data_model and path:
        raise ValueError("Only one of 'path' or 'data_model' should be provided")

    if data_model:
        assert isinstance(data_model, RSDataModel), "data_model must be an RSDataModel"
        dm = data_model
    elif path:
        dm = init_data_model(path)
    else:
        raise ValueError("Either 'path' or 'data_model' must be provided")

    global path_factory
    global references
    global module

    references = {}
    path_factory = PathFactory(model=dm)
    module = Library(rust_model=dm, path_factory=path_factory)

    for rs_type in dm.model.objects:
        if rs_type.name in module:
            module[rs_type.name].__mdmodels__.path_factory = path_factory
            continue

        py_type = build_type(dm, rs_type, module, ignore_attributes=ignore_attributes)
        py_type.__mdmodels__.path_factory = path_factory  # type: ignore

        module[rs_type.name] = py_type

    for obj, reference in references.items():
        module[obj].__mdmodels__.reference_paths += reference

    module.resolve_target_primary_keys()

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
    ignore_attributes: list[str] = [],
):
    """
    Build a Python type from a data model type.

    Args:
        dm (RSDataModel): The data model.
        rs_type: The data model type.
        py_types (dict): Dictionary of Python units.
    """

    forward_refs = []
    attrs = {}

    for attribute in rs_type.attributes:
        # Skip ignored attributes
        if attribute.name in ignore_attributes:
            continue

        params = {}
        dtypes = []

        for dtype in attribute.dtypes:
            dtype = get_dtype(dtype, dm, py_types, rs_type.name, ignore_attributes)

            if dtype.__name__ in py_types or hasattr(dtype, "__recursive__"):
                module.add_cross_connection(
                    source_type=rs_type.name,
                    source_attr=attribute.name,
                    target_type=dtype.__name__,
                    is_array=attribute.is_array,
                )

                if hasattr(dtype, "__recursive__"):
                    dtype = ForwardRef(dtype.__name__)
                    forward_refs.append(dtype)

                before_validator = partial(
                    _check_type_compliance,
                    cls=dtype,  # type: ignore
                    py_types=py_types,  # type: ignore
                )

                dtype = Annotated[dtype, BeforeValidator(before_validator)]  # type: ignore

            dtypes.append(dtype)

        dtypes = _set_custom_tags(attribute, dtypes)

        if len(dtypes) > 1:
            dtype = Union[tuple(dtypes)]  # type: ignore
        elif len(dtypes) == 0:
            raise ValueError(f"No data type found for attribute {attribute.name}")
        else:
            dtype = dtypes[0]

        if attribute.is_array:
            dtype = list[dtype]

        if description := attribute.docstring:
            params["description"] = description

        params["default"] = _get_default(attribute.default)

        if not attribute.required and not attribute.is_array:
            dtype = dtype | None  # type: ignore
        elif not attribute.required and attribute.is_array:
            params["default_factory"] = list
            del params["default"]

        attrs[attribute.name] = _process_xml_attribute(attribute, dtype, params)

    model = create_model(
        rs_type.name,
        __base__=DataModel,
        **attrs,
    )

    for ref in forward_refs:
        ref._evaluate(py_types, py_types, recursive_guard=set())

    _extract_references(rs_type, ignore_attributes)
    apply_adder_methods(model)

    return model


def _process_xml_attribute(attribute, dtype, params: dict) -> tuple[type, Any]:
    """
    Process an XML attribute and update the attrs dictionary.

    Args:
        attribute: The attribute to process.
        dtype: The data type of the attribute.
        params: Additional parameters for the attribute.

    Returns:
        Tuple[type, Any]: The processed attribute.
    """

    if attribute.xml is not None and attribute.xml.is_attr:
        assert not _is_wrapped_xml(attribute.xml.name), (
            "Wrapped XML is not allowed to be an attribute"
        )
        return (
            dtype,
            attr(
                name=attribute.xml.name,
                **params,
            ),
        )
    elif hasattr(attribute.xml, "wrapped"):
        path = "/".join(attribute.xml.wrapped)
        name = attribute.xml.name
        return (dtype, wrapped(path, element(tag=name, **params)))
    elif attribute.xml is not None and _is_multiple_xml(attribute.xml.name):
        return (dtype, element(**params))
    elif attribute.xml is not None:
        return (dtype, element(tag=attribute.xml.name, **params))
    else:
        return (dtype, element(tag=attribute.name, **params))


def _set_custom_tags(attribute, dtypes):
    """
    Set custom XML tags for the given attribute and data types.

    This function processes the XML name of the attribute to determine if it
    contains multiple or wrapped XML elements. It then assigns custom XML tags
    to the data types based on the parsed names.

    Args:
        attribute: The attribute containing the XML name to process.
        dtypes: A list of data types to which custom XML tags will be assigned.

    Returns:
        list: A list of data types with assigned custom XML tags.
    """
    new_dtypes = []
    if attribute.xml is not None and _is_multiple_xml(attribute.xml.name):
        paths = [p.strip() for p in attribute.xml.name.split(",")]

        if _is_wrapped_xml(attribute.xml.name):
            names = [p.split("/")[-1] for p in paths]
        else:
            names = paths

        for dtype, name in zip(dtypes, names):
            if dtype in BASIC_TYPE_ELEMENTS:
                dtype = copy.copy(BASIC_TYPE_ELEMENTS[dtype])
                dtype.__xml_tag__ = name
                new_dtypes.append(dtype)
            else:
                dtype = copy.copy(dtype)
                dtype.__xml_tag__ = name
                new_dtypes.append(dtype)
    else:
        return dtypes

    return new_dtypes


def _is_multiple_xml(name: str):
    """
    Check if the XML name contains multiple elements.

    Args:
        name (str): The XML name to check.

    Returns:
        bool: True if the name contains multiple elements, False otherwise.
    """
    return len(name.split(",")) > 1


def _is_wrapped_xml(name: str):
    """
    Check if the XML name is wrapped, indicating a nested structure.

    Args:
        name (str): The XML name to check.

    Returns:
        bool: True if the name is wrapped, False otherwise.
    """
    return len(name.split("/")) > 1


def _extract_references(obj, ignore_attributes: list[str] = []):
    """Extract attribute references from an object.

    References are used for cross-referencing objects in the data model.

    Args:
        obj: The object to extract references from.
        ignore_attributes: List of attribute names to ignore.

    Returns:
        List[str]: A list of references.
    """

    for attribute in obj.attributes:
        # Skip ignored attributes
        if attribute.name in ignore_attributes:
            continue
        if ref := extract_option(attribute, "references"):
            _create_ref_context(attribute, obj, ref)

            # Add cross connection for DB schemes
            tbl, col = path_factory.get_attr_type_by_dot(ref)
            module.add_cross_connection(
                source_type=obj.name,
                source_attr=attribute.name,
                target_type=tbl,
                target_attr=col,
                is_identifier=True,
            )

    return references


def _create_ref_context(attr, obj, ref: str):
    """
    Process a reference attribute and update the references dictionary.

    Args:
        attr: The attribute containing the reference.
        obj: The object to which the attribute belongs.
        ref (str): The reference string in dot notation.

    """
    root = ref.split(".")[0]
    target_path = path_factory.dot_to_json_path(ref)
    source_paths = path_factory.get_type_paths(root, obj.name, attr.name)
    for source_path in source_paths:
        ctx = ReferenceContext(
            source_path=source_path,
            target_path=target_path,
        )

        if root not in references:
            references[root] = []

        references[root].append(ctx)


def _get_default(default):
    """
    Get the default value from a given default object.

    Args:
        default: The default object to extract the value from.

    Returns:
        The extracted default value, which can be a string, boolean, integer, float, or None.
    """
    if default is None:
        return None

    if default.is_string():
        return default.as_string().replace('"', "")
    elif default.is_boolean():
        return default.as_boolean()
    elif default.is_integer():
        return default.as_integer()
    elif default.is_float():
        return default.as_float()


def get_dtype(
    dtype: str,
    dm: RSDataModel,
    py_types: dict,
    rs_type_name: str,
    ignore_attributes: list[str] = [],
):
    """
    Get the Python data type for an attribute.

    Args:
        dtype: The data type.
        dm (RSDataModel): The data model.
        py_types (dict): Dictionary of Python units.
        rs_type_name (str): The name of the data model type.
    Returns:
        type: The Python data type.
    """

    if dtype == rs_type_name:
        return type(rs_type_name, (DataModel,), {"__recursive__": True})

    if dtype in TYPE_MAPPING:
        return TYPE_MAPPING[dtype]
    elif dtype == "UnitDefinition":
        return UnitDefinitionAnnot
    elif dtype in py_types:
        return py_types[dtype]
    elif sub_obj := next((o for o in dm.model.objects if o.name == dtype), None):
        py_types[dtype] = build_type(
            dm, sub_obj, py_types, ignore_attributes=ignore_attributes
        )
        return py_types[dtype]
    elif enum_obj := next((o for o in dm.model.enums if o.name == dtype), None):
        py_types[dtype] = build_enum(enum_obj, py_types)
        return py_types[dtype]
    else:
        raise ValueError(f"Unknown type {dtype}")


def build_enum(enum_obj, py_types: dict):
    """
    Create a Python Enum from a data model Enum object.

    Args:
        enum_obj: The Enum object.
        py_types (dict): Dictionary of Python types/enums.

    Returns:
        Enum: The created Python Enum.
    """

    if enum_obj.name in py_types:
        return py_types[enum_obj.name]

    return Enum(enum_obj.name, enum_obj.mappings)


def _check_type_compliance(
    value: Any,
    info: ValidationInfo,
    cls: type[DataModel] | ForwardRef,
    py_types: Library,
):
    """
    Check if the value complies with the expected data model type.

    Args:
        value (Any): The value to check.
        info (ValidationInfo): Validation information.
        cls (type[DataModel]): The expected data model class.

    Returns:
        Any: The validated value.
    """
    if not hasattr(value.__class__, "model_fields"):
        return value
    if isinstance(cls, ForwardRef):
        cls = cls._evaluate(py_types, py_types, recursive_guard=set())  # type: ignore
    if type(value).__name__ == cls.__name__:  # type: ignore
        return cls(**value.model_dump())  # type: ignore

    return value
