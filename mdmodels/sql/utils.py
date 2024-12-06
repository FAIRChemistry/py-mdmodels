#  -----------------------------------------------------------------------------
#   Copyright \(c\) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files \(the "Software"\), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#  #
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#  #
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#   THE SOFTWARE.
#  -----------------------------------------------------------------------------
from typing import List

from mdmodels.create import TYPE_MAPPING
from mdmodels.library import Library

PK_KEYS = ["pk", "primary_key", "primary key", "primarykey"]
FK_KEYS = ["fk", "foreign_key", "foreign key", "foreignkey", "references"]


def extract_foreign_keys(library: Library):
    """
    Extract foreign keys from the data model.

    Args:
        library: The data model library.

    Returns:
        dict: A dictionary of foreign keys.
    """

    library.resolve_target_primary_keys(overwrite=True)

    foreign_keys = dict()
    model = library._rust_model.model
    for obj in model.objects:
        connections = library.get_object_connections(obj.name)
        foreign_keys[obj.name] = {
            conn.source_attr: (conn.target_type, conn.target_attr)
            for conn in connections
            if conn.is_identifier
        }

    return foreign_keys


def _find_fk_table(model, ref):
    """
    Find the foreign key table in the data model.

    Args:
        model: The data model.
        ref (str): The reference string.

    Returns:
        tuple: A tuple containing the parts and root of the foreign key table.
    """
    root, *parts = ref.split(".")
    for part in parts[:-1]:
        root = _extract_ref(model, part, root)

    _validate_fk_ref(model, parts, root)

    return parts, root


def _extract_ref(model, part, root):
    """
    Extract the reference from the data model.

    Args:
        model: The data model.
        part (str): The part of the reference.
        root (str): The root of the reference.

    Returns:
        str: The updated root of the reference.
    """
    ref_obj = next((o for o in model.objects if o.name == root), None)
    if ref_obj is None:
        raise ValueError(f"Referenced object '{root}' not found in model.")
    ref_attr = next((a for a in ref_obj.attributes if a.name == part), None)
    root = ref_attr.dtypes[0]
    return root


def _validate_fk_ref(model, parts, root):
    """
    Validate the foreign key reference in the data model.

    Args:
        model: The data model.
        parts (list): The parts of the reference.
        root (str): The root of the reference.

    Raises:
        ValueError: If the referenced object or attribute is not found in the model.
    """
    ref_obj = next((o for o in model.objects if o.name == root), None)
    if ref_obj is None:
        raise ValueError(f"Referenced object '{root}' not found in model.")
    elif ref_obj and parts[-1] not in [a.name for a in ref_obj.attributes]:
        raise ValueError(
            f"Referenced attribute '{parts[-1]}' not found in object '{root}'."
        )


def _find_reference_object(parts: List[str], objects):
    """
    Find a reference object in a list of objects.

    Args:
        parts (List[str]): A list of parts of the reference object.
        objects: A list of objects.

    Returns:
        DataModelObject: The reference object.
    """
    for obj in objects:
        if obj.name == parts[0]:
            return obj

    return None


def extract_primary_keys(model, primary_keys):
    """
    Extract primary keys from the data model.

    Args:
        model: The data model.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary of primary keys.
    """
    primary_keys = dict()
    for obj in model.objects:
        pk_fields = [
            (attr.name, TYPE_MAPPING[attr.dtypes[0]])
            for attr in obj.attributes
            if any(opt.key.lower() in PK_KEYS for opt in attr.options)
            or attr.name == "id"
        ]

        assert (
            len(pk_fields) <= 1
        ), f"Multiple primary keys found for object '{obj.name}'."

        if pk_fields:
            primary_keys[obj.name] = pk_fields[0]

    return primary_keys


def map_pk_types(model, primary_keys) -> dict[str, tuple[str, type]]:
    """
    Map primary key types from the data model.

    Args:
        model: The data model.
        primary_keys (dict): A dictionary of primary key mappings.

    Returns:
        dict: A dictionary of typed primary keys.
    """
    typed_pks = {}
    for obj_name, attr_name in primary_keys.items():
        obj = next((o for o in model.objects if o.name == obj_name), None)

        if obj is None:
            raise ValueError(f"Primary key object '{obj_name}' not found in model.")

        attr = next((a for a in obj.attributes if a.name == attr_name), None)
        if attr is None:
            raise ValueError(
                f"Primary key attribute '{attr_name}' not found in object '{obj_name}'."
            )

        if attr.dtypes[0] not in TYPE_MAPPING:
            raise ValueError(
                f"Type '{attr.dtypes[0]}' of primary key attribute '{attr_name}' not found in TYPE_MAPPING."
            )

        typed_pks[obj.name] = (attr.name, TYPE_MAPPING[attr.dtypes[0]])

    return typed_pks
