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
from typing import get_args, get_origin, Annotated


def extract_option(attr, names: str | list[str]):
    """
    Extract an option from an attribute.

    Args:
        attr: The attribute to extract the option from.
        names (str | list[str]): The names of the options.

    Returns:
        str: The value of the option.
    """
    if isinstance(names, str):
        names = [names]

    return next((opt.v() for opt in attr.options if opt.k().lower() in names), None)


def extract_dtype(dtype):
    """
    Extract the data type from a given type annotation.

    Args:
        dtype: The type annotation to extract the data type from.

    Returns:
        The extracted data type.
    """
    if args := get_args(dtype):
        annot = args[0]

        if get_origin(annot) is Annotated:
            return get_args(annot)[0]
        else:
            return annot

    return dtype


def extract_object(name: str, rust_model):
    """
    Extract an object from a Rust model.

    Args:
        name (str): The name of the object to extract.
        rust_model (DataModel): The Rust model to extract the object from.

    Returns:
        The extracted object.
    """
    try:
        return next(obj for obj in rust_model.model.objects if obj.name == name)
    except StopIteration:
        raise ValueError(f"Object '{name}' not found in model.")
