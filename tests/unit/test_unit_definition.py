import json

from mdmodels.datamodel import DataModel


class TestUnitDefinition:
    def test_parse_unit_definition(self):
        """
        Test the parsing of a simple unit definition.

        This test verifies that a UnitExample object can be created with
        a single unit and multiple units. It checks that the JSON representation
        of the object matches the expected output.

        Raises:
            AssertionError: If the generated JSON does not match the expected JSON.
        """
        # Arrange
        dm = DataModel.from_markdown("./tests/fixtures/model_units.md")

        # Act
        obj = dm.UnitExample(
            single_unit="mg",
            multiple_units=[
                "g",
                "mmol/l",
            ],
        )

        # Assert
        expected_json = open("./tests/fixtures/expected_units.json").read()
        assert json.loads(obj.model_dump_json(indent=2)) == json.loads(expected_json)

    def test_complex_unit_definition(self):
        """
        Test the parsing of a complex unit definition.

        This test verifies that a UnitExample object can be created with
        a complex unit string. It checks that the JSON representation of the
        object matches the expected output for complex units.

        Raises:
            AssertionError: If the generated JSON does not match the expected JSON.
        """
        # Arrange
        dm = DataModel.from_markdown("./tests/fixtures/model_units.md")

        # Act
        obj = dm.UnitExample(single_unit="mg / s * l mol^2")

        # Assert
        expected_json = open("./tests/fixtures/expected_units_complex.json").read()
        assert json.loads(obj.model_dump_json(indent=2)) == json.loads(expected_json)
