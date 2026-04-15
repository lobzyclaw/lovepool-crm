# Patch for Railway deployment
# Add this to the beginning of crm_db.py or create as a patch

import os
from pathlib import Path

# Use environment variable or default to local path
if os.environ.get('RAILWAY_ENVIRONMENT'):
    # Running on Railway - use /app/data
    CRM_DIR = Path("/app/data")
else:
    # Local development
    CRM_DIR = Path("/Users/lobzy/.openclaw/workspace/data/crm")

DB_PATH = CRM_DIR / "crm.db"

# Ensure directory exists
CRM_DIR.mkdir(parents=True, exist_ok=True)