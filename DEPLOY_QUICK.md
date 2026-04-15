# Quick Deploy Guide

## One-Command Deploy

```bash
cd data/crm/web
./deploy.sh
```

This will:
1. Initialize git (if needed)
2. Create GitHub repo
3. Push code
4. Give you Railway next steps

## Manual Steps (if script fails)

### 1. GitHub
```bash
git init
git add .
git commit -m "v1.0"
gh repo create lovepool-crm --public --push --source=.
```

### 2. Railway
- Go to [railway.app](https://railway.app)
- New Project → Deploy from GitHub
- Select `lovepool-crm`
- Railway auto-detects Dockerfile and deploys

### 3. Done
Your CRM will be live at `https://lovepool-crm.up.railway.app`

## Environment Variables (in Railway dashboard)

Set these if needed:
- `FLASK_ENV=production`
- `SECRET_KEY=your-secret-key`

## Database

SQLite is included. For production PostgreSQL:
1. Add PostgreSQL in Railway dashboard
2. Update `DATABASE_URL` in app.py

## Custom Domain

In Railway dashboard:
1. Go to Settings → Domains
2. Add `crm.lovepoolcare.com`
3. Update DNS CNAME to Railway URL