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
import json
from textwrap import dedent
from typing import List, Type

import httpx
import validators
from instructor import Instructor
from mdmodels.llm.prompts import BASE_INSTRUCTIONS, create_merge_prompt
from mdmodels.llm.utils import extract_user_query
from openai import BaseModel


def query_the_web(
    client, llm_model, pre_prompt, response, status, wrapped_response_model
):
    status.update("Querying the web for additional information...")
    responses = asyncio.run(
        _perform_batch_web_queries(client, llm_model, response, wrapped_response_model)
    )
    status.update("Merging responses...")
    merge_response = _aggregate_responses(
        responses=responses,  # type: ignore
        original_response=response.data,
        original_query=pre_prompt,
        client=client,
        response_model=wrapped_response_model,
        llm_model=llm_model,
    )
    merge_response.query_urls = response.query_urls
    response = merge_response
    return response


async def _perform_batch_web_queries(
    client,
    llm_model,
    response,
    wrapped_response_model,
):
    """
    Perform batch web queries to fetch additional information.

    Args:
        client: The OpenAI client.
        llm_model: The model to use for the queries.
        response: The initial response from the AI.
        wrapped_response_model: The model to use for the web query responses.

    Returns:
        A list of responses from the web queries.
    """
    tasks = [
        _process_web_request(
            client=client,
            llm_model=llm_model,
            query_url=query_url,
            response=response,
            response_model=wrapped_response_model,
        )
        for query_url in response.query_urls
    ]

    return await asyncio.gather(*tasks)


async def _process_web_request(
    client,
    llm_model,
    query_url,
    response,
    response_model,
):
    """
    Process a web request to fetch JSON data.

    Args:
        client: The OpenAI client.
        llm_model: The model to use for the query.
        query_url: The URL to query.
        response: The initial response from the AI.
        response_model: The model to use for the web query response.

    Returns:
        The response model with the fetched data.
    """

    from mdmodels.llm.prompts import create_query

    if not validators.url(query_url):
        return response_model(answer=f"Invalid URL: {query_url}").model_dump_json()

    is_json, web_response = _fetch_json_response(query_url)

    if not is_json:
        # Seems like the URL does not return JSON data
        return response_model(
            answer=f"Could not fetch JSON data from URL: {query_url}"
        ).model_dump_json()

    web_pre_prompt, web_query = create_query(
        query=dedent(
            f"""
            
            {BASE_INSTRUCTIONS}
            
            Extract metadata from the following response.
            
            """
        ),
        previous_response=response.model_dump_json(),
    )

    from mdmodels.llm.handler import fetch_response

    response = await fetch_response(
        client=client,
        response_model=response_model,
        to_parse=json.dumps(web_response),
        pre_prompt=web_pre_prompt + web_query,
        llm_model=llm_model,
    )

    if not response.data:
        return response_model(
            answer=f"Could not extract data from URL: {query_url}"
        ).model_dump_json()

    return response.data.model_dump_json()


def _aggregate_responses(
    responses: List[str],
    original_response: BaseModel,
    original_query: str,
    client: Instructor,
    response_model: Type[BaseModel],
    llm_model: str = "gpt-4o",
) -> BaseModel:
    """
    Aggregate responses from multiple web queries.

    Args:
        responses (List[str]): The list of responses to aggregate.
        original_response (BaseModel): The original response from the AI.
        original_query (str): The original query to the AI.
        client (Instructor): The OpenAI client.
        response_model (Type[BaseModel]): The model to use for the aggregated response.
        llm_model (str, optional): The model to use. Defaults to "gpt-4o".

    Returns:
        BaseModel: The aggregated response.
    """

    from mdmodels.llm.handler import fetch_response

    original_query = extract_user_query(original_query)
    pre_prompt, query = create_merge_prompt(
        original_query=original_query,
        original_response=original_response,
    )

    to_parse = "\n".join([response for response in responses])

    return asyncio.run(
        fetch_response(
            client=client,
            response_model=response_model,
            to_parse=query + to_parse,
            pre_prompt=pre_prompt,
            llm_model=llm_model,
            refine_query=False,
        )
    )


def _fetch_json_response(url: str) -> tuple[bool, dict]:
    """
    Fetch a JSON response from the given URL.

    Args:
        url (str): The URL to fetch the JSON response from.

    Returns:
        tuple[bool, dict]: A tuple containing a boolean indicating if the response is JSON and the JSON data as a dictionary.
    """
    response = httpx.get(url)

    if "application/json" in response.headers.get("Content-Type", ""):
        return True, response.json()
    else:
        return False, {}
