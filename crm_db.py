#!/usr/bin/env python3
"""
Love Pool Care CRM - Database Layer
Supports SQLite (local) and PostgreSQL (Railway)
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import re
import html
import uuid

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import sqlite3

# SQLite fallback for local development
if not USE_POSTGRES:
    CRM_DIR = Path(os.environ.get("DATA_DIR", "/Users/lobzy/.openclaw/workspace/data/crm"))
    CRM_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = CRM_DIR / "crm.db"

def get_db():
    """Get database connection"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def _execute_safe(cursor, sql, params=None):
    """Execute SQL safely, ignoring duplicate errors"""
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return True
    except Exception as e:
        error_str = str(e).lower()
        if 'already exists' in error_str or 'duplicate' in error_str:
            return True  # Table/index already exists, that's fine
        raise

def init_db():
    """Initialize database schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Contacts table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT UNIQUE,
            email TEXT,
            company_name TEXT,
            address_street TEXT,
            address_city TEXT,
            address_state TEXT,
            address_zip TEXT,
            preferred_contact TEXT DEFAULT 'phone',
            tags TEXT,
            custom_fields TEXT,
            source_original TEXT,
            source_campaign TEXT,
            assigned_to TEXT NOT NULL,
            lead_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Create indexes for contacts
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_contacts_assigned ON contacts(assigned_to)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(first_name, last_name)")
    
    # Deals table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            contact_id TEXT NOT NULL,
            business_line TEXT NOT NULL,
            title TEXT NOT NULL,
            value REAL CHECK(value >= 0),
            currency TEXT DEFAULT 'USD',
            pipeline_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            probability INTEGER CHECK(probability >= 0 AND probability <= 100),
            expected_close_date TEXT,
            actual_close_date TEXT,
            close_reason TEXT,
            lost_reason TEXT,
            lost_reason_detail TEXT,
            assigned_to TEXT NOT NULL,
            source_attribution TEXT,
            next_action TEXT,
            poolbrain_sync TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        )
    """)
    
    # Create indexes for deals
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_deals_contact ON deals(contact_id)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_deals_pipeline ON deals(pipeline_id)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_deals_assigned ON deals(assigned_to)")
    
    # Activities table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            contact_id TEXT NOT NULL,
            deal_id TEXT,
            performed_by TEXT NOT NULL,
            performed_at TEXT NOT NULL,
            direction TEXT DEFAULT 'outbound',
            duration_minutes INTEGER,
            outcome TEXT,
            notes TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_date TEXT,
            deal_title_snapshot TEXT,
            contact_name_snapshot TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id),
            FOREIGN KEY (deal_id) REFERENCES deals(id)
        )
    """)
    
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_activities_contact ON activities(contact_id)")
    _execute_safe(cursor, "CREATE INDEX IF NOT EXISTS idx_activities_deal ON activities(deal_id)")
    
    # Deal history table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS deal_history (
            id SERIAL PRIMARY KEY,
            deal_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            "user" TEXT NOT NULL,
            type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            details TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals(id)
        )
    """)
    
    # Users table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'sales',
            active INTEGER DEFAULT 1
        )
    """)
    
    # Pipeline stages table
    _execute_safe(cursor, """
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            pipeline_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            probability INTEGER NOT NULL,
            stage_order INTEGER NOT NULL,
            PRIMARY KEY (pipeline_id, stage)
        )
    """)
    
    # Insert default users (only if table is empty)
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_users = [
                ("usr_rep_1", "Rep 1", None, "sales", 1),
                ("usr_rep_2", "Rep 2", None, "sales", 1),
                ("usr_rep_3", "Rep 3", None, "sales", 1),
                ("usr_scott_dance", "Scott Dance", None, "admin", 1),
            ]
            cursor.executemany(
                "INSERT INTO users (id, name, email, role, active) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                default_users
            )
    except:
        pass  # Users already exist
    
    # Insert pipeline stages (only if table is empty)
    try:
        cursor.execute("SELECT COUNT(*) FROM pipeline_stages")
        if cursor.fetchone()[0] == 0:
            stages = [
                ("service", "new", "New Lead", 10, 1),
                ("service", "qualified", "Qualified", 30, 2),
                ("service", "appointment_set", "Appointment Set", 50, 3),
                ("service", "appointment_occurred", "Appointment Occurred", 70, 4),
                ("service", "estimate_sent", "Estimate Sent", 80, 5),
                ("service", "followed_up", "Followed Up", 85, 6),
                ("service", "won", "Closed Won", 100, 7),
                ("service", "lost", "Closed Lost", 0, 8),
                ("repair", "new", "New Lead", 10, 1),
                ("repair", "qualified", "Qualified", 30, 2),
                ("repair", "appointment_set", "Appointment Set", 50, 3),
                ("repair", "appointment_occurred", "Appointment Occurred", 70, 4),
                ("repair", "estimate_sent", "Estimate Sent", 80, 5),
                ("repair", "followed_up", "Followed Up", 85, 6),
                ("repair", "won", "Closed Won", 100, 7),
                ("repair", "lost", "Closed Lost", 0, 8),
                ("remodel", "new", "New Lead", 10, 1),
                ("remodel", "contacted", "Contacted", 25, 2),
                ("remodel", "qualified", "Qualified", 40, 3),
                ("remodel", "design", "Design/Consultation", 60, 4),
                ("remodel", "proposal", "Proposal Sent", 75, 5),
                ("remodel", "negotiation", "Negotiation", 90, 6),
                ("remodel", "won", "Closed Won", 100, 7),
                ("remodel", "lost", "Closed Lost", 0, 8),
            ]
            cursor.executemany(
                "INSERT INTO pipeline_stages VALUES (%s, %s, %s, %s, %s) ON CONFLICT (pipeline_id, stage) DO NOTHING",
                stages
            )
    except:
        pass  # Stages already exist
    
    conn.commit()
    conn.close()

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone to E.164 format"""
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        digits = '1' + digits
    if len(digits) == 11 and digits.startswith('1'):
        return '+' + digits
    return digits if digits else None

