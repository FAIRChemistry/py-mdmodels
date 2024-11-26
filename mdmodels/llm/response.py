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

import pandas as pd
from pydantic import BaseModel, Field, field_serializer, field_validator

from .plot import PlotTemplate
from .table import MarkdownDataFrame

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
        summary (str): A summary of the information extracted.
        chain_of_thought (str): The thought process used to extract the information.
        data (T | None): The parsed data, if available.
    """

    questions: List[str] = Field(
        [],
        description="Questions to ask the user. For instance, things you are not sure how to process",
    )
    dataset_description: str = Field(
        "",
        description="If you have a dataset, provide a detailed description of the dataset here. Please go into detail"
        "about the content and be as descriptive as possible.",
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
    query_urls: List[str] = Field(
        default_factory=list,
        description="If there are any suggested ready-to-use URLs to query and fetch metadata via REST APIs, provide them here"
        "in the query_urls field. The URLs should point to endpoints that return JSON data. If you cannot ensure that"
        "the data will be in JSON format, please do not provide the URL.",
    )
    action: Action = Field(
        default=Action.EXTRACTION,
        description="The action to take. Extraction is the default action."
        "If you want to suggest a plot, set the action to PLOT.",
    )
    plot_templates: List[PlotTemplate] = Field(
        default_factory=list,
        description="A list of plot templates to suggest for the user.",
    )
    dataframe: MarkdownDataFrame | None = Field(
        None,
        description="If you have a DataFrame to display, provide it here.",
    )

    @field_serializer("dataframe")
    def serialize_dataframe(self, value):
        if value is not None:
            return value.to_markdown()
        else:
            return None

    @classmethod
    @field_validator("dataframe")
    def validate_dataframe(cls, value):
        if isinstance(value, str):
            return MarkdownDataFrame.from_markdown(value)
        elif isinstance(value, pd.DataFrame):
            return value
        else:
            return None
