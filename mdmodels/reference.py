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
from typing import Any, Coroutine

import jsonpath
from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic_core import InitErrorDetails, PydanticCustomError


class ReferenceContext(BaseModel):
    """
    A class to represent the context for reference validation.

    Attributes:
        source_path (str): Path to the values to validate.
        target_path (str): Path to the values to validate against.
        source_vals (list[Any]): Values to validate.
        target_vals (list[Any]): Values to validate against.
    """

    source_path: str = Field(
        ...,
        description="Path to the values to validate",
    )
    target_path: str = Field(
        ...,
        description="Path to the values to validate against",
    )
    source_vals: list[Any] = Field(
        default_factory=list,
        description="Values to validate",
    )
    target_vals: list[Any] = Field(
        default_factory=list,
        description="Values to validate against",
    )

    model_config = ConfigDict(validate_assignment=True)

    @classmethod
    @field_validator("source_vals", "target_vals")
    def convert_to_list(cls, v):
        """
        Convert the values to a list if they are not already.

        Args:
            v: The value to convert.

        Returns:
            list: The value as a list.
        """
        return v if isinstance(v, list) else [v]

    async def prepare(self, json_rep: dict) -> None:
        """
        Prepare the source and target values by extracting them from the JSON representation.

        Args:
            json_rep (dict): The JSON representation to extract values from.
        """

        self.source_vals, self.target_vals = await asyncio.gather(
            jsonpath.findall_async(self.source_path, json_rep),
            jsonpath.findall_async(self.target_path, json_rep),
        )

    def validate_references(self) -> list[Coroutine[Any, Any, InitErrorDetails | None]]:
        """
        Validate the references by checking if each source value exists in the target values.

        Returns:
            list: A list of validation results for each source value.
        """

        if not self.target_vals:
            return []

        return [
            self._validate_single(source_value) for source_value in self.source_vals
        ]

    async def _validate_single(self, source_value) -> InitErrorDetails | None:
        """
        Validate a single source value against the target values.

        Args:
            source_value: The source value to validate.

        Returns:
            InitErrorDetails | None: The error details if the validation fails, otherwise None.
        """

        if source_value not in self.target_vals:
            error_type = PydanticCustomError(
                "Invalid Reference",
                "'{source_value}' does not appear in '{target_path}' - Expected one of '{target_values}'",
                {
                    "source_value": source_value,
                    "target_values": self.target_vals,
                    "target_path": self.target_path.lstrip("$."),
                },
            )

            return InitErrorDetails(
                type=error_type,
                loc=(self.source_path.lstrip("$."),),
                input=source_value,
                ctx={},
            )

        return None
