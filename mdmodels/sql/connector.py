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

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union, cast, overload

import dotenv
from sqlalchemy import Engine, event
from sqlalchemy.engine.url import URL
from sqlmodel import Session, SQLModel, create_engine, text

from mdmodels.config import AppConfig
from mdmodels.sql.base import SQLBase, SQLModelMeta
from mdmodels.sql.config import TableConfig
from mdmodels.sql.insert import insert_nested

if TYPE_CHECKING:
    from mdmodels.datamodel import DataModel
    from mdmodels.library import Library

DatabaseTypeLiteral = Literal[
    "postgresql",
    "postgres",
    "pgvector",
    "mysql",
    "sqlite",
    "mssql",
    "oracle",
]


class DatabaseType(Enum):
    """
    Enum representing different units of databases.

    Attributes:
        POSTGRESQL (tuple): PostgreSQL database with psycopg2 driver.
        MYSQL (tuple): MySQL database with pymysql driver.
        SQLITE (tuple): SQLite database with no driver.
        SQLSERVER (tuple): SQL Server database with pyodbc driver.
        ORACLE (tuple): Oracle database with cx_oracle driver.
    """

    POSTGRESQL = ("postgresql", "psycopg2")
    PGVECTOR = ("postgresql", "psycopg2")
    MYSQL = ("mysql", "pymysql")
    SQLITE = ("sqlite", "")
    SQLSERVER = ("mssql", "pyodbc")

    def __init__(self, db_name: str, default_driver: str):
        """
        Initialize the DatabaseType enum.

        Args:
            db_name (str): The name of the database.
            default_driver (str): The default driver for the database.
        """
        self.db_name = db_name
        self.default_driver = default_driver

    @classmethod
    def from_str(
        cls,
        db_type: DatabaseTypeLiteral,
    ) -> "DatabaseType":
        """
        Convert a string to a DatabaseType enum.
        """
        match db_type:
            case "postgresql":
                return cls.POSTGRESQL
            case "postgres":
                return cls.POSTGRESQL
            case "mysql":
                return cls.MYSQL
            case "sqlite":
                return cls.SQLITE
            case "pgvector":
                return cls.PGVECTOR
            case "mssql":
                return cls.SQLSERVER
            case _:
                raise ValueError(f"Invalid database type: {db_type}")


