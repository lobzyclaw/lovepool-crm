#!/usr/bin/env python3
"""
Fix script to recreate service and repair pipelines
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_db import get_db

def fix_pipelines():
    conn = get_db()
    cursor = conn.cursor()
    
    # Recreate service pipeline stages
    service_stages = [
        ("service", "new", "New Lead", 10, 1),
        ("service", "appointment_set", "Appointment Set", 50, 2),
        ("service", "estimate_sent", "Estimate Sent", 80, 3),
        ("service", "followed_up", "Followed Up", 85, 4),
        ("service", "won", "Closed Won", 100, 5),
        ("service", "lost", "Closed Lost", 0, 6),
    ]
    
    # Recreate repair pipeline stages
    repair_stages = [
        ("repair", "new", "New Lead", 10, 1),
        ("repair", "appointment_set", "Appointment Set", 50, 2),
        ("repair", "estimate_sent", "Estimate Sent", 80, 3),
        ("repair", "followed_up", "Followed Up", 85, 4),
        ("repair", "won", "Closed Won", 100, 5),
        ("repair", "lost", "Closed Lost", 0, 6),
    ]
    
    all_stages = service_stages + repair_stages
    
    for pipeline_id, stage, name, probability, order in all_stages:
        # Check if stage exists
        cursor.execute(
            "SELECT 1 FROM pipeline_stages WHERE pipeline_id = %s AND stage = %s",
            (pipeline_id, stage)
        )
        if not cursor.fetchone():
            # Insert new stage
            cursor.execute(
                "INSERT INTO pipeline_stages (pipeline_id, stage, stage_name, probability, stage_order) VALUES (%s, %s, %s, %s, %s)",
                (pipeline_id, stage, name, probability, order)
            )
            print(f"Added: {pipeline_id} - {name}")
        else:
            # Update existing stage
            cursor.execute(
                "UPDATE pipeline_stages SET stage_name = %s, probability = %s, stage_order = %s WHERE pipeline_id = %s AND stage = %s",
                (name, probability, order, pipeline_id, stage)
            )
            print(f"Updated: {pipeline_id} - {name}")
    
    conn.commit()
    conn.close()
    
    print("\nService and Repair pipelines restored!")

if __name__ == '__main__':
    fix_pipelines()