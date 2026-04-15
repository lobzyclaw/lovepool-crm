#!/bin/bash

# Debug startup
echo "Starting CRM..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Files in directory:"
ls -la

echo ""
echo "Testing Python imports..."
python -c "from app import app; print('App imported successfully')" 2>&1

echo ""
echo "Starting gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:${PORT:-5000} --timeout 120 --access-logfile - --error-logfile - app:app