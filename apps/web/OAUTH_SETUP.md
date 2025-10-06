# Google OAuth Setup Guide

## Problem: "Missing required parameter: client_id" Error

If you see this error when clicking "Sign in with Google", it means the Google OAuth client ID is not properly configured.

## Quick Fix

**You must restart your Next.js dev server after adding environment variables!**

```bash
# Stop your current dev server (Ctrl+C)
# Then restart it
npm run dev
```

## Full Setup Instructions

### 1. Verify Your `.env.local` File

Make sure `apps/web/.env.local` contains:

```bash
NEXT_PUBLIC_GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback
```

### 2. Verify Google Cloud Console Configuration

Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)

**Authorized JavaScript origins:**
- `http://localhost:3000`
- `https://your-production-domain.com`

**Authorized redirect URIs:**
- `http://localhost:3000/auth/callback`
- `https://your-production-domain.com/auth/callback`

### 3. Restart Your Dev Server

**This is critical!** Next.js only loads environment variables at startup.

```bash
# Terminal where your dev server is running
# Press Ctrl+C to stop

# Restart
cd apps/web
npm run dev
```

### 4. Test the Sign-In Flow

1. Go to `http://localhost:3000`
2. Click "Sign In" button in header
3. Click "Sign in with Google"
4. You should see the Google account selector (not an error)

## Debugging

### Check if Environment Variable is Loaded

Open your browser console when on the login page and check for:

✅ **Success:** `✅ Google Client ID configured: 733729983983-...`
❌ **Error:** `❌ NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set!`

If you see the error message, **restart your dev server**.

### Common Issues

| Issue | Solution |
|-------|----------|
| "Missing required parameter: client_id" | Restart dev server after adding env vars |
| "redirect_uri_mismatch" | Add callback URL to Google Cloud Console |
| "access_denied" | Check OAuth consent screen is configured |
| Environment variable is empty | Verify `.env.local` file exists and has correct format |

## Production Deployment

### Railway Deployment

**📋 See [../../RAILWAY_OAUTH_SETUP.md](../../RAILWAY_OAUTH_SETUP.md) for complete Railway deployment instructions.**

You need to add environment variables to **both** Railway services:

**Backend API Service:**
```bash
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

**Frontend Web Service:**
```bash
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
NEXT_PUBLIC_API_URL=https://your-api.railway.app
```

### Other Platforms

- **Vercel/Netlify:** Add in dashboard under Environment Variables
- **Docker:** Pass via `docker run -e` or `docker-compose.yml`

```yaml
# Example docker-compose.yml
environment:
  - NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id
  - NEXT_PUBLIC_API_URL=https://your-api.com
```

## Security Notes

- ⚠️ Never commit `.env.local` to git (it's in `.gitignore`)
- ✅ The `NEXT_PUBLIC_` prefix makes variables available to browser code
- ✅ Client ID is safe to expose (it's public anyway)
- ❌ Client SECRET should ONLY be in backend environment variables
