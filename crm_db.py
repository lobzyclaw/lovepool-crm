#!/usr/bin/env python3
"""
Love Pool Care CRM - Database Layer
SQLite backend with ACID transactions, concurrent-safe
"""

import os
from pathlib import Path

# Railway database path fix
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('PORT'):
    CRM_DIR = Path("/app/data")
else:
    CRM_DIR = Path(os.environ.get("DATA_DIR", "/Users/lobzy/.openclaw/workspace/data/crm"))

CRM_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = CRM_DIR / "crm.db"

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
import re
import html
import uuid

def get_db() -> sqlite3.Connection:
    """Get database connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

[840 more lines in file. Use offset=26 to continue.]