import json

from mdmodels import DataModel


class TestFromJsonSchema:
    def test_from_json_schema(self):
        """
        Test creating a DataModel from a JSON schema file.

        This test verifies that a DataModel can be correctly created from a JSON schema file
        and that the resulting model can instantiate objects with the expected structure.
        It checks the following:
        - Creation of expected classes from the JSON schema.
        - Instantiation of objects with proper attributes.
        - Addition of references to nested arrays.
        - Validation of the object's JSON output against expected JSON data.

        Raises:
            AssertionError: If the expected classes don't match or the generated JSON
                          doesn't match the expected JSON.
        """
        dm = DataModel.from_json_schema("tests/fixtures/model_json_schema.json")

        expected_classes = ["Test", "Nested"]
        present_classes = [name for name, _ in dm.models()]

        assert set(expected_classes) == set(present_classes), (
            "The expected classes do not match the present classes."
        )

        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            single_object=dm.Nested(
                reference="some_reference", names=["name1", "name2"]
            ),
            ontology=dm.Ontology.VALUE_1,
        )

        # Adding a reference to the nested array
        obj.add_to_nested_array(
            reference="some_reference",
            names=["name1", "name2"],
        )
        obj.validate()

        # Assert
        expected_json = json.loads(open("./tests/fixtures/expected_json.json").read())

        assert json.loads(obj.model_dump_json()) == expected_json, (
            "The generated JSON does not match the expected JSON."
        )

    def test_from_json_schema_string(self):
        """
        Test creating a DataModel from a JSON schema string.

        This test verifies that a DataModel can be correctly created from a JSON schema
        provided as a string rather than a file path. It performs the same validations
        as the file-based test to ensure consistency between the two methods.
        It checks the following:
        - Creation of expected classes from the JSON schema string.
        - Instantiation of objects with proper attributes.
        - Addition of references to nested arrays.
        - Validation of the object's JSON output against expected JSON data.

        Raises:
            AssertionError: If the expected classes don't match or the generated JSON
                          doesn't match the expected JSON.
        """
        json_schema = open("tests/fixtures/model_json_schema.json").read()
        dm = DataModel.from_json_schema_string(json_schema)

        expected_classes = ["Test", "Nested"]
        present_classes = [name for name, _ in dm.models()]

        assert set(expected_classes) == set(present_classes), (
            "The expected classes do not match the present classes."
        )

        obj = dm.Test(
            name="Test",
            to_reference=["some_reference"],
            number=1.0,
            single_object=dm.Nested(
                reference="some_reference", names=["name1", "name2"]
            ),
            ontology=dm.Ontology.VALUE_1,
        )

        # Adding a reference to the nested array
        obj.add_to_nested_array(
            reference="some_reference",
            names=["name1", "name2"],
        )
        obj.validate()

        # Assert
        expected_json = json.loads(open("./tests/fixtures/expected_json.json").read())

        assert json.loads(obj.model_dump_json()) == expected_json, (
            "The generated JSON does not match the expected JSON."
        )
