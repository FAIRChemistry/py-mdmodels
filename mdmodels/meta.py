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
from pydantic import BaseModel, Field
from pydantic_xml.model import XmlModelMeta  # noqa

from .path import PathFactory
from .reference import ReferenceContext


class MetaConfig(BaseModel):
    """
    Configuration class that contains all the metaclass options to control DataModel classes.

    Attributes:
        reference_paths (list[ReferenceContext]): A list of reference paths to validate within a data model.
        path_factory (PathFactory | None): The path factory for the data model.
    """

    reference_paths: list[ReferenceContext] = Field(
        default_factory=list,
        description="A list of reference paths to validate within a data model.",
    )

    path_factory: PathFactory | None = Field(
        None,
        description="The path factory for the data model.",
    )


class DataModelMeta(XmlModelMeta):
    """
    A metaclass for data models that extends XmlModelMeta.

    Attributes:
        reference_paths (dict[str, tuple[str, str]] | None): A dictionary of reference paths to validate within a data model.
    """

    def __new__(cls, name, bases, dct, **kwargs):
        """
        Create a new instance of the DataModelMeta class.

        Args:
            cls: The class being instantiated.
            name (str): The name of the new class.
            bases (tuple): The base classes of the new class.
            dct (dict): The class attributes.

        Returns:
            type: The newly created class.
        """

        new_class = super().__new__(cls, name, bases, dct, **kwargs)

        setattr(
            new_class,
            "__mdmodels__",
            MetaConfig(),
        )

        return new_class

    @staticmethod
    def _convert_ref_pair_to_context(source_path: str, target_path: str):
        """
        Convert a pair of reference paths to a ReferenceContext instance.

        Args:
            source_path (str): The source path.
            target_path (str): The target path.

        Returns:
            ReferenceContext: The ReferenceContext instance.
        """
        return ReferenceContext(
            source_path=source_path,
            target_path=target_path,
        )
