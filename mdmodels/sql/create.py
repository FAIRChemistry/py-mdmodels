#  -----------------------------------------------------------------------------
#   Copyright (c) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
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
import warnings
from typing import Any, Dict, List, Optional, Union

from mdmodels_core import DataModel  # type: ignore
from pydantic import ConfigDict, create_model
from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from mdmodels.sql.config import TableConfig

from ..create import TYPE_MAPPING
from ..datamodel import DataModel as DataModelType
from ..library import Library
from .base import SQLBase
from .connector import DatabaseType, DatabaseTypeLiteral
from .linked_type import LinkedType
from .utils import extract_foreign_keys


def generate_sqlmodel(
    *,
    data_model: Library[DataModelType],
    base_classes=None,
    database_type: Union[DatabaseTypeLiteral, DatabaseType] = DatabaseType.POSTGRESQL,
    table_config: Optional[Dict[str, TableConfig]] = None,
) -> Library[SQLModel]:
    """
    Convert a DataModel library to a library of SQLModel classes for database operations.

    This function takes a data model library and generates corresponding SQLModel classes
    that can be used with SQLAlchemy for database operations. It handles primary keys,
    foreign keys, relationships, and database-specific configurations.

    Args:
        data_model (Library[DataModel]): The library containing the data model objects
            to be converted to SQLModel classes.
        base_classes (List[type], optional): Additional base classes for the generated
            SQLModel classes to inherit from. Defaults to None.
        database_type (Union[DatabaseTypeLiteral, DatabaseType], optional): The target
            database type (e.g., PostgreSQL, SQLite). Affects field mappings and features.
            Defaults to DatabaseType.POSTGRESQL.
        table_config (Optional[Dict[str, TableConfig]], optional): Configuration for
            specific tables, including primary keys, indexing, and embedding settings.
            Defaults to None.

    Returns:
        Library[SQLModel]: A library containing SQLModel classes that correspond
            to the objects in the input data model, ready for database operations.

    Example:
        >>> from mdmodels import DataModel
        >>> from mdmodels.sql import generate_sqlmodel, TableConfig
        >>>
        >>> model = DataModel.from_markdown("model.md")
        >>> sql_models = generate_sqlmodel(
        ...     data_model=model,
        ...     database_type="postgresql",
        ...     table_config={
        ...         "Protein": TableConfig(primary_key="uniprot_id")
        ...     }
        ... )
    """
    # Initialize default values for optional parameters
    base_classes = base_classes or []
    table_config = table_config or {}

    # Extract the core model from the library
    model = data_model._rust_model.model  # type: ignore
    enums = {enum.name for enum in model.enums}

    # Normalize database type to enum if provided as string
    if isinstance(database_type, str):
        database_type = DatabaseType.from_str(database_type)

    # Extract relationship information from the data model
    foreign_keys = extract_foreign_keys(data_model)

    # Create linking tables for many-to-many relationships
    linking_tables, uses_linking_table = _extract_linking_tables(
        model=model,
        table_config=table_config,
    )

    # Get all types for looking up target objects
    dtypes = _all_types(model.objects)

    # Initialize the output library with the same structure as input
    models = Library(rust_model=data_model._rust_model)
    models._pydantic_library = data_model
    models._cross_connections = data_model._cross_connections

    # Process each object in the data model to create SQLModel classes
    for obj in model.objects:
        obj_fks = foreign_keys.get(obj.name, {})
        _process_object(
            linking_tables=linking_tables,
            uses_linking_table=uses_linking_table,
            models=models,
            obj=obj,
            base_classes=base_classes,
            foreign_keys=obj_fks,
            db_type=database_type,
            table_config=table_config.get(obj.name),
            table_configs=table_config,
            enums=enums,
            dtypes=dtypes,
        )

    # Rebuild all models to ensure proper relationships and validation
    _rebuild_models(models)

    return models


