from mdmodels import DataModel, Templates


class TestConversion:
    def test_conversion(self):
        """
        Test the conversion of a DataModel to a JSON schema.

        We skip the internal and json schema templates as they are covered elsewhere and need extra context to test.
        """
        dm = DataModel.from_markdown("tests/fixtures/model.md")

        for template in Templates:
            if template == Templates.INTERNAL:
                continue
            elif template == Templates.JSON_SCHEMA:
                continue
            elif template == Templates.JSON_SCHEMA_ALL:
                continue
            converted = dm.convert_to(template)
            assert converted is not None
