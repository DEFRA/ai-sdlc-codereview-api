"""Utilities for managing multiprocessing with asyncio and database connections.

This module provides functions to safely run async code in separate processes
with their own database connections, avoiding event loop conflicts.
"""
import asyncio
from typing import Any, Callable, Coroutine, TypeVar

from app.common.logging import get_logger
from app.database.connection import create_client

logger = get_logger(__name__)

T = TypeVar('T')

async def setup_process_database() -> None:
    """Set up a new database connection for the current process.
    
    This function creates a new MongoDB client and overrides the global
    database connection in the database_utils module for the current process.
    This ensures that each process has its own connection tied to its own event loop.
    """
    # Create a new client in this process with its own event loop
    # This ensures we don't reuse connections from the main process
    import app.database.database_utils
    client, db = create_client()
    app.database.database_utils.client = client
    app.database.database_utils.db = db
    
    logger.debug("Created new database connection for process")

async def cleanup_process_database() -> None:
    """Clean up the database connection for the current process."""
    import app.database.database_utils
    if hasattr(app.database.database_utils, 'client'):
        app.database.database_utils.client.close()
        logger.debug("Closed database connection for process")

async def run_with_new_connection(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine with a new database connection.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
    """
    try:
        await setup_process_database()
        return await coro
    finally:
        await cleanup_process_database()

def run_async_in_process(func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
    """Run an async function in a separate process with its own database connection.
    
    This is a wrapper function that sets up a new event loop and database connection
    in the new process, runs the async function, and then cleans up.
    
    Args:
        func: The async function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    """
    async def wrapper():
        return await run_with_new_connection(func(*args, **kwargs))
    
    asyncio.run(wrapper()) 