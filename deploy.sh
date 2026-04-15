#!/bin/bash

# Love Pool Care CRM - Deployment Script
# Usage: ./deploy.sh

echo "🚀 Love Pool Care CRM Deployment"
echo "================================"

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial CRM deployment"
fi

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI not found. Install with: brew install gh"
    exit 1
fi

# Check if logged into GitHub
if ! gh auth status &> /dev/null; then
    echo "🔑 Please login to GitHub:"
    gh auth login
fi

# Create GitHub repo if not exists
REPO_NAME="lovepool-crm"
if ! gh repo view "$REPO_NAME" &> /dev/null; then
    echo "📁 Creating GitHub repository..."
    gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
else
    echo "📁 Repository exists, pushing changes..."
    git add .
    git commit -m "Update $(date +%Y-%m-%d-%H:%M)" || true
    git push origin main
fi

echo ""
echo "✅ Code pushed to GitHub!"
echo ""
echo "Next steps:"
echo "1. Go to https://railway.app"
echo "2. Click 'New Project' → 'Deploy from GitHub repo'"
echo "3. Select '$REPO_NAME'"
echo "4. Railway will auto-deploy using Dockerfile"
echo ""
echo "Or run: railway up (if Railway CLI is installed)"