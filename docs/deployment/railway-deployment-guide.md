# Railway.app Production Deployment Guide

## Overview
This guide walks you through deploying A Fine Wine Dynasty to Railway.app - a beginner-friendly, budget-conscious platform that scales automatically.

**Expected Monthly Cost:** $5-30 (starts free, scales with usage)

## Prerequisites
- [x] GitHub account with your code pushed
- [ ] Railway.app account (free to create)
- [ ] Stripe account (for payments - free)
- [ ] Domain name (optional, ~$12/year)

---

## Phase 1: Pre-Deployment Setup (Local)

### Step 1.1: Fix Database Migration Issue

First, let's set up your local database properly:

```bash
# Navigate to API directory
cd apps/api

# Install Python dependencies (including alembic)
pip install -r requirements.txt

# Verify alembic is installed
alembic --version
```

### Step 1.2: Configure Local Environment

Create proper `.env` file:

```bash
# Copy example to actual .env
cp .env.example .env
```

Edit `apps/api/.env` with these values:

```env
# Database Configuration (local for now)
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=afinewinedynasty
POSTGRES_PORT=5432

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT Configuration - GENERATE A NEW SECRET!
SECRET_KEY=REPLACE_WITH_RANDOM_STRING_MIN_32_CHARS
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# CORS Configuration
BACKEND_CORS_ORIGINS=["http://localhost:3000"]

# Environment
ENVIRONMENT=development
```

**CRITICAL:** Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 1.3: Run Database Migrations Locally

```bash
# From apps/api directory
alembic upgrade head
```

This should create all tables in your local PostgreSQL database.

### Step 1.4: Test Local Setup

```bash
# Terminal 1: Start API
cd apps/api
uvicorn app.main:app --reload

# Terminal 2: Start Web
cd apps/web
npm run dev
```

Visit http://localhost:3000 and verify everything works.

---

## Phase 2: Prepare for Production

### Step 2.1: Update Configuration for Production

Create `apps/api/.env.production.example`:

```env
# Railway will inject these automatically
DATABASE_URL=${DATABASE_URL}
REDIS_URL=${REDIS_URL}

# JWT - You'll set these in Railway dashboard
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_MINUTES=10080

# CORS - Update after getting Railway domain
BACKEND_CORS_ORIGINS=${FRONTEND_URL}

# Stripe (get from Stripe dashboard)
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
STRIPE_PUBLISHABLE_KEY=${STRIPE_PUBLISHABLE_KEY}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}

# Google OAuth (optional for now)
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Step 2.2: Fix Hardcoded Secret Key

**CRITICAL SECURITY FIX:**

Edit `apps/api/app/core/config.py`:

```python
# Line 50 - REMOVE hardcoded key
SECRET_KEY: str = ""  # Must be set via environment variable
```

This forces you to set it properly in Railway.

### Step 2.3: Add Railway Configuration Files

Create `railway.json` in project root:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

Create `apps/api/Procfile`:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
release: alembic upgrade head
```

Create `apps/web/.env.production`:

```env
NEXT_PUBLIC_API_URL=${RAILWAY_API_URL}
NODE_ENV=production
```

---

## Phase 3: Railway Deployment

### Step 3.1: Create Railway Account

1. Go to https://railway.app
2. Sign up with GitHub
3. Authorize Railway to access your repositories

### Step 3.2: Create New Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose `afinewinedynasty` repository
4. Railway will detect your monorepo structure

