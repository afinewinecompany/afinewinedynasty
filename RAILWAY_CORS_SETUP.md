# Railway CORS Configuration Guide

## Problem: CORS Error When Testing OAuth Locally

When testing Google OAuth with your local frontend (`http://localhost:3000`) against the Railway production backend, you get:

```
Access to fetch at 'https://api-production-f7e0.up.railway.app/api/v1/auth/google/login'
from origin 'http://localhost:3000' has been blocked by CORS policy
```

This happens because the production backend's CORS policy doesn't allow `http://localhost:3000`.

---

## 🔧 Solution: Update Railway CORS Configuration

### Step 1: Open Railway Dashboard

1. Go to [Railway Dashboard](https://railway.app/)
2. Select your **API service** (backend FastAPI service)
3. Click the **Variables** tab

### Step 2: Update BACKEND_CORS_ORIGINS

**Find the variable:** `BACKEND_CORS_ORIGINS`

**Current value (probably):**
```
https://your-frontend.railway.app
```
or
```
${FRONTEND_URL}
```

**Update to include localhost:**
```json
["http://localhost:3000","http://127.0.0.1:3000","https://your-frontend.railway.app"]
```

**Important Format Notes:**
- Must be valid JSON array format
- Use double quotes `"` not single quotes `'`
- Separate URLs with commas
- No trailing comma
- Include `http://` or `https://` protocol
- Include both `localhost` and `127.0.0.1` for compatibility

### Step 3: Add as New Variable (If It Doesn't Exist)

If `BACKEND_CORS_ORIGINS` doesn't exist:

1. Click **"+ New Variable"**
2. **Variable name:** `BACKEND_CORS_ORIGINS`
3. **Value:**
   ```json
   ["http://localhost:3000","http://127.0.0.1:3000"]
   ```
4. Click **Add**

### Step 4: Redeploy

After updating the variable:

1. Railway will automatically trigger a redeploy
2. Wait for the deployment to complete (usually 2-3 minutes)
3. Look for "Deployment successful" or similar message

### Step 5: Verify CORS Configuration

Test the CORS configuration:

```bash
curl -I -X OPTIONS \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  https://api-production-f7e0.up.railway.app/api/v1/auth/google/login
```

You should see in the response headers:
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
```

---

## 📋 Complete CORS Configuration

For a full development + production setup, your `BACKEND_CORS_ORIGINS` should include:

```json
[
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://localhost:5173",
  "https://your-production-frontend.railway.app",
  "https://your-custom-domain.com"
]
```

This allows:
- Local development on default Next.js port (3000)
- Local development with IP address
- Local development on Vite port (5173) if needed
- Production Railway frontend
- Custom production domain (if you have one)

---

## 🔒 Security Considerations

### Development vs Production

**For Production Only:**
```json
["https://your-production-frontend.railway.app"]
```
✅ Most secure - only production frontend can access

**For Development + Production:**
```json
["http://localhost:3000","https://your-production-frontend.railway.app"]
```
⚠️ Less secure but needed for local development

### Best Practice

Create **two separate Railway services**:
1. **Production API** - CORS only allows production frontend
2. **Staging API** - CORS allows localhost for testing

Or use **Railway environments** to manage different CORS configs.

---

## 🐛 Troubleshooting

### "Still getting CORS error after updating"

**Solution:**
1. Verify the deployment completed successfully
2. Hard refresh your browser: `Ctrl + Shift + R`
3. Clear browser cache
4. Check Railway logs for any startup errors

### "Invalid JSON format error"

**Common mistakes:**
```json
// ❌ Wrong - single quotes
['http://localhost:3000']

// ❌ Wrong - trailing comma
["http://localhost:3000",]

// ❌ Wrong - missing quotes
[http://localhost:3000]

// ✅ Correct
["http://localhost:3000"]
```

### "Environment variable not taking effect"

**Solution:**
1. Check Railway logs: Does it show the CORS origins on startup?
2. Try triggering a manual redeploy
3. Verify variable isn't overridden by another config

### "CORS works for some endpoints but not others"

**Solution:**
- Check if specific endpoints have additional CORS middleware
- Verify all HTTP methods are allowed in CORS config
- Check for any API gateway/proxy in front of your service

---

## 🧪 Testing After Configuration

1. **Restart your local frontend dev server:**
   ```bash
   cd apps/web
   npm run dev
   ```

2. **Open browser DevTools** (F12) → Console tab

3. **Visit:** `http://localhost:3000/login`

4. **Click "Sign in with Google"**

5. **Complete Google OAuth flow**

6. **Check for success:**
   - No CORS errors in console
   - Successfully redirected back to your app
   - User is logged in

---

## 📊 Current Configuration Status

**Backend API Service Variables Needed:**

| Variable | Value | Status |
|----------|-------|--------|
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` | ⚠️ Update needed |
| `GOOGLE_CLIENT_ID` | Your Google OAuth client ID | ✅ Should be set |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth secret | ✅ Should be set |

After updating `BACKEND_CORS_ORIGINS`, the OAuth flow should work completely from local development to production backend! 🚀
