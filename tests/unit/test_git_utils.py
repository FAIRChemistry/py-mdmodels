import pytest

from mdmodels.git_utils import create_github_url


class TestGitUtils:
    """
    TestGitUtils contains unit tests for the create_github_url function
    in the mdmodels.git_utils module. It verifies that the function
    correctly constructs GitHub URLs based on the provided branch, tag,
    repository, and file path.
    """

    def test_create_github_url_with_branch(self):
        """
        Test the creation of a GitHub URL using a specified branch.

        This test checks that the create_github_url function returns the
        correct URL format when a branch is provided, and the tag is None.
        """
        branch = "main"
        repo = "owner/repo"
        spec_path = "path/to/file.md"
        expected_url = (
            "https://raw.githubusercontent.com/owner/repo/main/path/to/file.md"
        )
        assert create_github_url(branch, repo, spec_path, None) == expected_url

    def test_create_github_url_with_tag(self):
        """
        Test the creation of a GitHub URL using a specified tag.

        This test verifies that the create_github_url function returns the
        correct URL format when a tag is provided, and the branch is None.
        """
        tag = "v1.0.0"
        repo = "owner/repo"
        spec_path = "path/to/file.md"
        expected_url = (
            "https://raw.githubusercontent.com/owner/repo/tags/v1.0.0/path/to/file.md"
        )
        assert create_github_url(None, repo, spec_path, tag) == expected_url

    def test_create_github_url_without_branch_or_tag(self):
        """
        Test the creation of a GitHub URL when neither branch nor tag is provided.

        This test checks that the create_github_url function defaults to the
        main branch when both branch and tag are None.
        """
        repo = "owner/repo"
        spec_path = "path/to/file.md"
        expected_url = (
            "https://raw.githubusercontent.com/owner/repo/main/path/to/file.md"
        )
        assert create_github_url(None, repo, spec_path, None) == expected_url

    def test_create_github_url_with_both_branch_and_tag(self):
        """
        Test the creation of a GitHub URL when both branch and tag are provided.

        This test verifies that the create_github_url function raises an
        AssertionError when both a branch and a tag are specified, as this
        is not allowed.
        """
        branch = "main"
        tag = "v1.0.0"
        repo = "owner/repo"
        spec_path = "path/to/file.md"
        with pytest.raises(
            AssertionError, match="Either branch or tag must be provided, not both"
        ):
            create_github_url(branch, repo, spec_path, tag)

    def test_create_github_url_with_neither_branch_nor_tag(self):
        """
        Test the creation of a GitHub URL when neither branch nor tag is provided.

        This test checks that the create_github_url function defaults to the
        main branch when both branch and tag are None.
        """
        repo = "owner/repo"
        spec_path = "path/to/file.md"
        expected_url = (
            "https://raw.githubusercontent.com/owner/repo/main/path/to/file.md"
        )
        assert create_github_url(None, repo, spec_path, None) == expected_url
