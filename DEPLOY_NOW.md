# 🚀 Deploy to Railway NOW - Quick Start

**Your code is ready! Follow these steps to go live in ~15 minutes.**

---

## ⚡ Prerequisites (5 minutes)

1. **Generate SECRET_KEY**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   📋 **Copy this and save it** - you'll need it in step 3.3

2. **Sign up for Railway**
   - Go to https://railway.app
   - Click "Login with GitHub"
   - Authorize Railway

---

## 📦 Part 1: Set Up Infrastructure (3 minutes)

### 1.1 Create Project
1. Railway Dashboard → Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose `afinewinedynasty`
4. Click "Cancel" on the initial deploy (we'll configure first)

### 1.2 Add PostgreSQL
1. In project → Click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Done! Railway auto-configures connection.

### 1.3 Add Redis
1. Click "+ New" → "Database" → "Add Redis"
2. Done! Railway auto-configures connection.

---

## 🔧 Part 2: Deploy API (5 minutes)

### 2.1 Create API Service
1. Click "+ New" → "GitHub Repo"
2. Select `afinewinedynasty` (same repo)

### 2.2 Configure API
1. Click on the new service → "Settings" tab
2. Set **Service Name:** `api`
3. Set **Root Directory:** `apps/api`
4. Leave other settings default

### 2.3 Add Environment Variables
1. Go to "Variables" tab → "Raw Editor"
2. Paste this (replace SECRET_KEY with your generated one):

```
SECRET_KEY=YOUR_GENERATED_SECRET_KEY_FROM_STEP_1.1
BACKEND_CORS_ORIGINS=https://temporary.com
ENVIRONMENT=production
LOG_LEVEL=INFO
PYTHONPATH=.
```

3. Click "Update Variables"

### 2.4 Generate Public URL
1. Go to "Settings" → "Networking" section
2. Click "Generate Domain"
3. **📋 COPY THIS URL** (e.g., `api-production-abcd.up.railway.app`)
4. Save it for the next step!

### 2.5 Wait for Deployment
1. Go to "Deployments" tab
2. Watch the logs - should see:
   - ✅ Installing dependencies
   - ✅ Running migrations (alembic upgrade head)
   - ✅ Application startup complete

**✅ API is live!** Test it: `https://YOUR-API-URL/docs`

---

## 🌐 Part 3: Deploy Frontend (5 minutes)

### 3.1 Create Web Service
1. Back to project dashboard → "+ New" → "GitHub Repo"
2. Select `afinewinedynasty` again

### 3.2 Configure Web
1. Click on service → "Settings"
2. Set **Service Name:** `web`
3. Set **Root Directory:** `apps/web`
4. **Build Command:** `npm install && npm run build`
5. **Start Command:** `npm start`

### 3.3 Add Environment Variables
1. Go to "Variables" tab
2. Add (replace with your API URL from step 2.4):

```
NEXT_PUBLIC_API_URL=https://YOUR-API-URL-FROM-STEP-2.4
NODE_ENV=production
```

3. Click "Update Variables"

### 3.4 Generate Public URL
1. "Settings" → "Networking" → "Generate Domain"
2. **📋 COPY THIS URL** (e.g., `web-production-wxyz.up.railway.app`)

### 3.5 Wait for Deployment
1. "Deployments" tab → Watch logs
2. Should see:
   - ✅ npm install
   - ✅ npm run build
   - ✅ npm start

**✅ Frontend is live!** Visit: `https://YOUR-WEB-URL`

---

## 🔄 Part 4: Connect Frontend & Backend (2 minutes)

### 4.1 Update CORS
1. Go back to **API service** → "Variables"
2. Update `BACKEND_CORS_ORIGINS`:

```
BACKEND_CORS_ORIGINS=https://YOUR-WEB-URL-FROM-STEP-3.4
```

3. Railway auto-redeploys API

### 4.2 Verify
1. Visit your frontend URL
2. Open browser DevTools (F12) → Console tab
3. Should see NO CORS errors
4. Frontend can now call your API!

---

## ✅ You're Live!

**Your URLs:**
- 📖 API Docs: `https://YOUR-API-URL/docs`
- 🌐 Website: `https://YOUR-WEB-URL`
- 💾 Database: Managed by Railway (auto-backups daily)
- ⚡ Redis: Managed by Railway

---

## 🎯 Next Steps (Do Later)

### Monitor Your App
- Railway Dashboard → Your Project → "Metrics"
- Watch CPU, Memory, Requests

### Set Up Stripe (When Ready)
1. Get keys from https://dashboard.stripe.com
2. Add to API service variables:
   - `STRIPE_SECRET_KEY`
   - `STRIPE_PUBLISHABLE_KEY`
   - `STRIPE_WEBHOOK_SECRET`

### Add Custom Domain (Optional)
1. Railway → Web service → Settings → Custom Domain
2. Follow DNS instructions

### Set Up Error Tracking (Recommended)
1. Sign up: https://sentry.io (free tier)
2. Add `SENTRY_DSN` to API variables

---

## 💰 Cost Estimate

- **First month:** ~$5-15 (starter tier)
- **Low traffic:** ~$20-30/month
- **Moderate traffic:** ~$50-100/month

Railway has a $5 free trial credit to get started!

---

## 🆘 Need Help?

**Check logs if something fails:**
1. Railway → Service → Deployments → Click deployment → View logs

**Common Issues:**
- ❌ **Build failed:** Check logs for missing dependencies
- ❌ **Migration failed:** Usually fixes itself on redeploy
- ❌ **CORS errors:** Double-check URLs match exactly

**Full guides:**
- 📚 [Step-by-step checklist](docs/deployment/RAILWAY_DEPLOYMENT_CHECKLIST.md)
- 📖 [Detailed guide](docs/deployment/railway-deployment-guide.md)

**Railway Support:**
- https://docs.railway.app
- https://discord.gg/railway

---

## 🎉 Success Checklist

- [ ] API deployed to Railway
- [ ] Database migrations completed (check API logs)
- [ ] Frontend deployed to Railway
- [ ] CORS configured correctly
- [ ] Can access `/docs` endpoint
- [ ] Can access frontend
- [ ] No errors in browser console

**All checked? Congratulations - you're LIVE! 🚀**

---

**Ready? Start at Part 1 above! ⬆️**
