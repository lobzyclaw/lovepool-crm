FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application (app.py + crm_*.py + templates + static)
COPY . .

# Create data directory for SQLite on Railway
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PYTHONPATH=/app

# Start with gunicorn - shell form so ${PORT} expands correctly
CMD gunicorn -w 4 -b "0.0.0.0:${PORT:-5000}" --timeout 120 --access-logfile - --error-logfile - app:app