def _process_object(
    linking_tables: dict[str, SQLModel],
    uses_linking_table: dict[str, bool],
    models: dict,
    obj: DataModel,
    base_classes: List[type],
    foreign_keys: dict[str, tuple[str, str]],
    db_type: DatabaseType,
    table_config: Optional[TableConfig],
    table_configs: Dict[str, TableConfig],
    enums: set[str],
    dtypes: Dict[str, Any],
) -> None:
    """
    Process a single data model object and convert it to a SQLModel class.

    This function handles the conversion of a DataModel object to a SQLModel class,
    including field definitions, primary keys, foreign keys, relationships, and
    database-specific configurations like vector embeddings.

    Args:
        linking_tables (dict[str, SQLModel]): Dictionary of linking tables for
            many-to-many relationships.
        uses_linking_table (dict[str, bool]): Dictionary mapping join_name to bool
            indicating if linking table is used for the relationship.
        models (dict): Dictionary to store the processed SQLModel classes.
        obj (DataModel): The data model object to process.
        base_classes (List[type]): List of base classes for the SQLModel to inherit from.
        foreign_keys (dict[str, tuple[str, str]]): Dictionary mapping attribute names
            to their foreign key table and column references.
        db_type (DatabaseType): The target database type for optimization.
        table_config (Optional[TableConfig]): Configuration for this specific table.
        table_configs (Dict[str, TableConfig]): Dictionary of all table configurations.
        enums (set[str]): Set of enum type names in the model.
        dtypes (Dict[str, Any]): Dictionary mapping type names to type objects.

    Returns:
        None: The function modifies the models dictionary in place.
    """
    table_config = table_config or TableConfig()
    field_definitions = {}

    # Add default primary key if needed
    _add_default_primary_key(obj, table_config, field_definitions)

    # Process each attribute of the object
    for attr in obj.attributes:
        is_primary_key = attr.name == table_config.primary_key or attr.name == "id"
        fk = foreign_keys.get(attr.name)
        _process_attribute(
            attr=attr,
            field_definitions=field_definitions,
            linking_tables=linking_tables,
            uses_linking_table=uses_linking_table,
            obj=obj,
            is_primary_key=is_primary_key,
            db_type=db_type,
            fk=fk,
            table_config=table_config,
            table_configs=table_configs,
            enums=enums,
            dtypes=dtypes,
        )

    # Add vector embedding field if configured
    _add_embedding_field(db_type, table_config, field_definitions)

    # Create and store the SQLModel class
    model = _create_sqlmodel_class(
        obj.name,
        field_definitions,
        base_classes,
        table_config,
    )
    models[obj.name] = model


def _process_attribute(
    attr,
    field_definitions,
    linking_tables,
    uses_linking_table: dict[str, bool],
    obj,
    is_primary_key: bool,
    db_type: DatabaseType,
    table_config: TableConfig,
    table_configs: Dict[str, TableConfig],
    enums: set[str],
    dtypes: Dict[str, Any],
    fk: tuple[str, str] | None = None,
):
    """
    Process a single attribute and add its field definition to the SQLModel.

    This function determines how to handle an attribute based on its type:
    - Simple types (string, int, etc.) become regular database columns
    - Complex types (references to other objects) become relationships
      - With linking tables if either side is an array
      - Direct foreign key relationships otherwise (unidirectional, only on parent)

    Note: Direct relationships are unidirectional - fields are only created on the
    object that defines the attribute. No backrefs or reverse relationships are
    created on target objects. For example, if `viscosities` defines `mixture: mixtures`,
    the relationship fields are only created on `viscosities`, not on `mixtures`.

    Args:
        attr: The attribute object from the data model to process.
        field_definitions (dict): Dictionary to store the SQLModel field definitions.
        linking_tables (dict): Dictionary of linking tables for relationships.
        uses_linking_table (dict[str, bool]): Dictionary mapping join_name to bool
            indicating if linking table is used for the relationship.
        obj: The parent object containing this attribute.
        is_primary_key (bool): Whether this attribute is the primary key.
        db_type (DatabaseType): The target database type.
        table_config (TableConfig): Configuration for the parent table.
        table_configs (Dict[str, TableConfig]): Dictionary of all table configurations.
        enums (set[str]): Set of enum type names in the model.
        dtypes (Dict[str, Any]): Dictionary mapping type names to type objects.
        fk (tuple[str, str] | None, optional): Foreign key reference if applicable.

    Raises:
        ValueError: If the attribute type is not recognized and no relationship exists.
    """
    attr_type = attr.dtypes[0]
    join_name = _link_table_name(obj.name, attr.name, attr_type)

    # Determine the Python type for simple attributes
    dtype = _get_attribute_type(attr_type, enums)

    if dtype is not None:
        # Handle simple types (including enums)
        _create_simple_attr(
            attr=attr,
            dtype=dtype,
            field_definitions=field_definitions,
            is_primary_key=is_primary_key,
            fk=fk,
            db_type=db_type,
            table_config=table_config,
        )
    elif uses_linking_table.get(join_name, False):
        # Handle complex types that require linking tables (array relationships)
        _create_complex_attr(
            attr=attr,
            field_definitions=field_definitions,
            join_name=join_name,
            linking_tables=linking_tables,
        )
    elif attr_type in dtypes:
        # Handle complex types with direct relationships (non-array)
        # Note: Direct relationships are unidirectional - fields are only created
        # on the parent object (obj) that defines this attribute. No backrefs
        # or reverse relationships are created on the target object.
        target_obj = dtypes[attr_type]
        target_config = table_configs.get(attr_type, TableConfig())
        target_pk, target_pk_type = _get_primary_key(target_obj, target_config)

        _create_direct_relationship_attr(
            attr=attr,
            field_definitions=field_definitions,
            target_type_name=attr_type,
            target_pk_name=target_pk,
            target_pk_type=target_pk_type,
            source_table_name=obj.name,
        )
    else:
        raise ValueError(
            f"Type '{attr_type}' not found in TYPE_MAPPING, enums, or object types."
        )


