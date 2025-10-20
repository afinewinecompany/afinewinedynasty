# Railway Environment Variable Fix

## Issue

Mixed Content Error on production:
```
Mixed Content: The page at 'https://web-production-5cfe0.up.railway.app/projections'
was loaded over HTTPS, but requested an insecure resource
'http://api-production-f7e0.up.railway.app/api/v1/prospects/?position_type=hitter&limit=200'.
This request has been blocked; the content must be served over HTTPS.
```

## Root Cause

Next.js `NEXT_PUBLIC_*` environment variables are baked into the build at **build time**, not runtime. Even though the environment variable `NEXT_PUBLIC_API_URL` is correctly set in Railway with `https://`, the issue occurs because:

1. The variable may have been added or changed **after** the last build
2. Next.js requires a **rebuild** for `NEXT_PUBLIC_*` variables to take effect
3. The current deployed build has `undefined` or `http://` hardcoded into it

## Solution

Force a rebuild of the Next.js app so the environment variable is properly baked into the build.

### Steps to Fix in Railway Dashboard

1. **Go to Railway Dashboard**
   - Navigate to: https://railway.app/
   - Select the "A Fine Wine Dynasty" project
   - Click on the **web** service (Next.js frontend)

2. **Verify Environment Variable**
   - Click the "Variables" tab
   - Confirm `NEXT_PUBLIC_API_URL` exists
   - Verify value is: `https://api-production-f7e0.up.railway.app` (with **https://**)
   - If missing or incorrect, update it

3. **Force Rebuild (CRITICAL)**

   Since `NEXT_PUBLIC_*` variables are baked in at build time, you MUST rebuild:

   **Option A: Trigger New Deployment**
   - Go to "Deployments" tab
   - Click the three dots (•••) on the latest deployment
   - Click "Redeploy" (this rebuilds from scratch)

   **Option B: Dummy Commit**
   - Make a trivial change to any file (add a comment)
   - Push to trigger automatic rebuild

   **Option C: Change Environment Variable**
   - Edit the `NEXT_PUBLIC_API_URL` variable
   - Save it (even if value didn't change)
   - This triggers automatic rebuild

### Important Notes

- The API URL **MUST** use `https://` (not `http://`)
- Environment variables prefixed with `NEXT_PUBLIC_` are exposed to the browser
- `.env.local` files are NOT deployed to Railway (they're gitignored)
- Railway environment variables override local `.env` files in production

### Verify Fix

After redeployment, check:
1. Visit: https://web-production-5cfe0.up.railway.app/projections
2. Open browser DevTools (F12) → Network tab
3. Verify API requests are using `https://api-production-f7e0.up.railway.app`
4. Page should load without mixed content errors

### Additional Environment Variables Needed

While you're in Railway dashboard, ensure these are also set for the **web** service:

```env
NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app
NEXT_PUBLIC_API_VERSION=v1
NEXT_PUBLIC_GOOGLE_CLIENT_ID=733729983983-fnm9vvitbqu2uj2i36auqmmbvrmoplh6.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/callback
NEXT_PUBLIC_APP_NAME=A Fine Wine Dynasty
NEXT_PUBLIC_APP_VERSION=0.1.0
NODE_ENV=production
```

### Alternative: Check Current Railway Env Vars

To see what environment variables are currently set in Railway:

1. Railway Dashboard → web service → Variables tab
2. Look for `NEXT_PUBLIC_API_URL`
3. If it exists but is wrong (e.g., `http://` instead of `https://`), edit it
4. If it doesn't exist, add it as shown above

## Prevention

For future deployments, always ensure:
1. All `NEXT_PUBLIC_*` variables are set in Railway dashboard
2. API URLs use HTTPS in production
3. Test deployment before announcing to users

## Timeline

- **Issue Identified:** October 20, 2025 14:45
- **Root Cause:** Missing/incorrect Railway environment variable
- **Fix Required:** Set `NEXT_PUBLIC_API_URL=https://api-production-f7e0.up.railway.app`
- **ETA:** ~2 minutes after setting variable in Railway

---

*This fix addresses the mixed content error preventing the Projections page from loading in production.*
