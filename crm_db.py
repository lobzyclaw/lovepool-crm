#!/usr/bin/env python3
"""
Love Pool Care CRM - Database Layer
SQLite backend with ACID transactions, concurrent-safe
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import re
import html
import uuid

CRM_DIR = Path(os.environ.get("DATA_DIR", "/Users/lobzy/.openclaw/workspace/data/crm"))
DB_PATH = CRM_DIR / "crm.db"

def get_db() -> sqlite3.Connection:
    """Get database connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initialize database schema"""
    conn = get_db()
    
    # Contacts table
    conn.execute("""
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_assigned ON contacts(assigned_to)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(first_name, last_name)")
    
    # Deals table
    conn.execute("""
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_contact ON deals(contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_pipeline ON deals(pipeline_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_assigned ON deals(assigned_to)")
    
    # Activities table
    conn.execute("""
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
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_contact ON activities(contact_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_deal ON activities(deal_id)")
    
    # Deal history table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            user TEXT NOT NULL,
            type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            details TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals(id)
        )
    """)
    
    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'sales',
            active INTEGER DEFAULT 1
        )
    """)
    
    # Pipeline stages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            pipeline_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            probability INTEGER NOT NULL,
            stage_order INTEGER NOT NULL,
            PRIMARY KEY (pipeline_id, stage)
        )
    """)
    
    # Insert default users
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("usr_rep_1", "Rep 1", None, "sales", 1),
            ("usr_rep_2", "Rep 2", None, "sales", 1),
            ("usr_rep_3", "Rep 3", None, "sales", 1),
            ("usr_scott_dance", "Scott Dance", None, "admin", 1),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO users (id, name, email, role, active) VALUES (?, ?, ?, ?, ?)",
            default_users
        )
    
    # Insert pipeline stages
    cursor = conn.execute("SELECT COUNT(*) FROM pipeline_stages")
    if cursor.fetchone()[0] == 0:
        stages = [
            # Service
            ("service", "new", "New Lead", 10, 1),
            ("service", "qualified", "Qualified", 30, 2),
            ("service", "appointment_set", "Appointment Set", 50, 3),
            ("service", "appointment_occurred", "Appointment Occurred", 70, 4),
            ("service", "estimate_sent", "Estimate Sent", 80, 5),
            ("service", "followed_up", "Followed Up", 85, 6),
            ("service", "won", "Closed Won", 100, 7),
            ("service", "lost", "Closed Lost", 0, 8),
            # Repair
            ("repair", "new", "New Lead", 10, 1),
            ("repair", "qualified", "Qualified", 30, 2),
            ("repair", "appointment_set", "Appointment Set", 50, 3),
            ("repair", "appointment_occurred", "Appointment Occurred", 70, 4),
            ("repair", "estimate_sent", "Estimate Sent", 80, 5),
            ("repair", "followed_up", "Followed Up", 85, 6),
            ("repair", "won", "Closed Won", 100, 7),
            ("repair", "lost", "Closed Lost", 0, 8),
            # Remodel
            ("remodel", "new", "New Lead", 10, 1),
            ("remodel", "contacted", "Contacted", 25, 2),
            ("remodel", "qualified", "Qualified", 40, 3),
            ("remodel", "design", "Design/Consultation", 60, 4),
            ("remodel", "proposal", "Proposal Sent", 75, 5),
            ("remodel", "negotiation", "Negotiation", 90, 6),
            ("remodel", "won", "Closed Won", 100, 7),
            ("remodel", "lost", "Closed Lost", 0, 8),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO pipeline_stages VALUES (?, ?, ?, ?, ?)",
            stages
        )
    
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

# ============ CONTACT OPERATIONS ============

def db_contact_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    """Create contact with validation"""
    valid, errors = validate_required(data, ["first_name", "last_name"])
    if not valid:
        return False, errors
    
    if data.get("email") and not validate_email(data.get("email")):
        return False, ["Invalid email format"]
    
    phone = normalize_phone(data.get("phone"))
    
    conn = get_db()
    
    if phone:
        cursor = conn.execute("SELECT id FROM contacts WHERE phone = ?", (phone,))
        if cursor.fetchone():
            conn.close()
            return False, [f"Contact with phone {phone} already exists"]
    
    if data.get("email"):
        cursor = conn.execute("SELECT id FROM contacts WHERE email = ?", (data.get("email"),))
        if cursor.fetchone():
            conn.close()
            return False, [f"Contact with email {data.get('email')} already exists"]
    
    cursor = conn.execute("SELECT id FROM users WHERE id = ? AND active = 1", (data.get("assigned_to", "usr_rep_1"),))
    if not cursor.fetchone():
        conn.close()
        return False, ["Invalid or inactive user"]
    
    contact_id = f"cnt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    address = data.get("address", {})
    
    try:
        conn.execute("""
            INSERT INTO contacts (
                id, first_name, last_name, phone, email, company_name,
                address_street, address_city, address_state, address_zip,
                preferred_contact, tags, custom_fields, source_original, source_campaign,
                assigned_to, lead_score, status, notes, created_at, created_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        
        cursor = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except sqlite3.IntegrityError as e:
        conn.close()
        return False, [str(e)]

def db_contact_get(contact_id: str) -> Optional[Dict]:
    """Get contact by ID"""
    conn = get_db()
    cursor = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_contact_search(query: str, limit: int = 20, offset: int = 0) -> Tuple[int, List[Dict]]:
    """Search contacts with pagination"""
    conn = get_db()
    search = f"%{query}%"
    
    cursor = conn.execute("""
        SELECT COUNT(*) FROM contacts 
        WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? 
           OR email LIKE ? OR company_name LIKE ?
    """, (search, search, search, search, search))
    total = cursor.fetchone()[0]
    
    cursor = conn.execute("""
        SELECT * FROM contacts 
        WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? 
           OR email LIKE ? OR company_name LIKE ?
        ORDER BY last_name, first_name
        LIMIT ? OFFSET ?
    """, (search, search, search, search, search, limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    return total, [dict(row) for row in rows]

# ============ DEAL OPERATIONS ============

def db_deal_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    """Create deal with validation"""
    valid, errors = validate_required(data, ["contact_id", "business_line", "title"])
    if not valid:
        return False, errors
    
    if data.get("business_line") not in ["service", "repair", "remodel"]:
        return False, ["Invalid business line"]
    
    value = data.get("value")
    if value is not None and value < 0:
        return False, ["Deal value cannot be negative"]
    
    conn = get_db()
    
    cursor = conn.execute("SELECT id, assigned_to FROM contacts WHERE id = ?", (data.get("contact_id"),))
    contact = cursor.fetchone()
    if not contact:
        conn.close()
        return False, ["Contact not found"]
    
    assigned_to = data.get("assigned_to") or contact["assigned_to"]
    cursor = conn.execute("SELECT id FROM users WHERE id = ? AND active = 1", (assigned_to,))
    if not cursor.fetchone():
        conn.close()
        return False, ["Invalid or inactive user"]
    
    cursor = conn.execute("""
        SELECT stage, probability FROM pipeline_stages 
        WHERE pipeline_id = ? ORDER BY stage_order LIMIT 1
    """, (data.get("business_line"),))
    stage_row = cursor.fetchone()
    if not stage_row:
        conn.close()
        return False, ["Pipeline not configured"]
    
    deal_id = f"dpl_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    
    try:
        conn.execute("""
            INSERT INTO deals (
                id, contact_id, business_line, title, value, currency,
                pipeline_id, stage, probability, expected_close_date,
                assigned_to, source_attribution, notes, created_at, created_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deal_id,
            data.get("contact_id"),
            data.get("business_line"),
            data.get("title", "").strip(),
            value,
            "USD",
            data.get("business_line"),
            stage_row["stage"],
            stage_row["probability"],
            data.get("expected_close_date"),
            assigned_to,
            json.dumps({"original": "unknown"}),
            data.get("notes", ""),
            now_iso(),
            created_by,
            now_iso()
        ))
        
        conn.execute("""
            INSERT INTO deal_history (deal_id, timestamp, user, type, new_value, details)
            VALUES (?, ?, ?, 'deal_created', ?, ?)
        """, (deal_id, now_iso(), created_by, deal_id, json.dumps({"title": data.get("title")})))
        
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except sqlite3.IntegrityError as e:
        conn.close()
        return False, [str(e)]

def db_deal_get(deal_id: str) -> Optional[Dict]:
    """Get deal by ID with contact info"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT d.*, c.first_name, c.last_name, c.phone, c.email, c.company_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE d.id = ?
    """, (deal_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def db_deal_update_stage(deal_id: str, new_stage: str, updated_by: str = "system") -> Tuple[bool, Any]:
    """Update deal stage with validation"""
    conn = get_db()
    
    cursor = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    deal = cursor.fetchone()
    if not deal:
        conn.close()
        return False, ["Deal not found"]
    
    cursor = conn.execute(
        "SELECT probability FROM pipeline_stages WHERE pipeline_id = ? AND stage = ?",
        (deal["pipeline_id"], new_stage)
    )
    stage_row = cursor.fetchone()
    if not stage_row:
        conn.close()
        return False, [f"Invalid stage '{new_stage}' for this pipeline"]
    
    old_stage = deal["stage"]
    new_probability = stage_row["probability"]
    
    if new_stage == "won" and (deal["value"] is None or deal["value"] == 0):
        conn.close()
        return False, ["Cannot close deal as won with $0 value"]
    
    actual_close = now_iso() if new_stage in ["won", "lost"] else None
    
    try:
        conn.execute("""
            UPDATE deals 
            SET stage = ?, probability = ?, actual_close_date = ?, updated_at = ?
            WHERE id = ?
        """, (new_stage, new_probability, actual_close, now_iso(), deal_id))
        
        conn.execute("""
            INSERT INTO deal_history (deal_id, timestamp, user, type, old_value, new_value, details)
            VALUES (?, ?, ?, 'stage_change', ?, ?, ?)
        """, (deal_id, now_iso(), updated_by, old_stage, new_stage, 
              json.dumps({"probability_change": {"from": deal["probability"], "to": new_probability}})))
        
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except sqlite3.Error as e:
        conn.close()
        return False, [str(e)]

def db_deal_list(pipeline: Optional[str] = None, stage: Optional[str] = None,
                 assigned_to: Optional[str] = None, include_closed: bool = False,
                 limit: int = 50, offset: int = 0) -> Tuple[int, List[Dict]]:
    """List deals with pagination"""
    conn = get_db()
    
    where_clauses = []
    params = []
    
    if pipeline:
        where_clauses.append("d.pipeline_id = ?")
        params.append(pipeline)
    if stage:
        where_clauses.append("d.stage = ?")
        params.append(stage)
    if assigned_to:
        where_clauses.append("d.assigned_to = ?")
        params.append(assigned_to)
    if not include_closed:
        where_clauses.append("d.stage NOT IN ('won', 'lost')")
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(f"SELECT COUNT(*) FROM deals d WHERE {where_sql}", params)
    total = cursor.fetchone()[0]
    
    cursor = conn.execute(f"""
        SELECT d.*, c.first_name, c.last_name, c.company_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE {where_sql}
        ORDER BY d.updated_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    rows = cursor.fetchall()
    conn.close()
    
    return total, [dict(row) for row in rows]

# ============ ACTIVITY OPERATIONS ============

def db_activity_create(data: Dict, created_by: str = "usr_rep_1") -> Tuple[bool, Any]:
    """Create activity"""
    valid, errors = validate_required(data, ["type", "contact_id"])
    if not valid:
        return False, errors
    
    conn = get_db()
    
    cursor = conn.execute("SELECT first_name, last_name FROM contacts WHERE id = ?", (data.get("contact_id"),))
    contact = cursor.fetchone()
    if not contact:
        conn.close()
        return False, ["Contact not found"]
    
    deal_title = None
    if data.get("deal_id"):
        cursor = conn.execute("SELECT title FROM deals WHERE id = ?", (data.get("deal_id"),))
        deal = cursor.fetchone()
        if deal:
            deal_title = deal["title"]
    
    activity_id = f"act_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    
    try:
        conn.execute("""
            INSERT INTO activities (
                id, type, contact_id, deal_id, performed_by, performed_at,
                direction, duration_minutes, outcome, notes,
                follow_up_required, follow_up_date,
                deal_title_snapshot, contact_name_snapshot,
                created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            activity_id,
            data.get("type"),
            data.get("contact_id"),
            data.get("deal_id"),
            data.get("performed_by", created_by),
            data.get("performed_at") or now_iso(),
            data.get("direction", "outbound"),
            data.get("duration_minutes"),
            data.get("outcome"),
            data.get("notes", ""),
            1 if data.get("follow_up_required") else 0,
            data.get("follow_up_date"),
            deal_title,
            f"{contact['first_name']} {contact['last_name']}",
            now_iso(),
            created_by
        ))
        
        if data.get("follow_up_required") and data.get("deal_id"):
            conn.execute("""
                UPDATE deals 
                SET next_action = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps({
                "type": f"follow_up_{data.get('type')}",
                "due_date": data.get("follow_up_date"),
                "assigned_to": data.get("performed_by", created_by)
            }), now_iso(), data.get("deal_id")))
        
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except sqlite3.Error as e:
        conn.close()
        return False, [str(e)]

def db_activity_list(contact_id: Optional[str] = None, deal_id: Optional[str] = None,
                     limit: int = 50, offset: int = 0) -> Tuple[int, List[Dict]]:
    """List activities with pagination"""
    conn = get_db()
    
    where_clauses = []
    params = []
    
    if contact_id:
        where_clauses.append("contact_id = ?")
        params.append(contact_id)
    if deal_id:
        where_clauses.append("deal_id = ?")
        params.append(deal_id)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    cursor = conn.execute(f"SELECT COUNT(*) FROM activities WHERE {where_sql}", params)
    total = cursor.fetchone()[0]
    
    cursor = conn.execute(f"""
        SELECT * FROM activities 
        WHERE {where_sql}
        ORDER BY performed_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    rows = cursor.fetchall()
    conn.close()
    
    return total, [dict(row) for row in rows]

# ============ STATS & REPORTING ============

def db_get_stats(days: int = 30) -> Dict:
    """Get CRM statistics"""
    conn = get_db()
    cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()
    
    # Contact stats
    cursor = conn.execute("SELECT COUNT(*) FROM contacts")
    total_contacts = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM contacts WHERE created_at > ?", (cutoff,))
    new_contacts = cursor.fetchone()[0]
    
    # Deal stats
    cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE stage NOT IN ('won', 'lost')")
    open_deals = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE stage = 'won' AND actual_close_date > ?", (cutoff,))
    won_deals = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE stage = 'lost' AND actual_close_date > ?", (cutoff,))
    lost_deals = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COALESCE(SUM(value), 0) FROM deals WHERE stage NOT IN ('won', 'lost')")
    pipeline_value = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COALESCE(SUM(value), 0) FROM deals WHERE stage = 'won' AND actual_close_date > ?", (cutoff,))
    won_value = cursor.fetchone()[0]
    
    # By line
    by_line = {}
    for line in ['service', 'repair', 'remodel']:
        cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE business_line = ? AND stage NOT IN ('won', 'lost')", (line,))
        open_count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE business_line = ? AND stage = 'won'", (line,))
        won_count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM deals WHERE business_line = ? AND stage = 'lost'", (line,))
        lost_count = cursor.fetchone()[0]
        by_line[line] = {"open": open_count, "won": won_count, "lost": lost_count}
    
    conn.close()
    
    return {
        "period_days": days,
        "contacts": {"total": total_contacts, "new": new_contacts},
        "deals": {"open": open_deals, "won": won_deals, "lost": lost_deals, 
                  "pipeline_value": pipeline_value, "value_won": won_value},
        "by_line": by_line
    }

def db_get_stale_deals(days: int = 14) -> List[Dict]:
    """Get deals with no recent activity"""
    conn = get_db()
    cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()
    
    # Use a subquery instead of HAVING
    cursor = conn.execute("""
        SELECT d.*, c.first_name, c.last_name, 
               COALESCE((SELECT MAX(performed_at) FROM activities WHERE deal_id = d.id), d.created_at) as last_activity
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE d.stage NOT IN ('won', 'lost')
          AND COALESCE((SELECT MAX(performed_at) FROM activities WHERE deal_id = d.id), d.created_at) < ?
        ORDER BY last_activity
    """, (cutoff,))
    
    rows = cursor.fetchall()
    conn.close()
    
    deals = []
    for row in rows:
        deal = dict(row)
        last_act = datetime.fromisoformat(deal['last_activity'])
        deal['_stale_days'] = (datetime.now() - last_act).days
        deal['_contact_name'] = f"{deal['first_name']} {deal['last_name']}"
        deals.append(deal)
    
    return deals

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)

def db_contact_update(contact_id: str, data: Dict, updated_by: str = "system") -> Tuple[bool, Any]:
    """Update contact with audit logging"""
    conn = get_db()
    
    # Check contact exists
    cursor = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
    old = cursor.fetchone()
    if not old:
        conn.close()
        return False, ["Contact not found"]
    
    # Build update fields
    updates = []
    params = []
    
    if "first_name" in data:
        updates.append("first_name = ?")
        params.append(data["first_name"].strip())
    if "last_name" in data:
        updates.append("last_name = ?")
        params.append(data["last_name"].strip())
    if "phone" in data:
        phone = normalize_phone(data["phone"])
        if phone:
            cursor = conn.execute("SELECT id FROM contacts WHERE phone = ? AND id != ?", (phone, contact_id))
            if cursor.fetchone():
                conn.close()
                return False, ["Phone number already in use"]
        updates.append("phone = ?")
        params.append(phone)
    if "email" in data:
        if data["email"] and not validate_email(data["email"]):
            conn.close()
            return False, ["Invalid email format"]
        updates.append("email = ?")
        params.append(data["email"])
    if "company_name" in data:
        updates.append("company_name = ?")
        params.append(data["company_name"])
    if "assigned_to" in data:
        cursor = conn.execute("SELECT id FROM users WHERE id = ? AND active = 1", (data["assigned_to"],))
        if not cursor.fetchone():
            conn.close()
            return False, ["Invalid or inactive user"]
        updates.append("assigned_to = ?")
        params.append(data["assigned_to"])
    if "notes" in data:
        updates.append("notes = ?")
        params.append(data["notes"])
    if "tags" in data:
        updates.append("tags = ?")
        params.append(json.dumps(data["tags"]))
    if "custom_fields" in data:
        updates.append("custom_fields = ?")
        params.append(json.dumps(data["custom_fields"]))
    
    if not updates:
        conn.close()
        return True, dict(old)
    
    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(contact_id)
    
    try:
        conn.execute(f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
    except sqlite3.IntegrityError as e:
        conn.close()
        return False, [str(e)]


def db_deal_close(deal_id: str, outcome: str, lost_reason: Optional[str] = None, 
                  lost_detail: str = "", updated_by: str = "system") -> Tuple[bool, Any]:
    """Close deal as won or lost"""
    if outcome not in ["won", "lost"]:
        return False, ["Outcome must be 'won' or 'lost'"]
    
    conn = get_db()
    
    cursor = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    deal = cursor.fetchone()
    if not deal:
        conn.close()
        return False, ["Deal not found"]
    
    if outcome == "lost" and lost_reason:
        valid_reasons = ["price", "timing", "competitor", "no_response", "scope", "financing", "other"]
        if lost_reason not in valid_reasons:
            conn.close()
            return False, [f"Invalid lost reason: {lost_reason}"]
    
    # Check $0 value for won deals
    if outcome == "won" and (deal["value"] is None or deal["value"] == 0):
        conn.close()
        return False, ["Cannot close deal as won with $0 value"]
    
    old_stage = deal["stage"]
    
    try:
        conn.execute("""
            UPDATE deals 
            SET stage = ?, probability = ?, actual_close_date = ?, 
                lost_reason = ?, lost_reason_detail = ?, updated_at = ?
            WHERE id = ?
        """, (outcome, 100 if outcome == "won" else 0, now_iso(),
              lost_reason if outcome == "lost" else None,
              lost_detail if outcome == "lost" else None,
              now_iso(), deal_id))
        
        conn.execute("""
            INSERT INTO deal_history (deal_id, timestamp, user, type, old_value, new_value, details)
            VALUES (?, ?, ?, 'deal_closed', ?, ?, ?)
        """, (deal_id, now_iso(), updated_by, old_stage, outcome,
              json.dumps({"outcome": outcome, "lost_reason": lost_reason})))
        
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        return True, dict(row)
        
    except sqlite3.Error as e:
        conn.close()
        return False, [str(e)]
