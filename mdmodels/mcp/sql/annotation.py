from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional

from sqlmodel import Field, SQLModel

from mdmodels.sql.config import TableConfig


class Annotation(SQLModel, table=True):
    """
    Annotation store.
    Stores annotations for a given model and row.
    """

    __tablename__: ClassVar[str] = "_annotation"

    # Align with SQLBase so ORM/session hooks that probe `_table_config` never break.
    _table_config: ClassVar[Optional[TableConfig]] = None

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    table_name: str = Field(index=True)
    row_pk: int = Field(index=True)
    tags: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        unique_together = [("table_name", "row_pk")]


def create_annotation_tables(engine) -> None:
    """
    Create _annotation tables if they don't exist.
    Safe to call at startup alongside SQLModel.metadata.create_all() —
    uses checkfirst=True so it never overwrites existing tables.
    """
    SQLModel.metadata.create_all(engine, checkfirst=True)
