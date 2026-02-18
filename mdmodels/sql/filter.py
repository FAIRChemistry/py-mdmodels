from enum import Enum
from typing import Generic, List, Literal, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import and_, intersect, select, union

from ..library import Library
from ..relations import apply_join_chain

# Create a TypeVar bound to Enum for generic FilterSpec
TEnum = TypeVar("TEnum", bound=Enum)


class TableConnection(BaseModel):
    """
    Represents a relationship between two tables via their respective columns.

    Attributes:
        source_table (str): Name of the source table in the relationship.
        source_column (str): Name of the linking column in the source table.
        target_table (str): Name of the target/related table.
        target_column (str): Name of the linking column in the target table.
    """

    source_table: str
    source_column: str
    target_table: str
    target_column: str


class Operation(Enum):
    """
    Enumerates possible comparison/filter operations for a database column.
    """

    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER = "greater"
    GREATER_EQUAL = "greater_equal"
    LOWER = "lower"
    LOWER_EQUAL = "lower_equal"
    IN = "in"
    NOT_IN = "not_in"


# Mapping from Operation enum to corresponding SQLAlchemy expressions.
_OPERATION_FUNCTIONS = {
    Operation.EQUAL: lambda col, value: col == value,
    Operation.NOT_EQUAL: lambda col, value: col != value,
    Operation.GREATER: lambda col, value: col > value,
    Operation.GREATER_EQUAL: lambda col, value: col >= value,
    Operation.LOWER: lambda col, value: col < value,
    Operation.LOWER_EQUAL: lambda col, value: col <= value,
    Operation.IN: lambda col, value: col.in_(value),
    Operation.NOT_IN: lambda col, value: ~col.in_(value),
}


class FilterSpec(BaseModel):
    """
    Specification for a single column filter.
    """

    column: str
    operation: Operation
    value: Union[str, int, float, bool, list[Union[str, int, float, bool]]]

    def to_expression(self, table_name: str, db_models: Library):
        """
        Generate a SQLAlchemy expression for this filter.
        """
        table_class = db_models[table_name]
        col = getattr(table_class, self.column)
        operation_func = _OPERATION_FUNCTIONS[self.operation]
        return operation_func(col, self.value)


class FilterTask(BaseModel, Generic[TEnum]):
    """
    Represents a collection of FilterSpec filters to be applied (with AND/OR logic)
    to a table, optionally across relations via subqueries/joins.
    """

    table: TEnum
    filters: List[FilterSpec]
    condition: Literal["and", "or"]

    def to_expression(self, db_models: Library):
        """
        Convert this filter task into a single SQL WHERE expression.
        """
        table_name = self.table.name
        if self.condition == "and":
            return and_(
                *[
                    filter.to_expression(table_name, db_models)
                    for filter in self.filters
                ]
            )
        elif self.condition == "or":
            return or_(
                *[
                    filter.to_expression(table_name, db_models)
                    for filter in self.filters
                ]
            )
        else:
            raise ValueError(f"Invalid condition: {self.condition}")

    @staticmethod
    def is_primary_key(table_class: type, attr_name: str) -> bool:
        """
        Check if an attribute is a primary key in a SQLModel table.
        """
        if not hasattr(table_class, "__table__"):
            return False

        primary_key_columns = table_class.__table__.primary_key.columns.keys()  # type: ignore[attr-defined]
        return attr_name in primary_key_columns

    def build_subquery(
        self,
        table_name: str,
        table_class: type,
        db_models: Library,
    ):
        """
        Build a subquery for this filter task.

        If the filter is on the main table, builds a simple SELECT WHERE filter_expression.
        If filtering on a related table, builds joins following the computed join chain.
        """
        task_table_name = self.table.name

        if task_table_name not in db_models:
            raise ValueError(f"Table {task_table_name} not found in database")

        # Use FilterTask.to_expression() which handles and/or logic
        filter_expression = self.to_expression(db_models)

        if task_table_name == table_name:
            # Direct table filter (no join required).
            return select(table_class).where(filter_expression)

        # Traverse relationships using the join chain between the main and filter tables.
        join_chain = db_models.find_join_chain(
            source=table_name,
            target=task_table_name,
        )

        if not join_chain:
            raise ValueError(f"No join path between {table_name} and {task_table_name}")

        stmt = select(table_class)
        stmt = apply_join_chain(
            stmt,
            start_cls=table_class,
            join_chain=join_chain,
            db_models=db_models,
        )

        return stmt.where(filter_expression)

    @staticmethod
    def build_filtered_query(
        table_name: str,
        table_class: type,
        filters: List["FilterTask"],
        db_models: Library,
        logic: Literal["union", "intersect"] = "union",
    ):
        """
        Combines multiple filter tasks (possibly on different tables) using UNION.
        """
        subqueries = [
            task.build_subquery(table_name, table_class, db_models) for task in filters
        ]

        if logic == "intersect":
            return intersect(*subqueries)
        elif logic == "union":
            return union(*subqueries)
        else:
            raise ValueError(f"Invalid logic: {logic}")
