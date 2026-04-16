#!/usr/bin/env python3
"""
CallRail Integration for Love Pool Care CRM
Receives webhooks from CallRail and creates contacts/opportunities
"""

import os
from datetime import datetime
from crm_api_v2 import api_contact_create, api_deal_create

# CallRail webhook handler
def handle_callrail_webhook(payload: dict) -> dict:
    """
    Process CallRail webhook payload
    
    Expected payload from CallRail:
    {
        "call": {
            "id": "12345",
            "datetime": "2026-04-16T10:30:00-07:00",
            "customer_name": "John Smith",
            "customer_phone_number": "+14805551234",
            "source": "Google Ads",
            "campaign": "Pool Service Phoenix",
            "tracking_phone_number": "+14805559999",
            "duration": 120,
            "recording_url": "https://...",
            "answered": true,
            "first_call": true
        }
    }
    Or for form submissions:
    {
        "form_submission": {
            "id": "67890",
            "submitted_at": "2026-04-16T10:30:00-07:00",
            "customer_name": "Jane Doe",
            "customer_phone_number": "+14805555678",
            "customer_email": "jane@email.com",
            "source": "Website",
            "campaign": "Remodel Landing Page",
            "form_data": {
                "service_type": "Pool Remodel",
                "budget": "$25,000-$50,000"
            }
        }
    }
    """
    
    result = {"success": False, "contact": None, "opportunity": None}
    
    try:
        # Handle phone calls
        if "call" in payload:
            call = payload["call"]
            
            # Parse name (CallRail sends full name)
            name_parts = call.get("customer_name", "").split(" ", 1)
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Create contact
            contact_data = {
                "first_name": first_name,
                "last_name": last_name,
                "phone": call.get("customer_phone_number"),
                "email": call.get("customer_email"),  # May be empty
                "company_name": None,
                "address": {"street": None, "city": None, "state": None, "zip": None},
                "source": map_callrail_source(call.get("source", "call")),
                "assigned_to": "usr_rep_1",  # Default rep
                "notes": f"CallRail call from {call.get('source', 'unknown')}. Duration: {call.get('duration', 0)}s. Tracking #: {call.get('tracking_phone_number', 'N/A')}",
                "custom_fields": {
                    "callrail_id": call.get("id"),
                    "recording_url": call.get("recording_url"),
                    "first_call": call.get("first_call", False)
                }
            }
            
            contact_result = api_contact_create(contact_data, created_by="callrail")
            
            if contact_result["success"]:
                result["contact"] = contact_result["contact"]
                
                # Create opportunity for new calls
                if call.get("first_call", False) or call.get("duration", 0) > 60:
                    opp_data = {
                        "contact_id": contact_result["contact"]["id"],
                        "business_line": infer_business_line(call.get("source", "")),
                        "title": f"Call from {first_name} {last_name} - {call.get('source', 'Unknown')}",
                        "value": None,  # Unknown until qualified
                        "expected_close_date": None,
                        "assigned_to": "usr_rep_1",
                        "notes": f"Inbound call via {call.get('source', 'unknown')}. Duration: {call.get('duration', 0)} seconds."
                    }
                    
                    opp_result = api_deal_create(opp_data, created_by="callrail")
                    if opp_result["success"]:
                        result["opportunity"] = opp_result["deal"]
                
                result["success"] = True
            else:
                # Contact might already exist
                result["error"] = contact_result.get("errors", ["Unknown error"])
        
        # Handle form submissions
        elif "form_submission" in payload:
            form = payload["form_submission"]
            
            name_parts = form.get("customer_name", "").split(" ", 1)
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            contact_data = {
                "first_name": first_name,
                "last_name": last_name,
                "phone": form.get("customer_phone_number"),
                "email": form.get("customer_email"),
                "company_name": None,
                "address": {"street": None, "city": None, "state": None, "zip": None},
                "source": map_callrail_source(form.get("source", "website")),
                "assigned_to": "usr_rep_1",
                "notes": f"CallRail form submission from {form.get('source', 'website')}. Campaign: {form.get('campaign', 'N/A')}",
                "custom_fields": {
                    "callrail_id": form.get("id"),
                    "form_data": form.get("form_data", {})
                }
            }
            
            contact_result = api_contact_create(contact_data, created_by="callrail")
            
            if contact_result["success"]:
                result["contact"] = contact_result["contact"]
                
                # Create opportunity from form
                form_data = form.get("form_data", {})
                opp_data = {
                    "contact_id": contact_result["contact"]["id"],
                    "business_line": infer_business_line_from_form(form_data),
                    "title": f"Web Form - {first_name} {last_name}",
                    "value": parse_budget(form_data.get("budget", "")),
                    "expected_close_date": None,
                    "assigned_to": "usr_rep_1",
                    "notes": f"Form submission: {form_data}"
                }
                
                opp_result = api_deal_create(opp_data, created_by="callrail")
                if opp_result["success"]:
                    result["opportunity"] = opp_result["deal"]
                
                result["success"] = True
            else:
                result["error"] = contact_result.get("errors", ["Unknown error"])
        
        else:
            result["error"] = "Unknown webhook type"
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def map_callrail_source(source: str) -> str:
    """Map CallRail source to CRM source"""
    source_map = {
        "Google Ads": "google",
        "Google Organic": "google",
        "Facebook": "facebook",
        "Instagram": "instagram",
        "Direct": "website",
        "Referral": "referral",
        "Bing": "other"
    }
    return source_map.get(source, "other")


def infer_business_line(source: str) -> str:
    """Infer business line from CallRail source/tracking number"""
    source_lower = source.lower()
    if "service" in source_lower or "cleaning" in source_lower:
        return "service"
    elif "repair" in source_lower or "fix" in source_lower:
        return "repair"
    elif "remodel" in source_lower or "renovation" in source_lower or "build" in source_lower:
        return "remodel"
    return "service"  # Default


def infer_business_line_from_form(form_data: dict) -> str:
    """Infer business line from form data"""
    service_type = form_data.get("service_type", "").lower()
    if "service" in service_type or "cleaning" in service_type or "maintenance" in service_type:
        return "service"
    elif "repair" in service_type or "fix" in service_type or "pump" in service_type:
        return "repair"
    elif "remodel" in service_type or "renovation" in service_type or "build" in service_type or "construction" in service_type:
        return "remodel"
    return "service"


def parse_budget(budget_str: str) -> float:
    """Parse budget string to numeric value"""
    try:
        # Handle formats like "$25,000-$50,000" or "$5,000"
        budget_str = budget_str.replace("$", "").replace(",", "")
        if "-" in budget_str:
            # Take the average of the range
            parts = budget_str.split("-")
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            return (low + high) / 2
        else:
            return float(budget_str)
    except:
        return None