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
from rich.console import Console

from mdmodels import DataModel
from mdmodels.llm.fetcher import prepare_query, fetch_response
from mdmodels.llm.response import Action
from mdmodels.llm.utils import _print_response
from mdmodels.llm.web import query_the_web

DATA_UPDATE_ACTIONS = [Action.EXTRACTION, Action.DATA_UPDATE]


def query_openai(
    response_model: Type[DataModel],
    to_parse: str,
    pre_prompt: str = "",
    base_url: str | None = None,
    api_key: str | None = None,
    llm_model: str = "gpt-4o",
    verbose: bool = True,
    query_web: bool = True,
    refine_query: bool = True,
    previous_data_response: DataModel = None,
):
    """
    Query the OpenAI API with the provided parameters.

    Args:
        response_model (Type[DataModel]): The model to use for the response.
        to_parse (str): The content to parse.
        pre_prompt (str, optional): The pre-prompt to use. Defaults to "".
        base_url (str | None, optional): The base URL for the API. Defaults to None.
        api_key (str | None, optional): The API key for authentication. Defaults to None.
        llm_model (str, optional): The model to use. Defaults to "gpt-4o".
        verbose (bool, optional): Whether to print the response. Defaults to True.
        query_web (bool, optional): Whether to query the web for additional information. Defaults to True.
        refine_query (bool, optional): Whether to refine the query. Defaults to True.
        previous_data_response (DataModel, optional): The previous data response. Defaults to None.

    Returns:
        The response from the API.
    """
    if llm_model != "ollama":
        assert api_key is not None or os.environ.get("OPENAI_API_KEY"), (
            "API key is required for non-ollama models. "
            "Either provide it or set it as an environment variable 'OPENAI_API_KEY'"
        )
    else:
        assert base_url is not None, "Base URL is required for ollama model"

    client = create_oai_client(api_key=api_key, base_url=base_url)
    console = Console()

    wrapped_response_model = prepare_query(response_model)

    with console.status("Processing...", spinner="dots") as status:
        status.update("Fetching response...")
        response = asyncio.run(
            fetch_response(
                client=client,
                response_model=wrapped_response_model,
                to_parse=to_parse,
                pre_prompt=pre_prompt,
                llm_model=llm_model,
                refine_query=refine_query,
                previous_response=previous_data_response.model_dump_json()
                if previous_data_response
                else "",
            )
        )

        if query_web and response.query_urls:
            response = query_the_web(
                client, llm_model, pre_prompt, response, status, wrapped_response_model
            )

        if response.action == Action.PLOT and response.plot_templates:
            for plot_template in response.plot_templates:
                plot_template.plot(data=previous_data_response)
        elif response.action not in DATA_UPDATE_ACTIONS:
            response.data = previous_data_response

    if verbose:
        _print_response(response=response, console=console)

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
    return from_openai(
        OpenAI(api_key=api_key, base_url=base_url),
        mode=instructor.Mode.JSON,
    )
