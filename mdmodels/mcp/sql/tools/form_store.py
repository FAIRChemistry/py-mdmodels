from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import MetaData, delete
from sqlmodel import Column, Field, Session, SQLModel, Text, create_engine, select

_STORE_FILENAME = "mdmodels_open_forms.sqlite"
_STORE_TABLE_NAME = "open_forms"
_MAX_FORM_AGE = timedelta(hours=1)

FORM_STORE_METADATA = MetaData()


class OpenForm(SQLModel, table=True):
    """Dedicated form lifecycle table stored in temp SQLite."""

    metadata = FORM_STORE_METADATA
    __tablename__: ClassVar[str] = _STORE_TABLE_NAME

    form_id: str = Field(primary_key=True)
    opened_at: datetime = Field(default_factory=datetime.now, nullable=False)
    completed: bool = Field(default=False, nullable=False, index=True)
    submitted_payload: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


_DB_PATH = Path(tempfile.gettempdir()) / _STORE_FILENAME
_ENGINE = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)


def init_form_store() -> None:
    """Create the isolated open_forms table if missing."""
    FORM_STORE_METADATA.create_all(_ENGINE, checkfirst=True)


def prune_stale_forms(now: datetime | None = None) -> int:
    """Drop forms older than one hour."""
    reference = now or datetime.utcnow()
    cutoff = reference - _MAX_FORM_AGE
    with Session(_ENGINE) as session:
        stale_ids = session.exec(
            select(OpenForm.form_id).where(OpenForm.opened_at < cutoff)
        ).all()
        if stale_ids:
            session.execute(
                delete(OpenForm).where(OpenForm.opened_at < cutoff)  # pyright: ignore[reportArgumentType]
            )
        session.commit()
        return len(stale_ids)


def get_form(form_id: str) -> dict[str, Any] | None:
    with Session(_ENGINE) as session:
        row = session.exec(select(OpenForm).where(OpenForm.form_id == form_id)).first()
        if row is None:
            return None
        payload: dict[str, Any] | None = None
        if row.submitted_payload:
            try:
                payload = json.loads(row.submitted_payload)
            except json.JSONDecodeError:
                payload = None
        return {
            "form_id": row.form_id,
            "opened_at": row.opened_at,
            "completed": row.completed,
            "submitted_payload": payload,
        }


def track_open_form(form_id: str, opened_at: datetime | None = None) -> None:
    with Session(_ENGINE) as session:
        row = session.exec(select(OpenForm).where(OpenForm.form_id == form_id)).first()
        if row is None:
            session.add(
                OpenForm(form_id=form_id, opened_at=opened_at or datetime.utcnow())
            )
            session.commit()


def mark_form_completed(form_id: str, values: dict[str, Any]) -> None:
    with Session(_ENGINE) as session:
        row = session.exec(select(OpenForm).where(OpenForm.form_id == form_id)).first()
        if row is None:
            row = OpenForm(form_id=form_id, opened_at=datetime.utcnow())
            session.add(row)
        row.completed = True
        row.submitted_payload = json.dumps(values, ensure_ascii=False)
        session.commit()
