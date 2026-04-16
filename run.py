#!/usr/bin/env python3
"""
Production runner for Railway
"""
import os
import sys
import subprocess

# Debug
print("Starting CRM...")
print(f"Current directory: {os.getcwd()}")

# Railway always sets PORT, but let's check all vars
for key, value in sorted(os.environ.items()):
    print(f"  {key}={value}")

# Try to get port - Railway should set this
port = os.environ.get('PORT')
if port:
    try:
        int(port)
        print(f"Using PORT from env: {port}")
    except ValueError:
        print(f"PORT is not a number: {port!r}")
        print("Falling back to default 5000")
        port = '5000'
else:
    print("PORT not set, using default 5000")
    port = '5000'

# Build gunicorn command
cmd = [
    'gunicorn',
    '-w', '4',
    '-b', f'0.0.0.0:{port}',
    '--timeout', '120',
    '--access-logfile', '-',
    '--error-logfile', '-',
    'app:app'
]

print(f"Running: {cmd}")
sys.stdout.flush()

# Run gunicorn
os.execvp('gunicorn', cmd)