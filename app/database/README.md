# Database Module

This module provides centralized database connection management for the application.

## Structure

- `connection.py`: Core connection management functions
- `database_utils.py`: Global database instance and utility functions
- `database_init.py`: Database initialization and schema validation

## Connection Management

The application uses a centralized approach to database connection management:

1. `connection.py` provides the core functions for creating database connections with consistent configuration
2. `database_utils.py` creates a global database connection for the main application process
3. `process_utils.py` provides utilities for creating separate database connections in child processes

## Usage

### Main Application

The main application uses the global database connection from `database_utils.py`:

```python
from app.database.database_utils import get_database

async def some_function():
    db = await get_database()
    # Use db...
```

### Child Processes

Child processes should create their own database connections using the utilities in `process_utils.py`:

```python
from app.utils.process_utils import run_async_in_process

# Run an async function in a separate process with its own database connection
Process(
    target=run_async_in_process,
    args=(my_async_function, arg1, arg2)
).start()
```

### Scripts

Scripts can use the connection module directly:

```python
from app.database.connection import create_client

client, db = create_client()
# Use db...
``` 