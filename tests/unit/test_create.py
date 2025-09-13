from pathlib import Path
from mdmodels.create import build_module


class TestCreate:
    def test_create(self):
        """
        Test the creation of a data model library from a markdown file.

        This test performs the following steps:
        1. Act: Build the data model library using the specified markdown file.
        2. Assert: Check that the expected parts are present in the library.

        Raises:
            AssertionError: If any expected part is not found in the library.
        """
        # Act
        library = build_module(Path("./tests/fixtures/model.md"))

        # Assert
        expected_parts = ["Test", "Nested", "Ontology"]

        for part in expected_parts:
            assert part in library, f"Part {part} not found in library"

    def test_create_from_string(self):
        """
        Test the creation of a data model library from a markdown string.
        """
        library = build_module(content=open("./tests/fixtures/model.md").read())

        # Assert
        expected_parts = ["Test", "Nested", "Ontology"]

        for part in expected_parts:
            assert part in library, f"Part {part} not found in library"
