#!/usr/bin/env python3
"""
Love Pool Care CRM - Web Application
Flask-based web UI for the CRM
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from crm_api_v2 import (
    api_contact_create, api_contact_get, api_contact_search, api_contact_update,
    api_deal_create, api_deal_get, api_deal_update_stage, api_deal_close, api_deal_list,
    api_activity_create, api_activity_list,
    api_pipeline_view, api_dashboard, api_report_sales, api_reference_data
)
from crm_db import init_db
import json
from datetime import datetime

# Initialize database
init_db()

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
CORS(app)

# ============ ROUTES ============

@app.route('/')
def dashboard():
    """Main dashboard"""
    result = api_dashboard()
    if not result['success']:
        return render_template('error.html', error=result.get('error', 'Unknown error'))
    
    return render_template('dashboard.html', data=result)

@app.route('/contacts')
def contacts_list():
    """Contacts list page"""
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    limit = 20
    offset = (page - 1) * limit
    
    if query:
        result = api_contact_search(query, limit=limit, offset=offset)
    else:
        result = api_contact_search('', limit=limit, offset=offset)
    
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    return render_template('contacts.html', 
                         contacts=result.get('contacts', []),
                         total=result.get('total', 0),
                         page=page,
                         limit=limit,
                         query=query)

@app.route('/contacts/new', methods=['GET', 'POST'])
def contact_new():
    """Create new contact"""
    if request.method == 'POST':
        data = {
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'company_name': request.form.get('company_name'),
            'address': {
                'street': request.form.get('address_street'),
                'city': request.form.get('address_city'),
                'state': request.form.get('address_state'),
                'zip': request.form.get('address_zip')
            },
            'source': request.form.get('source'),
            'assigned_to': request.form.get('assigned_to', 'usr_rep_1'),
            'notes': request.form.get('notes'),
            'custom_fields': {
                'pool_type': request.form.get('pool_type'),
                'pool_size': request.form.get('pool_size'),
                'budget_range': request.form.get('budget_range')
            }
        }
        
        result = api_contact_create(data, created_by='usr_rep_1')
        if result['success']:
            return redirect(url_for('contact_detail', contact_id=result['contact']['id']))
        else:
            ref = api_reference_data()
            return render_template('contact_form.html', 
                                 error=result.get('errors', ['Unknown error']),
                                 data=request.form,
                                 sources=ref.get('sources', []),
                                 users=ref.get('users', []))
    
    ref = api_reference_data()
    return render_template('contact_form.html',
                         sources=ref.get('sources', []),
                         users=ref.get('users', []))

@app.route('/contacts/<contact_id>')
def contact_detail(contact_id):
    """Contact detail page"""
    result = api_contact_get(contact_id, include_activities=True)
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    return render_template('contact_detail.html', 
                         contact=result['contact'],
                         deals=result.get('deals', []),
                         activities=result.get('activities', []))

@app.route('/deals')
def deals_list():
    """Deals list page"""
    pipeline = request.args.get('pipeline')
    stage = request.args.get('stage')
    assigned = request.args.get('assigned')
    page = int(request.args.get('page', 1))
    limit = 20
    offset = (page - 1) * limit
    
    result = api_deal_list(
        pipeline=pipeline,
        stage=stage,
        assigned_to=assigned,
        include_closed=False,
        limit=limit,
        offset=offset
    )
    
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    ref = api_reference_data()
    return render_template('deals.html',
                         deals=result.get('deals', []),
                         total=result.get('total', 0),
                         page=page,
                         limit=limit,
                         pipelines=ref.get('pipelines', {}),
                         users=ref.get('users', []))

@app.route('/deals/new', methods=['GET', 'POST'])
def deal_new():
    """Create new opportunity"""
    contact_id = request.args.get('contact_id')
    
    # Get contacts for dropdown
    contacts_result = api_contact_search('', limit=100)
    contacts = contacts_result.get('contacts', []) if contacts_result.get('success') else []
    
    if request.method == 'POST':
        try:
            data = {
                'contact_id': request.form.get('contact_id'),
                'business_line': request.form.get('business_line'),
                'title': request.form.get('title'),
                'value': float(request.form.get('value', 0)) if request.form.get('value') else None,
                'expected_close_date': request.form.get('expected_close_date'),
                'assigned_to': request.form.get('assigned_to'),
                'notes': request.form.get('notes')
            }
            
            result = api_deal_create(data, created_by='usr_rep_1')
            if result['success']:
                return redirect(url_for('deal_detail', deal_id=result['deal']['id']))
            else:
                ref = api_reference_data()
                return render_template('deal_form.html',
                                     error=result.get('errors', ['Unknown error']),
                                     data=request.form,
                                     pipelines=ref.get('pipelines', {}),
                                     users=ref.get('users', []),
                                     contacts=contacts,
                                     contact_id=contact_id)
        except Exception as e:
            ref = api_reference_data()
            return render_template('deal_form.html',
                                 error=[str(e)],
                                 data=request.form,
                                 pipelines=ref.get('pipelines', {}),
                                 users=ref.get('users', []),
                                 contacts=contacts,
                                 contact_id=contact_id)
    
    ref = api_reference_data()
    return render_template('deal_form.html',
                         pipelines=ref.get('pipelines', {}),
                         users=ref.get('users', []),
                         contacts=contacts,
                         contact_id=contact_id)

@app.route('/deals/<deal_id>')
def deal_detail(deal_id):
    """Deal detail page"""
    result = api_deal_get(deal_id)
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    return render_template('deal_detail.html',
                         deal=result['deal'],
                         contact=result.get('contact', {}),
                         activities=result.get('activities', []),
                         available_stages=result.get('available_stages', []),
                         history=result.get('history', []))

@app.route('/deals/<deal_id>/update_stage', methods=['POST'])
def deal_update_stage(deal_id):
    """Update deal stage"""
    new_stage = request.form.get('stage')
    result = api_deal_update_stage(deal_id, new_stage, updated_by='usr_rep_1')
    
    if request.is_json:
        return jsonify(result)
    
    if result['success']:
        return redirect(url_for('deal_detail', deal_id=deal_id))
    else:
        return render_template('error.html', error=result.get('errors', ['Unknown error']))

@app.route('/deals/<deal_id>/close', methods=['POST'])
def deal_close(deal_id):
    """Close deal"""
    outcome = request.form.get('outcome')
    lost_reason = request.form.get('lost_reason') if outcome == 'lost' else None
    lost_detail = request.form.get('lost_detail', '') if outcome == 'lost' else ''
    
    result = api_deal_close(deal_id, outcome, lost_reason, lost_detail, updated_by='usr_rep_1')
    
    if request.is_json:
        return jsonify(result)
    
    if result['success']:
        return redirect(url_for('deal_detail', deal_id=deal_id))
    else:
        return render_template('error.html', error=result.get('errors', ['Unknown error']))

@app.route('/pipelines/<pipeline_id>')
def pipeline_view(pipeline_id):
    """Pipeline kanban view"""
    result = api_pipeline_view(pipeline_id)
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    return render_template('pipeline.html',
                         pipeline_id=pipeline_id,
                         columns=result.get('columns', []))

@app.route('/reports/sales')
def sales_report():
    """Sales report page"""
    days = int(request.args.get('days', 30))
    user_id = request.args.get('user_id')
    
    result = api_report_sales(days=days, user_id=user_id)
    ref = api_reference_data()
    
    if not result['success']:
        return render_template('error.html', error=result.get('error'))
    
    return render_template('sales_report.html',
                         report=result,
                         users=ref.get('users', []),
                         days=days,
                         selected_user=user_id)

# ============ API ROUTES (for AJAX) ============

@app.route('/api/contacts/search')
def api_contacts_search():
    """API: Search contacts"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    result = api_contact_search(query, limit=limit)
    return jsonify(result)

@app.route('/api/activities', methods=['POST'])
def api_activity_add():
    """API: Add activity"""
    data = request.get_json()
    result = api_activity_create(data, created_by='usr_rep_1')
    return jsonify(result)

@app.route('/api/reference')
def api_ref_data():
    """API: Get reference data"""
    result = api_reference_data()
    return jsonify(result)

# ============ MAIN ============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)