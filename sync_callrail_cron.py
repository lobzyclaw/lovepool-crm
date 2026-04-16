#!/usr/bin/env python3
"""
CallRail Sync Cron Job
Run this every hour to sync new calls and forms
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from callrail_api import sync_callrail_data
from datetime import datetime

def main():
    print(f"[{datetime.now()}] Starting CallRail sync...")
    
    # Sync last 2 hours (overlap to catch any missed calls)
    result = sync_callrail_data(hours=2)
    
    print(f"Calls processed: {result['calls_processed']}")
    print(f"Forms processed: {result['forms_processed']}")
    print(f"Contacts created: {result['contacts_created']}")
    print(f"Opportunities created: {result['opportunities_created']}")
    
    if result['errors']:
        print(f"Errors: {len(result['errors'])}")
        for error in result['errors'][:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    print(f"[{datetime.now()}] Sync complete.")

if __name__ == '__main__':
    main()