#!/bin/bash

# first arg: either revision or upgrade
# if first arg is revision, second arg is message for autogenerate

# Check if ELROY_DATABASE_URL environment variable is set
if [ -z "$ELROY_DATABASE_URL" ]; then
    echo "ERROR: ELROY_DATABASE_URL environment variable is not set"
    echo "Please set ELROY_DATABASE_URL before running alembic operations"
    exit 1
fi

echo "Using database: $ELROY_DATABASE_URL"

if [ "$1" = "revision" ]; then
    if [ -z "$2" ]; then
        echo "Error: When using revision, you must provide a message as the second argument"
        exit 1
    fi
    
    echo "Running SQLite alembic revision..."
    if ! alembic -c elroy/db/sqlite/alembic/alembic.ini revision --autogenerate -m "$2"; then
        echo "ERROR: SQLite alembic revision failed"
        exit 1
    fi
    echo "SQLite alembic revision completed successfully"
    
    echo "Running PostgreSQL alembic revision..."
    if ! alembic -c elroy/db/postgres/alembic/alembic.ini revision --autogenerate -m "$2"; then
        echo "ERROR: PostgreSQL alembic revision failed"
        exit 1
    fi
    echo "PostgreSQL alembic revision completed successfully"
    
elif [ "$1" = "upgrade" ]; then
    echo "Running SQLite alembic upgrade..."
    if ! alembic -c elroy/db/sqlite/alembic/alembic.ini upgrade head; then
        echo "ERROR: SQLite alembic upgrade failed"
        exit 1
    fi
    echo "SQLite alembic upgrade completed successfully"
    
    echo "Running PostgreSQL alembic upgrade..."
    if ! alembic -c elroy/db/postgres/alembic/alembic.ini upgrade head; then
        echo "ERROR: PostgreSQL alembic upgrade failed"
        exit 1
    fi
    echo "PostgreSQL alembic upgrade completed successfully"
    
else
    echo "Error: First argument must be either 'revision' or 'upgrade'"
    echo "Usage: $0 revision \"message\" OR $0 upgrade"
    exit 1
fi