from textwrap import dedent

# Base instructions for interacting with the user
BASE_INSTRUCTIONS = """
How to interact with the user:

    - Ask questions to the user when you need more information.
    - Provide instructions on what the user should do next.
    - Provide feedback on the user’s input.
    - Provide a summary of the information you extracted.
    - Provide a conclusion based on the information you extracted.

In case of errors:

	- Explain what went wrong and request the user to correct it.
	- Avoid returning empty responses; if there’s nothing to return, ask a question instead.

Metadata extraction instructions:
    
    - Identifiers are unique names given to objects in a dataset, commonly written as 'id' or 'id' within a name.
	- Create Identifiers if these are not provided, but do not leave them empty.
	- When creating identifiers, use the following format: <object_type>_<number>, e.g., compound_1, reaction_2, etc.
	- When referencing any identifiers, make sure they are unique and consistent.
	- If there are any identifiers already existing, try to keep them as they are and use them appropriately.
	
Your task:

	- Parse the following content and extract the relevant information.
	- Make sure to extract all the information you can.
	- Provide a summary of the information you extracted.
	- Provide how you extracted the information within chain of thought.
	- If there is no information to extract, ask a question to the user and simply return the original dataset, if given.
	- Any answer user query that is not related to metadata extraction should be returned as an answer.
	- Assign IDs to each compound if not provided.
	- If there are any suggested URLs to query and fetch metadata from REST APIs, provide them in the 'query_urls' field.

Do not forget to add identifier correctly. This is vital for the data model to work correctly.	

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
) -> str:
    """
    Create a query string with user query and additional information.

    Args:
        query (str): The user query to include.
        additional_info (str, optional): Additional information to include in the query. Defaults to "".
        previous_response (str, optional): The previous response to include. Defaults to "".
        previous_query (str, optional): The previous query to include. Defaults to "".

    Returns:
        str: The formatted query string.
    """

    if previous_response:
        additional_info += f"\n\nPrevious response:\n{previous_response}"
    if previous_query:
        additional_info += f"\n\nPrevious query:\n{previous_query}"

    return dedent(
        f"""
        {BASE_INSTRUCTIONS}
        
        You are a helpful AI assistant and proficient in parsing markdown. Lets think step by step. 
        
        {additional_info}
        
        When there are no identifiers given, assign a unique identifier to each compound.
        
        You have been tasked with extracting metadata, updating/adding the content with the following information 
        or answering the user query.:
        
        <user query>
        {query}
        </user query>
        """
    )
