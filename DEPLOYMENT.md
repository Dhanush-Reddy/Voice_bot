# 🚀 DEPLOYMENT GUIDE - Netlify + Render

Deploy your Voice AI application with **Netlify** (Frontend) + **Render** (Backend).

## 📋 Prerequisites

1. **Netlify account**: https://app.netlify.com/signup
2. **Render account**: https://render.com/signup
3. **LiveKit Cloud account**: https://cloud.livekit.io (already set up)
4. **Google Cloud account** with Vertex AI enabled (already set up)
5. **GitHub/GitLab** repository with your code

---

## 🎯 QUICK DEPLOYMENT (5 minutes)

### Step 1: Deploy Backend to Render

#### Option A: Using Render Blueprint (Recommended)

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/voice-ai.git
   git push -u origin main
   ```

2. **Go to Render Dashboard**: https://dashboard.render.com

3. **Click "New" → "Blueprint"**

4. **Connect your GitHub repo**

5. **Render will automatically detect `render.yaml`** and configure the service

6. **Add Environment Variables** in Render Dashboard:
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   GOOGLE_CLOUD_PROJECT=your-gcp-project-id
   GOOGLE_CLOUD_LOCATION=us-central1
   ```

7. **Upload Google Credentials**:
   - Go to Render Dashboard → Your Service → Disks
   - SSH into the disk or use Render's shell
   - Create `/app/credentials/google-credentials.json` with your service account JSON

8. **Click "Deploy"**

#### Option B: Manual Deploy

1. **Go to Render Dashboard** → "New" → "Web Service"

2. **Connect your GitHub repo**

3. **Configure**:
   - **Name**: `voice-ai-backend`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `backend/Dockerfile.backend`
   - **Plan**: Standard ($7/month) or Free (limited)

4. **Add Environment Variables** (same as above)

5. **Add Disk**:
   - Name: `credentials`
   - Mount Path: `/app/credentials`
   - Size: 1 GB

6. **Deploy**

---

### Step 2: Get Your Backend URL

After deployment, Render will give you a URL like:
```
https://voice-ai-backend.onrender.com
```

**Copy this URL** - you'll need it for the frontend.

---

### Step 3: Update Frontend for Production

1. **Update `netlify.toml`**:
   ```toml
   [[redirects]]
     from = "/api/*"
     to = "https://voice-ai-backend.onrender.com/api/:splat"  # <-- YOUR BACKEND URL
     status = 200
     force = true
   ```

2. **Commit and push**:
   ```bash
   git add netlify.toml
   git commit -m "Update backend URL for production"
   git push
   ```

---

### Step 4: Deploy Frontend to Netlify

#### Option A: Git Integration (Recommended)

1. **Go to Netlify**: https://app.netlify.com

2. **Click "Add new site" → "Import an existing project"**

3. **Connect to GitHub** and select your repo

4. **Configure build settings**:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `out`

5. **Add Environment Variables**:
   ```
   NEXT_PUBLIC_LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_URL=wss://your-project.livekit.cloud
   ```

6. **Click "Deploy site"**

#### Option B: Drag & Drop

1. **Build locally**:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. **Go to Netlify** → "Sites" → "Add new site" → "Deploy manually"

3. **Drag and drop** the `frontend/out` folder

---

### Step 5: Configure Custom Domain (Optional)

1. **Netlify**: Go to Site settings → Domain management → Add custom domain
2. **Render**: Go to Service settings → Custom domains → Add domain

---

## 🔧 POST-DEPLOYMENT SETUP

### Test Your Deployment

1. **Open your Netlify URL** (e.g., `https://voice-ai.netlify.app`)

2. **Click "Tap to Connect"**

3. **Allow microphone access**

4. **Say "Hello" or "Namaskaram"**

5. **You should hear the AI respond!**

---

### Troubleshooting

#### Issue: "Cannot connect to backend"

**Solution**: Check CORS settings
- Ensure backend has CORS enabled for your Netlify domain
- The `render.yaml` already includes CORS headers

#### Issue: "SSL/HTTPS errors"

**Solution**: 
- Both Netlify and Render provide SSL automatically
- Ensure you're using `https://` not `http://`

#### Issue: "Google credentials not found"

**Solution**:
1. SSH into your Render disk:
   ```bash
   render ssh YOUR_SERVICE_NAME
   ```
2. Create the credentials file:
   ```bash
   mkdir -p /app/credentials
   nano /app/credentials/google-credentials.json
   # Paste your Google service account JSON
   ```

#### Issue: "LiveKit connection failed"

**Solution**:
- Verify LiveKit URL starts with `wss://` not `https://`
- Check LiveKit API key/secret are correct
- Ensure LiveKit Cloud project is active

---

## 💰 COST ESTIMATION

### Free Tier
- **Netlify**: Free (100GB bandwidth/month)
- **Render**: Free (limited hours, sleeps after 15min inactivity)
- **LiveKit**: Free tier (10,000 minutes/month)
- **Google Cloud**: Free tier ($300 credits, then ~$0.0001/request)

**Total: $0/month** (for light usage)

### Production Tier
- **Netlify**: $19/month (Pro plan)
- **Render**: $7/month (Standard plan)
- **LiveKit**: $0.004/minute (~$120/month for 1000 hours)
- **Google Cloud**: ~$10-50/month (depends on usage)

**Total: ~$150-200/month** (for production)

---

## 🔄 UPDATING YOUR DEPLOYMENT

### Update Frontend

```bash
git add .
git commit -m "Update frontend"
git push
# Netlify auto-deploys on push
```

### Update Backend

```bash
git add .
git commit -m "Update backend"
git push
# Render auto-deploys on push (if auto-deploy enabled)
```

Or manually in Render dashboard: "Manual Deploy" → "Deploy latest commit"

---

## 📊 MONITORING

### Netlify Analytics
- Go to your site → Analytics
- Monitor bandwidth, build times, popular pages

### Render Monitoring
- Go to your service → Metrics
- Monitor CPU, memory, response times
- View logs in real-time

### LiveKit Monitoring
- Go to https://cloud.livekit.io
- Monitor connection quality, minutes used

---

## 🎉 YOU'RE LIVE!

Your Voice AI is now deployed at:
- **Frontend**: https://your-app.netlify.app
- **Backend**: https://voice-ai-backend.onrender.com

**Share your URL and let people try it!** 🚀

---

## 🆘 NEED HELP?

### Useful Commands

```bash
# Check Render logs
render logs voice-ai-backend --tail

# Restart Render service
render services restart voice-ai-backend

# SSH into Render disk
render ssh voice-ai-backend

# Check Netlify build logs
# Go to Netlify Dashboard → Your Site → Deploys
```

### Support Links
- **Netlify Docs**: https://docs.netlify.com
- **Render Docs**: https://render.com/docs
- **LiveKit Docs**: https://docs.livekit.io

---

**Your Voice AI is now accessible from anywhere in the world!** 🌍🎙️
