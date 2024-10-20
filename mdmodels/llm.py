import asyncio
import json
from typing import List, TypeVar, Generic, Type

import httpx
import instructor
import validators
from instructor import Instructor, from_openai
from ipython_genutils.text import dedent
from openai import OpenAI
from pydantic import BaseModel, Field
from rich.console import Console

from mdmodels import DataModel
from mdmodels.prompts import create_query, BASE_INSTRUCTIONS

T = TypeVar("T")


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
    summary: str = Field(
        "",
        description="A summary of what you have done. This should be a high-level overview",
    )
    answer: str = Field(
        "",
        description="If there are any questions that are not related to metadata extraction, return them as an answer",
    )
    chain_of_thought: str = Field(
        "",
        description="The thought process you used to extract the information",
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

    Returns:
        The response from the API.
    """
    if llm_model != "ollama":
        assert api_key is not None, "API key is required for non-ollama models"
    else:
        assert base_url is not None, "Base URL is required for ollama model"

    client = create_oai_client(api_key=api_key, base_url=base_url)
    console = Console()

    wrapped_response_model = _prepare_query(response_model)

    with console.status("Processing...", spinner="dots") as status:
        status.update("Fetching response...")
        response = _fetch_response(
            client=client,
            response_model=wrapped_response_model,
            to_parse=to_parse,
            pre_prompt=pre_prompt,
            llm_model=llm_model,
            refine_query=refine_query,
        )

        if query_web and response.query_urls:
            status.update("Querying the web for additional information...")
            tasks = []

            for query_url in response.query_urls:
                task = _process_web_request(
                    client=client,
                    llm_model=llm_model,
                    query_url=query_url,
                    response=response,
                    response_model=wrapped_response_model,
                )

                tasks.append(task)

            responses = asyncio.run(asyncio.gather(*tasks))

            console.print(responses)

    if verbose:
        _print_response(response=response, console=console)

    return response


async def _process_web_request(client, llm_model, query_url, response, response_model):
    validators.url(query_url)
    web_response = httpx.get(query_url).json()
    web_response = json.dumps(web_response, indent=2)
    web_pre_prompt = create_query(
        query=dedent(
            f"""
            
            {BASE_INSTRUCTIONS}
            
            Extract metadata from the following response.
            """
        ),
        previous_response=response.model_dump_json(indent=2),
    )
    response = _fetch_response(
        client=client,
        response_model=response_model,
        to_parse=web_response,
        pre_prompt=web_pre_prompt,
        llm_model=llm_model,
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
    return from_openai(
        OpenAI(api_key=api_key, base_url=base_url),
        mode=instructor.Mode.JSON,
    )


def _fetch_response(
        client: Instructor,
        response_model: Type[BaseModel],
        to_parse: str,
        pre_prompt: str = "",
        llm_model: str = "gpt-4o",
        refine_query: bool = True,
) -> BaseModel:
    """
    Fetch the response from the OpenAI API.

    Args:
        client (Instructor): The OpenAI client.
        response_model (Type[BaseModel]): The model to use for the response.
        to_parse (str): The content to parse.
        pre_prompt (str, optional): The pre-prompt to use. Defaults to "".
        llm_model (str, optional): The model to use. Defaults to "gpt-4o".
        refine_query (bool, optional): Whether to refine the query. Defaults to False.

    Returns:
        The response from the API.
    """

    if refine_query:
        res = _refine_query(
            client=client,
            query=pre_prompt,
            llm_model=llm_model,
        )

        assert res.refined_query, "Refined query is empty"

        pre_prompt = res.refined_query

    return client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": pre_prompt},
            {"role": "user", "content": to_parse},
        ],
        response_model=response_model,
    )


def _refine_query(
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
                    Refine the query to improve the AI's response.
                    
                    {query}
                    """
                ),
            }
        ],
        response_model=RefinedQuery,
    )


def _prepare_query(cls: Type[DataModel]) -> Type[Response]:
    """
    Prepare a query response model for the given data model class.

    Args:
        cls (Type[DataModel]): The data model class.

    Returns:
        Type[Response]: The prepared response model.
    """
    return Response[cls]


def _print_response(console: Console, response: BaseModel):
    """
    Print the response from the AI to the console.

    Args:
        console (Console): The console to print the response to.
        response (Response): The response model containing the AI's response.
    """

    for key, value in response:
        if not value or key == "data" or key == "query_urls":
            continue

        console.print(f"\n[bold green]{key.capitalize()}:[/bold green]")

        if isinstance(value, list):
            for item in value:
                console.print("  - " + item)
        else:
            console.print(value)

    if response.query_urls:
        console.print("\n[bold green]Query URLs:[/bold green]")

        for query_url in response.query_urls:
            console.print(f"  - Query URL: {query_url}")

    console.print("\n[bold green]Data:[/bold green]")
    console.print(response.data)


def _is_pydantic_model(cls) -> bool:
    if not isinstance(cls, type):
        return False

    return issubclass(cls, BaseModel) and cls != BaseModel


def _collection_is_pydantic_model(collection) -> bool:
    return all(_is_pydantic_model(item) for item in collection)
