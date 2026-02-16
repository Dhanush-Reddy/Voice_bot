#!/bin/bash
# Production Deployment Script for Voice AI
# Run this on your production server

set -e

echo "🚀 Starting Production Deployment for Voice AI"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
   echo -e "${RED}❌ Please run as root or with sudo${NC}"
   exit 1
fi

# Get domain name
read -p "Enter your domain name (e.g., voiceai.yourdomain.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}❌ Domain name is required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Domain: $DOMAIN${NC}"

# Update system
echo -e "${YELLOW}📦 Updating system packages...${NC}"
apt-get update && apt-get upgrade -y

# Install required packages
echo -e "${YELLOW}📦 Installing required packages...${NC}"
apt-get install -y \
    docker.io \
    docker-compose \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    git \
    ufw

# Start Docker
echo -e "${YELLOW}🐳 Starting Docker...${NC}"
systemctl start docker
systemctl enable docker

# Create app directory
APP_DIR="/opt/voice-ai"
echo -e "${YELLOW}📁 Creating application directory: $APP_DIR${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# Clone repository (or copy files)
echo -e "${YELLOW}📥 Setting up application files...${NC}"
# Note: In production, you would clone from git or copy files
# git clone https://github.com/yourusername/voice-ai.git .

# Create credentials directory
mkdir -p credentials

# Setup environment file
echo -e "${YELLOW}⚙️  Setting up environment configuration...${NC}"
cat > .env << EOF
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-credentials.json

# Application Configuration
AGENT_POOL_SIZE=3
ENVIRONMENT=production
EOF

echo -e "${YELLOW}⚠️  IMPORTANT: Please edit .env file with your actual credentials${NC}"

# Update nginx config with domain
sed -i "s/YOUR_DOMAIN.COM/$DOMAIN/g" nginx/nginx.conf

# Setup firewall
echo -e "${YELLOW}🔥 Configuring firewall...${NC}"
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Create Docker network
echo -e "${YELLOW}🌐 Creating Docker network...${NC}"
docker network create voice-network 2>/dev/null || true

# Build and start services
echo -e "${YELLOW}🏗️  Building Docker images...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 10

# Check health
echo -e "${YELLOW}🏥 Checking service health...${NC}"
if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is healthy${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
fi

# Setup SSL with Certbot
echo -e "${YELLOW}🔒 Setting up SSL certificates...${NC}"
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || true

# Reload nginx
echo -e "${YELLOW}🔄 Reloading Nginx...${NC}"
nginx -t && systemctl reload nginx

# Setup auto-renewal for SSL
echo -e "${YELLOW}🔄 Setting up SSL auto-renewal...${NC}"
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

# Create systemd service for auto-start
echo -e "${YELLOW}📝 Creating systemd service...${NC}"
cat > /etc/systemd/system/voice-ai.service << EOF
[Unit]
Description=Voice AI Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable voice-ai.service

echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "=============================================="
echo -e "${GREEN}Your Voice AI is now running at: https://$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT NEXT STEPS:${NC}"
echo "1. Copy your Google Cloud credentials JSON to: $APP_DIR/credentials/google-credentials.json"
echo "2. Update the .env file with your actual credentials: nano $APP_DIR/.env"
echo "3. Restart the services: docker-compose -f docker-compose.prod.yml restart"
echo ""
echo -e "${YELLOW}📋 Useful Commands:${NC}"
echo "  View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  Restart: docker-compose -f docker-compose.prod.yml restart"
echo "  Stop: docker-compose -f docker-compose.prod.yml down"
echo "  Update: docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo -e "${GREEN}✨ Your voice AI is ready to use!${NC}"
