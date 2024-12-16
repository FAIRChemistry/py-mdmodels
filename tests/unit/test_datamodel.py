from pathlib import Path
from pytest_httpx import httpx_mock  # noqa: F401
from mdmodels.datamodel import DataModel


class TestDataModel:
    def test_info(self):
        """
        Test the info method of the DataModel class.

        This test verifies that the info method can be called on a DataModel instance
        created from a markdown file. It does not assert any specific output,
        but ensures that the method executes without errors.
        """
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        dm.info()

    def test_parse_from_path(self):
        """
        Test parsing a DataModel from a local markdown file.

        This test checks that the DataModel can be correctly created from a markdown file
        located at a specified path. It asserts that the expected parts are present in the
        resulting library.

        Raises:
            AssertionError: If any expected part is not found in the library.
        """
        library = DataModel.from_markdown(Path("./tests/fixtures/model.md"))
        expected_parts = ["Test", "Nested", "Ontology"]

        for part in expected_parts:
            assert part in library, f"Part {part} not found in library"

    def test_parse_from_url(self, httpx_mock):
        """
        Test parsing a DataModel from a URL.

        This test verifies that the DataModel can be created from a markdown file
        retrieved from a specified URL. It uses httpx_mock to simulate the HTTP response
        and checks that the expected parts are present in the resulting library.

        Raises:
            AssertionError: If any expected part is not found in the library.
        """
        httpx_mock.add_response(
            url="http://www.example.com/model.md",
            text=open("./tests/fixtures/model.md").read(),
        )

        library = DataModel.from_markdown("http://www.example.com/model.md")
        expected_parts = ["Test", "Nested", "Ontology"]

        for part in expected_parts:
            assert part in library, f"Part {part} not found in library"

    def test_find(self):
        """
        Test the find method of the DataModel object.

        This test verifies that the find method can correctly retrieve values
        from the DataModel object based on JSONPath expressions. It checks
        various attributes including simple fields and nested structures.

        Raises:
            AssertionError: If the retrieved values do not match the expected values.
        """
        dm = DataModel.from_markdown(Path("./tests/fixtures/model.md"))
        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            nested_array=[
                dm.Nested(reference="some_reference", names=["name1", "name2"])
            ],
        )
        assert obj.find("$.number") == [1.0]
        assert obj.find("$.to_reference") == [["some_reference"]]
        assert obj.find("$.nested_array[0].reference") == ["some_reference"]
        assert obj.find("$.nested_array[0].names") == [["name1", "name2"]]
        assert (
            obj.find("$.nested_array[?(@.reference == 'some_reference')]")[0][
                "reference"
            ]
            == "some_reference"
        )

    def test_find_multiple(self):
        """
        Test the find method for multiple JSONPath expressions.

        This test verifies that the find method can handle multiple search queries
        and return the expected results for each. It checks both simple fields and
        nested structures, ensuring that the correct values are retrieved.

        Raises:
            AssertionError: If any retrieved value does not match the expected value.
        """
        dm = DataModel.from_markdown(Path("./tests/fixtures/model.md"))
        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            single_object=dm.Nested(
                reference="some_reference", names=["name1", "name2"]
            ),
            nested_array=[
                dm.Nested(reference="some_reference", names=["name1", "name2"])
            ],
        )

        to_search = [
            "$.name",
            "$.number",
            "$.single_object.reference",
            "$.single_object.names",
            "$.single_object.number",
            "$.nested_array[0].reference",
            "$.nested_array[0].names",
            "$.nested_array[0].number",
        ]

        to_expect = [
            "Test",
            1.0,
            "some_reference",
            ["name1", "name2"],
            None,
            "some_reference",
            ["name1", "name2"],
            None,
        ]

        for search, expect in zip(to_search, to_expect):
            assert obj.find(search) == [expect], f"Search: {search}, Expect: {expect}"
