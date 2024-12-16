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


def create_github_url(branch, repo, spec_path, tag):
    """
    Create a GitHub URL for accessing raw content from a repository.

    Args:
        branch (str | None): The branch name. Either branch or tag must be provided.
        repo (str): The repository name in the format 'owner/repo'.
        spec_path (str): The path to the file in the repository.
        tag (str | None): The tag name. Either branch or tag must be provided.

    Returns:
        str: The constructed GitHub URL.

    Raises:
        AssertionError: If neither branch nor tag is provided, or if both are provided.
    """
    assert (
        branch is None or tag is None
    ), "Either branch or tag must be provided, not both"

    if branch:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{spec_path}"
    elif tag:
        url = f"https://raw.githubusercontent.com/{repo}/tags/{tag}/{spec_path}"
    else:
        url = f"https://raw.githubusercontent.com/{repo}/main/{spec_path}"
    return url
