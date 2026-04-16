#!/usr/bin/env python3
"""
Love Pool Care CRM - API Layer v2
Clean JSON API using SQLite backend
"""

import sys
sys.path.insert(0, '/Users/lobzy/.openclaw/workspace/data/crm')

from crm_db import (
    init_db, db_contact_create, db_contact_get, db_contact_search,
    db_deal_create, db_deal_get, db_deal_update_stage, db_deal_close, db_deal_list,
    db_activity_create, db_activity_list,
    db_get_stats, db_get_stale_deals, get_db, normalize_phone, escape_html
)
from typing import Optional, Dict, List, Any
import json

# Initialize DB on import
init_db()

# ============ CONTACT API ============

def api_contact_create(data: Dict, created_by: str = "usr_rep_1") -> Dict:
    """Create contact from form data"""
    success, result = db_contact_create(data, created_by)
    if success:
        return {"success": True, "contact": _serialize_contact(result)}
    return {"success": False, "errors": result}

def api_contact_get(contact_id: str, include_activities: bool = False) -> Dict:
    """Get contact with optional activities"""
    contact = db_contact_get(contact_id)
    if not contact:
        return {"success": False, "error": "Contact not found"}
    
    result = {"success": True, "contact": _serialize_contact(contact)}
    
    if include_activities:
        total, activities = db_activity_list(contact_id=contact_id, limit=50)
        result["activities"] = [_serialize_activity(a) for a in activities]
        result["activity_count"] = total
    
    # Get deals for this contact
    total, deals = db_deal_list(assigned_to=None, include_closed=True, limit=100)
    contact_deals = [d for d in deals if d['contact_id'] == contact_id]
    result["deals"] = [{
        "id": d["id"],
        "title": d["title"],
        "business_line": d["business_line"],
        "stage": d["stage"],
        "value": d["value"],
        "probability": d["probability"]
    } for d in contact_deals]
    
    return result

def api_contact_update(contact_id: str, data: Dict, updated_by: str = "system") -> Dict:
    """Update contact"""
    from crm_db import db_contact_update
    success, result = db_contact_update(contact_id, data, updated_by)
    if success:
        return {"success": True, "contact": _serialize_contact(result)}
    return {"success": False, "errors": result}

def api_contact_search(query: str, limit: int = 20, offset: int = 0) -> Dict:
    """Search contacts with pagination"""
    total, contacts = db_contact_search(query, limit, offset)
    return {
        "success": True,
        "contacts": [_serialize_contact(c) for c in contacts],
        "total": total,
        "limit": limit,
        "offset": offset
    }

# ============ DEAL API ============

def api_deal_create(data: Dict, created_by: str = "usr_rep_1") -> Dict:
    """Create deal"""
    success, result = db_deal_create(data, created_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_get(deal_id: str) -> Dict:
    """Get deal with full details"""
    deal = db_deal_get(deal_id)
    if not deal:
        return {"success": False, "error": "Deal not found"}
    
    # Get activities
    total, activities = db_activity_list(deal_id=deal_id, limit=50)
    
    # Get available stages
    conn = get_db()
    cursor = conn.execute(
        "SELECT stage, stage_name, probability FROM pipeline_stages WHERE pipeline_id = ? ORDER BY stage_order",
        (deal["pipeline_id"],)
    )
    stages = [{"id": r["stage"], "name": r["stage_name"], "probability": r["probability"]} for r in cursor.fetchall()]
    conn.close()
    
    # Get history
    conn = get_db()
    cursor = conn.execute(
        "SELECT * FROM deal_history WHERE deal_id = ? ORDER BY timestamp DESC",
        (deal_id,)
    )
    history = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "success": True,
        "deal": _serialize_deal(deal),
        "contact": {
            "first_name": deal["first_name"],
            "last_name": deal["last_name"],
            "phone": deal["phone"],
            "email": deal["email"],
            "company_name": deal["company_name"]
        },
        "activities": [_serialize_activity(a) for a in activities],
        "available_stages": stages,
        "history": history
    }

