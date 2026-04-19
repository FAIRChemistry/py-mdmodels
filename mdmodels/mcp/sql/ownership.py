from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, ClassVar, Optional

from sqlmodel import Field, Session, SQLModel, select

from mdmodels.sql.config import TableConfig


class Identity(SQLModel, table=True):
    """
    Auth-provider-agnostic identity store.
    Accepts raw provider + subject on creation, stores only a SHA-256 hash.
    Never persists the raw subject claim.
    """

    __tablename__: ClassVar[str] = "_identity"

    # Align with SQLBase so ORM/session hooks that probe `_table_config` never break.
    _table_config: ClassVar[Optional[TableConfig]] = None

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    subject_hash: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        unique_together = [("provider", "subject_hash")]


class Ownership(SQLModel, table=True):
    """
    Maps any domain table row to the identity that inserted it.
    Uses generic (table_name, row_id) to remain fully decoupled from
    the domain schema. Orphaned rows on deletion are intentionally ignored.
    """

    __tablename__: ClassVar[str] = "_ownership"

    _table_config: ClassVar[Optional[TableConfig]] = None

    table_name: str = Field(primary_key=True)
    row_id: int = Field(primary_key=True)
    identity_id: int = Field(foreign_key="_identity.id")
    created_at: datetime = Field(default_factory=datetime.now)


def create_ownership_tables(engine) -> None:
    """
    Create _identity and _ownership tables if they don't exist.
    Safe to call at startup alongside SQLModel.metadata.create_all() —
    uses checkfirst=True so it never overwrites existing tables.

    Args:
        engine: SQLAlchemy engine connected to your database.
    """
    SQLModel.metadata.create_all(engine, checkfirst=True)


def resolve_identity(
    session: Session,
    provider: str,
    subject: str,
) -> Identity:
    """
    Resolve or create an Identity from OIDC claims.
    Only iss and sub are used — both guaranteed by the OIDC spec.
    Pass raw subject — the validator hashes it automatically.

    Args:
        session:  Active SQLModel session.
        provider: JWT iss claim (e.g. "https://keycloak.example.com/realms/piv").
        subject:  JWT sub claim (stable unique user ID). Never stored raw.

    Returns:
        Identity: The resolved or newly created Identity record.
    """
    subject_hash = _hash_subject(provider, subject)

    identity = session.exec(
        select(Identity).where(
            Identity.provider == provider,
            Identity.subject_hash == subject_hash,
        )
    ).first()

    if not identity:
        identity = Identity(provider=provider, subject_hash=subject_hash)
        session.add(identity)
        session.flush()

    return identity


def track_ownership(
    session: Session,
    model_name: str,
    inserted_objects: list[Any],
    provider: str,
    subject: str,
    shared_tables: set[str],
) -> None:
    """
    Record ownership for every inserted row in a non-shared table.
    No-op for shared tables. Safe on upsert — original owner never overwritten.
    Orphaned rows on deletion are intentionally not cleaned up.

    Args:
        session:          Active SQLModel session.
        model_name:       MCP model name, e.g. "PivExperiment".
        inserted_objects: SQLModel objects returned by insert_nested.
        provider:         JWT iss claim.
        subject:          JWT sub claim. Used only to compute hash, never stored.
        shared_tables:    Set of table names exempt from ownership tracking.
    """
    if _is_shared(model_name, shared_tables):
        return

    identity = resolve_identity(session, provider, subject)

    assert identity.id is not None, "Identity ID is required"

    for obj in inserted_objects:
        if type(obj).__name__ != model_name:
            continue
        if not _is_owned(session, model_name, obj.id):
            session.add(
                Ownership(
                    table_name=model_name,
                    row_id=obj.id,
                    identity_id=identity.id,
                )
            )


def get_owned_ids(
    session: Session,
    table_name: str,
    provider: str,
    subject: str,
) -> list[int]:
    """
    Return all row IDs in a given table owned by this identity.
    Returns empty list if the identity does not exist yet.

    Args:
        session:    Active SQLModel session.
        table_name: Domain table name, e.g. "PivExperiment".
        provider:   JWT iss claim.
        subject:    JWT sub claim.

    Returns:
        list[int]: List of row IDs owned by the identity in the specified table.
    """
    identity = _resolve_identity_readonly(session, provider, subject)

    if not identity:
        return []

    return list(
        session.exec(
            select(Ownership.row_id).where(
                Ownership.table_name == table_name,
                Ownership.identity_id == identity.id,
            )
        ).all()
    )


def is_scoped(table_name: str, shared_tables: set[str]) -> bool:
    """
    Return True if this table is subject to ownership scoping on reads.
    Convenience function for use in select/aggregate tool registration.

    Args:
        table_name:    Domain table name to check.
        shared_tables: Set of table names exempt from ownership scoping.

    Returns:
        bool: True if the table requires ownership scoping, False if it's shared.
    """
    return not _is_shared(table_name, shared_tables)


def _hash_subject(provider: str, subject: str) -> str:
    """
    SHA-256 hash of provider + subject. No secret required for now.

    Args:
        provider: JWT iss claim identifying the token provider.
        subject: JWT sub claim identifying the user/entity.

    Returns:
        str: SHA-256 hexdigest of the provider:subject combination.
    """
    return hashlib.sha256(f"{provider}:{subject}".encode()).hexdigest()


def _is_shared(table_name: str, shared_tables: set[str]) -> bool:
    """
    Return True if the table is a shared lab resource.

    Args:
        table_name: Domain table name to check.
        shared_tables: Set of table names exempt from ownership tracking.

    Returns:
        bool: True if the table is shared, False if it requires ownership tracking.
    """
    return table_name in shared_tables


def _is_owned(session: Session, table_name: str, row_id: int) -> bool:
    """
    Return True if an ownership record already exists for this row.

    Args:
        session: Active SQLModel session.
        table_name: Domain table name.
        row_id: Primary key of the row to check.

    Returns:
        bool: True if an ownership record exists, False otherwise.
    """
    return (
        session.exec(
            select(Ownership).where(
                Ownership.table_name == table_name,
                Ownership.row_id == row_id,
            )
        ).first()
        is not None
    )


def _resolve_identity_readonly(
    session: Session,
    provider: str,
    subject: str,
) -> Identity | None:
    """
    Look up an existing Identity without creating one.
    Used for read-path scoping where identity creation is not appropriate.

    Args:
        session: Active SQLModel session.
        provider: JWT iss claim identifying the token provider.
        subject: JWT sub claim identifying the user/entity.

    Returns:
        Identity | None: The existing Identity record, or None if not found.
    """
    subject_hash = _hash_subject(provider, subject)
    return session.exec(
        select(Identity).where(
            Identity.provider == provider,
            Identity.subject_hash == subject_hash,
        )
    ).first()
