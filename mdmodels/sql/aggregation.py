from typing import Any, List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy import Row, func
from sqlalchemy import select as sa_select

from ..library import Library


class AggregationResult(BaseModel):
    """
    Represents a single aggregation result.

    Attributes:
        column (str): The name of the column that was aggregated.
        value (float): The numeric result of the aggregation.
    """

    column: str
    value: float


class Aggregation(BaseModel):
    """
    Represents an aggregation operation that can be performed on a table column.

    Attributes:
        function: The aggregation function to apply (e.g., "count", "sum", "avg", etc.).
        column: The name of the column to aggregate.

    Supported Functions:
        - "count":       Count the number of values.
        - "sum":         Sum of the values in the column.
        - "avg":         Average of the values in the column.
        - "min":         Minimum value in the column.
        - "max":         Maximum value in the column.
        - "stddev":      Standard deviation of the values.
        - "variance":    Variance of the values.
    """

    function: Literal[
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "stddev",
        "variance",
    ]
    column: str

    @staticmethod
    def _get_function(function_name: str):
        """
        Get the SQLAlchemy function for an aggregation function name.

        Args:
            function_name: Name of the aggregation function

        Returns:
            SQLAlchemy function

        Raises:
            ValueError: If the function name is not supported
        """
        func_map = {
            "count": func.count,
            "sum": func.sum,
            "avg": func.avg,
            "min": func.min,
            "max": func.max,
            "stddev": func.stddev,
            "variance": func.variance,
        }
        aggregation_func = func_map.get(function_name)
        if aggregation_func is None:
            raise ValueError(f"Unsupported aggregation function: {function_name}")
        return aggregation_func

    def to_expression(self, table_name: str, db_models: Library):
        """
        Generate a SQLAlchemy aggregation expression for the given column.

        Args:
            table_name (str): Name of the target table.
            db_models (Library): Contains all table models.

        Returns:
            SQLAlchemy aggregation expression (e.g. func.sum(Column)).
        """
        table_class = db_models[table_name]
        col = getattr(table_class, self.column)
        aggregation_func = self._get_function(self.function)
        return aggregation_func(col)

    def to_filtered_expression(self, subquery):
        """
        Generate a SQLAlchemy expression for this aggregation on a filtered subquery.

        Args:
            subquery: SQLAlchemy subquery from a union statement

        Returns:
            SQLAlchemy aggregation expression on the subquery column.
        """
        col = getattr(subquery.c, self.column)
        aggregation_func = self._get_function(self.function)
        return aggregation_func(col)

    @staticmethod
    def build_query(
        table_name: str,
        table_class: type,
        aggregations: List["Aggregation"],
        db_models: Library,
    ):
        """
        Build a SQL SELECT query with aggregation expressions on a regular table.

        Args:
            table_name (str): Name of the main table
            table_class (type): SQLModel class for the main table
            aggregations (List[Aggregation]): List of Aggregation objects
            db_models (Library): Library of all database models

        Returns:
            SQL SELECT query with aggregation expressions (unfiltered).
        """
        from mdmodels import sql

        aggregation_expressions = [
            agg.to_expression(table_name, db_models) for agg in aggregations
        ]

        return sql.select(*aggregation_expressions).select_from(table_class)

    @staticmethod
    def build_filtered_query(
        aggregations: List["Aggregation"],
        union_stmt,
    ):
        """
        Build an aggregation query from a union statement (filtered results).

        Args:
            aggregations (List[Aggregation]): List of Aggregation objects
            union_stmt: Union statement from filtered queries

        Returns:
            SQLAlchemy select query with aggregation expressions applied over the subquery.
        """
        subquery = union_stmt.subquery()
        aggregation_expressions = [
            agg.to_filtered_expression(subquery) for agg in aggregations
        ]
        return sa_select(*aggregation_expressions)

    @staticmethod
    def build_query_with_filters(
        table_name: str,
        table_class: type,
        aggregations: List["Aggregation"],
        db_models: Library,
        union_stmt=None,
    ):
        """
        Build an aggregation query, optionally with filters (via a union subquery).

        Args:
            table_name (str): Name of the main table
            table_class (type): SQLModel class for the main table
            aggregations (List[Aggregation]): List of Aggregation objects
            db_models (Library): Library of models
            union_stmt (optional): Union statement from filtered queries

        Returns:
            SQLAlchemy select query with aggregation expressions, with or without filters
        """
        if union_stmt is not None:
            return Aggregation.build_filtered_query(aggregations, union_stmt)
        else:
            return Aggregation.build_query(
                table_name, table_class, aggregations, db_models
            )

    @staticmethod
    def format_results(
        result: Optional[Any],
        aggregations: List["Aggregation"],
    ) -> List["AggregationResult"]:
        """
        Format aggregation query results into a list of AggregationResult objects.

        Args:
            result (Any | None): Result from query execution
                (can be SQLAlchemy Row, tuple, or None)
            aggregations (List[Aggregation]): Aggregations used in the query

        Returns:
            List of AggregationResult objects with column and value fields.
            If no result, returns an empty list.
        """
        if result is None:
            raise ValueError("Result is None")

        # Convert result to list format for consistent handling
        if isinstance(result, tuple):
            result = list(result)
        elif isinstance(result, Row):
            result = list(result)
        elif not isinstance(result, list):
            result = [result]

        results = []
        for i, agg in enumerate(aggregations):
            # Access result by index (works for both Row and tuple)
            try:
                value = result[i]
            except (IndexError, TypeError):
                raise ValueError(
                    f"IndexError or TypeError for aggregation {agg.function} on column {agg.column}: "
                    f" {result}"
                )

            # Handle None values
            # For count: None means 0 rows (valid)
            # For other aggregations: None typically means no matching rows or all NULL values
            # This could indicate a problem with filters or the query itself
            if value is None:
                raise ValueError(
                    f"Value is None for aggregation {agg.function} on column {agg.column}"
                )

            try:
                results.append(AggregationResult(column=agg.column, value=float(value)))
            except (ValueError, TypeError):
                raise ValueError(
                    f"Failed to convert value {value} to float for aggregation {agg.function} on column {agg.column}"
                )

        return results
