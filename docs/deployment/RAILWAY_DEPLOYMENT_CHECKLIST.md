# Railway Deployment Checklist

Follow these steps to deploy to Railway.app

## Prerequisites

- [ ] GitHub account with code pushed
- [ ] Railway account (sign up at https://railway.app)
- [ ] Generate new SECRET_KEY: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## Part 1: Create Railway Project

### 1.1 Sign Up & Create Project

1. Go to https://railway.app
2. Click "Login" → "Login with GitHub"
3. Authorize Railway to access your GitHub repositories
4. Click "New Project"
5. Select "Deploy from GitHub repo"
6. Choose `afinewinedynasty` repository
7. Click "Add variables" to skip initial deployment

### 1.2 Add PostgreSQL Database

1. In your Railway project dashboard, click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Railway automatically creates database and sets `DATABASE_URL`
4. **Note:** Railway will automatically inject these variables into your API service:
   - `DATABASE_URL`
   - `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`

### 1.3 Add Redis Cache

1. Click "+ New" → "Database" → "Add Redis"
2. Railway automatically sets `REDIS_URL`

---

## Part 2: Deploy API Service

### 2.1 Create API Service

1. Click "+ New" → "GitHub Repo"
2. Select your `afinewinedynasty` repository
3. Railway will detect it's a monorepo

### 2.2 Configure API Service Settings

1. Click on the newly created service
2. Go to "Settings" tab:
   - **Name:** `api`
   - **Root Directory:** `apps/api`
   - **Custom Start Command:** Leave blank (uses railway.toml)
3. Click "Deploy"

### 2.3 Add API Environment Variables

1. Go to "Variables" tab
2. Click "Raw Editor"
3. Paste the following (replace placeholders):

```
SECRET_KEY=<paste-your-generated-secret-key-here>
BACKEND_CORS_ORIGINS=https://temporary-will-update-later.com
ENVIRONMENT=production
LOG_LEVEL=INFO
PYTHONPATH=.
```

4. Click "Update Variables"

### 2.4 Enable Public Networking

1. Go to "Settings" tab
2. Scroll to "Networking" section
3. Click "Generate Domain"
4. **Copy your API URL** (e.g., `api-production-xxxx.up.railway.app`)
5. Save this URL for later!

### 2.5 Check Deployment Logs

1. Go to "Deployments" tab
2. Click on the active deployment
3. Watch the build logs
4. Look for:
   - ✅ `pip install -r requirements.txt` success
   - ✅ `alembic upgrade head` success (migrations)
   - ✅ `uvicorn app.main:app` starting
5. Once you see "Application startup complete", the API is live!

### 2.6 Test API Health

1. Visit: `https://<your-api-url>.up.railway.app/docs`
2. You should see the FastAPI Swagger documentation
3. Test health endpoint: `https://<your-api-url>.up.railway.app/health`

---

## Part 3: Deploy Web Frontend

### 3.1 Create Web Service

1. Click "+ New" → "GitHub Repo"
2. Select `afinewinedynasty` again (yes, same repo)
3. Railway creates a second service

### 3.2 Configure Web Service Settings

1. Click on the new service
2. Go to "Settings" tab:
   - **Name:** `web`
   - **Root Directory:** `apps/web`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm start`

### 3.3 Add Web Environment Variables

1. Go to "Variables" tab
2. Add:

```
NEXT_PUBLIC_API_URL=https://<your-api-url-from-step-2.4>.up.railway.app
NODE_ENV=production
```

3. Click "Update Variables"

### 3.4 Enable Public Networking

1. Go to "Settings" tab → "Networking"
2. Click "Generate Domain"
3. **Copy your Web URL** (e.g., `web-production-yyyy.up.railway.app`)

### 3.5 Deploy

1. Railway should automatically deploy
2. Go to "Deployments" tab and watch logs
3. Look for:
   - ✅ `npm install` success
   - ✅ `npm run build` success
   - ✅ `npm start` running

---

## Part 4: Update CORS Configuration

Now that both services are deployed, update the API to allow requests from your frontend:

### 4.1 Update API CORS Settings

1. Go back to **API service** → "Variables" tab
2. Update `BACKEND_CORS_ORIGINS`:

```
BACKEND_CORS_ORIGINS=https://<your-web-url-from-step-3.4>.up.railway.app
```

3. Click "Update Variables"
4. Railway will automatically redeploy the API

---

## Part 5: Verification

### 5.1 Test Full Stack

1. Visit your frontend URL: `https://<your-web-url>.up.railway.app`
2. Open browser DevTools (F12) → Network tab
3. Check for API calls to your backend
4. Verify no CORS errors

### 5.2 Check Database Migrations

1. Go to API service → "Deployments" → Latest deployment
2. In logs, search for "alembic upgrade"
3. Should see: "Running upgrade -> <migration_id>"
4. Should see all 15 migrations applied

### 5.3 Test API Endpoints

Visit `https://<your-api-url>.up.railway.app/docs` and test:
- [ ] GET `/health` → Should return `{"status": "healthy"}`
- [ ] POST `/api/v1/auth/register` → Create a test user
- [ ] POST `/api/v1/auth/login` → Login with test user

---

## Part 6: Post-Deployment Setup (Optional)

### 6.1 Add Custom Domain (Optional)

**If you have a domain:**

1. Go to Web service → Settings → Domains
2. Click "Custom Domain"
3. Enter your domain (e.g., `afinewinedynasty.com`)
4. Add CNAME record in your DNS provider:
   - Type: `CNAME`
   - Name: `@` (or `www`)
   - Value: `<railway-provided-value>`
5. Railway auto-provisions SSL certificate

### 6.2 Set Up Stripe (When Ready)

1. Go to https://dashboard.stripe.com
2. Get API keys: Developers → API Keys
3. Add to Railway API service variables:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   ```
4. Set up webhook:
   - Stripe Dashboard → Developers → Webhooks
   - Endpoint URL: `https://<your-api-url>/api/v1/webhooks/stripe`
   - Copy webhook secret → Add to Railway:
     ```
     STRIPE_WEBHOOK_SECRET=whsec_...
     ```

### 6.3 Set Up Monitoring (Recommended)

**Free tier: Sentry.io**

1. Sign up at https://sentry.io (free: 5k errors/month)
2. Create Python project for API
3. Get DSN
4. Add to Railway API variables:
   ```
   SENTRY_DSN=https://...@sentry.io/...
   ```

**Free tier: UptimeRobot**

1. Sign up at https://uptimerobot.com (free: 50 monitors)
2. Add monitors:
   - API: `https://<your-api-url>/health`
   - Web: `https://<your-web-url>/`
3. Configure email alerts

---

## Troubleshooting

### API Won't Start

**Check logs:**
1. API service → Deployments → Click latest → View logs

**Common issues:**
- Missing environment variables → Add them in Variables tab
- Database connection failed → Ensure PostgreSQL service is running
- Port binding error → Railway should set `$PORT` automatically

### Migration Errors

**If migrations fail:**
```bash
# Railway CLI method:
railway link  # Link to your project
railway run --service api alembic upgrade head
```

### CORS Errors

**Symptoms:** Browser console shows CORS policy errors

**Fix:**
1. API service → Variables
2. Verify `BACKEND_CORS_ORIGINS` matches your web URL exactly
3. Include `https://` in the URL
4. No trailing slash

### Build Failures

**Frontend build fails:**
- Check Node version in logs
- Ensure `package.json` and `package-lock.json` are committed
- Check for missing dependencies

**Backend build fails:**
- Check Python version (should be 3.11+)
- Ensure `requirements.txt` has all dependencies
- Check for syntax errors in code

---

## Cost Monitoring

Railway pricing (as of 2025):

- **Free Trial:** $5 credit
- **Starter:** $5/month (hobby projects)
- **Usage-based:** $0.000463/GB-hour RAM, $0.000231/vCPU-hour

**Expected costs for this project:**
- Development: ~$15-20/month
- Production (low traffic): ~$30-50/month
- Production (moderate traffic): ~$100-200/month

**Monitor usage:**
1. Railway Dashboard → Usage
2. Set up billing alerts
3. Scale down services when not in use

---

## Next Steps After Deployment

1. **Security Review:**
   - [ ] Rotate all secrets/keys
   - [ ] Enable 2FA on Railway account
   - [ ] Review Railway access logs

2. **Performance:**
   - [ ] Monitor response times in Railway metrics
   - [ ] Set up database indexes (already in migrations)
   - [ ] Enable Railway CDN for static assets

3. **Backups:**
   - [ ] Railway auto-backs up PostgreSQL daily
   - [ ] Download manual backup: PostgreSQL service → Data → Export

4. **Scale Planning:**
   - [ ] Monitor Railway metrics dashboard
   - [ ] Plan vertical scaling (more RAM/CPU) if needed
   - [ ] Consider migrating to AWS/GCP if costs exceed $200/month

---

## Support Resources

- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Railway Status:** https://status.railway.app
- **Deployment Guide:** See `docs/deployment/railway-deployment-guide.md`

---

## Success Criteria

✅ API deployed and accessible at `https://<api-url>.up.railway.app/docs`
✅ Web deployed and accessible at `https://<web-url>.up.railway.app`
✅ Database migrations completed (15 migrations)
✅ No CORS errors in browser console
✅ Health endpoint returns `{"status": "healthy"}`
✅ User registration/login works

**You're live! 🎉**