def api_deal_update_stage(deal_id: str, new_stage: str, updated_by: str = "system") -> Dict:
    """Move deal to new stage"""
    success, result = db_deal_update_stage(deal_id, new_stage, updated_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_close(deal_id: str, outcome: str, lost_reason: Optional[str] = None, 
                   lost_detail: str = "", updated_by: str = "system") -> Dict:
    """Close deal"""
    success, result = db_deal_close(deal_id, outcome, lost_reason, lost_detail, updated_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_list(pipeline: Optional[str] = None, stage: Optional[str] = None,
                  assigned_to: Optional[str] = None, include_closed: bool = False,
                  limit: int = 50, offset: int = 0) -> Dict:
    """List deals with filters"""
    total, deals = db_deal_list(pipeline, stage, assigned_to, include_closed, limit, offset)
    return {
        "success": True,
        "deals": [_serialize_deal(d) for d in deals],
        "total": total,
        "limit": limit,
        "offset": offset
    }

# ============ ACTIVITY API ============

def api_activity_create(data: Dict, created_by: str = "usr_rep_1") -> Dict:
    """Log activity"""
    success, result = db_activity_create(data, created_by)
    if success:
        return {"success": True, "activity": _serialize_activity(result)}
    return {"success": False, "errors": result}

def api_activity_list(contact_id: Optional[str] = None, deal_id: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> Dict:
    """List activities"""
    total, activities = db_activity_list(contact_id, deal_id, limit, offset)
    return {
        "success": True,
        "activities": [_serialize_activity(a) for a in activities],
        "total": total,
        "limit": limit,
        "offset": offset
    }

# ============ PIPELINE & REPORTING ============

def api_pipeline_view(pipeline_id: str) -> Dict:
    """Get pipeline view with deals grouped by stage"""
    conn = get_db()
    
    # Get stages
    cursor = conn.execute(
        "SELECT stage, stage_name, probability FROM pipeline_stages WHERE pipeline_id = ? ORDER BY stage_order",
        (pipeline_id,)
    )
    stages = [{"id": r["stage"], "name": r["stage_name"], "probability": r["probability"]} for r in cursor.fetchall()]
    
    # Get deals for this pipeline
    cursor = conn.execute("""
        SELECT d.*, c.first_name, c.last_name, c.company_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE d.pipeline_id = ?
        ORDER BY d.updated_at DESC
    """, (pipeline_id,))
    deals = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    # Group by stage
    columns = []
    for stage in stages:
        stage_deals = [d for d in deals if d["stage"] == stage["id"]]
        columns.append({
            "stage": stage,
            "deals": [_serialize_deal(d) for d in stage_deals],
            "count": len(stage_deals),
            "total_value": sum(d.get("value", 0) or 0 for d in stage_deals)
        })
    
    return {"success": True, "pipeline_id": pipeline_id, "columns": columns}

def api_dashboard() -> Dict:
    """Get dashboard data"""
    stats = db_get_stats(days=30)
    stale = db_get_stale_deals(days=14)
    
    # Get follow-ups due
    conn = get_db()
    today = __import__('datetime').datetime.now().isoformat()[:10]
    cursor = conn.execute("""
        SELECT d.id, d.title, d.next_action, c.first_name, c.last_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE d.stage NOT IN ('won', 'lost')
          AND d.next_action IS NOT NULL
    """)
    follow_ups = []
    for row in cursor.fetchall():
        next_action = json.loads(row["next_action"]) if row["next_action"] else {}
        if next_action.get("due_date", "") <= today:
            follow_ups.append({
                "deal_id": row["id"],
                "deal_title": row["title"],
                "contact_name": f"{row['first_name']} {row['last_name']}",
                "action": next_action
            })
    conn.close()
    
    return {
        "success": True,
        "stats": stats,
        "stale_deals": stale[:10],
        "follow_ups": follow_ups[:10]
    }

def api_report_sales(days: int = 30, user_id: Optional[str] = None) -> Dict:
    """Sales performance report"""
    conn = get_db()
    cutoff = (__import__('datetime').datetime.now() - __import__('datetime').timedelta(days=days)).isoformat()
    
    # Base query
    where = "WHERE actual_close_date > ? AND stage = 'won'"
    params = [cutoff]
    if user_id:
        where += " AND assigned_to = ?"
        params.append(user_id)
    
    # Won deals
    cursor = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(value), 0) FROM deals {where}", params)
    won_count, won_value = cursor.fetchone()
    
    # Lost deals
    cursor = conn.execute(f"SELECT COUNT(*) FROM deals WHERE actual_close_date > ? AND stage = 'lost'" + (" AND assigned_to = ?" if user_id else ""), 
                         [cutoff] + ([user_id] if user_id else []))
    lost_count = cursor.fetchone()[0]
    
    # Pipeline
    cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(value), 0) FROM deals WHERE stage NOT IN ('won', 'lost')" + (" AND assigned_to = ?" if user_id else ""),
                         ([user_id] if user_id else []))
    open_count, pipeline_value = cursor.fetchone()
    
    # By source
    cursor = conn.execute(f"""
        SELECT source_attribution, COUNT(*), SUM(value)
        FROM deals
        {where}
        GROUP BY source_attribution
    """, params)
    by_source = {}
    for row in cursor.fetchall():
        source = json.loads(row["source_attribution"]).get("original", "unknown") if row["source_attribution"] else "unknown"
        by_source[source] = {"count": row[1], "value": row[2] or 0}
    
    conn.close()
    
    total_closed = won_count + lost_count
    win_rate = round(won_count / total_closed * 100, 1) if total_closed > 0 else 0
    
    return {
        "success": True,
        "period_days": days,
        "summary": {
            "won_count": won_count,
            "won_value": won_value,
            "lost_count": lost_count,
            "open_count": open_count,
            "pipeline_value": pipeline_value,
            "win_rate": win_rate
        },
        "by_source": by_source
    }

