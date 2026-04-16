#!/usr/bin/env python3
"""
Sample data for Love Pool Care CRM
Run this to populate the database with test data
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_db import init_db, get_db
from crm_api_v2 import (
    api_contact_create, api_deal_create, api_deal_update_stage,
    api_deal_close, api_activity_create
)
from datetime import datetime, timedelta

def add_sample_data():
    """Add sample contacts and deals"""
    print("Adding sample data...")
    
    # Sample contacts
    contacts = [
        {
            "first_name": "Michael",
            "last_name": "Harrington",
            "phone": "+14805551234",
            "email": "mike.h@email.com",
            "company_name": "Harrington Residence",
            "address": {
                "street": "1234 Camelback Rd",
                "city": "Paradise Valley",
                "state": "AZ",
                "zip": "85253"
            },
            "source": "referral",
            "assigned_to": "usr_rep_1",
            "notes": "High-value remodel prospect. Referred by Johnson.",
            "custom_fields": {"pool_type": "resort_style", "pool_size": "large", "budget_range": "75k-100k"}
        },
        {
            "first_name": "Jennifer",
            "last_name": "Walsh",
            "phone": "+14805555678",
            "email": "jen.walsh@email.com",
            "company_name": None,
            "address": {
                "street": "5678 Scottsdale Rd",
                "city": "Scottsdale",
                "state": "AZ",
                "zip": "85251"
            },
            "source": "google",
            "assigned_to": "usr_rep_2",
            "notes": "Weekly service inquiry. Pool needs cleaning.",
            "custom_fields": {"pool_type": "standard", "pool_size": "medium", "budget_range": "3k-5k"}
        },
        {
            "first_name": "David",
            "last_name": "Chen",
            "phone": "+14805559012",
            "email": "david.chen@email.com",
            "company_name": "Chen Family LLC",
            "address": {
                "street": "9012 University Dr",
                "city": "Tempe",
                "state": "AZ",
                "zip": "85281"
            },
            "source": "website",
            "assigned_to": "usr_rep_1",
            "notes": "Pump repair needed. Urgent.",
            "custom_fields": {"pool_type": "standard", "pool_size": "small", "budget_range": "1k-2k"}
        },
        {
            "first_name": "Robert",
            "last_name": "Martinez",
            "phone": "+14805553456",
            "email": "robert.m@email.com",
            "company_name": None,
            "address": {
                "street": "3456 Main St",
                "city": "Mesa",
                "state": "AZ",
                "zip": "85201"
            },
            "source": "facebook",
            "assigned_to": "usr_rep_3",
            "notes": "Remodel consultation scheduled.",
            "custom_fields": {"pool_type": "infinity_edge", "pool_size": "medium", "budget_range": "25k-35k"}
        },
        {
            "first_name": "Amanda",
            "last_name": "Thompson",
            "phone": "+14805557890",
            "email": "amanda.t@email.com",
            "company_name": None,
            "address": {
                "street": "7890 Central Ave",
                "city": "Phoenix",
                "state": "AZ",
                "zip": "85012"
            },
            "source": "yard_sign",
            "assigned_to": "usr_rep_2",
            "notes": "New weekly service. Just moved in.",
            "custom_fields": {"pool_type": "standard", "pool_size": "medium", "budget_range": "3k-5k"}
        }
    ]
    
    created_contacts = []
    for contact_data in contacts:
        result = api_contact_create(contact_data, created_by="usr_scott_dance")
        if result['success']:
            created_contacts.append(result['contact'])
            print(f"  Created contact: {contact_data['first_name']} {contact_data['last_name']}")
        else:
            print(f"  Failed to create {contact_data['first_name']}: {result.get('errors')}")
    
    if not created_contacts:
        print("No contacts created, skipping deals")
        return
    
    # Sample deals
    deals = [
        # Remodel deal - in proposal stage
        {
            "contact_id": created_contacts[0]['id'],
            "business_line": "remodel",
            "title": "Full Pool Remodel - Paradise Valley",
            "value": 85000,
            "assigned_to": "usr_rep_1",
            "notes": "Complete remodel with new tile, coping, and equipment. Proposal sent."
        },
        # Service deal - qualified
        {
            "contact_id": created_contacts[1]['id'],
            "business_line": "service",
            "title": "Weekly Pool Service - Scottsdale",
            "value": 4200,
            "assigned_to": "usr_rep_2",
            "notes": "Weekly cleaning and chemical service. Estimate sent, awaiting approval."
        },
        # Repair deal - closed won
        {
            "contact_id": created_contacts[2]['id'],
            "business_line": "repair",
            "title": "Pump Replacement - Tempe",
            "value": 2400,
            "assigned_to": "usr_rep_1",
            "notes": "Replaced main pump and motor. Completed yesterday."
        },
        # Remodel deal - closed lost
        {
            "contact_id": created_contacts[3]['id'],
            "business_line": "remodel",
            "title": "Deck Resurfacing - Mesa",
            "value": 18500,
            "assigned_to": "usr_rep_3",
            "notes": "Lost to competitor. Price was too high."
        },
        # Service deal - new
        {
            "contact_id": created_contacts[4]['id'],
            "business_line": "service",
            "title": "Weekly Service - Phoenix",
            "value": 3600,
            "assigned_to": "usr_rep_2",
            "notes": "New lead from yard sign. Needs follow-up call."
        }
    ]
    
    created_deals = []
    for deal_data in deals:
        result = api_deal_create(deal_data, created_by="usr_scott_dance")
        if result['success']:
            created_deals.append(result['deal'])
            print(f"  Created deal: {deal_data['title']}")
        else:
            print(f"  Failed to create deal: {result.get('errors')}")
    
    # Move deals through pipeline stages
    if len(created_deals) >= 5:
        # Deal 0: Remodel - move to proposal
        api_deal_update_stage(created_deals[0]['id'], 'proposal', 'usr_rep_1')
        print(f"  Moved deal to proposal: {created_deals[0]['title']}")
        
        # Deal 1: Service - move to estimate_sent
        api_deal_update_stage(created_deals[1]['id'], 'estimate_sent', 'usr_rep_2')
        print(f"  Moved deal to estimate_sent: {created_deals[1]['title']}")
        
        # Deal 2: Repair - close as won
        api_deal_close(created_deals[2]['id'], 'won', updated_by='usr_rep_1')
        print(f"  Closed deal as won: {created_deals[2]['title']}")
        
        # Deal 3: Remodel - close as lost
        api_deal_close(created_deals[3]['id'], 'lost', 'competitor', 'Went with Desert Pools', 'usr_rep_3')
        print(f"  Closed deal as lost: {created_deals[3]['title']}")
        
        # Deal 4: Service - stays at new
        print(f"  Left deal at new: {created_deals[4]['title']}")
    
    # Add some activities
    activities = [
        {
            "type": "call",
            "contact_id": created_contacts[0]['id'],
            "deal_id": created_deals[0]['id'] if created_deals else None,
            "performed_by": "usr_rep_1",
            "duration_minutes": 30,
            "outcome": "proposal_requested",
            "notes": "Client wants full remodel proposal. Budget confirmed at $85K.",
            "follow_up_required": True,
            "follow_up_date": (datetime.now() + timedelta(days=3)).isoformat()
        },
        {
            "type": "email",
            "contact_id": created_contacts[1]['id'],
            "deal_id": created_deals[1]['id'] if len(created_deals) > 1 else None,
            "performed_by": "usr_rep_2",
            "duration_minutes": 15,
            "outcome": "estimate_sent",
            "notes": "Sent weekly service estimate. Waiting for approval.",
            "follow_up_required": True,
            "follow_up_date": (datetime.now() + timedelta(days=2)).isoformat()
        },
        {
            "type": "site_visit",
            "contact_id": created_contacts[2]['id'],
            "deal_id": created_deals[2]['id'] if len(created_deals) > 2 else None,
            "performed_by": "usr_rep_1",
            "duration_minutes": 120,
            "outcome": "completed",
            "notes": "Replaced pump and motor. Tested system. Client satisfied.",
            "follow_up_required": False
        }
    ]
    
    for activity_data in activities:
        if activity_data['contact_id']:
            result = api_activity_create(activity_data, created_by="usr_scott_dance")
            if result['success']:
                print(f"  Created activity: {activity_data['type']}")
    
    print("\nSample data added successfully!")
    print(f"  Contacts: {len(created_contacts)}")
    print(f"  Deals: {len(created_deals)}")

if __name__ == "__main__":
    init_db()
    add_sample_data()