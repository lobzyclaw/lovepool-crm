#!/usr/bin/env python3
"""
Love Pool Care CRM - Core Data Layer
Desktop/Web-first CRM with clean API for future web UI
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid

CRM_DIR = Path("/Users/lobzy/.openclaw/workspace/data/crm")

def generate_id(prefix: str) -> str:
    """Generate unique ID: prefix_YYYYMMDD_random"""
    today = datetime.now().strftime("%Y%m%d")
    random = uuid.uuid4().hex[:8]
    return f"{prefix}_{today}_{random}"

def load_json(path: Path) -> Dict:
    """Load JSON file, return empty dict if not exists"""
    if not path.exists():
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path: Path, data: Dict):
    """Save JSON file with pretty printing"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def now_iso() -> str:
    """Current timestamp in ISO format"""
    return datetime.now().isoformat()

def validate_user(user_id: str) -> bool:
    """Check if user exists and is active"""
    users = load_json(CRM_DIR / "users.json").get("users", [])
    return any(u["id"] == user_id and u.get("active", True) for u in users)

def validate_pipeline_stage(pipeline_id: str, stage_id: str) -> bool:
    """Check if stage exists in pipeline"""
    pipeline = load_json(CRM_DIR / "pipelines" / f"{pipeline_id}.json")
    stages = pipeline.get("stages", [])
    return any(s["id"] == stage_id for s in stages)

def get_stage_probability(pipeline_id: str, stage_id: str) -> int:
    """Get probability for a stage"""
    pipeline = load_json(CRM_DIR / "pipelines" / f"{pipeline_id}.json")
    stage = next((s for s in pipeline.get("stages", []) if s["id"] == stage_id), None)
    return stage["probability"] if stage else 0

# ============ CONTACT OPERATIONS ============

def create_contact(
    first_name: str,
    last_name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    company_name: Optional[str] = None,
    address: Optional[Dict] = None,
    source: Optional[str] = None,
    source_campaign: Optional[str] = None,
    assigned_to: str = "usr_rep_1",
    custom_fields: Optional[Dict] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
    created_by: str = "usr_rep_1"
) -> Dict:
    """Create a new contact and update indexes"""
    
    # Validate assigned user
    if not validate_user(assigned_to):
        raise ValueError(f"Invalid or inactive user: {assigned_to}")
    
    # Check for duplicate by phone
    if phone:
        existing = find_contact_by_phone(phone)
        if existing:
            raise ValueError(f"Contact with phone {phone} already exists: {existing['id']}")
    
    contact_id = generate_id("cnt")
    contact = {
        "id": contact_id,
        "created_at": now_iso(),
        "created_by": created_by,
        "updated_at": now_iso(),
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "email": email,
        "company_name": company_name,
        "address": address or {},
        "preferred_contact": "phone" if phone else "email",
        "tags": tags or [],
        "custom_fields": {
            "pool_type": custom_fields.get("pool_type") if custom_fields else None,
            "pool_size": custom_fields.get("pool_size") if custom_fields else None,
            "cleaning_system": custom_fields.get("cleaning_system") if custom_fields else None,
            "sanitizer": custom_fields.get("sanitizer") if custom_fields else None,
            "budget_range": custom_fields.get("budget_range") if custom_fields else None,
            "timeline": custom_fields.get("timeline") if custom_fields else None,
            "current_service_company": custom_fields.get("current_service_company") if custom_fields else None,
            "_custom": custom_fields.get("_custom", {}) if custom_fields else {}
        },
        "source": {
            "original": source or "other",
            "campaign": source_campaign,
            "landing_page": None,
            "gclid": None
        },
        "assigned_to": assigned_to,
        "lead_score": 0,
        "status": "active",
        "deal_ids": [],
        "activity_ids": [],
        "notes": notes
    }
    
    # Save contact
    save_json(CRM_DIR / "contacts" / f"{contact_id}.json", contact)
    
    # Update indexes
    update_contact_index(contact)
    
    return contact

def get_contact(contact_id: str) -> Optional[Dict]:
    """Load contact by ID"""
    return load_json(CRM_DIR / "contacts" / f"{contact_id}.json")

def find_contact_by_phone(phone: str) -> Optional[Dict]:
    """Find contact by phone number"""
    index = load_json(CRM_DIR / "contacts" / "index.json")
    contact_id = index.get("by_phone", {}).get(phone)
    return get_contact(contact_id) if contact_id else None

