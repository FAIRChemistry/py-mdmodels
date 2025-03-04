import json

from pydantic import ValidationError
import pytest

from mdmodels import DataModel


class TestParse:
    def test_parse_and_create_object(self):
        """
        Test the parsing and creation of a DataModel object from a markdown file.

        This test verifies that a DataModel can be correctly instantiated with
        specified attributes and that the resulting object's JSON representation
        matches the expected output. It checks the following:
        - Creation of a Test object with given attributes.
        - Addition of references to a nested array.
        - Validation of the object's JSON output against expected JSON data.

        Raises:
            AssertionError: If the generated JSON does not match the expected JSON.
        """
        # Act
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            single_object=dm.Nested(
                reference="some_reference", names=["name1", "name2"]
            ),
            ontology=dm.Ontology.GO,
        )

        # Adding a reference to the nested array
        obj.add_to_nested_array(reference="some_reference", names=["name1", "name2"])
        obj.validate()

        # Assert
        expected_json = json.loads(open("./tests/fixtures/expected_json.json").read())

        assert (
            json.loads(obj.model_dump_json()) == expected_json
        ), "The generated JSON does not match the expected JSON."

    def test_parse_and_create_object_with_false_reference(self):
        """
        Test the creation of a DataModel object with an invalid reference.

        This test verifies that when an invalid reference is added to the nested array,
        a ValidationError is raised. It checks the following:
        - Creation of a Test object with valid attributes.
        - Attempt to add an invalid reference to the nested array.
        - Validation of the object should raise a ValidationError.

        Raises:
            ValidationError: If the object validation fails due to invalid references.
        """
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            ontology=dm.Ontology.GO,
        )

        # Attempting to add an invalid reference
        obj.add_to_nested_array(
            reference="some_unknown_reference", names=["name1", "name2"]
        )

        with pytest.raises(ValidationError):
            obj.validate()

    def test_parse_json(self):
        """
        Test the parsing of JSON data into a DataModel object.

        This test verifies that a DataModel can correctly parse a JSON string
        and instantiate a Test object with the specified attributes. It checks
        the following:
        - Creation of a Test object with given attributes.
        - Addition of references to a nested array.
        - Validation of the object's attributes against the expected output.

        Raises:
            AssertionError: If the parsed object's attributes do not match the expected attributes.
        """
        # Arrange
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        obj = self._create_object()

        # Act
        result = dm.Test.model_validate_json(
            open("./tests/fixtures/expected_json.json").read()
        )

        # Assert
        expected = obj.model_dump_json()
        assert json.loads(result.model_dump_json()) == json.loads(
            expected
        ), "The parsed JSON does not match the expected attributes."

    def test_parse_xml(self):
        """
        Test the parsing of XML data into a DataModel object.

        This test verifies that a DataModel can correctly parse an XML string
        and instantiate a Test object with the specified attributes. It checks
        the following:
        - Creation of a Test object with given attributes.
        - Validation of the object's attributes against the expected output.

        Raises:
            AssertionError: If the parsed XML does not match the expected attributes.
        """
        # Arrange
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        obj = self._create_object()

        # Act
        expected = obj.model_dump_json()
        result = dm.Test.from_xml(open("./tests/fixtures/expected_xml.xml").read())

        # Assert
        assert (
            result.model_dump_json() == expected
        ), "The parsed XML does not match the expected attributes."

    def _create_object(self):
        """
        Helper method to create a Test object for testing.

        This method instantiates a Test object with predefined attributes and
        adds a reference to the nested array. It is used in multiple test cases
        to ensure consistency in object creation.

        Returns:
            Test: An instance of the Test object with specified attributes.
        """
        dm = DataModel.from_markdown("./tests/fixtures/model.md")
        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            ontology=dm.Ontology.GO,
            single_object=dm.Nested(
                reference="some_reference", names=["name1", "name2"]
            ),
        )

        obj.add_to_nested_array(reference="some_reference", names=["name1", "name2"])

        return obj

    def test_parse_recursion(self):
        """
        Test the parsing of recursive structures in a DataModel object.

        This test verifies that a DataModel can correctly handle recursive
        definitions by creating a Recursive object that references itself.
        It checks the following:
        - Creation of a Recursive object with nested references.
        - Validation that the deepest level of recursion resolves to None.

        Raises:
            AssertionError: If the recursion does not resolve as expected.
        """
        dm = DataModel.from_markdown("./tests/fixtures/model_recursion.md")
        obj = dm.Recursive(
            recursive=dm.Recursive(
                recursive=dm.Recursive(recursive=dm.Recursive(recursive=dm.Recursive()))
            )
        )

        assert (
            obj.recursive.recursive.recursive.recursive.recursive is None
        ), "The deepest level of recursion should resolve to None"

    def test_parse_wrapped_xml(self):
        """
        Test the parsing and serialization of WrappedXML structures in a DataModel object.

        This test verifies that a WrappedXML object can be correctly instantiated
        from a DataModel and that its XML representation matches the expected output.
        It also checks that the object can be reconstructed from its XML representation.

        Raises:
            AssertionError: If the generated XML does not match the expected XML
            or if the reconstructed object does not equal the original object.
        """
        dm = DataModel.from_markdown("./tests/fixtures/model_wrapped_xml.md")
        obj = dm.WrappedXML(
            list_of_some_xml=[
                dm.Some(some_field="some_field_1", some_element="some_element_1"),
                dm.Some(some_field="some_field_2", some_element="some_element_2"),
            ],
            single_xml=dm.Some(
                some_field="some_field_3", some_element="some_element_3"
            ),
        )

        assert obj.xml().replace(" ", "").replace("\n", "") == open(
            "./tests/fixtures/expected_wrapped_xml.xml"
        ).read().replace(" ", "").replace("\n", ""), "The XML strings are not equal"

        obj2 = dm.WrappedXML.from_xml(obj.xml())
        assert obj2 == obj, "The objects are not equal"
