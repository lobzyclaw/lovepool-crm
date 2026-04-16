#!/bin/sh
# Railway entrypoint - properly handle PORT

# Debug
echo "PORT from env: $PORT"

# Default to 5000 if not set
if [ -z "$PORT" ]; then
    echo "PORT not set, using default 5000"
    PORT=5000
fi

echo "Starting gunicorn on port $PORT"
exec gunicorn -w 4 -b "0.0.0.0:$PORT" --timeout 120 app:app