### Step 3.3: Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "PostgreSQL"
3. Railway automatically creates database and sets `DATABASE_URL`
4. Click on PostgreSQL service → "Variables" tab
5. Note the connection details (you won't need to manually configure)

### Step 3.4: Add Redis Cache

1. Click "New" → "Database" → "Redis"
2. Railway automatically sets `REDIS_URL`

### Step 3.5: Deploy API Service

1. Click "New" → "GitHub Repo"
2. Select your repository
3. Settings:
   - **Name:** `api`
   - **Root Directory:** `apps/api`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Build Command:** `pip install -r requirements.txt`

4. Go to "Variables" tab and add:
   ```
   SECRET_KEY=<generate using: python -c "import secrets; print(secrets.token_urlsafe(32))">
   BACKEND_CORS_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}
   ENVIRONMENT=production
   ```

5. Go to "Settings" tab:
   - Enable "Public Networking"
   - Note your API URL (e.g., `api-production-xxxx.up.railway.app`)

### Step 3.6: Run Database Migrations

1. In Railway API service, go to "Settings"
2. Add custom start command:
   ```
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. Or use Railway CLI:
   ```bash
   railway run alembic upgrade head
   ```

### Step 3.7: Deploy Web Frontend

1. Click "New" → "GitHub Repo" (same repo)
2. Settings:
   - **Name:** `web`
   - **Root Directory:** `apps/web`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm start`

3. Go to "Variables" tab:
   ```
   NEXT_PUBLIC_API_URL=https://<your-api-url>.up.railway.app
   NODE_ENV=production
   ```

4. Enable "Public Networking"
5. Note your frontend URL

### Step 3.8: Update CORS Settings

1. Go back to API service → Variables
2. Update `BACKEND_CORS_ORIGINS` with your frontend URL:
   ```
   BACKEND_CORS_ORIGINS=https://<your-web-url>.up.railway.app
   ```

---

## Phase 4: External Services Setup

### Step 4.1: Stripe Configuration

1. Go to https://stripe.com → Sign up
2. Get API keys from Dashboard → Developers → API Keys
3. In Railway API service → Variables:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   ```

4. Set up webhook:
   - Stripe Dashboard → Developers → Webhooks
   - Add endpoint: `https://<your-api-url>/api/v1/webhooks/stripe`
   - Copy webhook secret → Add to Railway:
     ```
     STRIPE_WEBHOOK_SECRET=whsec_...
     ```

### Step 4.2: Google OAuth (Optional)

1. Go to https://console.cloud.google.com
2. Create new project
3. Enable Google+ API
4. Create OAuth credentials
5. Add to Railway variables:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://<your-web-url>/auth/google/callback
   ```

---

## Phase 5: Monitoring & Maintenance

### Step 5.1: Railway Built-in Monitoring

Railway provides:
- ✅ CPU/Memory usage graphs
- ✅ Deployment logs
- ✅ Request metrics
- ✅ Automatic health checks

Access via: Project → Service → "Metrics" tab

### Step 5.2: Add Error Tracking (Optional but Recommended)

**Free Tier: Sentry.io**

1. Sign up at https://sentry.io (free tier: 5k errors/month)
2. Create new project (Python for API, Next.js for Web)
3. Get DSN key
4. Install Sentry:

```bash
# Add to apps/api/requirements.txt
sentry-sdk[fastapi]>=1.40.0
```

5. Update `apps/api/app/main.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENVIRONMENT,
    traces_sample_rate=0.1,
    integrations=[FastApiIntegration()],
)
```

6. Add to Railway variables:
   ```
   SENTRY_DSN=https://...@sentry.io/...
   ```

### Step 5.3: Set Up Uptime Monitoring (Free)

Use **UptimeRobot** (free tier: 50 monitors):

1. Sign up at https://uptimerobot.com
2. Add monitor for: `https://<your-api-url>/health`
3. Add monitor for: `https://<your-web-url>`
4. Configure email alerts

---

## Phase 6: Custom Domain (Optional)

### Step 6.1: Purchase Domain

- Namecheap, Google Domains, Cloudflare: ~$12/year

### Step 6.2: Configure in Railway

1. Railway project → Web service → Settings → Domains
2. Click "Add Custom Domain"
3. Enter your domain: `afinewinedynasty.com`
4. Add CNAME record in your DNS provider:
   ```
   Type: CNAME
   Name: @
   Value: <railway-provided-value>
   ```

5. Railway automatically provisions SSL certificate

---

## Cost Breakdown

### Estimated Monthly Costs:

**Starter (0-100 users):**
- Railway: $5-15/month (pay-as-you-go)
- Domain: $1/month ($12/year)
- **Total: $6-16/month**

**Growth (100-1000 users):**
- Railway: $20-50/month
- Sentry: $0 (free tier)
- **Total: $20-50/month**

**Scale (1000+ users):**
- Railway: $50-200/month
- Consider migrating to AWS/GCP with reserved instances
- **Total: $50-200/month**

---

## Deployment Checklist

Before going live:

- [ ] Local database migrations run successfully
- [ ] All tests pass: `cd apps/api && pytest`
- [ ] Frontend builds: `cd apps/web && npm run build`
- [ ] Environment variables set in Railway
- [ ] Database connected (check Railway logs)
- [ ] Redis connected
- [ ] API health check returns 200: `https://<api-url>/health`
- [ ] Frontend loads correctly
- [ ] Stripe test payment works
- [ ] CORS configured correctly
- [ ] Error tracking configured (Sentry)
- [ ] Uptime monitoring active
- [ ] Backup strategy in place (Railway auto-backups PostgreSQL)

---

## Rollback Procedure

If deployment fails:

1. Railway → Service → Deployments
2. Find last working deployment
3. Click "..." → "Redeploy"
4. Railway automatically rolls back

---

## Next Steps After Deployment

1. **Security Audit:**
   - Run: `npm audit` in apps/web
   - Run: `pip-audit` in apps/api
   - Enable Railway's automatic security updates

2. **Performance Optimization:**
   - Enable Railway's CDN
   - Add database indexes (already in migrations)
   - Configure Redis caching

3. **Backup Strategy:**
   - Railway auto-backups PostgreSQL daily
   - Download manual backup: Railway → PostgreSQL → Data → Export

4. **Scale Planning:**
   - Monitor Railway metrics
   - Set up alerts for high usage
   - Plan migration to AWS/GCP if exceeding $200/month

---

## Troubleshooting

### Database Migration Fails
```bash
# Railway CLI
railway run alembic upgrade head

# Check logs
railway logs --service api
```

### API Won't Start
- Check Railway logs for errors
- Verify all environment variables are set
- Ensure DATABASE_URL is injected

### CORS Errors
- Verify BACKEND_CORS_ORIGINS includes frontend URL
- Check Railway variables are saved
- Redeploy API service

### 500 Errors
- Check Sentry for error details
- Review Railway logs: `railway logs`

---

## Support Resources

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Railway Status: https://status.railway.app
- This project's issues: File in GitHub

---

**Ready to deploy?** Start with Phase 1 and work through each phase systematically.
