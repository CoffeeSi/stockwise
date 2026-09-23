#!/bin/sh
set -e

# Wait for PostgreSQL database if DATABASE_URL is provided
if [ -n "$DATABASE_URL" ]; then
    echo "Checking database availability..."
    python - << 'EOF'
import os
import sys
import time
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
max_retries = int(os.getenv("DB_MAX_RETRIES", "30"))
retry_interval = int(os.getenv("DB_RETRY_INTERVAL", "2"))

for attempt in range(1, max_retries + 1):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection successfully established.")
        sys.exit(0)
    except Exception as exc:
        print(f"Waiting for database (attempt {attempt}/{max_retries}): {type(exc).__name__}")
        time.sleep(retry_interval)

print("Error: Database connection timed out.", file=sys.stderr)
sys.exit(1)
EOF
fi

# Ensure credentials and the durable job queue exist before API startup.
python -m backend.infrastructure.migrate

# Execute main container command
exec "$@"