def api_reference_data() -> Dict:
    """Get reference data for forms"""
    conn = get_db()
    
    cursor = conn.execute("SELECT id, name, role FROM users WHERE active = 1")
    users = [{"id": r["id"], "name": r["name"], "role": r["role"]} for r in cursor.fetchall()]
    
    cursor = conn.execute("SELECT DISTINCT pipeline_id FROM pipeline_stages")
    pipelines = [r[0] for r in cursor.fetchall()]
    
    pipeline_stages = {}
    for pipeline in pipelines:
        cursor = conn.execute(
            "SELECT stage, stage_name, probability FROM pipeline_stages WHERE pipeline_id = ? ORDER BY stage_order",
            (pipeline,)
        )
        pipeline_stages[pipeline] = [{"id": r["stage"], "name": r["stage_name"], "probability": r["probability"]} for r in cursor.fetchall()]
    
    conn.close()
    
    sources = [
        {"id": "google_ads", "name": "Google Ads"},
        {"id": "facebook_ads", "name": "Facebook Ads"},
        {"id": "organic_search", "name": "Organic Search"},
        {"id": "direct", "name": "Direct"},
        {"id": "referral", "name": "Referral"},
        {"id": "website_form", "name": "Website Form"},
        {"id": "phone", "name": "Phone Call"},
        {"id": "walk_in", "name": "Walk In"},
        {"id": "nextdoor", "name": "Nextdoor"},
        {"id": "yelp", "name": "Yelp"},
        {"id": "google_business", "name": "Google Business Profile"},
        {"id": "other", "name": "Other"}
    ]
    
    lost_reasons = [
        {"id": "price", "label": "Price too high"},
        {"id": "timing", "label": "Bad timing"},
        {"id": "competitor", "label": "Went with competitor"},
        {"id": "no_response", "label": "No response after follow-up"},
        {"id": "scope", "label": "Scope mismatch"},
        {"id": "financing", "label": "Financing fell through"},
        {"id": "other", "label": "Other"}
    ]
    
    return {
        "success": True,
        "users": users,
        "pipelines": pipeline_stages,
        "sources": sources,
        "lost_reasons": lost_reasons
    }

# ============ SERIALIZATION HELPERS ============

def _serialize_contact(row: Dict) -> Dict:
    """Convert contact row to API response"""
    return {
        "id": row["id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "phone": row["phone"],
        "email": row["email"],
        "company_name": row["company_name"],
        "address": {
            "street": row["address_street"],
            "city": row["address_city"],
            "state": row["address_state"],
            "zip": row["address_zip"]
        },
        "preferred_contact": row["preferred_contact"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "custom_fields": json.loads(row["custom_fields"]) if row["custom_fields"] else {},
        "source": {
            "original": row["source_original"],
            "campaign": row["source_campaign"]
        },
        "assigned_to": row["assigned_to"],
        "lead_score": row["lead_score"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "updated_at": row["updated_at"]
    }

def _serialize_deal(row: Dict) -> Dict:
    """Convert deal row to API response"""
    return {
        "id": row["id"],
        "contact_id": row["contact_id"],
        "business_line": row["business_line"],
        "title": row["title"],
        "value": row["value"],
        "currency": row["currency"],
        "pipeline_id": row["pipeline_id"],
        "stage": row["stage"],
        "probability": row["probability"],
        "expected_close_date": row["expected_close_date"],
        "actual_close_date": row["actual_close_date"],
        "lost_reason": row["lost_reason"],
        "lost_reason_detail": row["lost_reason_detail"],
        "assigned_to": row["assigned_to"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "updated_at": row["updated_at"],
        "_contact_name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() if row.get('first_name') else "Unknown"
    }

def _serialize_activity(row: Dict) -> Dict:
    """Convert activity row to API response"""
    return {
        "id": row["id"],
        "type": row["type"],
        "contact_id": row["contact_id"],
        "deal_id": row["deal_id"],
        "performed_by": row["performed_by"],
        "performed_at": row["performed_at"],
        "direction": row["direction"],
        "duration_minutes": row["duration_minutes"],
        "outcome": row["outcome"],
        "notes": row["notes"],
        "follow_up_required": bool(row["follow_up_required"]),
        "follow_up_date": row["follow_up_date"],
        "deal_title_snapshot": row["deal_title_snapshot"],
        "contact_name_snapshot": row["contact_name_snapshot"],
        "created_at": row["created_at"]
    }

if __name__ == "__main__":
    print("CRM API v2 loaded. Use functions to interact with data.")