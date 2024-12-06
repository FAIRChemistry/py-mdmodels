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

import re
from textwrap import dedent
from typing import Type

from instructor import Instructor
from pydantic import BaseModel

from mdmodels import DataModel
from mdmodels.llm.response import RefinedQuery, Response


async def fetch_response(
    client: Instructor,
    response_model: Type[BaseModel],
    query: str,
    pre_prompt: str = "",
    llm_model: str = "gpt-4o",
    refine_query: bool = False,
    previous_response: str | None = None,
) -> BaseModel:
    """
    Fetch the response from the OpenAI API.

    Args:
        client (Instructor): The OpenAI client.
        response_model (Type[BaseModel]): The model to use for the response.
        query (str): The content to parse.
        pre_prompt (str, optional): The pre-prompt to use. Defaults to "".
        llm_model (str, optional): The model to use. Defaults to "gpt-4o".
        refine_query (bool, optional): Whether to refine the query. Defaults to False.
        previous_response (str | None, optional): The previous response. Defaults to None.

    Returns:
        The response from the API.
    """

    if refine_query:
        res = await _refine_query(
            client=client,
            query=query,
            llm_model=llm_model,
        )

        assert res.refined_query, "Refined query is empty"

        pattern = re.compile(r"<user query>.*</user query>")
        query = pattern.sub(f"<user query>{res.refined_query}</user query>", query)

    messages = [
        {"role": "system", "content": pre_prompt},
    ]

    if previous_response:
        messages.append(
            {
                "role": "user",
                "content": f"This has been the previous response {previous_response}",
            }
        )

    return client.chat.completions.create(
        model=llm_model,
        messages=[
            *messages,
            {"role": "user", "content": query},
        ],
        temperature=0,
        response_model=response_model,
    )


async def _refine_query(
    client,
    query,
    llm_model="gpt-4o",
) -> RefinedQuery:
    """
    Refine the query to improve the AI's response.

    Args:
        client: The OpenAI client.
        query: The initial query to be refined.
        llm_model (str, optional): The model to use for refining the query. Defaults to "gpt-4o".

    Returns:
        RefinedQuery: The refined query model.
    """

    return client.chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "user",
                "content": dedent(
                    f"""
                    Refine the query to improve the AI's response. It is vital that you provide a clear and concise query.
                    Think step by step and avoid reducing the information in the query yet make it as concise as possible.
                    
                    {query}
                    """
                ),
            }
        ],
        temperature=0,
        response_model=RefinedQuery,
    )


def prepare_query(cls: Type[DataModel]) -> Type[Response]:
    """
    Prepare a query response model for the given data model class.

    Args:
        cls (Type[DataModel]): The data model class.

    Returns:
        Type[Response]: The prepared response model.
    """
    return Response[cls]
