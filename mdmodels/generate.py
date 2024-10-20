import mdmodels_core


def generate(template: mdmodels_core.Templates, dm: mdmodels_core.DataModel) -> str:
    """
    Convert a DataModel to a specified template.

    Args:
        template (mdmodels_core.Templates): The template to convert the DataModel to.
        dm (mdmodels_core.DataModel): The DataModel to be converted.
    """
    return dm.convert_to(template)
