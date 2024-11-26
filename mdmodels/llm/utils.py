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
import pandas as pd
from pydantic import BaseModel
from rich.console import Console


def _print_response(console: Console, response: BaseModel):
    """
    Print the response from the AI to the console.

    Args:
        console (Console): The console to print the response to.
        response (Response): The response model containing the AI's response.
    """

    for key, value in response:
        if not isinstance(value, pd.DataFrame):
            if not value or key == "data" or key == "query_urls":
                continue

        console.print(f"\n[bold green]{key.capitalize()}:[/bold green]")

        if isinstance(value, list) and not _collection_is_pydantic_model(value):
            for item in value:
                console.print("  - " + item)
        elif isinstance(value, list) and _collection_is_pydantic_model(value):
            for item in value:
                console.print(item)
        else:
            console.print(value)

    if response.query_urls:
        console.print("\n[bold green]Query URLs:[/bold green]")

        for query_url in response.query_urls:
            console.print(f"  - Query URL: {query_url}")

    console.print("\n[bold green]Data:[/bold green]")
    console.print(response.data)


def _is_pydantic_model(cls) -> bool:
    """
    Check if the given class is a Pydantic model.

    Args:
        cls: The class to check.

    Returns:
        bool: True if the class is a Pydantic model, False otherwise.
    """

    return isinstance(cls, BaseModel)


def _collection_is_pydantic_model(collection) -> bool:
    """
    Check if all items in the collection are Pydantic models.

    Args:
        collection: The collection to check.

    Returns:
        bool: True if all items in the collection are Pydantic models, False otherwise.
    """
    return all(_is_pydantic_model(item) for item in collection)


def extract_user_query(original_query: str):
    """
    Extract the user query from the original query string.

    Args:
        original_query (str): The original query string containing the user query.

    Returns:
        str: The extracted user query if found, otherwise the original query string.
    """
    if "<user query>" in original_query and "</user query>" in original_query:
        # Extract the user query from the original query
        return original_query.split("<user query>")[1].split("</user query>")[0].strip()

    return original_query
