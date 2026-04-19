from __future__ import annotations

from typing import TypedDict


class TableConnection(TypedDict):
    """Represents a foreign key relationship between two database tables.

    This TypedDict defines the structure for describing how tables are connected
    through foreign key relationships in the database schema. It captures both
    the source (referencing) and target (referenced) sides of the relationship.

    Attributes:
        source_table: Name of the table that contains the foreign key column
        source_column: Name of the foreign key column in the source table
        target_table: Name of the table being referenced by the foreign key
        target_column: Name of the primary key column in the target table
    """

    source_table: str
    source_column: str
    target_table: str
    target_column: str
