#!/usr/bin/env python3
"""
Love Pool Care CRM - API Layer v2
Clean JSON API using SQLite or PostgreSQL backend
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_db import (
    init_db, db_contact_create, db_contact_get, db_contact_search,
    db_deal_create, db_deal_get, db_deal_update_stage, db_deal_close, db_deal_list,
    db_activity_create, db_activity_list,
    db_get_stats, db_get_stale_deals, get_db, normalize_phone, escape_html, USE_POSTGRES
)
from typing import Optional, Dict, List, Any
import json

# Initialize DB on import
init_db()

def _format_query(sql: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s if needed"""
    if USE_POSTGRES:
        # Replace ? with %s for PostgreSQL
        # Need to be careful not to replace ? in string literals
        # Simple approach: replace all ? with %s
        return sql.replace('?', '%s')
    return sql

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
        "value": d["value"]
    } for d in contact_deals]
    
    return result

def api_contact_search(query: str, limit: int = 20, offset: int = 0) -> Dict:
    """Search contacts"""
    total, contacts = db_contact_search(query, limit=limit, offset=offset)
    return {
        "success": True,
        "contacts": [_serialize_contact(c) for c in contacts],
        "total": total,
        "page": (offset // limit) + 1,
        "limit": limit
    }

def api_contact_update(contact_id: str, data: Dict, updated_by: str = "usr_rep_1") -> Dict:
    """Update contact"""
    success, result = db_contact_update(contact_id, data, updated_by)
    if success:
        return {"success": True, "contact": _serialize_contact(result)}
    return {"success": False, "errors": result}

# ============ DEAL API ============

def api_deal_create(data: Dict, created_by: str = "usr_rep_1") -> Dict:
    """Create deal from form data"""
    success, result = db_deal_create(data, created_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_get(deal_id: str) -> Dict:
    """Get deal with full details"""
    deal = db_deal_get(deal_id)
    if not deal:
        return {"success": False, "error": "Deal not found"}
    
    result = {
        "success": True,
        "deal": _serialize_deal(deal),
        "contact": {
            "id": deal["contact_id"],
            "name": f"{deal['first_name']} {deal['last_name']}",
            "phone": deal.get("phone"),
            "email": deal.get("email"),
            "company": deal.get("company_name")
        }
    }
    
    # Get activities
    total, activities = db_activity_list(deal_id=deal_id, limit=50)
    result["activities"] = [_serialize_activity(a) for a in activities]
    
    # Get available next stages
    conn = get_db()
    cursor = conn.execute(_format_query(
        "SELECT stage, stage_name, probability FROM pipeline_stages WHERE pipeline_id = ? ORDER BY stage_order"),
        (deal["pipeline_id"],)
    )
    stages = [(r["stage"], r["stage_name"], r["probability"]) for r in cursor.fetchall()]
    conn.close()
    
    current_stage = deal["stage"]
    current_idx = next((i for i, (s, _, _) in enumerate(stages) if s == current_stage), -1)
    
    # Allow moving to next stage, previous stage, or won/lost
    available = []
    if current_idx >= 0:
        # Can go back one stage
        if current_idx > 0:
            available.append({"id": stages[current_idx-1][0], "name": stages[current_idx-1][1]})
        # Can go forward one stage (unless at won/lost)
        if current_idx < len(stages) - 3:  # Not at won/lost yet
            available.append({"id": stages[current_idx+1][0], "name": stages[current_idx+1][1]})
        # Can always jump to won or lost
        available.append({"id": "won", "name": "Close Won"})
        available.append({"id": "lost", "name": "Close Lost"})
    
    result["available_stages"] = available
    
    # Get stage history
    conn = get_db()
    cursor = conn.execute(_format_query(
        "SELECT timestamp, \"user\", type, old_value, new_value FROM deal_history WHERE deal_id = ? ORDER BY timestamp DESC"),
        (deal_id,)
    )
    result["history"] = [{
        "timestamp": r["timestamp"],
        "user": r["user"],
        "type": r["type"],
        "from": r["old_value"],
        "to": r["new_value"]
    } for r in cursor.fetchall()]
    conn.close()
    
    return result

def api_deal_update_stage(deal_id: str, new_stage: str, updated_by: str = "usr_rep_1") -> Dict:
    """Update deal stage"""
    success, result = db_deal_update_stage(deal_id, new_stage, updated_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_close(deal_id: str, outcome: str, lost_reason: Optional[str] = None,
                   lost_detail: str = "", updated_by: str = "usr_rep_1") -> Dict:
    """Close deal as won or lost"""
    success, result = db_deal_close(deal_id, outcome, lost_reason, lost_detail, updated_by)
    if success:
        return {"success": True, "deal": _serialize_deal(result)}
    return {"success": False, "errors": result}

def api_deal_list(pipeline: Optional[str] = None, stage: Optional[str] = None,
                  assigned_to: Optional[str] = None, include_closed: bool = False,
                  limit: int = 50, offset: int = 0) -> Dict:
    """List deals with filtering"""
    total, deals = db_deal_list(
        pipeline=pipeline,
        stage=stage,
        assigned_to=assigned_to,
        include_closed=include_closed,
        limit=limit,
        offset=offset
    )
    return {
        "success": True,
        "deals": [_serialize_deal(d) for d in deals],
        "total": total,
        "page": (offset // limit) + 1,
        "limit": limit
    }

# ============ PIPELINE & DASHBOARD API ============

def api_pipeline_view(pipeline_id: str) -> Dict:
    """Get pipeline view with deals grouped by stage"""
    conn = get_db()
    
    # Get stages
    cursor = conn.execute(_format_query(
        "SELECT stage, stage_name, probability FROM pipeline_stages WHERE pipeline_id = %s ORDER BY stage_order"),
        (pipeline_id,)
    )
    stages = [{"id": r["stage"], "name": r["stage_name"], "probability": r["probability"]} for r in cursor.fetchall()]
    
    # Get deals for this pipeline
    cursor = conn.execute(_format_query("""
        SELECT d.*, c.first_name, c.last_name, c.company_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE d.pipeline_id = %s
        ORDER BY d.updated_at DESC
    """), (pipeline_id,))
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
    
    return {
        "success": True,
        "stats": stats,
        "stale_deals": [_serialize_deal(d) for d in stale[:10]],
        "follow_ups": []  # TODO: Implement follow-up tracking
    }

def api_report_sales(days: int = 30, user_id: Optional[str] = None) -> Dict:
    """Generate sales report"""
    stats = db_get_stats(days=days)
    
    # Get won deals
    conn = get_db()
    where_clause = "stage = 'won' AND actual_close_date > (NOW() - INTERVAL '%s days')" if USE_POSTGRES else "stage = 'won' AND actual_close_date > date('now', '-%s days')"
    params = (days,)
    
    if user_id:
        where_clause += " AND assigned_to = %s"
        params = (days, user_id)
    
    cursor = conn.execute(_format_query(f"""
        SELECT d.*, c.first_name, c.last_name
        FROM deals d
        JOIN contacts c ON d.contact_id = c.id
        WHERE {where_clause}
        ORDER BY d.actual_close_date DESC
    """), params)
    
    won_deals = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    total_won = len(won_deals)
    total_value = sum(d.get("value", 0) or 0 for d in won_deals)
    avg_value = total_value / total_won if total_won > 0 else 0
    
    # Win rate
    conn = get_db()
    cursor = conn.execute(_format_query("""
        SELECT COUNT(*) FROM deals WHERE stage IN ('won', 'lost') AND actual_close_date > (NOW() - INTERVAL '%s days')
    """ if USE_POSTGRES else """
        SELECT COUNT(*) FROM deals WHERE stage IN ('won', 'lost') AND actual_close_date > date('now', '-%s days')
    """), (days,))
    total_closed = cursor.fetchone()[0]
    conn.close()
    
    win_rate = (total_won / total_closed * 100) if total_closed > 0 else 0
    
    return {
        "success": True,
        "period_days": days,
        "summary": {
            "deals_won": total_won,
            "total_value": total_value,
            "avg_deal_size": avg_value,
            "win_rate": round(win_rate, 1)
        },
        "deals": [_serialize_deal(d) for d in won_deals],
        "by_line": stats.get("by_line", {})
    }

def api_reference_data() -> Dict:
    """Get reference data for forms"""
    conn = get_db()
    
    # Get users
    cursor = conn.execute("SELECT id, name, role FROM users WHERE active = 1 ORDER BY name")
    users = [{"id": r["id"], "name": r["name"], "role": r["role"]} for r in cursor.fetchall()]
    
    # Get pipeline stages
    cursor = conn.execute("SELECT pipeline_id, stage, stage_name FROM pipeline_stages ORDER BY pipeline_id, stage_order")
    pipelines = {}
    for r in cursor.fetchall():
        if r["pipeline_id"] not in pipelines:
            pipelines[r["pipeline_id"]] = []
        pipelines[r["pipeline_id"]].append({"id": r["stage"], "name": r["stage_name"]})
    
    conn.close()
    
    return {
        "success": True,
        "users": users,
        "pipelines": pipelines,
        "sources": ["website", "referral", "google", "facebook", "instagram", "nextdoor", "yard_sign", "door_hanger", "other"],
        "lost_reasons": [
            {"id": "price", "label": "Price too high"},
            {"id": "timing", "label": "Bad timing"},
            {"id": "competitor", "label": "Chose competitor"},
            {"id": "no_response", "label": "No response"},
            {"id": "scope", "label": "Scope changed"},
            {"id": "financing", "label": "Financing issues"},
            {"id": "other", "label": "Other"}
        ]
    }

# ============ ACTIVITY API ============

def api_activity_create(data: Dict, created_by: str = "usr_rep_1") -> Dict:
    """Create activity"""
    success, result = db_activity_create(data, created_by)
    if success:
        return {"success": True, "activity": _serialize_activity(result)}
    return {"success": False, "errors": result}

def api_activity_list(contact_id: Optional[str] = None, deal_id: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> Dict:
    """List activities"""
    total, activities = db_activity_list(
        contact_id=contact_id,
        deal_id=deal_id,
        limit=limit,
        offset=offset
    )
    return {
        "success": True,
        "activities": [_serialize_activity(a) for a in activities],
        "total": total
    }

# ============ SERIALIZATION HELPERS ============

def _serialize_contact(contact: Dict) -> Dict:
    """Convert contact row to clean dict"""
    return {
        "id": contact["id"],
        "first_name": contact["first_name"],
        "last_name": contact["last_name"],
        "phone": contact.get("phone"),
        "email": contact.get("email"),
        "company_name": contact.get("company_name"),
        "address": {
            "street": contact.get("address_street"),
            "city": contact.get("address_city"),
            "state": contact.get("address_state"),
            "zip": contact.get("address_zip")
        },
        "assigned_to": contact["assigned_to"],
        "source": contact.get("source_original", "other"),
        "status": contact.get("status", "active"),
        "notes": contact.get("notes", ""),
        "created_at": contact["created_at"],
        "updated_at": contact["updated_at"]
    }

def _serialize_deal(deal: Dict) -> Dict:
    """Convert deal row to clean dict"""
    return {
        "id": deal["id"],
        "title": deal["title"],
        "business_line": deal["business_line"],
        "stage": deal["stage"],
        "value": deal.get("value"),
        "probability": deal.get("probability", 0),
        "expected_close_date": deal.get("expected_close_date"),
        "actual_close_date": deal.get("actual_close_date"),
        "assigned_to": deal["assigned_to"],
        "contact_id": deal["contact_id"],
        "contact_name": f"{deal.get('first_name', '')} {deal.get('last_name', '')}".strip() if 'first_name' in deal else None,
        "company_name": deal.get("company_name"),
        "notes": deal.get("notes", ""),
        "created_at": deal["created_at"],
        "updated_at": deal["updated_at"]
    }

def _serialize_activity(activity: Dict) -> Dict:
    """Convert activity row to clean dict"""
    return {
        "id": activity["id"],
        "type": activity["type"],
        "contact_id": activity["contact_id"],
        "deal_id": activity.get("deal_id"),
        "performed_by": activity["performed_by"],
        "performed_at": activity["performed_at"],
        "direction": activity.get("direction", "outbound"),
        "duration_minutes": activity.get("duration_minutes"),
        "outcome": activity.get("outcome"),
        "notes": activity.get("notes", ""),
        "follow_up_required": bool(activity.get("follow_up_required", 0)),
        "follow_up_date": activity.get("follow_up_date"),
        "contact_name": activity.get("contact_name_snapshot"),
        "deal_title": activity.get("deal_title_snapshot"),
        "created_at": activity["created_at"]
    }