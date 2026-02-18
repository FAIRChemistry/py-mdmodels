from contextvars import ContextVar

from fastmcp.server.middleware import Middleware, MiddlewareContext
from sqlmodel import Session

from ...sql import DatabaseConnector

# Context variable storing the current database session for this MCP request.
CTX_SESSION: ContextVar[Session | None] = ContextVar(
    "db_session",
    default=None,
)


class DBSessionMiddleware(Middleware):
    """
    Middleware for managing the SQLModel Session lifecycle in MCP requests.

    This middleware uses the DatabaseConnector as a context manager to control
    the lifecycle of a database session for each incoming request.

    Workflow:
      - On request entry: Enters the connector, creating a new session.
      - The session is set in `ctx_session` (a context variable) and becomes
        accessible from anywhere in the request lifecycle.
      - The downstream handler (`call_next`) is awaited, allowing request processing
        to use the active session.
      - On completion (success or exception): The connector context is exited,
        which will handle commit or rollback, and close the session.
      - Finally, the `ctx_session` context variable is reset to `None`.

    Args:
        connector (DatabaseConnector): The database connector object to provide sessions.
    """

    def __init__(self, connector: DatabaseConnector):
        """
        Initialize the session middleware.

        Args:
            connector (DatabaseConnector): The connector to open/close sessions.
        """
        self.connector = connector

    async def on_request(self, context: MiddlewareContext, call_next):
        """
        Handles a request with database session lifecycle management.

        Enters the DatabaseConnector context, sets the session in the context
        variable, calls the next request handler, and then ensures cleanup.

        Args:
            context (MiddlewareContext): The current middleware/request context.
            call_next (callable): The next handler to call.

        Returns:
            The result of `call_next(context)`.
        """
        with self.connector as session:
            CTX_SESSION.set(session)
            try:
                result = await call_next(context)
                return result
            finally:
                # Clear the session from context after request
                CTX_SESSION.set(None)
