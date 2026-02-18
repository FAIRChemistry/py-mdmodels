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

import os
from typing import IO, Any, List, Literal, Type, TypeVar, Union, overload

from openai import OpenAI
from openai.types.shared_params.reasoning import Reasoning
from pydantic import BaseModel
from rich.console import Console

from mdmodels import DataModel

# Type aliases
Purpose = Literal["vision", "pdf"]
File = tuple[IO, Purpose]

# TypeVar with bounds for precise return typing
T = TypeVar("T", bound=Union[BaseModel, DataModel])
SingleResponseModel = Union[Type[DataModel], Type[BaseModel]]
IterableResponseModel = Union[Type[List[DataModel]], Type[List[BaseModel]]]
OutputModel = Union[DataModel, BaseModel, List[DataModel], List[BaseModel]]


@overload
def query_openai(
    response_model: Type[T],
    query: str,
    *,
    pre_prompt: str = "",
    files: list[File] | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    llm_model: str = "gpt-4.1",
    temperature: float | None = 0.0,
    reasoning: Literal["low", "medium", "high"] | None = None,
) -> T: ...


@overload
def query_openai(
    response_model: Type[List[T]],
    query: str,
    *,
    pre_prompt: str = "",
    files: list[File] | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    llm_model: str = "gpt-4.1",
    temperature: float | None = 0.0,
    reasoning: Literal["low", "medium", "high"] | None = None,
) -> List[T]: ...


def query_openai(
    response_model: Type[Any],
    query: str,
    *,
    pre_prompt: str = "",
    files: list[File] | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    llm_model: str = "gpt-4.1",
    temperature: float | None = 0.0,
    reasoning: Literal["low", "medium", "high"] | None = None,
) -> Any:
    """
    Query the OpenAI API with structured response parsing.

    This function sends a query to the OpenAI API and returns a structured response
    based on the provided response model. It supports file uploads for vision and
    PDF processing capabilities.

    Args:
        response_model: The Pydantic model class to use for response parsing.
        query: The main query content to send to the API.
        pre_prompt: Optional system prompt to provide context. Defaults to "".
        files: Optional list of (file, purpose) tuples for file uploads. Defaults to None.
        base_url: Optional base URL for the API (useful for local models). Defaults to None.
        api_key: Optional API key for authentication. If None, uses OPENAI_API_KEY env var.
        llm_model: The language model to use. Defaults to "gpt-4o".
        temperature: The temperature for the language model. Defaults to 0.0.
    Returns:
        An instance of the response_model with the parsed API response.

    Raises:
        RuntimeError: If the API request fails or response parsing fails.
        ValueError: If required authentication is missing.

    Example:
        >>> from pydantic import BaseModel
        >>> from mdmodels.llm.handler import query_openai
        >>>
        >>> class CityInfo(BaseModel):
        ...     name: str
        ...     country: str
        ...     population: int
        >>>
        >>> response = query_openai(
        ...     response_model=CityInfo,
        ...     query="What is the capital of France and its population?",
        ...     api_key="your_api_key"
        ... )
        >>> print(f"{response.name}, {response.country}: {response.population}")
        Paris, France: 2161000
    """
    if files is None:
        files = []

    client = _create_openai_client(api_key=api_key, base_url=base_url)
    console = Console()

    with console.status("Processing query...", spinner="dots") as status:
        status.update("Building request...")
        messages = _build_messages(query, pre_prompt, files, client)

        status.update("Fetching response...")
        try:
            response = client.responses.parse(
                model=llm_model,
                input=messages,  # type: ignore
                text_format=response_model,
                temperature=None if reasoning else temperature,
                reasoning=Reasoning(effort=reasoning) if reasoning else None,
            )

            if response.output_parsed is None:
                raise RuntimeError("API returned None for parsed response")

            return response.output_parsed

        except Exception as e:
            raise RuntimeError(
                f"Failed to get structured response from OpenAI: {e}"
            ) from e


def _build_messages(
    query: str, pre_prompt: str, files: list[File], client: OpenAI
) -> list[dict]:
    """Build the message list for the OpenAI API request."""
    messages = []

    if pre_prompt:
        messages.append({"role": "system", "content": pre_prompt})

    file_content = []
    for file, purpose in files:
        file_dict = _upload_file(client, file, purpose)
        file_content.append(file_dict)

    if file_content:
        messages.append({"role": "user", "content": file_content})

    messages.append({"role": "user", "content": query})
    return messages


def _upload_file(client: OpenAI, file: IO, purpose: Purpose) -> dict:
    """
    Upload a file to the OpenAI API for processing.

    Args:
        client: The OpenAI client instance.
        file: The file object to upload.
        purpose: The intended use of the file ("vision" for images, "pdf" for documents).

    Returns:
        A dictionary containing the file type and file ID for API consumption.

    Raises:
        RuntimeError: If the file upload fails.
        ValueError: If an invalid purpose is provided.
    """
    purpose_to_type = {
        "vision": "input_image",
        "pdf": "input_file",
    }

    if purpose not in purpose_to_type:
        raise ValueError(
            f"Invalid purpose: {purpose}. Must be one of: {list(purpose_to_type.keys())}"
        )

    try:
        file_obj = client.files.create(file=file, purpose="user_data")
        return {
            "type": purpose_to_type[purpose],
            "file_id": file_obj.id,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to upload file to OpenAI: {e}") from e


def _create_openai_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> OpenAI:
    """
    Create and configure an OpenAI client.

    Args:
        api_key: Optional API key for authentication. If None, uses OPENAI_API_KEY env var.
        base_url: Optional base URL for the API (useful for local models).

    Returns:
        A configured OpenAI client instance.

    Raises:
        ValueError: If no API key is provided or found in environment variables.
    """
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")

    if api_key is None:
        raise ValueError(
            "API key is required. Either provide it as a parameter or set the "
            "OPENAI_API_KEY environment variable."
        )

    return OpenAI(api_key=api_key, base_url=base_url)
