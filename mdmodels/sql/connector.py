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

from enum import Enum
from typing import Optional, Dict

from pydantic import BaseModel, model_validator
from sqlalchemy.engine.url import URL
from sqlmodel import create_engine, SQLModel, Session


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
    MYSQL = ("mysql", "pymysql")
    SQLITE = ("sqlite", None)
    SQLSERVER = ("mssql", "pyodbc")
    ORACLE = ("oracle", "cx_oracle")

    def __init__(self, db_name: str, default_driver: str):
        """
        Initialize the DatabaseType enum.

        Args:
            db_name (str): The name of the database.
            default_driver (str): The default driver for the database.
        """
        self.db_name = db_name
        self.default_driver = default_driver


class DatabaseConfig(BaseModel):
    """
    Configuration model for database connection.

    Attributes:
        db_type (DatabaseType): The type of the database.
        host (str): The database host address.
        port (Optional[int]): The port number for the database.
        username (Optional[str]): The database username.
        password (Optional[str]): The database password.
        driver (Optional[str]): The driver for the database.
        database (Optional[str]): The name of the database.
        query (Optional[dict]): Additional query parameters for the connection string.
    """

    db_type: DatabaseType
    host: str
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    driver: Optional[str] = None
    database: Optional[str] = None
    query: Optional[dict] = None

    @model_validator(mode="after")
    def check_database_requirements(self):
        """
        Validate the database configuration after initialization.

        Raises:
            ValueError: If required fields are missing for non-SQLite databases.
        """
        if self.db_type != DatabaseType.SQLITE:
            missing_values = []

            if not self.host:
                missing_values.append("host")
            if not self.port:
                missing_values.append("port")
            if not self.username:
                missing_values.append("username")
            if not self.password:
                missing_values.append("password")

            if missing_values:
                raise ValueError(f"Missing values: {', '.join(missing_values)}")
        else:
            if self.database is None:
                raise ValueError("Missing value: database")

        return self


class DatabaseConnector:
    """
    A class to manage database connections and sessions.

    Attributes:
        db_config (dict): The database configuration.
        _active_session (Optional[Session]): The active database session.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
        database: Optional[str] = None,
        query: Optional[dict] = None,
        db_type: DatabaseType = DatabaseType.SQLITE,
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
        """
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
        self._create_engine()

    def create_tables(self, models: Dict[str, SQLModel]):
        """
        Create all tables in the database.
        """

        assert len(models) > 0, "No models to create"

        SQLModel.metadata.create_all(self._engine)

    def _create_engine(self):
        """
        Lazy-load the engine if not already created.

        Returns:
            Engine: The SQLAlchemy engine.
        """
        if not hasattr(self, "_engine"):
            connection_url = URL.create(**self.db_config)
            self._engine = create_engine(connection_url)

        return self._engine

    def __enter__(self):
        """
        Enter the context manager, creating a session.

        Returns:
            Session: The active database session.
        """
        self._active_session = Session(self._create_engine())
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
