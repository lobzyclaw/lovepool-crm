FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy web app files
COPY . .

# Copy CRM core files from parent directory (these are in data/crm/)
COPY crm_api_v2.py crm_db.py crm_core.py ./

# Create data directory for SQLite on Railway
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_APP=app.py \
    DATA_DIR=/app/data

# Expose port
EXPOSE 5000

# IMPORTANT: Use shell form so ${PORT} expands correctly on Railway
CMD gunicorn -w 4 -b "0.0.0.0:${PORT:-5000}" --timeout 120 --access-logfile - --error-logfile - app:app