class DatabaseConnector:
    """
    A class to manage database connections and sessions.

    Attributes:
        db_config (dict): The database configuration.
        _active_session (Optional[Session]): The active database session.
    """

    def __init__(
        self,
        library: Library[DataModel],
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
        database: Optional[str] = None,
        query: Optional[dict] = None,
        db_type: Union[
            DatabaseTypeLiteral,
            DatabaseType,
        ] = DatabaseType.SQLITE,
        table_config: Optional[Dict[str, TableConfig]] = None,
    ):
        """
        Initialize the DatabaseConnector with the given parameters.

        Args:
            host (Optional[str]): The database host address.
            port (Optional[int]): The port number for the database.
            username (Optional[str]): The database username.
            password (Optional[str]): The database password.
            driver (Optional[str]): The driver for the database.
            database (Optional[str]): The name of the database.
            query (Optional[dict]): Additional query parameters for the connection string.
            db_type (DatabaseType): The type of the database.
            table_config (Optional[TableConfig]): The table configuration.
        """

        from ..library import Library

        if isinstance(db_type, str):
            db_type = DatabaseType.from_str(db_type)
        else:
            db_type = db_type

        driver_name = db_type.db_name

        if driver:
            driver_name += f"+{driver}"
        elif db_type.default_driver:
            driver_name += f"+{db_type.default_driver}"

        self.db_config = {
            "drivername": driver_name,
            "username": username,
            "password": password,
            "host": host,
            "port": port,
            "database": database,
            "query": query,
        }

        self._active_session = None
        self._table_config = table_config
        self._db_type = db_type
        self._db_models = cast(
            Library[SQLBase],
            library.to_sqlmodel(db_type, table_config),
        )
        self._models = library
        self._pydantic_library = library
        self._create_engine()

        if db_type == DatabaseType.PGVECTOR:
            with self as session:
                session.exec(
                    text("CREATE EXTENSION IF NOT EXISTS vector"),  # pyright: ignore[reportCallIssue, reportArgumentType]
                )

    @property
    def engine(self) -> Engine:
        """
        Return an active SQLAlchemy engine.
        Initialize it once or recreate it if disposed.
        """
        if self._engine is None:
            # Create the engine if it is not already created
            return self._create_engine()

        if getattr(self._engine, "pool", None) is None:
            # Recreate the engine if it was explicitly disposed
            return self._create_engine()

        # Return the engine if it is already created and not disposed
        return self._engine

    @property
    def db_type(self) -> DatabaseType:
        """
        Return the database type.
        """
        return self._db_type

    @property
    def db_models(self) -> Library[SQLBase]:
        """
        Return the database models.
        """
        return self._db_models

    @property
    def table_config(self) -> Optional[Dict[str, TableConfig]]:
        """
        Return the table configuration.
        """
        return self._table_config

    @classmethod
    def from_config(cls, config: AppConfig) -> "DatabaseConnector":
        """
        Create a DatabaseConnector from a config.
        """

        from mdmodels.datamodel import DataModel

        dotenv.load_dotenv()

        if config.model.repo is not None:
            library = DataModel.from_github(
                repo=config.model.repo,
                spec_path=config.model.path.as_posix(),
                branch=config.model.branch,
                tag=config.model.tag,
            )
        else:
            library = DataModel.from_markdown(config.model.path)

        table_config = {
            name: TableConfig.from_config(config, name)
            for name in config.sql.tables.keys()
        }

        db_type = DatabaseType.from_str(
            cast(DatabaseTypeLiteral, config.sql.type),
        )

        username = os.getenv("DB_USERNAME")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST", config.sql.host)
        port = int(os.getenv("DB_PORT", str(config.sql.port)))
        database = os.getenv("DB_DATABASE", config.sql.database)

        if username is None:
            raise ValueError("DB_USERNAME environment variable must be set")
        if password is None:
            raise ValueError("DB_PASSWORD environment variable must be set")
        if host is None:
            raise ValueError("DB_HOST environment variable must be set")
        if port is None:
            raise ValueError("DB_PORT environment variable must be set")
        if database is None:
            raise ValueError("DB_DATABASE environment variable must be set")

        return cls(
            library=library,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            db_type=db_type,
            table_config=table_config,
        )

    def create_tables(self):
        """
        Create all tables in the database.
        """

        from ..library import Library

        SQLModel.metadata.create_all(self._engine)

        return cast(Library[SQLBase], self._db_models)

    def insert_nested(
        self,
        data: Union[DataModel, List[DataModel]],
    ) -> None:
        """
        Insert nested DataModel instances into the database.

        This method handles the insertion of complex nested data structures into the database,
        automatically managing relationships and foreign keys. It requires an active database
        session to be available through the context manager.

        Args:
            data (Union[DataModel, List[DataModel]]): A single DataModel instance or a list
                of DataModel instances to insert into the database. The method will handle
                nested relationships and ensure proper insertion order.

        Raises:
            AssertionError: If the pydantic library is not properly initialized.
            ValueError: If no active database session is found. Use the context manager
                'with db as session:' to create an active session before calling this method.

        Example:
            ```python
            with db as session:
                db.insert_nested(my_data_model)
                session.commit()
            ```

        Note:
            This method adds the converted SQLModel instances to the active session but does
            not commit the transaction. You must call session.commit() to persist the changes.
        """

        assert self._pydantic_library is not None, "Pydantic library is not set"

        if self._active_session is None:
            raise ValueError(
                "No active session found. Please use the context manager to create a session. Use 'with db as session:'"
            )

        to_add = insert_nested(
            data=data,
            library=self._pydantic_library,
            session=self._active_session,
            models=self._db_models,
        )

        self._active_session.add_all(to_add)

    @staticmethod
    def _get_embed_col(target: SQLModel) -> Optional[str]:
        """Get the embedding column name for a model class or instance."""

        if isinstance(target, SQLModelMeta):
            cfg = getattr(target, "_table_config", None)
            return cfg.embed_column if cfg is not None else None

        cfg = getattr(type(target), "_table_config", None)
        if cfg is not None:
            return cfg.embed_column
        return None

    @staticmethod
    @overload
    def embedding_tables(
        models: Library[SQLBase],
        as_enum: Literal[False] = False,
    ) -> List[str]: ...

    @staticmethod
    @overload
    def embedding_tables(
        models: Library[SQLBase],
        as_enum: Literal[True],
    ) -> Enum: ...

    @staticmethod
    def embedding_tables(
        models: Library[SQLBase],
        as_enum: bool = False,
    ) -> Union[List[str], Enum]:
        tables = [
            name
            for name, model in models.items()
            if not name.startswith("_")
            and DatabaseConnector._get_embed_col(model) is not None
        ]

        if as_enum:
            EmbeddingTables = Enum(
                "EmbeddingTables", {table: table for table in tables}
            )
            return EmbeddingTables
        else:
            return tables

    def _create_engine(self):
        """
        Lazy-load the engine if not already created.

        Returns:
            Engine: The SQLAlchemy engine.
        """
        if not hasattr(self, "_engine"):
            connection_url = URL.create(**self.db_config)
            self._engine = create_engine(connection_url)

        # Register the event listener only once
        if not hasattr(self, "_embed_listener_registered"):
            event.listens_for(Session, "before_flush")(self._auto_embed)
            self._embed_listener_registered = True

        return self._engine

    def _auto_embed(self, session, flush_context, instances):
        """
        Event listener for before_flush that automatically generates embeddings
        for model instances that have an embed_column defined.

        Args:
            session: The SQLAlchemy session.
            flush_context: The flush context.
            instances: The instances being flushed.
        """
        if self._table_config is None:
            return

        targets = session.new.union(session.dirty)

        for target in targets:
            embed_col = DatabaseConnector._get_embed_col(target)

            if embed_col is None:
                continue

            to_embed = getattr(target, embed_col)

            if to_embed is not None and to_embed != "":
                table_config = self._table_config[target.__class__.__name__]

                assert table_config.embed_model is not None, (
                    "Embedding model is not defined for this table"
                )

                embed = table_config.embed_model.embed(to_embed)
                setattr(target, "embedding", embed)

    def __enter__(self):
        """
        Enter the context manager, creating a session.

        Returns:
            Session: The active database session.
        """
        self._active_session = Session(self.engine)
        return self._active_session

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit the context manager, ensuring the session is properly closed.

        Args:
            exc_type: The exception type.
            exc_value: The exception value.
            traceback: The traceback object.
        """
        if self._active_session:
            try:
                if exc_type:
                    self._active_session.rollback()
                else:
                    self._active_session.commit()
            finally:
                self._active_session.close()
            self._active_session = None
