# Mixed Content Error Fix - URGENT

## Problem
The production frontend (HTTPS) is trying to call the backend API using HTTP, which browsers block for security. This causes the "Mixed Content" error:

```
Mixed Content: The page at 'https://web-production-5cfe0.up.railway.app/' was loaded over HTTPS,
but requested an insecure resource 'http://api-production-f7e0.up.railway.app/api/v1/prospects/...'
```

## Root Cause
Railway environment variable `NEXT_PUBLIC_API_URL` is set to `http://` instead of `https://`

## Fix Instructions

### Step 1: Update Railway Environment Variable
1. Go to Railway dashboard: https://railway.app/
2. Navigate to the **web** service (Next.js frontend)
3. Go to **Variables** tab
4. Find `NEXT_PUBLIC_API_URL`
5. Change from: `http://api-production-f7e0.up.railway.app`
6. Change to: `https://api-production-f7e0.up.railway.app`
7. Click **Save** or **Deploy**

### Step 2: Verify Other Environment Variables
While you're in the Variables tab, also verify:

```bash
# Required variables:
NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app
NEXT_PUBLIC_API_VERSION=v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback

# Optional (can be empty for now):
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
```

### Step 3: Redeploy
After saving the environment variable:
1. Railway should automatically trigger a rebuild
2. If not, manually trigger a deploy from the Railway dashboard
3. Wait for deployment to complete (~2-5 minutes)

### Step 4: Test
1. Visit: https://web-production-5cfe0.up.railway.app/prospects
2. Open browser DevTools (F12) → Console tab
3. Verify there are NO "Mixed Content" errors
4. The page should now load successfully

## Expected Result
After the fix:
- ✅ No Mixed Content errors
- ✅ API calls use HTTPS: `https://api-production-f7e0.up.railway.app/api/v1/...`
- ✅ Prospects page loads successfully
- ✅ All data displays correctly

## Additional Issues Found

### Stripe Configuration Warning
There's also a Stripe error in the console:
```
IntegrationError: Please call Stripe() with your publishable key. You used an empty string.
```

**Fix:** If you're not using Stripe payments yet, you can ignore this. Otherwise, set `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` in Railway environment variables.

## Files Already Updated
The following files in the codebase already have the correct HTTPS URLs:
- ✅ `apps/web/.env.local` - Has `NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app`
- ✅ All API client code is environment-aware and will use the Railway env var

## Summary
**Action Required:** Update `NEXT_PUBLIC_API_URL` in Railway dashboard to use `https://` instead of `http://`

Once this is done, all the routing fixes we made will work correctly and the prospects page will load.