def _create_complex_attr(
    attr,
    field_definitions: dict[str, tuple[Any, Any]],
    join_name: str,
    linking_tables: dict[str, SQLModel],
):
    """
    Create a complex attribute that represents a relationship to another object.

    Complex attributes are those that reference other objects in the data model,
    requiring relationships rather than simple database columns. This function
    handles both single references and arrays of references using linking tables.

    Args:
        attr: The attribute object representing the relationship.
        field_definitions (dict[str, tuple[Any, Any]]): Dictionary to store field definitions.
        join_name (str): The name of the linking table for this relationship.
        linking_tables (dict[str, SQLModel]): Dictionary of available linking tables.
    """
    # Determine the type annotation based on whether it's an array
    if attr.is_array:
        dtype = List[attr.dtypes[0]]  # List of related objects
    else:
        dtype = attr.dtypes[0]  # Single related object

    # Make the relationship optional if not required
    if not attr.required:
        dtype = _wrap_optional(dtype)

    # Create the relationship field using the appropriate linking table
    field_definitions[attr.name] = (
        dtype,
        Relationship(
            link_model=linking_tables[join_name],
        ),
    )


def _create_direct_relationship_attr(
    attr,
    field_definitions: dict[str, tuple[Any, Any]],
    target_type_name: str,
    target_pk_name: str,
    target_pk_type: Any,
    source_table_name: str,
):
    """
    Create a direct relationship attribute without a linking table.

    This function handles one-to-one or many-to-one relationships by creating
    a foreign key field and a relationship field directly on the parent table.

    Important: This function only creates fields on the parent object (the one
    containing the foreign key). No backref or reverse relationship is created
    on the target object. For example, if `viscosities` has `mixture: mixtures`,
    this will create `mixture_id` and `mixture` fields on `viscosities`, but
    nothing on `mixtures`.

    Args:
        attr: The attribute object representing the relationship.
        field_definitions (dict[str, tuple[Any, Any]]): Dictionary to store field definitions.
        target_type_name (str): The name of the target object type.
        target_pk_name (str): The primary key column name of the target table.
        target_pk_type (Any): The Python type of the target primary key.
        table_config (TableConfig): Configuration for the parent table.
    """
    # Create foreign key field: {attr_name}_id
    fk_field_name = f"{attr.name}_id"
    fk_dtype = target_pk_type
    if not attr.required:
        fk_dtype = _wrap_optional(fk_dtype)

    field_definitions[fk_field_name] = (
        fk_dtype,
        Field(
            default=None if not attr.required else ...,
            foreign_key=f"{target_type_name.lower()}.{target_pk_name}",
            nullable=True,
            index=True,
            exclude=True,
        ),
    )

    # Create relationship field: {attr_name}
    # Use forward reference string for the target type
    relationship_dtype = target_type_name
    if not attr.required:
        relationship_dtype = _wrap_optional(relationship_dtype)

    field_definitions[attr.name] = (
        relationship_dtype,
        Relationship(
            sa_relationship_kwargs={
                "lazy": "selectin",
                "foreign_keys": f"[{source_table_name}.{fk_field_name}]",
            }
        ),
    )


