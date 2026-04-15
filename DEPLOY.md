# Love Pool Care CRM - Web UI Deployment Guide

## Quick Start (Local Development)

```bash
# Navigate to web directory
cd data/crm/web

# Install dependencies
pip install flask flask-cors

# Run the app
python app.py

# Open browser
open http://localhost:5000
```

## Production Deployment Options

### Option 1: PythonAnywhere (Easiest)

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload files via Git or SFTP
3. Create a new web app with Flask
4. Set WSGI file to point to `app.py`
5. Done!

### Option 2: VPS/Dedicated Server

**Requirements:**
- Python 3.8+
- Nginx (reverse proxy)
- Gunicorn (WSGI server)

**Setup:**

```bash
# Install dependencies
pip install flask flask-cors gunicorn

# Test with gunicorn
gunicorn -w 4 -b 127.0.0.1:8000 app:app

# Nginx config
server {
    listen 80;
    server_name crm.lovepoolcare.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static {
        alias /path/to/crm/web/static;
        expires 1y;
    }
}
```

### Option 3: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
# Build and run
docker build -t lovepool-crm .
docker run -p 5000:5000 lovepool-crm
```

## Configuration

### Environment Variables

Create `.env` file:

```bash
FLASK_ENV=production
FLASK_SECRET_KEY=your-secret-key-here
DATABASE_PATH=/path/to/crm.db
```

### Authentication (To Be Implemented)

Currently no auth. For production, add:

```python
from flask_login import LoginManager, login_required

login_manager = LoginManager()
login_manager.init_app(app)

@app.route('/login')
def login():
    # Implement login
    pass

@app.before_request
def require_login():
    if request.endpoint not in ['login', 'static']:
        # Check auth
        pass
```

## Database

The SQLite database is at `data/crm/crm.db`.

**Backup:**
```bash
cp data/crm/crm.db data/crm/crm_backup_$(date +%Y%m%d).db
```

**Migrate from v1:**
```python
# Run migration script (if needed)
python migrate_v1_to_v2.py
```

## Features Available

✅ Dashboard with stats  
✅ Pipeline kanban view (Service/Repair/Remodel)  
✅ Contact management (CRUD)  
✅ Deal management with stage transitions  
✅ Activity logging  
✅ Sales reporting  
✅ Mobile responsive  

## Next Steps

1. **Add authentication** - Login/logout for reps
2. **Email notifications** - Follow-up reminders
3. **PoolBrain integration** - Sync customers/jobs
4. **Lead capture forms** - Website integration

## Support

Questions? Check the main README at `data/crm/README.md`