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

from pydantic import create_model, BaseModel, field_validator
from sqlmodel import SQLModel, Field


class LinkedType(BaseModel):
    """
    A class representing a linked type in the database.

    Attributes:
        source_type (str): The source type.
        source_field (str): The source field.
        target_type (str): The target type.
    """

    source_type: str
    source_field: str
    target_type: str
    source_pk: tuple[str, type] = ("id", int)
    target_pk: tuple[str, type] = ("id", int)

    @field_validator("source_pk", "target_pk", mode="before")
    @classmethod
    def assign_default(cls, value, info):
        if value is None:
            return cls.model_fields[info.field_name].default

        return value

    def __hash__(self):
        """
        Generate a hash value for the LinkedType instance.

        Returns:
            int: The hash value.
        """
        names = [
            self.source_type,
            self.source_field,
            self.target_type,
        ]

        names.sort()

        return hash(tuple(names))

    def get_sql_model(self):
        """
        Generate a SQLModel class for the linked type.

        Returns:
            SQLModel: The generated SQLModel class.
        """

        src_col_name, src_col_type = self.source_pk
        tgt_col_name, tgt_col_type = self.target_pk

        field_definitions = {
            self.source_type: (
                src_col_type,
                Field(
                    default=None,
                    foreign_key=f"{self.source_type.lower()}.{src_col_name}",
                    primary_key=True,
                ),
            ),
            self.target_type: (
                tgt_col_type,
                Field(
                    default=None,
                    foreign_key=f"{self.target_type.lower()}.{tgt_col_name}",
                    primary_key=True,
                ),
            ),
        }
        return create_model(
            f"{self.source_type}__{self.source_field}__{self.target_type}__Link",
            __base__=SQLModel,
            __cls_kwargs__={"table": True},
            **field_definitions,
        )

    @staticmethod
    def get_mapping(join_table: SQLModel):
        """
        Get the mapping of source type, source field, and target type from the join table.

        Args:
            join_table (SQLModel): The join table.

        Returns:
            tuple: A tuple containing the source type, source field, and target type.
        """
        name = join_table.__name__

        assert name.endswith("__Link"), f"Invalid join table name: {name}"

        return (
            name.split("__")[0],
            name.split("__")[1],
            name.split("__")[2],
        )
