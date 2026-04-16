#!/usr/bin/env python3
"""
PoolBrain Integration Module
Syncs closed service deals to PoolBrain as customers and recurring jobs
"""

import os
import requests
import json
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

POOLBRAIN_API_KEY = os.environ.get('POOLBRAIN_API_KEY')
POOLBRAIN_BASE_URL = os.environ.get('POOLBRAIN_BASE_URL', 'https://api.poolbrain.com/v1')

def _get_headers() -> Dict[str, str]:
    """Get API headers with auth"""
    return {
        'Authorization': f'Bearer {POOLBRAIN_API_KEY}',
        'Content-Type': 'application/json'
    }

def create_customer(contact_data: Dict) -> Tuple[bool, Any]:
    """
    Create a customer in PoolBrain from CRM contact data
    
    Args:
        contact_data: Dict with contact info from CRM
        
    Returns:
        (success: bool, result: dict or error message)
    """
    if not POOLBRAIN_API_KEY:
        return False, "POOLBRAIN_API_KEY not configured"
    
    # Map CRM contact to PoolBrain customer format
    customer_payload = {
        "first_name": contact_data.get('first_name'),
        "last_name": contact_data.get('last_name'),
        "email": contact_data.get('email'),
        "phone": contact_data.get('phone'),
        "company_name": contact_data.get('company_name'),
        "address": {
            "street": contact_data.get('address_street'),
            "city": contact_data.get('address_city'),
            "state": contact_data.get('address_state'),
            "zip": contact_data.get('address_zip')
        },
        "source": "crm",
        "crm_contact_id": contact_data.get('id'),
        "notes": contact_data.get('notes', ''),
        "custom_fields": {
            "pool_type": contact_data.get('custom_fields', {}).get('pool_type'),
            "pool_size": contact_data.get('custom_fields', {}).get('pool_size')
        }
    }
    
    try:
        response = requests.post(
            f"{POOLBRAIN_BASE_URL}/customers",
            headers=_get_headers(),
            json=customer_payload,
            timeout=30
        )
        
        if response.status_code == 201:
            return True, response.json()
        elif response.status_code == 409:
            # Customer already exists, try to get existing
            return _get_customer_by_phone(contact_data.get('phone'))
        else:
            return False, f"PoolBrain API error: {response.status_code} - {response.text}"
            
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def _get_customer_by_phone(phone: str) -> Tuple[bool, Any]:
    """Get existing customer by phone number"""
    try:
        response = requests.get(
            f"{POOLBRAIN_BASE_URL}/customers",
            headers=_get_headers(),
            params={'phone': phone},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('customers'):
                return True, data['customers'][0]
        
        return False, "Customer not found"
        
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def create_recurring_job(customer_id: str, deal_data: Dict, service_type: str = "weekly") -> Tuple[bool, Any]:
    """
    Create a recurring service job in PoolBrain
    
    Args:
        customer_id: PoolBrain customer ID
        deal_data: Deal info from CRM
        service_type: 'weekly', 'biweekly', or 'monthly'
        
    Returns:
        (success: bool, result: dict or error message)
    """
    if not POOLBRAIN_API_KEY:
        return False, "POOLBRAIN_API_KEY not configured"
    
    # Map service type to PoolBrain frequency
    frequency_map = {
        "weekly": 7,
        "biweekly": 14,
        "monthly": 30
    }
    
    # Calculate next service date (start tomorrow)
    next_service = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    job_payload = {
        "customer_id": customer_id,
        "job_type": "recurring_service",
        "frequency_days": frequency_map.get(service_type, 7),
        "next_service_date": next_service,
        "service_details": {
            "type": "pool_maintenance",
            "includes": ["chemical_check", "skimming", "filter_check"]
        },
        "pricing": {
            "amount": deal_data.get('value', 0),
            "currency": "USD",
            "billing_frequency": service_type
        },
        "source": "crm_deal",
        "crm_deal_id": deal_data.get('id'),
        "notes": f"Created from CRM deal: {deal_data.get('title', '')}"
    }
    
    try:
        response = requests.post(
            f"{POOLBRAIN_BASE_URL}/jobs/recurring",
            headers=_get_headers(),
            json=job_payload,
            timeout=30
        )
        
        if response.status_code == 201:
            return True, response.json()
        else:
            return False, f"PoolBrain API error: {response.status_code} - {response.text}"
            
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def get_customer_jobs(customer_id: str) -> Tuple[bool, Any]:
    """
    Get all jobs for a customer from PoolBrain
    
    Args:
        customer_id: PoolBrain customer ID
        
    Returns:
        (success: bool, result: list of jobs or error message)
    """
    if not POOLBRAIN_API_KEY:
        return False, "POOLBRAIN_API_KEY not configured"
    
    try:
        response = requests.get(
            f"{POOLBRAIN_BASE_URL}/customers/{customer_id}/jobs",
            headers=_get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"PoolBrain API error: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def sync_deal_to_poolbrain(deal_id: str, contact_data: Dict, deal_data: Dict) -> Tuple[bool, str]:
    """
    Full sync workflow: Create customer + recurring job from a closed deal
    
    Args:
        deal_id: CRM deal ID
        contact_data: Contact information
        deal_data: Deal information
        
    Returns:
        (success: bool, message: str)
    """
    # Step 1: Create or get customer
    success, customer_result = create_customer(contact_data)
    if not success:
        return False, f"Failed to create customer: {customer_result}"
    
    customer_id = customer_result.get('id')
    if not customer_id:
        return False, "No customer ID returned from PoolBrain"
    
    # Step 2: Create recurring job
    # Determine service frequency from deal value or notes
    service_type = "weekly"  # default
    deal_value = deal_data.get('value', 0)
    
    # Heuristic: higher value = more frequent service
    if deal_value < 200:
        service_type = "monthly"
    elif deal_value < 400:
        service_type = "biweekly"
    else:
        service_type = "weekly"
    
    success, job_result = create_recurring_job(customer_id, deal_data, service_type)
    if not success:
        return False, f"Customer created but job failed: {job_result}"
    
    job_id = job_result.get('id', 'unknown')
    
    return True, f"Synced to PoolBrain: Customer {customer_id}, Job {job_id}"

def check_sync_status(deal_id: str) -> Optional[Dict]:
    """
    Check if a deal has been synced to PoolBrain
    
    Args:
        deal_id: CRM deal ID
        
    Returns:
        Dict with sync status or None
    """
    # This would query PoolBrain API to check for existing customer/job
    # with matching crm_deal_id
    
    if not POOLBRAIN_API_KEY:
        return None
    
    try:
        response = requests.get(
            f"{POOLBRAIN_BASE_URL}/jobs",
            headers=_get_headers(),
            params={'crm_deal_id': deal_id},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('jobs'):
                return {
                    'synced': True,
                    'poolbrain_job_id': data['jobs'][0].get('id'),
                    'poolbrain_customer_id': data['jobs'][0].get('customer_id')
                }
        
        return {'synced': False}
        
    except requests.exceptions.RequestException:
        return None