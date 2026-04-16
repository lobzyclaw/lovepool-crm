#!/usr/bin/env python3
"""
Migration script to remove old pipeline stages
Run this once to clean up service and repair pipelines
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_db import get_db

def migrate():
    conn = get_db()
    cursor = conn.cursor()
    
    # Delete old stages
    cursor.execute("""
        DELETE FROM pipeline_stages 
        WHERE pipeline_id IN ('service', 'repair') 
        AND stage IN ('qualified', 'appointment_occurred')
    """)
    
    # Fix order numbers for remaining stages
    stages_to_fix = [
        ('service', 'new', 1),
        ('service', 'appointment_set', 2),
        ('service', 'estimate_sent', 3),
        ('service', 'followed_up', 4),
        ('service', 'won', 5),
        ('service', 'lost', 6),
        ('repair', 'new', 1),
        ('repair', 'appointment_set', 2),
        ('repair', 'estimate_sent', 3),
        ('repair', 'followed_up', 4),
        ('repair', 'won', 5),
        ('repair', 'lost', 6),
    ]
    
    for pipeline_id, stage, order in stages_to_fix:
        cursor.execute("""
            UPDATE pipeline_stages 
            SET stage_order = %s 
            WHERE pipeline_id = %s AND stage = %s
        """, (order, pipeline_id, stage))
    
    conn.commit()
    conn.close()
    
    print("Migration complete!")
    print("Removed: qualified, appointment_occurred from service and repair")
    print("Fixed stage order numbers")

if __name__ == '__main__':
    migrate()