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
import json
import os

import rich
from pydantic import BaseModel, Field, model_validator

from mdmodels import DataModel
from mdmodels.llm import query_openai


class ResponseModel(BaseModel):
    """
    Model to handle the response from the LLM.

    Attributes:
        json_paths (list[str]): List of JSON paths to look for the answer.
        instructions (list[str]): Description on how the JSON paths shall be used to answer the question.
    """

    json_paths: list[str] = Field(
        ...,
        description="List of JSON paths to extract to match your instructions",
    )
    instructions: list[str] = Field(
        ...,
        description="Description on how the JSON paths you proposed shall be used to answer the question. "
        "Each instruction should at least contain one JSON Path from your proposal. "
        "An instruction should include an action that describes how to use the JSON paths to answer the question.",
    )

    @model_validator(mode="after")
    def validate_json_path(self):
        """
        Validate that the JSON paths are unique.
        """
        used_paths = set()
        for instruction in self.instructions:
            paths_in_instruction = {
                path for path in self.json_paths if path in instruction
            }

            if not paths_in_instruction:
                raise ValueError(
                    f"Instruction '{instruction}' does not contain any JSON path from your proposal"
                )

            used_paths.update(paths_in_instruction)

        self.json_paths = list(used_paths)
        return self

    def extract_data(self, data: DataModel):
        """
        Extract data from the DataModel based on the JSON paths.

        Args:
            data (DataModel): The data model to extract data from.

        Returns:
            str: The extracted data in JSON format.
        """
        return json.dumps(data.find_multiple(self.json_paths), default=str)


class FinalAnswer(BaseModel):
    """
    Model to represent the final answer.

    Attributes:
        answer (str): The final answer based on the analysis.
    """

    answer: str = Field(..., description="The final answer based on your analysis")


# Predefined prompt for the initial query
PRE_PROMPT = """
You are a helpful assistant, proficient in JSON and JSON Paths. You are tasked to answer questions about a dataset.

1. You may propose new, compatible JSON paths by analyzing the given paths.
    - For example, if provided with ['$.a.b.c', '$.a.b.d'], you can deduce and propose a broader path such as ['$.a.b'].
    - If given ['$.a.b.c'], you can also create paths with conditions, such as ['$.a[?(@.b == "something")]'].
2. Approach the task systematically:
    - Start by analyzing the given paths.
    - Propose intermediate or higher-level paths where appropriate.
    - Validate your suggestions against the dataset context.
3. Leave instructions for the next step. These should guide the assistant on how to use the paths to answer the user's
   question. Use bullet points for clarity.
   
Important:

	- Avoid suggesting paths that are already encompassed by a broader, more general path in the dataset.
	- Specifically, if a general path exists, any of its more specific sub-paths should be considered redundant.
	- The user provides additional context in "user_info" to help you propose the most relevant paths.
	

Example:

    Given the following paths
    
    $.a.b      # General path  
    $.a.b.c    # Redundant (sub-path of $.a.b)  
    $.a.b.d    # Redundant (sub-path of $.a.b)  
    
    Preferred output:
    Only the general path ($.a.b) should be retained, as it inherently includes the more 
    specific paths ($.a.b.c and $.a.b.d).

<json_paths>
{PATHS}
</json_paths>

<user_info>
{USER_PRE_PROMPT}
</user_info>

Determine the relevant JSON paths that can help answer the question.
"""

# Predefined prompt for the follow-up query
FOLLOW_UP_PROMPT = """
**Instructions**:

Follow these steps to answer the user's question:

{INSTRUCTIONS}

**Dataset Analysis**:  
Based on your last suggestion, these are the relevant parts of the dataset:  
{DATA}

### Question:

{QUESTION}
"""

# Predefined prompt for the follow-up pre-query
FOLLOW_UP_PRE_PROMPT = """
Based on you analysis answer the users question. Think step by step and be as concise as possible.

{USER_PRE_PROMPT}
"""


def dataset_query(
    data: DataModel,
    query: str,
    pre_prompt: str = "",
    display_thought_process: bool = False,
    model: str = "gpt-4o",
    base_url: str | None = None,
    api_key: str | None = None,
):
    """
    Query the dataset using the provided question and return the final answer.

    Args:
        data (DataModel): The data model to query.
        query (str): The question to ask the LLM.
        pre_prompt (str, optional): The pre-prompt to use. Defaults to "".
        api_key (str, optional): The API key for the LLM. Defaults to None.
        display_thought_process (bool, optional): Whether to display the thought process. Defaults to False.
        model (str, optional): The model to use for the query. Defaults to "gpt-4o".

    Returns:
        str: The final answer from the LLM.

    Raises:
        ValueError: If the API key is not provided and not set as an environment variable.
    """

    # Based on the provided JSON paths, the assistant will analyze the dataset
    # propose relevant JSON paths to answer the user's question. In addition,
    # the assistant will provide instructions on how to use the JSON paths to
    # answer the user's question.
    response = query_openai(
        query=query,
        pre_prompt=PRE_PROMPT.format(
            PATHS=data.json_paths(leafs=False),
            USER_PRE_PROMPT=pre_prompt,
        ).strip(),
        response_model=ResponseModel,
        use_scaffold=False,
        api_key=api_key,
        llm_model=model,
        base_url=base_url,
    )

    if display_thought_process:
        rich.print(response)

    query = FOLLOW_UP_PROMPT.format(
        INSTRUCTIONS="\n".join(response.instructions),
        DATA=response.extract_data(data),
        QUESTION=query,
    ).strip()

    # The assistant will now analyze the dataset based on the extracted JSON paths
    # and provide the final answer to the user's question.
    response = query_openai(
        query=query,
        pre_prompt=FOLLOW_UP_PRE_PROMPT.format(
            USER_PRE_PROMPT=pre_prompt,
        ).strip(),
        response_model=FinalAnswer,
        use_scaffold=False,
        api_key=api_key,
        llm_model=model,
    )

    return response.answer
