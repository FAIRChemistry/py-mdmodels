from mdmodels import sql
from mdmodels.datamodel import DataModel


class TestDatabase:
    """
    TestDatabase contains integration tests for the database operations
    related to the DataModel. It verifies that the database can be
    created, populated, and queried correctly using the defined data model.
    """

    def test_database(self):
        """
        Test the database integration by performing the following steps:
        1. Arrange: Load the data model from a markdown file.
        2. Act: Create a database connection, generate SQL models,
           create tables, and insert a sample object into the database.
        3. Assert: Retrieve the object from the database and verify
           that it matches the expected values.

        This test ensures that the database operations work as intended
        and that the data model is correctly represented in the database.
        """
        # Arrange
        library = DataModel.from_markdown("./tests/fixtures/model_database.md")

        # Act
        db = sql.DatabaseConnector(database="")
        sql_models = sql.generate_sqlmodel(data_model=library)

        db.create_tables(sql_models)

        # Create a full example
        obj = library.Test(
            name="test",
            float_field=1.0,
            string_field="test",
            boolean_field=True,
            single_complex_field=library.Nested(
                value="test",
                other_ref="test",
            ),
            nested_array_field=[
                library.Nested(
                    value="test",
                    other_ref="test",
                )
            ],
        )

        with db as session:
            to_insert = sql.insert_nested(obj, library, session, sql_models)
            session.add_all(to_insert)

        # Assert
        expected = {
            "float_field": 1.0,
            "string_field": "test",
            "name": "test",
            "boolean_field": True,
            "single_complex_field": {"id": 1, "value": "test", "other_ref": "test"},
            "nested_array_field": [{"id": 2, "value": "test", "other_ref": "test"}],
        }

        with db as session:
            result = session.exec(sql.select(sql_models.Test)).first()
            assert result.to_dict() == expected  # type: ignore
