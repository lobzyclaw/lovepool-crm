#!/usr/bin/env python3
"""
CallRail API Integration for Love Pool Care CRM
Fetches calls and form submissions via REST API
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from crm_api_v2 import api_contact_create, api_deal_create

# Get API key from environment variable
CALLRAIL_API_KEY = os.environ.get('CALLRAIL_API_KEY')
CALLRAIL_ACCOUNT_ID = os.environ.get('CALLRAIL_ACCOUNT_ID')  # Your CallRail account ID

BASE_URL = "https://api.callrail.com/v3"

def get_headers():
    """Get API headers with authentication"""
    return {
        'Authorization': f'Token token={CALLRAIL_API_KEY}',
        'Content-Type': 'application/json'
    }

def fetch_recent_calls(hours: int = 24) -> List[Dict]:
    """
    Fetch recent calls from CallRail API
    
    Args:
        hours: How many hours back to fetch (default 24)
    
    Returns:
        List of call records
    """
    if not CALLRAIL_API_KEY or not CALLRAIL_ACCOUNT_ID:
        print("CallRail API credentials not configured")
        return []
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=hours)
    
    url = f"{BASE_URL}/a/{CALLRAIL_ACCOUNT_ID}/calls.json"
    
    params = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'per_page': 100  # Max per page
    }
    
    try:
        response = requests.get(url, headers=get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('calls', [])
    except Exception as e:
        print(f"Error fetching calls: {e}")
        return []

def fetch_recent_form_submissions(hours: int = 24) -> List[Dict]:
    """
    Fetch recent form submissions from CallRail API
    
    Args:
        hours: How many hours back to fetch (default 24)
    
    Returns:
        List of form submission records
    """
    if not CALLRAIL_API_KEY or not CALLRAIL_ACCOUNT_ID:
        print("CallRail API credentials not configured")
        return []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=hours)
    
    url = f"{BASE_URL}/a/{CALLRAIL_ACCOUNT_ID}/form_submissions.json"
    
    params = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'per_page': 100
    }
    
    try:
        response = requests.get(url, headers=get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('form_submissions', [])
    except Exception as e:
        print(f"Error fetching form submissions: {e}")
        return []

def process_call(call: Dict) -> Dict:
    """
    Process a CallRail call and create contact/opportunity
    
    Args:
        call: CallRail call record
    
    Returns:
        Result dict with contact and opportunity info
    """
    result = {"success": False, "contact": None, "opportunity": None}
    
    try:
        # Parse customer info
        customer_name = call.get('customer_name', 'Unknown Caller')
        name_parts = customer_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else 'Unknown'
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        phone = call.get('customer_phone_number')
        if not phone:
            result['error'] = 'No phone number'
            return result
        
        # Create contact
        contact_data = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': call.get('customer_email', ''),
            'company_name': None,
            'address': {'street': None, 'city': None, 'state': None, 'zip': None},
            'source': map_callrail_source(call.get('source', 'call')),
            'assigned_to': 'usr_rep_1',
            'notes': build_call_notes(call),
            'custom_fields': {
                'callrail_call_id': call.get('id'),
                'callrail_tracking_number': call.get('tracking_phone_number'),
                'call_duration': call.get('duration'),
                'call_recording': call.get('recording_url', ''),
                'call_answered': call.get('answered', False)
            }
        }
        
        contact_result = api_contact_create(contact_data, created_by='callrail_api')
        
        if contact_result['success']:
            result['contact'] = contact_result['contact']
            
            # Create opportunity for qualified calls
            duration = call.get('duration', 0)
            answered = call.get('answered', False)
            
            if answered and duration > 60:  # Qualified call
                opp_data = {
                    'contact_id': contact_result['contact']['id'],
                    'business_line': infer_business_line(call.get('source', '')),
                    'title': f"Call from {first_name} {last_name}",
                    'value': None,
                    'expected_close_date': None,
                    'assigned_to': 'usr_rep_1',
                    'notes': f"Duration: {duration}s | Source: {call.get('source', 'Unknown')} | Answered: {answered}"
                }
                
                opp_result = api_deal_create(opp_data, created_by='callrail_api')
                if opp_result['success']:
                    result['opportunity'] = opp_result['deal']
            
            result['success'] = True
        else:
            # Contact might already exist - try to find by phone
            from crm_db import db_contact_search
            _, existing = db_contact_search(phone, limit=1)
            if existing:
                result['contact'] = existing[0]
                result['success'] = True
                result['note'] = 'Contact already existed'
            else:
                result['error'] = contact_result.get('errors', ['Unknown error'])
    
    except Exception as e:
        result['error'] = str(e)
    
    return result

def process_form_submission(form: Dict) -> Dict:
    """
    Process a CallRail form submission
    
    Args:
        form: Form submission record
    
    Returns:
        Result dict with contact and opportunity info
    """
    result = {"success": False, "contact": None, "opportunity": None}
    
    try:
        # Parse customer info
        customer_name = form.get('customer_name', 'Unknown')
        name_parts = customer_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else 'Unknown'
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        phone = form.get('customer_phone_number')
        email = form.get('customer_email')
        
        if not phone and not email:
            result['error'] = 'No contact info provided'
            return result
        
        # Get form field data
        form_data = form.get('form_data', {})
        
        # Create contact
        contact_data = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'email': email,
            'company_name': None,
            'address': {'street': None, 'city': None, 'state': None, 'zip': None},
            'source': map_callrail_source(form.get('source', 'website')),
            'assigned_to': 'usr_rep_1',
            'notes': f"Form submission from {form.get('source', 'website')}. Campaign: {form.get('campaign', 'N/A')}",
            'custom_fields': {
                'callrail_form_id': form.get('id'),
                'form_fields': form_data
            }
        }
        
        contact_result = api_contact_create(contact_data, created_by='callrail_api')
        
        if contact_result['success']:
            result['contact'] = contact_result['contact']
            
            # Create opportunity from form
            opp_data = {
                'contact_id': contact_result['contact']['id'],
                'business_line': infer_business_line_from_form(form_data),
                'title': f"Web Form - {first_name} {last_name}",
                'value': parse_budget(form_data.get('budget', '')),
                'expected_close_date': None,
                'assigned_to': 'usr_rep_1',
                'notes': f"Form data: {form_data}"
            }
            
            opp_result = api_deal_create(opp_data, created_by='callrail_api')
            if opp_result['success']:
                result['opportunity'] = opp_result['deal']
            
            result['success'] = True
        else:
            result['error'] = contact_result.get('errors', ['Unknown error'])
    
    except Exception as e:
        result['error'] = str(e)
    
    return result

def sync_callrail_data(hours: int = 24) -> Dict:
    """
    Main sync function - fetch and process all recent CallRail data
    
    Args:
        hours: How many hours back to sync
    
    Returns:
        Summary of processed records
    """
    summary = {
        'calls_processed': 0,
        'forms_processed': 0,
        'contacts_created': 0,
        'opportunities_created': 0,
        'errors': []
    }
    
    # Process calls
    calls = fetch_recent_calls(hours)
    for call in calls:
        result = process_call(call)
        if result['success']:
            summary['calls_processed'] += 1
            if result.get('contact'):
                summary['contacts_created'] += 1
            if result.get('opportunity'):
                summary['opportunities_created'] += 1
        else:
            summary['errors'].append(f"Call {call.get('id')}: {result.get('error')}")
    
    # Process forms
    forms = fetch_recent_form_submissions(hours)
    for form in forms:
        result = process_form_submission(form)
        if result['success']:
            summary['forms_processed'] += 1
            if result.get('contact'):
                summary['contacts_created'] += 1
            if result.get('opportunity'):
                summary['opportunities_created'] += 1
        else:
            summary['errors'].append(f"Form {form.get('id')}: {result.get('error')}")
    
    return summary

# Helper functions (same as webhook version)
def map_callrail_source(source: str) -> str:
    """Map CallRail source to CRM source"""
    source_map = {
        'Google Ads': 'google',
        'Google Organic': 'google',
        'Facebook': 'facebook',
        'Instagram': 'instagram',
        'Direct': 'website',
        'Referral': 'referral',
        'Bing': 'other'
    }
    return source_map.get(source, 'other')

def infer_business_line(source: str) -> str:
    """Infer business line from source"""
    source_lower = source.lower()
    if 'service' in source_lower or 'cleaning' in source_lower:
        return 'service'
    elif 'repair' in source_lower or 'fix' in source_lower:
        return 'repair'
    elif 'remodel' in source_lower or 'renovation' in source_lower:
        return 'remodel'
    return 'service'

def infer_business_line_from_form(form_data: dict) -> str:
    """Infer business line from form data"""
    service_type = form_data.get('service_type', '').lower()
    if 'service' in service_type or 'cleaning' in service_type:
        return 'service'
    elif 'repair' in service_type or 'fix' in service_type:
        return 'repair'
    elif 'remodel' in service_type or 'renovation' in service_type:
        return 'remodel'
    return 'service'

def parse_budget(budget_str: str) -> Optional[float]:
    """Parse budget string to numeric value"""
    try:
        budget_str = budget_str.replace('$', '').replace(',', '')
        if '-' in budget_str:
            parts = budget_str.split('-')
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            return (low + high) / 2
        else:
            return float(budget_str)
    except:
        return None

def build_call_notes(call: Dict) -> str:
    """Build notes from call data"""
    notes = []
    notes.append(f"Source: {call.get('source', 'Unknown')}")
    notes.append(f"Duration: {call.get('duration', 0)} seconds")
    notes.append(f"Answered: {'Yes' if call.get('answered') else 'No'}")
    if call.get('recording_url'):
        notes.append(f"Recording: {call.get('recording_url')}")
    if call.get('tracking_phone_number'):
        notes.append(f"Called: {call.get('tracking_phone_number')}")
    return '\n'.join(notes)