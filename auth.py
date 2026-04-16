#!/usr/bin/env python3
"""
Authentication module for Love Pool Care CRM
Simple admin-based authentication using Flask-Login
"""

import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Blueprint for auth routes
auth_bp = Blueprint('auth', __name__)

class AdminUser(UserMixin):
    """Simple admin user class"""
    def __init__(self, id='admin'):
        self.id = id
    
    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    """Load user from session"""
    if user_id == 'admin':
        return AdminUser()
    return None

def verify_admin_password(password):
    """Verify admin password against env var"""
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if not admin_password:
        # Default password for development (CHANGE IN PRODUCTION!)
        admin_password = 'lovepool2024'
    return password == admin_password

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    # If already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        if username == 'admin' and verify_admin_password(password):
            user = AdminUser()
            login_user(user, remember=request.form.get('remember_me') == 'on')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

# Public routes that don't require authentication
PUBLIC_ROUTES = [
    'auth.login',
    'auth.logout',
    'callrail_webhook',  # Webhook has its own auth
    'static',
]

def is_public_route(endpoint):
    """Check if route is public"""
    if not endpoint:
        return False
    return endpoint in PUBLIC_ROUTES or endpoint.startswith('static')

def init_auth(app):
    """Initialize authentication for the app"""
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)
    
    # Check if admin password is set
    if not os.environ.get('ADMIN_PASSWORD'):
        print("WARNING: ADMIN_PASSWORD not set. Using default password. Set ADMIN_PASSWORD env var for security.")