#!/usr/bin/env python3
"""
WSGI entry point for Railway
Handles PORT environment variable properly
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, '/app')
sys.path.insert(0, '/Users/lobzy/.openclaw/workspace/data/crm')

# Get PORT from environment
port = os.environ.get('PORT', '5000')
print(f"PORT environment variable: {port}")
print(f"All environment variables: {dict(os.environ)}")

# Import the Flask app
from app import app

if __name__ == "__main__":
    # This won't be used by gunicorn, but useful for testing
    app.run(host='0.0.0.0', port=int(port))