def _create_simple_attr(
    attr,
    dtype: Any,
    field_definitions: dict[str, tuple[Any, Any]],
    is_primary_key: bool,
    db_type: DatabaseType,
    table_config: TableConfig,
    fk: tuple[str, str] | None = None,
):
    """
    Create a simple attribute that maps to a database column.

    Simple attributes are those with primitive types (string, int, float, etc.)
    that can be directly stored in database columns. This function handles
    various database-specific optimizations and configurations.

    Args:
        attr: The attribute object to process.
        dtype (Any): The Python type for this attribute.
        field_definitions (dict[str, tuple[Any, Any]]): Dictionary to store field definitions.
        is_primary_key (bool): Whether this attribute is the primary key.
        db_type (DatabaseType): The target database type.
        table_config (TableConfig): Configuration for the parent table.
        fk (tuple[str, str] | None, optional): Foreign key reference if applicable.

    Returns:
        None: Modifies field_definitions in place, or returns early for unsupported types.
    """
    # Skip array types for non-PostgreSQL databases (not supported)
    if attr.is_array and db_type != DatabaseType.POSTGRESQL:
        warnings.warn(
            f"Array of simple units not supported.Skipping attribute '{attr.name}'.",
        )
        return

    # Build field parameters
    field_params = _build_field_parameters(
        attr=attr,
        is_primary_key=is_primary_key,
        db_type=db_type,
        table_config=table_config,
        fk=fk,
    )

    # Handle optional attributes
    if not attr.required:
        dtype = _wrap_optional(dtype)

    # Create the field definition
    field_definitions[attr.name] = (dtype, Field(**field_params))

    # Add foreign key relationship if applicable
    if fk:
        _add_foreign_key_relationship(attr.name, fk, field_definitions)


def _add_default_primary_key(
    obj: DataModel,
    table_config: TableConfig,
    field_definitions: dict[str, tuple[Any, Any]],
) -> None:
    """Add default 'id' primary key if needed."""
    has_id = any(attr.name == "id" for attr in obj.attributes)
    if table_config.primary_key is None and not has_id:
        table_config.primary_key = "id"
        field_definitions["id"] = (
            Optional[int],
            Field(default=None, primary_key=True),
        )


def _add_embedding_field(
    db_type: DatabaseType,
    table_config: TableConfig,
    field_definitions: dict[str, tuple[Any, Any]],
) -> None:
    """Add vector embedding field if configured for pgvector database."""
    if db_type == DatabaseType.PGVECTOR and table_config.embed_model is not None:
        from pgvector.sqlalchemy import Vector

        field_definitions["embedding"] = (
            Any,
            Field(
                sa_type=Vector(dim=table_config.embed_model.dimension),  # pyright: ignore[reportArgumentType]
                exclude=True,  # Exclude from serialization
            ),
        )


def _create_sqlmodel_class(
    name: str,
    field_definitions: dict[str, tuple[Any, Any]],
    base_classes: List[type],
    table_config: TableConfig,
) -> SQLModel:
    """Create a SQLModel class with the given field definitions."""
    cls_kwargs: dict[str, Any] = {
        "table": True,
        "__table_config__": table_config,
    }

    model = create_model(  # pyright: ignore[reportCallIssue]
        name,
        __base__=tuple([SQLBase, *base_classes]),  # type: ignore
        __cls_kwargs__=cls_kwargs,
        __config__=ConfigDict(arbitrary_types_allowed=True),
        **field_definitions,  # pyright: ignore[reportArgumentType]
    )

    # Add unique constraint across all non-id fields to prevent duplicates
    non_id_fields = [field for field in field_definitions.keys() if field != "id"]
    if non_id_fields:
        model.__table_args__ = UniqueConstraint(
            *non_id_fields,
            name=f"unique_{name}_constraints",
        )

    return model


def _get_attribute_type(attr_type: str, enums: set[str]) -> Any | None:
    """Get the Python type for an attribute, or None if it's a complex type."""
    if attr_type in TYPE_MAPPING:
        return TYPE_MAPPING[attr_type]
    if attr_type in enums:
        return str
    return None


