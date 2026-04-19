from __future__ import annotations

import inspect
from typing import List

from fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import select
from toon_format import encode

from mdmodels.mcp.sql.annotation import Annotation

from ..middleware import CTX_SESSION

ANNOTATE_DESCRIPTION = (
    "Add one or more free-text annotations to any row in any table. "
    "Use this to record observations, deviations, decisions, or any prose "
    "context that does not fit a structured field — e.g. 'the curve looked "
    "anomalous at t=30 min' or 'pH drifted, suspect buffer issue'. "
    "Each annotation is permanently linked to a specific row via table + row_pk. "
    "Multiple annotations can be submitted in a single call; prefer batching "
    "when narrating observations about several rows at once. "
    "author is optional — supply it when the identity cannot be inferred from "
    "the session token (e.g. when annotating on behalf of a colleague)."
)

GET_ANNOTATIONS_DESCRIPTION = (
    "Retrieve all annotations for one or more rows from a single table in one call. "
    "Pass the table name and a list of row PKs — all rows must belong to the same table. "
    "Returns all matching annotations in chronological order, each tagged with its row_pk "
    "for grouping. After fetching an experiment tree, call this once per table that has "
    "annotated rows to surface the full annotation picture."
)


class AnnotationInput(BaseModel):
    """A single annotation to attach to a database row."""

    row_pk: int = Field(
        description=(
            "Primary key of the row being annotated, serialised as a string. "
            "For integer PKs pass the number as a string, e.g. '42'."
        ),
    )
    text: str = Field(
        description="Free-text observation, note, or commentary.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description=(
            "Optional list of short labels for filtering, "
            "e.g. ['outlier', 'pH-drift']. Keep tags lowercase and hyphen-separated."
        ),
    )


def register_annotate_tool(
    *,
    app: FastMCP,
    available_tables,
) -> None:
    """Register Annotate_Entries and Get_Annotations MCP tools.

    The _annotation table is a hand-crafted SQLModel that lives in the MCP
    layer — it is NOT generated from model.md. It must be created at startup
    via create_annotation_table(engine) before these tools are called.

    Both tools operate directly on the Annotation SQLModel; they do not go
    through db_models and are not subject to ownership scoping.

    Args:
        app: FastMCP application instance.
        available_tables: Annotated Literal type enumerating valid domain
            table names. Injected into both tool signatures via __annotations__
            so the LLM receives a constrained enum in the tool schema.
    """

    def annotate_entries(table: str, annotations: List[AnnotationInput]) -> str:
        """Write one or more annotations to the _annotation table.

        Each annotation is permanently linked to a specific row via its
        table name and primary key. All annotations in the list are written
        in a single transaction — either all succeed or all are rolled back.

        Args:
            annotations: List of annotations to persist. Prefer batching
                all observations from one narration pass into a single call.

        Returns:
            str: Encoded JSON list of the persisted annotation records.

        Raises:
            RuntimeError: If no active DB session is found in context.
        """
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        inserted = []

        for ann in annotations:
            row = Annotation(
                table_name=table,
                row_pk=ann.row_pk,
                text=ann.text,
                tags=",".join(ann.tags) if ann.tags else None,
            )
            session.add(row)
            session.flush()
            inserted.append(row)

        session.commit()

        return encode(
            [
                {
                    "id": row.id,
                    "table_name": row.table_name,
                    "row_pk": row.row_pk,
                    "text": row.text,
                    "tags": row.tags.split(",") if row.tags else None,
                    "created_at": row.created_at.isoformat(),
                }
                for row in inserted
            ]
        )

    annotate_entries.__annotations__ = {
        "table": available_tables,
        "annotations": List[AnnotationInput],
        "return": str,
    }  # type: ignore[assignment]
    annotate_entries.__signature__ = inspect.signature(annotate_entries)  # type: ignore[attr-defined]

    def get_annotations(table: str, row_pks: List[int]) -> str:  # pyright: ignore[reportInvalidTypeForm]
        """Retrieve all annotations for a list of rows from a single table.

        Pass the table name and all row PKs you want to inspect in one call.
        After fetching an experiment tree, collect the PKs for the rows of
        interest within each table and resolve their annotations in a single
        round trip per table.

        Args:
            table: Name of the domain table the rows belong to.
            row_pks: List of primary keys to retrieve annotations for.

        Returns:
            str: Encoded JSON list of annotation records, oldest first,
                each carrying row_pk so the caller can group by row.

        Raises:
            RuntimeError: If no active DB session is found in context.
        """
        session = CTX_SESSION.get()
        if session is None:
            raise RuntimeError("No active DB session in context")

        results = session.exec(
            select(Annotation)
            .where(
                Annotation.table_name == table,
                Annotation.row_pk.in_(row_pks),  # pyright: ignore[reportAttributeAccessIssue]
            )
            .order_by(text("created_at"))
        ).all()

        return encode(
            [
                {
                    "id": row.id,
                    "table_name": row.table_name,
                    "row_pk": row.row_pk,
                    "text": row.text,
                }
                for row in results
            ]
        )

    get_annotations.__annotations__ = {
        "table": available_tables,
        "row_pks": List[int],
        "return": str,
    }  # type: ignore[assignment]
    get_annotations.__signature__ = inspect.signature(get_annotations)  # type: ignore[attr-defined]

    app.tool(
        annotate_entries,
        name="Annotate_Entries",
        description=ANNOTATE_DESCRIPTION,
    )

    app.tool(
        get_annotations,
        name="Get_Annotations",
        description=GET_ANNOTATIONS_DESCRIPTION,
    )
