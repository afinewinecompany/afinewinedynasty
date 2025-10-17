# Railway Deployment - Google OAuth Setup

## ⚠️ Required Environment Variables for Railway

You need to add Google OAuth environment variables to **BOTH** your Railway services:

### 🔹 Backend API Service (FastAPI) ⚠️ MISSING - THIS IS CAUSING THE 502 ERROR

Add these in Railway Dashboard → Your API Service → Variables:

```bash
GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-google-client-secret-from-google-cloud-console>
GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback
```

> **CRITICAL:** These are MISSING in Railway backend! The 502 error happens because the backend can't exchange the OAuth code without these credentials.
> **SECURITY:** Get the actual `GOOGLE_CLIENT_SECRET` from your local `.env` file or Google Cloud Console. Never commit secrets to Git!

### 🔹 Frontend Web Service (Next.js)

Add these in Railway Dashboard → Your Web Service → Variables:

```bash
NEXT_PUBLIC_GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback
NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app
```

> **Note:** These values are from your `.env.local` file - use the actual production URLs

---

## 📋 Step-by-Step Instructions

### 1. Update Google Cloud Console

Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)

Click on your OAuth 2.0 Client ID

**Add to Authorized JavaScript origins:**
```
https://web-production-5cfe0.up.railway.app
```

**Add to Authorized redirect URIs:**
```
https://web-production-5cfe0.up.railway.app/auth/callback
```

### 2. Add Variables to Railway Backend

1. Open Railway Dashboard
2. Select your **API service** (backend FastAPI)
3. Go to **Variables** tab
4. Click **+ New Variable**
5. Add each variable:

| Variable Name | Value |
|--------------|-------|
| `GOOGLE_CLIENT_ID` | `733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Get from your `.env` file or Google Cloud Console (never commit to Git!) |
| `GOOGLE_REDIRECT_URI` | `https://web-production-5cfe0.up.railway.app/auth/callback` |

6. Click **Deploy** to restart with new variables

### 3. Add Variables to Railway Frontend

1. In Railway Dashboard, select your **Web service** (Next.js)
2. Go to **Variables** tab
3. Click **+ New Variable**
4. Add each variable:

| Variable Name | Value |
|--------------|-------|
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | `733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com` |
| `NEXT_PUBLIC_GOOGLE_REDIRECT_URI` | `https://web-production-5cfe0.up.railway.app/auth/callback` |
| `NEXT_PUBLIC_API_URL` | `https://api-production-f7e0.up.railway.app` |

5. Click **Deploy** to rebuild with new variables

---

## 🔍 How to Verify It's Working

### Backend API

Test the backend OAuth endpoint:

```bash
curl https://your-api.railway.app/api/v1/auth/google/login \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"code":"test","state":"test"}'
```

You should get a 400/401 error (not 500) - this means OAuth is configured.

### Frontend Web

1. Visit your Railway frontend URL
2. Click "Sign In" button
3. Click "Sign in with Google"
4. Check browser console for: `✅ Google Client ID configured`
5. You should see Google account selector

---

## 🔐 Security Checklist

- [x] Backend has `GOOGLE_CLIENT_SECRET` (keep secret!)
- [x] Frontend has `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (safe to expose)
- [x] Google Cloud Console has production redirect URIs
- [x] CORS origins include frontend Railway URL
- [ ] Test OAuth flow end-to-end on production

---

## 🐛 Troubleshooting

### "Missing required parameter: client_id"

**Cause:** Frontend environment variable not set or service not rebuilt.

**Fix:**
1. Verify `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set in Railway Web service
2. Trigger a new deploy (Railway → Web service → Deploy)
3. Wait for build to complete
4. Hard refresh browser (Ctrl+Shift+R)

### "redirect_uri_mismatch"

**Cause:** Your Railway URL is not in Google Cloud Console.

**Fix:**
1. Copy your exact Railway frontend URL (e.g., `https://web-production-abc.railway.app`)
2. Add to Google Cloud Console → Credentials → Authorized redirect URIs
3. Add: `https://web-production-abc.railway.app/auth/callback`

### "Invalid client_secret"

**Cause:** Backend secret is missing or incorrect.

**Fix:**
1. Check Railway Backend service has `GOOGLE_CLIENT_SECRET`
2. Verify it matches your Google Cloud Console secret
3. Redeploy backend service

### Backend can't verify OAuth code

**Cause:** Backend doesn't have Google OAuth credentials.

**Fix:**
1. Add `GOOGLE_CLIENT_ID` to backend Railway service
2. Add `GOOGLE_CLIENT_SECRET` to backend Railway service
3. Redeploy backend

---

## 📊 Environment Variables Summary

### Backend API (Required for OAuth to work)
```bash
# Core Google OAuth - ⚠️ ADD THESE TO RAILWAY BACKEND SERVICE
GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<get-from-your-local-env-file-or-google-console>
GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback

# Already set (verify these exist)
SECRET_KEY=<your-jwt-secret>
DATABASE_URL=<railway-postgres-url>
BACKEND_CORS_ORIGINS=["https://web-production-5cfe0.up.railway.app"]
```

> **SECURITY NOTE:** The actual `GOOGLE_CLIENT_SECRET` is in `apps/api/.env` file (starts with `GOCSPX-`). Get it from there or Google Cloud Console.

### Frontend Web (Required for OAuth to work)
```bash
# Core Google OAuth - ✅ ALREADY SET
NEXT_PUBLIC_GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback
NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app
```

---

## ✅ Quick Checklist

Before testing OAuth in production:

- [ ] ⚠️ **Backend Railway service has `GOOGLE_CLIENT_ID`** (MISSING - ADD THIS!)
- [ ] ⚠️ **Backend Railway service has `GOOGLE_CLIENT_SECRET`** (MISSING - ADD THIS!)
- [ ] ⚠️ **Backend Railway service has `GOOGLE_REDIRECT_URI`** (MISSING - ADD THIS!)
- [x] Frontend Railway service has `NEXT_PUBLIC_GOOGLE_CLIENT_ID` ✅
- [x] Frontend Railway service has `NEXT_PUBLIC_GOOGLE_REDIRECT_URI` ✅
- [x] Frontend Railway service has `NEXT_PUBLIC_API_URL` ✅
- [ ] Google Cloud Console has your Railway frontend URL in authorized origins
- [ ] Google Cloud Console has your Railway frontend `/auth/callback` in redirect URIs
- [ ] Backend service redeployed after adding variables
- [ ] Browser cache cleared / hard refresh performed

---

## 🚀 After Setup

Once everything is configured, users can:

1. Visit your Railway frontend URL
2. Click "Sign In"
3. Click "Sign in with Google"
4. Authenticate with their Google account
5. Get redirected back to your app, signed in

The OAuth flow:
```
User clicks "Sign in with Google"
  ↓
Redirected to Google account selector
  ↓
User selects account & grants permissions
  ↓
Google redirects back to /auth/callback?code=...
  ↓
Frontend sends code to backend /api/v1/auth/google/login
  ↓
Backend exchanges code for Google user info
  ↓
Backend creates/updates user & generates JWT tokens
  ↓
Frontend stores tokens & redirects to dashboard
  ✅ User is signed in!
```