def _build_field_parameters(
    attr,
    is_primary_key: bool,
    db_type: DatabaseType,
    table_config: TableConfig,
    fk: tuple[str, str] | None,
) -> dict[str, Any]:
    """Build field parameters for a simple attribute."""
    should_index = (
        is_primary_key
        or attr.name in table_config.deduplicate_on + table_config.indexed_columns
    )

    field_params: dict[str, Any] = {
        "default": None if not attr.required else ...,
        "nullable": not attr.required and not attr.is_array,
    }

    if should_index:
        field_params["index"] = True

    if is_primary_key:
        field_params["primary_key"] = True

    if not attr.required and not attr.is_array:
        field_params["nullable"] = True

    if db_type == DatabaseType.POSTGRESQL and attr.is_array:
        field_params["sa_column"] = Column(JSON)

        if "nullable" in field_params:
            del field_params["nullable"]

    if fk:
        table_name, column = fk
        field_params["foreign_key"] = f"{table_name.lower()}.{column}"

    if attr.docstring:
        field_params["description"] = attr.docstring

    return field_params


def _add_foreign_key_relationship(
    attr_name: str,
    fk: tuple[str, str],
    field_definitions: dict[str, tuple[Any, Any]],
) -> None:
    """Add a relationship field for foreign key access."""
    table_name, _ = fk
    field_definitions[f"{attr_name}__ref"] = (
        table_name,
        Relationship(
            sa_relationship_kwargs={
                "cascade": "all",
                "lazy": "selectin",
            }
        ),
    )


def _rebuild_models(models: dict) -> None:
    """Rebuild all models to ensure proper relationships and validation."""
    for name, model in models.items():
        if not name.startswith("_"):  # Skip internal/private models
            model.model_rebuild()


def _wrap_optional(dtype):
    """
    Wrap a data type in Optional to allow None values.

    This is used for attributes that are not required, allowing them to be
    NULL in the database and None in Python.

    Args:
        dtype: The data type to wrap.

    Returns:
        Optional[dtype]: The wrapped data type that allows None values.
    """
    return Optional[dtype]


def _link_table_name(
    source_type: str,
    source_field: str,
    target_type,
) -> str:
    """
    Generate a standardized name for a linking table.

    Linking tables are used for many-to-many relationships between objects.
    This function creates a consistent naming convention for these tables.

    Args:
        source_type (str): The name of the source object type.
        source_field (str): The name of the field in the source object.
        target_type: The name of the target object type.

    Returns:
        str: A standardized linking table name in the format:
             "{source_type}__{source_field}__{target_type}__Link"

    Example:
        >>> _link_table_name("Experiment", "proteins", "Protein")
        "Experiment__proteins__Protein__Link"
    """
    return f"{source_type}__{source_field}__{target_type}__Link"


def _extract_linking_tables(
    model: DataModel,
    table_config: Dict[str, TableConfig],
) -> tuple[dict[str, SQLModel], dict[str, bool]]:
    """
    Extract and create all linking tables needed for relationships in the data model.

    Linking tables are intermediate tables that handle many-to-many relationships
    between objects. This function identifies all such relationships and creates
    the necessary linking table SQLModel classes. Only relationships where either
    side is an array require linking tables.

    Args:
        model (DataModel): The data model to analyze for relationships.
        table_config (Dict[str, TableConfig]): Dictionary mapping object names
            to their table configurations.

    Returns:
        tuple[dict[str, SQLModel], dict[str, bool]]: Tuple containing:
            - Dictionary mapping linking table names to their SQLModel classes
            - Dictionary mapping join_name to bool indicating if linking table is used
    """
    dtypes = _all_types(model.objects)
    links = []
    uses_linking_table = {}

    for obj in model.objects:
        obj_links, obj_uses_linking = _extract_links(dtypes, obj, table_config)
        links.extend(obj_links)
        uses_linking_table.update(obj_uses_linking)

    tables = {}
    for link in set(links):
        sql_model = link.get_sql_model()
        tables[sql_model.__name__] = sql_model

    return tables, uses_linking_table


