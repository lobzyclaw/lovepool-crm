FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create data directory for SQLite on Railway with proper permissions
RUN mkdir -p /app/data && chmod 777 /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PYTHONPATH=/app \
    DATA_DIR=/app/data

# Start with gunicorn - shell form so ${PORT} expands correctly
CMD python -c "from sample_data import add_sample_data; add_sample_data()" 2>/dev/null || true; gunicorn -w 4 -b "0.0.0.0:${PORT:-5000}" --timeout 120 --access-logfile - --error-logfile - app:app