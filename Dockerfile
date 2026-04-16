FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite on Railway
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_APP=app.py

# IMPORTANT: Use shell form so ${PORT} expands correctly on Railway
CMD gunicorn -w 4 -b "0.0.0.0:${PORT:-5000}" --timeout 120 --access-logfile - --error-logfile - app:app