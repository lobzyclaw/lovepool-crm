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
print(f"Files: {os.listdir('.')}")

# Get port
port = os.environ.get('PORT', '5000')
print(f"PORT env var: {port}")

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

print(f"Running: {' '.join(cmd)}")
sys.stdout.flush()

# Run gunicorn
os.execvp('gunicorn', cmd)