#!/bin/bash
# Quick deployment script for Netlify + Render

set -e

echo "🚀 Voice AI Deployment Script"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check for required tools
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 found${NC}"
        return 0
    fi
}

echo "Checking prerequisites..."
check_command git
check_command curl

# Get configuration
echo ""
echo -e "${YELLOW}Configuration${NC}"
echo "=============="

read -p "Enter your GitHub repository URL (e.g., https://github.com/username/voice-ai): " REPO_URL
read -p "Enter your Render backend URL (e.g., https://voice-ai-backend.onrender.com): " BACKEND_URL
read -p "Enter your LiveKit URL (e.g., wss://your-project.livekit.cloud): " LIVEKIT_URL

# Update configuration files
echo ""
echo -e "${YELLOW}Updating configuration files...${NC}"

# Update netlify.toml
sed -i.bak "s|https://your-backend-url.onrender.com|$BACKEND_URL|g" netlify.toml
echo -e "${GREEN}✓ Updated netlify.toml${NC}"

# Update frontend environment
cat > frontend/.env.production << EOF
NEXT_PUBLIC_LIVEKIT_URL=$LIVEKIT_URL
LIVEKIT_URL=$LIVEKIT_URL
EOF
echo -e "${GREEN}✓ Created frontend/.env.production${NC}"

# Git operations
echo ""
echo -e "${YELLOW}Preparing for deployment...${NC}"

if [ ! -d .git ]; then
    echo "Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit for deployment"
else
    echo "Git repository already initialized"
fi

# Check if remote exists
if ! git remote get-url origin &>/dev/null; then
    if [ ! -z "$REPO_URL" ]; then
        git remote add origin $REPO_URL
        echo -e "${GREEN}✓ Added remote origin${NC}"
    fi
fi

# Commit changes
git add -A
git commit -m "Prepare for Netlify + Render deployment" || echo "No changes to commit"

# Push to GitHub
echo ""
echo -e "${YELLOW}Pushing to GitHub...${NC}"
if git push origin main 2>/dev/null || git push origin master 2>/dev/null; then
    echo -e "${GREEN}✓ Pushed to GitHub${NC}"
else
    echo -e "${RED}❌ Failed to push. Please push manually:${NC}"
    echo "  git push -u origin main"
fi

# Instructions
echo ""
echo -e "${GREEN}🎉 Preparation Complete!${NC}"
echo "========================"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. ${GREEN}Deploy Backend to Render:${NC}"
echo "   → Go to https://dashboard.render.com"
echo "   → Click 'New' → 'Blueprint'"
echo "   → Connect your GitHub repo"
echo "   → Add environment variables in Render dashboard"
echo "   → Upload Google Cloud credentials to /app/credentials/"
echo ""
echo "2. ${GREEN}Deploy Frontend to Netlify:${NC}"
echo "   → Go to https://app.netlify.com"
echo "   → Click 'Add new site' → 'Import from Git'"
echo "   → Connect your GitHub repo"
echo "   → Build settings:"
echo "     * Base directory: frontend"
echo "     * Build command: npm run build"
echo "     * Publish directory: out"
echo "   → Add environment variables"
echo ""
echo "3. ${GREEN}Test your deployment:${NC}"
echo "   → Open your Netlify URL"
echo "   → Click 'Tap to Connect'"
echo "   → Say 'Hello' or 'Namaskaram'"
echo ""
echo -e "${YELLOW}Your app will be live at:${NC}"
echo "  Frontend: https://your-app-name.netlify.app"
echo "  Backend: $BACKEND_URL"
echo ""
echo -e "${GREEN}Good luck! 🚀${NC}"
