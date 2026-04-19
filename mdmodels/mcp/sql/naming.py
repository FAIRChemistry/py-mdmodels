from __future__ import annotations

import re


def camel_to_snake(name: str, capitalize: bool = True) -> str:
    """Convert CamelCase/PascalCase to snake_case for predictable tool names.

    This function transforms class names from CamelCase or PascalCase convention
    to snake_case, which is used for generating consistent MCP tool names.

    Args:
        name: The CamelCase or PascalCase string to convert
        capitalize: If True, capitalize each word in the result (e.g., "User_Profile").
                   If False, return lowercase snake_case (e.g., "user_profile").

    Returns:
        The converted string in snake_case format
    """
    # Insert underscore before uppercase letters that follow lowercase letters or digits
    step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters that follow lowercase letters or digits
    step2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1)
    result = step2.lower()
    if capitalize:
        return "_".join(word.capitalize() for word in result.split("_"))
    return result
