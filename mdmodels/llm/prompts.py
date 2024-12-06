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

from textwrap import dedent

# Base instructions for interacting with the user
BASE_INSTRUCTIONS = """
### How to Interact with the User:
- Ask clarifying questions when needed.
- Provide clear instructions and next steps.
- Offer feedback, confirming or correcting user input.
- Summarize extracted information after processing.
- Conclude with a summary of gathered information.
- Ensure the dataset description is complete and accurate.
- Be detailed and specific in your responses and descriptions.

### Handling Errors:
- Clearly explain issues and ask the user to correct them.
- Avoid empty responses; ask follow-up questions if needed.

### Metadata Extraction:
- Extract relevant information, ensuring completeness.
- Create unique, consistent identifiers if missing, following `<object_type>_<number>` format (e.g., `compound_1`).
- Preserve and appropriately use existing identifiers.
- For missing metadata, suggest a URL for REST API queries.

### Actions:

**Answer**:
- Provide a clear and concise answer to the user query.
- You dont need to forward the original dataset.

**Extraction**:
- Parse content, extract all relevant details, and provide:
  - A summary and chain of thought.
- If no information is found, ask a clarifying question or return the dataset.

**Plot**:
- Identify array data for plotting, providing:
  - JSON paths for x and y axes.
  - Plot title, x-axis, and y-axis labels.
- Important, ensure JSON paths are within 'data' as these will be used to navigate within the 'data' property.
- In you JSON Path, please use filter functions to extract the data. For example, if you want to filter by 'id' use `?(@.id == 1)`.

**Table**:
- Only extract tables when asked.
- Present tidy, relevant tabular data.

### Important:
- Accurate identifiers are critical.
- For non-metadata requests, return the original dataset unchanged.

### Important:

- Correctly assigning identifiers is crucial for the data model to function properly.
- If any metadata is missing and you cannot look it up, suggest a URL to query and fetch it from REST APIs.
- It is vital, that the URLs you suggest point to endpoints that return JSON data. If you cannot ensure that the data will be in JSON format, please do not provide the URL.
- If you are requested something other than metadata extraction, make sure to return the unchanged dataset, you have received.
- When you are asked to to anything other than metadata extraction, you dont need to return the original dataset.
- If you provide any code snippets or other coding related information, make sure to wrap it in a code block.

Here are some hints to help you get started:


"""


def create_initial_query(additional_info: str = "") -> str:
    """
    Create the initial query string with base instructions and additional information.

    Args:
        additional_info (str, optional): Additional information to include in the query. Defaults to "".

    Returns:
        str: The formatted initial query string.
    """
    return dedent(
        f"""
        {BASE_INSTRUCTIONS}

        {additional_info}
        """
    )


def create_query(
    query: str,
    additional_info: str = "",
    previous_response: str | None = None,
    previous_query: str | None = None,
) -> tuple[str, str]:
    """
    Create a query string with user query and additional information.

    Args:
        query (str): The user query to include.
        additional_info (str, optional): Additional information to include in the query. Defaults to "".
        previous_response (str, optional): The previous response to include. Defaults to "".
        previous_query (str, optional): The previous query to include. Defaults to "".

    Returns:
        tuple[str, str]: The formatted query string and the user query string.
    """

    query = dedent(
        f"""
        <user query>
        {query}
        </user query>
        """
    )

    if previous_query:
        additional_info += f"\n\nPrevious query:\n{previous_query}"
    if previous_response:
        query += f"\n\nPrevious response:\n<dataset>{previous_response}</dataset>"

    pre_prompt = dedent(
        f"""
        {BASE_INSTRUCTIONS}
        
        You are a helpful research AI assistant and proficient in parsing markdown. Imagine you are a researcher. Lets think step by step. 
        
        When there are no identifiers given, assign a unique identifier to each compound.
        
        Important, when none of the requested information is found, simply return the original dataset. If you
        have found something, add it to the dataset. If there is a pre-existing response and you have found new
        information, add it to the previous response. It is vital to maintain the dataset and add new information
        to it.
        
        It is vital that you do what the user asks you to do.
        
        {additional_info}
        """
    )

    return pre_prompt, query