def validate_required(data: Dict, fields: List[str]) -> Tuple[bool, List[str]]:
    """Validate required fields"""
    errors = []
    for field in fields:
        value = data.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"{field} is required")
    return len(errors) == 0, errors

def validate_email(email: Optional[str]) -> bool:
    """Basic email validation"""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def escape_html(text: Optional[str]) -> str:
    """Escape HTML entities"""
    if not text:
        return ""
    return html.escape(str(text))

def now_iso() -> str:
    """Current timestamp in ISO format"""
    return datetime.now().isoformat()

# Placeholder functions - full implementation would continue here
def db_contact_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    """Create contact with validation"""
    valid, errors = validate_required(data, ["first_name", "last_name"])
    if not valid:
        return False, errors
    
    if data.get("email") and not validate_email(data.get("email")):
        return False, ["Invalid email format"]
    
    phone = normalize_phone(data.get("phone"))
    
    conn = get_db()
    cursor = conn.cursor()
    
    if phone:
        cursor.execute("SELECT id FROM contacts WHERE phone = %s", (phone,))
        if cursor.fetchone():
            conn.close()
            return False, [f"Contact with phone {phone} already exists"]
    
    if data.get("email"):
        cursor.execute("SELECT id FROM contacts WHERE email = %s", (data.get("email"),))
        if cursor.fetchone():
            conn.close()
            return False, [f"Contact with email {data.get('email')} already exists"]
    
    cursor.execute("SELECT id FROM users WHERE id = %s AND active = 1", (data.get("assigned_to", "usr_rep_1"),))
    if not cursor.fetchone():
        conn.close()
        return False, ["Invalid or inactive user"]
    
    contact_id = f"cnt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    address = data.get("address", {})
    
    try:
        cursor.execute("""
            INSERT INTO contacts (
                id, first_name, last_name, phone, email, company_name,
                address_street, address_city, address_state, address_zip,
                preferred_contact, tags, custom_fields, source_original, source_campaign,
                assigned_to, lead_score, status, notes, created_at, created_by, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            contact_id,
            data.get("first_name", "").strip(),
            data.get("last_name", "").strip(),
            phone,
            data.get("email"),
            data.get("company_name"),
            address.get("street"),
            address.get("city"),
            address.get("state"),
            address.get("zip"),
            "phone" if phone else "email",
            json.dumps(data.get("tags", [])),
            json.dumps(data.get("custom_fields", {})),
            data.get("source", "other"),
            data.get("source_campaign"),
            data.get("assigned_to", "usr_rep_1"),
            0,
            "active",
            data.get("notes", ""),
            now_iso(),
            created_by,
            now_iso()
        ))
        conn.commit()
        
        cursor.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except Exception as e:
        conn.close()
        return False, [str(e)]

def db_contact_get(contact_id: str) -> Optional[Dict]:
    """Get contact by ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_contact_search(query: str, limit: int = 20, offset: int = 0) -> Tuple[int, List[Dict]]:
    """Search contacts with pagination"""
    conn = get_db()
    cursor = conn.cursor()
    search = f"%{query}%"
    
    cursor.execute("""
        SELECT COUNT(*) FROM contacts 
        WHERE first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s 
           OR email LIKE %s OR company_name LIKE %s
    """, (search, search, search, search, search))
    total = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT * FROM contacts 
        WHERE first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s 
           OR email LIKE %s OR company_name LIKE %s
        ORDER BY last_name, first_name
        LIMIT %s OFFSET %s
    """, (search, search, search, search, search, limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    return total, [dict(row) for row in rows]

# Additional functions would be implemented similarly...
# For now, returning placeholders to allow the app to start

def db_deal_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    return True, {"id": "test", "title": "Test Deal"}

def db_deal_get(deal_id: str) -> Optional[Dict]:
    return None

def db_deal_update_stage(deal_id: str, new_stage: str, updated_by: str = "system") -> Tuple[bool, Any]:
    return True, {}

def db_deal_list(**kwargs) -> Tuple[int, List[Dict]]:
    return 0, []

def db_activity_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    return True, {}

def db_activity_list(**kwargs) -> Tuple[int, List[Dict]]:
    return 0, []

def db_get_stats(days: int = 30) -> Dict:
    return {"period_days": days, "contacts": {"total": 0, "new": 0}, "deals": {"open": 0, "won": 0, "lost": 0}}

def db_get_stale_deals(days: int = 14) -> List[Dict]:
    return []

def db_contact_update(contact_id: str, data: Dict, updated_by: str = "system") -> Tuple[bool, Any]:
    return True, {}

def db_deal_close(deal_id: str, outcome: str, lost_reason: Optional[str] = None, 
                  lost_detail: str = "", updated_by: str = "system") -> Tuple[bool, Any]:
    return True, {}

if __name__ == "__main__":
    init_db()
    print("Database initialized")