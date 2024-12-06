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

from enum import Enum
from typing import List, TypeVar, Generic

from pydantic import BaseModel, Field

T = TypeVar("T")


class Action(Enum):
    """
    An enumeration representing the action to take.

    Attributes:
        EXTRACT: Extract metadata from the user query.
        REFINE: Refine the query to improve the AI's response.
    """

    ANSWER = "answer"
    DATA_UPDATE = "data_update"
    EXTRACTION = "extraction"
    PLOT = "plot"
    TABLE = "table"


class RefinedQuery(BaseModel):
    """
    A model representing a refined query.

    Attributes:
        refined_query (str): The refined query to improve the AI's response.
    """

    refined_query: str = Field(
        "",
        description="The refined query to improve the AI's response.",
    )


class Response(BaseModel, Generic[T]):
    """
    A model representing the response from the AI.

    Attributes:
        questions (List[str]): Questions to ask the user for clarification.
        answer (str): The answer to the user query.
        chain_of_thought (str): The thought process used to extract the information.
        data (T | None): The parsed data, if available.
    """

    questions: List[str] = Field(
        [],
        description="Questions to ask the user. For instance, things you are not sure how to process",
    )
    answer: str = Field(
        "",
        description="If there are queries that do not require any action on the data but need to be answered, provide the answer here",
    )
    chain_of_thought: str = Field(
        "",
        description="The thought process you used when processing the query. This should be a detailed explanation",
    )
    data: T | None = Field(
        None,
        description="This is where you will put the parsed data. If you are unsure, ask a question",
    )
