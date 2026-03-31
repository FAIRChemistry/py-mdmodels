from typing import Any, cast

from mdmodels import sql
from mdmodels.datamodel import DataModel
from mdmodels.library import Library
from mdmodels.sql.base import SQLBase
from mdmodels.sql.childref import ChildRef, reconstruct_model


class TestDatabase:
    """
    TestDatabase contains integration tests for the database operations
    related to the DataModel. It verifies that the database can be
    created, populated, and queried correctly using the defined data model.
    """

    def test_database(
        self,
        integration_db: tuple[
            sql.DatabaseConnector, Library[SQLBase], Library[DataModel]
        ],
    ):
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
        db, sql_models, library = integration_db

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

    def test_database_with_childref(
        self,
        integration_db: tuple[
            sql.DatabaseConnector, Library[SQLBase], Library[DataModel]
        ],
    ):
        """
        Test inserting nested rows and then linking to existing rows via ChildRef.

        Uses in-memory SQLite and verifies that ChildRef(row_pk_=...) resolves
        existing related rows for both scalar and list relationships.
        """
        db, sql_models, library = integration_db

        full_obj = library.Test(
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
            some_other_field=library.SomeOther(name="test"),
        )

        ReconstructedTest = reconstruct_model(library.Test)

        # Act + Assert in a single session for in-memory SQLite stability
        with db as session:
            to_insert = sql.insert_nested(full_obj, library, session, sql_models)
            session.add_all(to_insert)

            nested_rows = session.exec(sql.select(sql_models.Nested)).all()
            assert len(nested_rows) >= 2

            childref_obj = ReconstructedTest(
                name="test-childref",
                float_field=2.0,
                string_field="childref",
                boolean_field=False,
                single_complex_field=ChildRef(row_pk=getattr(nested_rows[0], "id")),
                nested_array_field=[ChildRef(row_pk=getattr(nested_rows[1], "id"))],
                some_other_field=ChildRef(row_pk="test"),
            )

            to_insert = sql.insert_nested(
                cast(DataModel, childref_obj), library, session, sql_models
            )
            session.add_all(to_insert)

            all_tests = session.exec(sql.select(sql_models.Test)).all()
            assert len(all_tests) == 2

            by_name = {getattr(row, "name"): row.to_dict() for row in all_tests}
            assert "test" in by_name
            assert "test-childref" in by_name

            childref_inserted = cast(dict[str, Any], by_name["test-childref"])
            single_complex = childref_inserted["single_complex_field"]
            nested_array = childref_inserted["nested_array_field"]

            assert isinstance(single_complex, dict)
            assert single_complex.get("id") is not None
            assert isinstance(nested_array, list)
            assert len(nested_array) == 1
