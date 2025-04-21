#!/bin/sh

echo "Running Alembic migrations..."
alembic upgrade head

echo "Migration completed"

echo "Starting FastAPI server..."
exec "$@"