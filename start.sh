#!/bin/bash

# Debug startup
echo "Starting CRM..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "PORT env var: $PORT"

# Use default port if not set
PORT=${PORT:-5000}
echo "Using port: $PORT"

echo ""
echo "Files in directory:"
ls -la

echo ""
echo "Starting gunicorn on port $PORT..."
exec gunicorn -w 4 -b "0.0.0.0:$PORT" --timeout 120 --access-logfile - --error-logfile - app:app