def _check_needs_linking_table(
    source_obj,
    source_attr,
    target_obj,
    dtypes: Dict[str, Any],
) -> bool:
    """
    Check if a relationship requires a linking table.

    A linking table is needed when:
    - The source attribute is an array, OR
    - The target object has a reverse array relationship back to the source.

    Args:
        source_obj: The source object containing the attribute.
        source_attr: The attribute defining the relationship.
        target_obj: The target object being referenced.
        dtypes (Dict[str, Any]): Dictionary mapping type names to type objects.

    Returns:
        bool: True if a linking table is needed, False otherwise.
    """
    # Check source side - if source attribute is array, need linking table
    if source_attr.is_array:
        return True

    # Check target side for reverse array relationship
    for target_attr in target_obj.attributes:
        if target_attr.is_array:
            complex_types = _filter_complex_types(target_attr.dtypes, dtypes)
            # _filter_complex_types returns objects despite type annotation saying list[str]
            if any(
                getattr(dtype, "name", None) == source_obj.name
                for dtype in complex_types
            ):  # type: ignore
                return True

    return False


def _extract_links(
    dtypes: Dict[str, Any],
    obj,
    table_configs: Dict[str, TableConfig],
) -> tuple[list[LinkedType], dict[str, bool]]:
    """
    Extract all relationship links from a single object.

    This function examines all attributes of an object to find those that
    reference other objects in the data model, creating LinkedType objects
    to represent these relationships. It also tracks which relationships
    require linking tables.

    Args:
        dtypes (Dict[str, Any]): Dictionary mapping type names to type objects.
        obj: The object to examine for relationships.
        table_configs (Dict[str, TableConfig]): Dictionary of table configurations.

    Returns:
        tuple[list[LinkedType], dict[str, bool]]: Tuple containing:
            - List of LinkedType objects representing relationships that need linking tables
            - Dictionary mapping join_name to bool indicating if linking table is used
    """
    to_link = []
    uses_linking_table = {}
    source_config = table_configs.get(obj.name, TableConfig())
    source_pk, source_pk_type = _get_primary_key(obj, source_config)

    # Examine each attribute for complex type references
    for attr in obj.attributes:
        complex_types = _filter_complex_types(attr.dtypes, dtypes)
        for dtype in complex_types:
            target_config = table_configs.get(dtype.name, TableConfig())  # type: ignore
            target_pk, target_pk_type = _get_primary_key(dtype, target_config)

            join_name = _link_table_name(obj.name, attr.name, dtype.name)  # type: ignore
            needs_linking = _check_needs_linking_table(obj, attr, dtype, dtypes)
            uses_linking_table[join_name] = needs_linking

            if needs_linking:
                to_link.append(
                    LinkedType(
                        source_type=obj.name,
                        source_field=attr.name,
                        target_type=dtype.name,  # type: ignore
                        source_pk=(source_pk, source_pk_type),
                        target_pk=(target_pk, target_pk_type),
                    )
                )

    return to_link, uses_linking_table


def _get_primary_key(obj, table_config: TableConfig) -> tuple[str, Any]:
    if table_config.primary_key:
        source_pk = table_config.primary_key
        source_pk_type = _get_primary_key_type(obj, table_config.primary_key)
    else:
        source_pk = "id"
        source_pk_type = int
    return source_pk, source_pk_type


def _get_primary_key_type(obj: DataModel, primary_key: str) -> Any:
    """
    Get the type of the primary key for an object.
    """
    attr = next((a for a in obj.attributes if a.name == primary_key), None)
    if attr is None:
        raise ValueError(
            f"Primary key attribute '{primary_key}' not found in object '{obj.name}'."
        )

    try:
        return TYPE_MAPPING[attr.dtypes[0]]
    except KeyError:
        raise ValueError(
            f"Type '{attr.dtypes[0]}' of primary key attribute '{primary_key}' not found in TYPE_MAPPING = {TYPE_MAPPING}."
        )


def _filter_complex_types(dtypes: list[str], all_types: Dict[str, Any]) -> list[str]:
    """
    Filter a list of data types to find only complex types (object references).

    Complex types are those that reference other objects in the data model,
    as opposed to primitive types like string, int, etc.

    Args:
        dtypes (list[str]): List of data type names to filter.
        all_types (list[str]): List of all object type names in the data model.

    Returns:
        list[str]: List containing only the complex types (those that appear
                  in the all_types list).
    """
    return [obj for obj in all_types.values() if obj.name in dtypes]


def _all_types(objects) -> Dict[str, Any]:
    """
    Extract all object type names from a list of objects.

    This is a utility function to get the names of all objects in the data model,
    which is used to identify complex types and relationships.

    Args:
        objects: List of object definitions from the data model.

    Returns:
        list[str]: List of all object type names.
    """
    return {obj.name: obj for obj in objects}
