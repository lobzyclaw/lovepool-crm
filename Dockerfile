FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PYTHONPATH=/app

# Shell form so ${PORT} expands on Railway
CMD gunicorn -w 4 -b "0.0.0.0:${PORT:-5000}" --timeout 120 --access-logfile - --error-logfile - app:app