def update_contact(contact_id: str, updates: Dict, updated_by: str = "system") -> Optional[Dict]:
    """Update contact fields with audit logging"""
    contact = get_contact(contact_id)
    if not contact:
        return None
    
    # Track changes for audit
    changes = {}
    for key, new_val in updates.items():
        if key in contact and contact[key] != new_val:
            changes[key] = {"from": contact[key], "to": new_val}
    
    if changes:
        contact.setdefault("history", []).append({
            "timestamp": now_iso(),
            "user": updated_by,
            "changes": changes
        })
    
    contact.update(updates)
    contact["updated_at"] = now_iso()
    save_json(CRM_DIR / "contacts" / f"{contact_id}.json", contact)
    
    # Rebuild index if phone/email/address changed
    if any(k in updates for k in ["phone", "email", "address"]):
        rebuild_contact_index()
    
    return contact

def update_contact_index(contact: Dict):
    """Add contact to indexes"""
    index = load_json(CRM_DIR / "contacts" / "index.json")
    
    if contact.get("phone"):
        index.setdefault("by_phone", {})[contact["phone"]] = contact["id"]
    if contact.get("email"):
        index.setdefault("by_email", {})[contact["email"]] = contact["id"]
    if contact.get("address"):
        addr = contact["address"]
        if addr.get("street") and addr.get("city"):
            addr_key = f"{addr['street']}, {addr['city']}"
            index.setdefault("by_address", {})[addr_key] = contact["id"]
    
    save_json(CRM_DIR / "contacts" / "index.json", index)

def rebuild_contact_index():
    """Rebuild contact indexes from scratch"""
    index = {"by_phone": {}, "by_email": {}, "by_address": {}}
    
    contacts_dir = CRM_DIR / "contacts"
    for file in contacts_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        contact = load_json(file)
        
        if contact.get("phone"):
            index["by_phone"][contact["phone"]] = contact["id"]
        if contact.get("email"):
            index["by_email"][contact["email"]] = contact["id"]
        if contact.get("address"):
            addr = contact["address"]
            if addr.get("street") and addr.get("city"):
                addr_key = f"{addr['street']}, {addr['city']}"
                index["by_address"][addr_key] = contact["id"]
    
    save_json(CRM_DIR / "contacts" / "index.json", index)

# ============ DEAL OPERATIONS ============

