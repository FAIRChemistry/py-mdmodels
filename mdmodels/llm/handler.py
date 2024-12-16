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
import os
from typing import Type

import instructor
from instructor import from_openai
from openai import OpenAI
from pydantic import BaseModel
from rich.console import Console

from mdmodels import DataModel
from mdmodels.llm.fetcher import prepare_query, fetch_response


def query_openai(
    response_model: Type[DataModel] | Type[BaseModel],
    query: str,
    pre_prompt: str = "",
    base_url: str | None = None,
    api_key: str | None = None,
    llm_model: str = "gpt-4o",
    refine_query: bool = False,
    previous_data_response: DataModel | None = None,
    use_scaffold: bool = True,
):
    """
    Queries the OpenAI API using the specified parameters and returns the response.

    This function constructs a query to the OpenAI API, optionally refining the query
    and using a scaffold if specified. It requires an API key for authentication unless
    using the 'ollama' model, which requires a base URL.

    Args:
        response_model (Type[DataModel] | Type[BaseModel]): The model to use for the response.
        query (str): The content to parse and send to the API.
        pre_prompt (str, optional): An optional pre-prompt to include with the query. Defaults to "".
        base_url (str | None, optional): The base URL for the API. Required for 'ollama' model. Defaults to None.
        api_key (str | None, optional): The API key for authentication. Required for non-'ollama' models. Defaults to None.
        llm_model (str, optional): The language model to use. Defaults to "gpt-4o".
        refine_query (bool, optional): Indicates whether to refine the query before sending. Defaults to False.
        previous_data_response (DataModel, optional): The previous data response to include in the query. Defaults to None.
        use_scaffold (bool, optional): Indicates whether to use a scaffold for the query. Defaults to True.

    Returns:
        BaseModel: The response from the OpenAI API.

    Example:
        >>> from mdmodels.llm.handler import query_openai
        >>> response = query_openai(
        ...     response_model=dataset,
        ...     query="What is the capital of France?",
        ...     api_key="your_api_key"
        ... )
        >>> print(response)
        DataModel(field1="Paris", field2="France")
    """

    client = create_oai_client(api_key=api_key, base_url=base_url)
    console = Console()

    if use_scaffold:
        wrapped_response_model = prepare_query(response_model)
    else:
        wrapped_response_model = response_model

    with console.status("Processing...", spinner="dots") as status:
        status.update("Fetching response...")
        response = asyncio.run(
            fetch_response(
                client=client,
                response_model=wrapped_response_model,
                query=query,
                pre_prompt=pre_prompt,
                llm_model=llm_model,
                refine_query=refine_query,
                previous_response=(
                    previous_data_response.model_dump_json()
                    if previous_data_response
                    else ""
                ),
            )
        )

    return response


def create_oai_client(
    api_key: str,
    base_url: str | None = None,
):
    """
    Create an OpenAI client.

    Args:
        api_key (str): The API key for authentication.
        base_url (str | None, optional): The base URL for the API. Defaults to None.

    Returns:
        Instructor: The created OpenAI client.
    """

    assert api_key is not None or os.environ.get("OPENAI_API_KEY"), (
        "API key is required for non-ollama models. "
        "Either provide it or set it as an environment variable 'OPENAI_API_KEY'"
    )

    if base_url:
        mode = instructor.Mode.JSON
    else:
        mode = instructor.Mode.TOOLS_STRICT

    return from_openai(
        OpenAI(api_key=api_key, base_url=base_url),
        mode=mode,
    )
