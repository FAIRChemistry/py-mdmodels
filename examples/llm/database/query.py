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
# ignore all warnings
import warnings
from enum import Enum
from typing import TypeVar, Generic, List, Iterable

import rich
from instructor import OpenAISchema
from pydantic import Field, BaseModel
from sqlalchemy import or_, func

from mdmodels import DataModel, sql, llm
from mdmodels.library import Library

warnings.filterwarnings("ignore")


class BaseTypes(Enum):
    string = "string"
    integer = "integer"
    float = "float"
    boolean = "boolean"


E = TypeVar("E", bound=Enum)


class SelectQuery(BaseModel):
    column: str = Field(..., description="The column to select.")
    to_match: list[str | float | int] = Field(..., description="The value(s) to match.")
    dtype: BaseTypes = Field(..., description="The data type of the value(s) to match.")
    exact: bool = Field(
        False,
        description="If the value should be matched exactly. "
        "Prefer inexact queries, if you dont know the content yet. "
        "Default is False.",
    )


class ResponseModel(BaseModel, Generic[E]):
    table: E = Field(..., description="The table that should be queried.")
    thought: str = Field(
        ...,
        description="The thought process behind the query and possible follow-up queries.",
    )
    queries: List[SelectQuery] = Field(
        ...,
        description="The queries to execute. If all rows should be selected, leave the list empty.",
        default_factory=list,
    )
    limit: int = Field(
        10,
        description="The maximum number of rows to return. Use -1 to return all rows.",
    )

    def query(self, session, models: Library):
        model = models[self.table.value]
        statement = sql.select(model)

        for query in self.queries:
            attr = getattr(model, query.column)

            if query.dtype == BaseTypes.string:
                statement = self._match_string(attr, query, statement)
            else:
                statement = statement.where(
                    or_(*[attr == term for term in query.to_match])
                )

        if self.limit != -1:
            statement = statement.limit(self.limit)

        return session.exec(statement).all()

    @staticmethod
    def _match_string(attr, query, statement):
        if query.exact:
            statement = statement.where(
                or_(*[func.lower(attr) == term.lower() for term in query.to_match])
            )
        else:
            statement = statement.where(
                or_(*[attr.like(f"%{term}%") for term in query.to_match])
            )
        return statement


enzymeml = DataModel.from_github(
    repo="EnzymeML/dm-specifications",
    branch="dm-2",
    spec_path="specifications/dm.md",
)

models = sql.generate_sqlmodel(
    data_model=enzymeml,
    base_classes=[OpenAISchema],
)

db = sql.DatabaseConnector(database="test.db")

sql_schemes = ""

for name, table in models.sql_schema().items():
    sql_schemes += f"{name}:\n"
    sql_schemes += f"{table}\n\n"

pre_prompt = f"""
Suggest which tables should be queried. These are the schemas that are available in the database:

{sql_schemes}
"""

response = llm.query_openai(
    response_model=Iterable[ResponseModel[models.to_enum()]],
    pre_prompt=pre_prompt,
    query="Extract glucose and fructose from the database.",
    use_scaffold=False,
    llm_model="gpt-4o",
)

with db as session:
    results = []
    for model in response:
        results += model.query(session, models)

    rich.print(results)