def create_deal(
    contact_id: str,
    business_line: str,
    title: str,
    value: Optional[float] = None,
    assigned_to: Optional[str] = None,
    expected_close_date: Optional[str] = None,
    notes: str = "",
    created_by: str = "usr_rep_1"
) -> Dict:
    """Create a new deal linked to a contact"""
    
    # Validate inputs
    contact = get_contact(contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")
    
    if business_line not in ["service", "repair", "remodel"]:
        raise ValueError(f"Invalid business line: {business_line}")
    
    assigned = assigned_to or contact.get("assigned_to", "usr_rep_1")
    if not validate_user(assigned):
        raise ValueError(f"Invalid or inactive user: {assigned}")
    
    if value is not None and value < 0:
        raise ValueError("Deal value cannot be negative")
    
    deal_id = generate_id("dpl")
    pipeline = load_json(CRM_DIR / "pipelines" / f"{business_line}.json")
    first_stage = pipeline["stages"][0]["id"]
    
    deal = {
        "id": deal_id,
        "created_at": now_iso(),
        "created_by": created_by,
        "updated_at": now_iso(),
        "contact_id": contact_id,
        "company_id": None,
        "business_line": business_line,
        "title": title,
        "value": value,
        "currency": "USD",
        "pipeline_id": business_line,
        "stage": first_stage,
        "probability": pipeline["stages"][0]["probability"],
        "expected_close_date": expected_close_date,
        "actual_close_date": None,
        "close_reason": None,
        "lost_reason": None,
        "lost_reason_detail": None,
        "assigned_to": assigned,
        "source_attribution": contact.get("source", {}),
        "activity_ids": [],
        "next_action": None,
        "history": [],
        "poolbrain_sync": {
            "status": "pending",
            "customer_id": None,
            "job_id": None
        },
        "notes": notes
    }
    
    # Save deal
    save_json(CRM_DIR / "deals" / f"{deal_id}.json", deal)
    
    # Link to contact
    contact["deal_ids"].append(deal_id)
    contact["updated_at"] = now_iso()
    save_json(CRM_DIR / "contacts" / f"{contact_id}.json", contact)
    
    # Update deal indexes
    update_deal_index(deal)
    
    return deal

def get_deal(deal_id: str) -> Optional[Dict]:
    """Load deal by ID"""
    return load_json(CRM_DIR / "deals" / f"{deal_id}.json")

def update_deal_stage(deal_id: str, new_stage: str, updated_by: str = "system") -> Optional[Dict]:
    """Move deal to new stage with history tracking"""
    deal = get_deal(deal_id)
    if not deal:
        return None
    
    # Validate stage
    if not validate_pipeline_stage(deal["pipeline_id"], new_stage):
        raise ValueError(f"Invalid stage {new_stage} for pipeline {deal['pipeline_id']}")
    
    old_stage = deal["stage"]
    old_probability = deal["probability"]
    new_probability = get_stage_probability(deal["pipeline_id"], new_stage)
    
    # Log change to history
    deal["history"].append({
        "timestamp": now_iso(),
        "user": updated_by,
        "type": "stage_change",
        "from": old_stage,
        "to": new_stage,
        "probability_change": {"from": old_probability, "to": new_probability}
    })
    
    deal["stage"] = new_stage
    deal["probability"] = new_probability
    deal["updated_at"] = now_iso()
    
    # If closing
    if new_stage == "won":
        deal["actual_close_date"] = now_iso()
    elif new_stage == "lost":
        deal["actual_close_date"] = now_iso()
    
    save_json(CRM_DIR / "deals" / f"{deal_id}.json", deal)
    
    # Update indexes (remove from old stage, add to new)
    rebuild_deal_index()
    
    return deal

def close_deal(
    deal_id: str, 
    outcome: str, 
    lost_reason: Optional[str] = None, 
    lost_detail: str = "",
    updated_by: str = "system"
) -> Optional[Dict]:
    """Close deal as won or lost with full audit"""
    deal = get_deal(deal_id)
    if not outcome:
        return None
    
    if outcome not in ["won", "lost"]:
        raise ValueError("Outcome must be 'won' or 'lost'")
    
    if outcome == "lost" and lost_reason:
        valid_reasons = [r["id"] for r in get_lost_reasons()]
        if lost_reason not in valid_reasons:
            raise ValueError(f"Invalid lost reason: {lost_reason}")
    
    old_stage = deal["stage"]
    
    deal["history"].append({
        "timestamp": now_iso(),
        "user": updated_by,
        "type": "deal_closed",
        "outcome": outcome,
        "from_stage": old_stage,
        "lost_reason": lost_reason if outcome == "lost" else None
    })
    
    deal["stage"] = outcome
    deal["actual_close_date"] = now_iso()
    deal["probability"] = 100 if outcome == "won" else 0
    
    if outcome == "lost":
        deal["lost_reason"] = lost_reason
        deal["lost_reason_detail"] = lost_detail
    
    deal["updated_at"] = now_iso()
    save_json(CRM_DIR / "deals" / f"{deal_id}.json", deal)
    
    rebuild_deal_index()
    
    return deal

def update_deal_index(deal: Dict):
    """Add deal to indexes (used on creation)"""
    index = load_json(CRM_DIR / "deals" / "index.json")
    
    # By stage
    index.setdefault("by_stage", {}).setdefault(deal["stage"], [])
    if deal["id"] not in index["by_stage"][deal["stage"]]:
        index["by_stage"][deal["stage"]].append(deal["id"])
    
    # By assignee
    index.setdefault("by_assignee", {}).setdefault(deal["assigned_to"], [])
    if deal["id"] not in index["by_assignee"][deal["assigned_to"]]:
        index["by_assignee"][deal["assigned_to"]].append(deal["id"])
    
    # By pipeline
    index.setdefault("by_pipeline", {}).setdefault(deal["pipeline_id"], [])
    if deal["id"] not in index["by_pipeline"][deal["pipeline_id"]]:
        index["by_pipeline"][deal["pipeline_id"]].append(deal["id"])
    
    save_json(CRM_DIR / "deals" / "index.json", index)

def rebuild_deal_index():
    """Rebuild deal indexes from scratch to ensure consistency"""
    index = {"by_stage": {}, "by_assignee": {}, "by_pipeline": {}, "by_close_date": {}}
    
    deals_dir = CRM_DIR / "deals"
    for file in deals_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        deal = load_json(file)
        
        # By stage
        stage = deal.get("stage", "unknown")
        index["by_stage"].setdefault(stage, []).append(deal["id"])
        
        # By assignee
        assignee = deal.get("assigned_to", "unassigned")
        index["by_assignee"].setdefault(assignee, []).append(deal["id"])
        
        # By pipeline
        pipeline = deal.get("pipeline_id", "unknown")
        index["by_pipeline"].setdefault(pipeline, []).append(deal["id"])
        
        # By close date (for won/lost)
        if deal.get("actual_close_date"):
            close_date = deal["actual_close_date"][:10]  # YYYY-MM-DD
            index["by_close_date"].setdefault(close_date, []).append(deal["id"])
    
    save_json(CRM_DIR / "deals" / "index.json", index)

# ============ ACTIVITY OPERATIONS ============

def log_activity(
    activity_type: str,
    contact_id: str,
    deal_id: Optional[str] = None,
    performed_by: str = "usr_rep_1",
    performed_at: Optional[str] = None,
    direction: str = "outbound",
    duration_minutes: Optional[int] = None,
    outcome: Optional[str] = None,
    notes: str = "",
    follow_up_required: bool = False,
    follow_up_date: Optional[str] = None,
    created_by: str = "usr_rep_1"
) -> Dict:
    """Log an activity against a contact and optionally a deal"""
    
    # Validate user
    if not validate_user(performed_by):
        raise ValueError(f"Invalid user: {performed_by}")
    
    activity_id = generate_id("act")
    activity = {
        "id": activity_id,
        "created_at": now_iso(),
        "created_by": created_by,
        "performed_at": performed_at or now_iso(),
        "type": activity_type,
        "contact_id": contact_id,
        "deal_id": deal_id,
        "performed_by": performed_by,
        "direction": direction,
        "duration_minutes": duration_minutes,
        "outcome": outcome,
        "notes": notes,
        "follow_up_required": follow_up_required,
        "follow_up_date": follow_up_date,
        "attachments": []
    }
    
    # Save activity
    save_json(CRM_DIR / "activities" / f"{activity_id}.json", activity)
    
    # Link to contact
    contact = get_contact(contact_id)
    if contact:
        contact["activity_ids"].append(activity_id)
        contact["updated_at"] = now_iso()
        save_json(CRM_DIR / "contacts" / f"{contact_id}.json", contact)
    
    # Link to deal and update next action
    if deal_id:
        deal = get_deal(deal_id)
        if deal:
            deal["activity_ids"].append(activity_id)
            deal["updated_at"] = now_iso()
            
            # Update next action if follow-up required
            if follow_up_required and follow_up_date:
                deal["next_action"] = {
                    "type": f"follow_up_{activity_type}",
                    "due_date": follow_up_date,
                    "assigned_to": performed_by
                }
            
            save_json(CRM_DIR / "deals" / f"{deal_id}.json", deal)
    
    return activity

def get_activity(activity_id: str) -> Optional[Dict]:
    """Load activity by ID"""
    return load_json(CRM_DIR / "activities" / f"{activity_id}.json")

def get_contact_activities(contact_id: str, limit: int = 50) -> List[Dict]:
    """Get activities for a contact, newest first"""
    contact = get_contact(contact_id)
    if not contact:
        return []
    
    activities = []
    for act_id in contact.get("activity_ids", [])[-limit:]:
        act = get_activity(act_id)
        if act:
            activities.append(act)
    
    return sorted(activities, key=lambda x: x.get("performed_at", ""), reverse=True)

# ============ SEARCH OPERATIONS ============

def search_contacts(query: str, limit: int = 20) -> List[Dict]:
    """Search contacts by name, phone, email, company"""
    results = []
    query_lower = query.lower()
    
    contacts_dir = CRM_DIR / "contacts"
    for file in contacts_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        contact = load_json(file)
        
        # Search name
        full_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".lower()
        if query_lower in full_name:
            results.append(contact)
            continue
        
        # Search company name
        if contact.get("company_name") and query_lower in contact["company_name"].lower():
            results.append(contact)
            continue
        
        # Search phone
        if contact.get("phone") and query in contact["phone"]:
            results.append(contact)
            continue
        
        # Search email
        if contact.get("email") and query_lower in contact.get("email", "").lower():
            results.append(contact)
            continue
        
        # Search address
        addr = contact.get("address", {})
        addr_str = f"{addr.get('street', '')} {addr.get('city', '')} {addr.get('zip', '')}".lower()
        if query_lower in addr_str:
            results.append(contact)
            continue
    
    return results[:limit]

def get_pipeline_deals(pipeline_id: str, stage: Optional[str] = None) -> List[Dict]:
    """Get all deals in a pipeline, optionally filtered by stage"""
    index = load_json(CRM_DIR / "deals" / "index.json")
    deal_ids = index.get("by_pipeline", {}).get(pipeline_id, [])
    
    deals = []
    for deal_id in deal_ids:
        deal = get_deal(deal_id)
        if deal:
            if stage is None or deal["stage"] == stage:
                deals.append(deal)
    
    return deals

def get_user_deals(user_id: str, include_closed: bool = False) -> List[Dict]:
    """Get all deals assigned to a user"""
    index = load_json(CRM_DIR / "deals" / "index.json")
    deal_ids = index.get("by_assignee", {}).get(user_id, [])
    
    deals = []
    for deal_id in deal_ids:
        deal = get_deal(deal_id)
        if deal:
            if include_closed or deal["stage"] not in ["won", "lost"]:
                deals.append(deal)
    
    return deals

def get_stale_deals(days: int = 14) -> List[Dict]:
    """Get deals with no activity in N days"""
    from datetime import datetime, timedelta
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    deals = []
    deals_dir = CRM_DIR / "deals"
    for file in deals_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        deal = load_json(file)
        
        if deal.get("stage") in ["won", "lost"]:
            continue
        
        last_activity = deal.get("updated_at")
        if last_activity and last_activity < cutoff:
            # Get most recent activity date
            activities = [get_activity(aid) for aid in deal.get("activity_ids", [])]
            if activities:
                last_act_date = max(a.get("performed_at", "") for a in activities if a)
                if last_act_date < cutoff:
                    deal["_stale_days"] = (datetime.now() - datetime.fromisoformat(last_act_date)).days
                    deals.append(deal)
            else:
                deal["_stale_days"] = (datetime.now() - datetime.fromisoformat(deal["created_at"])).days
                deals.append(deal)
    
    return sorted(deals, key=lambda x: x.get("_stale_days", 0), reverse=True)

# ============ HELPER FUNCTIONS ============

def get_pipeline_stages(pipeline_id: str) -> List[Dict]:
    """Get stages for a pipeline"""
    pipeline = load_json(CRM_DIR / "pipelines" / f"{pipeline_id}.json")
    return pipeline.get("stages", [])

def get_users(active_only: bool = True) -> List[Dict]:
    """Get all users"""
    users = load_json(CRM_DIR / "users.json").get("users", [])
    if active_only:
        return [u for u in users if u.get("active", True)]
    return users

def get_sources() -> List[Dict]:
    """Get all lead sources"""
    return load_json(CRM_DIR / "sources.json").get("sources", [])

def get_lost_reasons() -> List[Dict]:
    """Get all lost reasons"""
    return load_json(CRM_DIR / "lost_reasons.json").get("lost_reasons", [])

def get_stats(days: int = 30) -> Dict:
    """Get CRM statistics for period"""
    from datetime import datetime, timedelta
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    stats = {
        "period_days": days,
        "contacts": {"total": 0, "new": 0},
        "deals": {"total": 0, "open": 0, "won": 0, "lost": 0, "value_won": 0, "pipeline_value": 0},
        "by_line": {"service": {"open": 0, "won": 0, "lost": 0}, "repair": {"open": 0, "won": 0, "lost": 0}, "remodel": {"open": 0, "won": 0, "lost": 0}}
    }
    
    # Count contacts
    contacts_dir = CRM_DIR / "contacts"
    for file in contacts_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        contact = load_json(file)
        stats["contacts"]["total"] += 1
        if contact.get("created_at", "") > cutoff:
            stats["contacts"]["new"] += 1
    
    # Count deals
    deals_dir = CRM_DIR / "deals"
    for file in deals_dir.glob("*.json"):
        if file.name == "index.json":
            continue
        deal = load_json(file)
        stats["deals"]["total"] += 1
        
        line = deal.get("business_line", "service")
        stage = deal.get("stage", "new")
        value = deal.get("value", 0) or 0
        
        if stage == "won":
            stats["deals"]["won"] += 1
            stats["by_line"][line]["won"] += 1
            if deal.get("actual_close_date", "") > cutoff:
                stats["deals"]["value_won"] += value
        elif stage == "lost":
            stats["deals"]["lost"] += 1
            stats["by_line"][line]["lost"] += 1
        else:
            stats["deals"]["open"] += 1
            stats["deals"]["pipeline_value"] += value
            stats["by_line"][line]["open"] += 1
    
    return stats

if __name__ == "__main__":
    print("CRM Core loaded. Use functions to interact with data.")