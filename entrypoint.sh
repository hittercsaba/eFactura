#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."

# Wait for PostgreSQL to be ready
until PGPASSWORD=efactura_pass psql -h db -U efactura_user -d efactura_db -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - executing migrations"

# Set Flask app
export FLASK_APP=manage.py

# Initialize migrations if env.py doesn't exist
if [ ! -f "migrations/env.py" ]; then
  echo "Initializing migrations..."
  flask db init
fi

# Create initial migration if no versions exist (excluding .gitkeep)
if [ ! -d "migrations/versions" ] || [ -z "$(find migrations/versions -name '*.py' -type f 2>/dev/null)" ]; then
  echo "Creating initial migration..."
  flask db migrate -m "Initial migration" || echo "Migration creation failed or already exists"
fi

# Run database migrations
echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn server..."

# Start Gunicorn
exec gunicorn -w 4 -b 0.0.0.0:8000 "manage:app"

