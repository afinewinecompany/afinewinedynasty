# Fantrax Authentication Setup

## Current Status: Selenium Not Working in Railway ❌

After extensive testing and troubleshooting, **Selenium-based authentication is not viable in Railway's containerized environment** due to persistent DevTools connection issues.

The Fantrax integration has **three authentication methods**:

1. **Cookie-Based Auth** ✅ **RECOMMENDED** - Manual cookie import, most reliable
2. **OAuth Flow** - Requires Fantrax API credentials (if available)
3. **Selenium In-Browser Auth** ❌ **NOT WORKING** - Chrome/ChromeDriver incompatible with Railway

## Diagnosis Summary

**Attempts Made:**
1. ✅ Installed Chromium (v130.0.6723.116) and ChromeDriver via Nixpacks
2. ✅ Auto-detection of Chrome binaries working correctly (`/root/.nix-profile/bin/chromium`)
3. ✅ Chrome starts successfully in headless mode
4. ❌ Chrome immediately disconnects from DevTools during page navigation
5. ❌ Error: `"disconnected: Unable to receive message from renderer"`

**Root Cause:**
Railway's containerized environment has resource/process limitations that prevent Chrome's renderer process from communicating with DevTools, even with `--single-process` flag. This is a known issue with Selenium in Docker/container environments.

**Tested Configurations:**
- `--headless=new` with `--single-process`
- `--disable-dev-shm-usage` and `--no-sandbox`
- Multiple stability flags (disable-gpu, disable-extensions, disable-setuid-sandbox, etc.)
- All configurations fail at the same point: `driver.get(url)` navigation

**Diagnostic Endpoints Created:**
- `GET /api/v1/diagnostics/chrome-status` - Shows Chrome/ChromeDriver installation
- `GET /api/v1/diagnostics/test-chrome-init` - Tests Selenium initialization

## Recommended Solution: Cookie-Based Authentication ✅

Since Selenium is not viable, use the **cookie-based authentication** method that's already implemented in the codebase.

### How Cookie-Based Auth Works

1. User logs into Fantrax manually in their browser
2. User exports cookies using browser extension:
   - [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) (Chrome)
   - [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/) (Firefox)
3. User pastes cookies (JSON format) into the app
4. Backend encrypts and stores cookies using `encrypt_value()`
5. Backend uses stored cookies for all Fantrax API requests

### Implementation Files Already Available

**Backend Services:**
- `apps/api/app/services/fantrax_cookie_service.py` - Cookie encryption/storage
- `apps/api/app/services/fantrax_integration_service.py` - API requests with cookies
- `apps/api/app/core/security.py` - `encrypt_value()` and `decrypt_value()`

**Database:**
- `User.fantrax_cookies` column stores encrypted cookies

**API Endpoints to Create:**
```python
@router.post("/cookie-auth")
async def authenticate_with_cookies(
    cookies_json: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate to Fantrax using manually exported cookies.

    Frontend should provide cookies exported from browser in JSON format.
    """
    # Parse cookies
    cookies = json.loads(cookies_json)

    # Encrypt and store
    encrypted = encrypt_value(json.dumps(cookies))
    current_user.fantrax_cookies = encrypted
    await db.commit()

    return {"success": True, "message": "Fantrax cookies stored successfully"}
```

### Frontend Implementation

**Component to Create:**
```typescript
// CookieAuthModal.tsx
function CookieAuthModal() {
  const [cookies, setCookies] = useState("");

  const handleSubmit = async () => {
    // 1. Validate JSON
    JSON.parse(cookies);

    // 2. Send to backend
    await fetch("/api/v1/fantrax/cookie-auth", {
      method: "POST",
      body: JSON.stringify({ cookies_json: cookies }),
      headers: { "Content-Type": "application/json" }
    });

    // 3. Test connection
    const leagues = await fetch("/api/v1/integrations/fantrax/leagues");
    // ...
  };

  return (
    <Modal>
      <h2>Connect to Fantrax with Cookies</h2>
      <ol>
        <li>Install EditThisCookie extension</li>
        <li>Log into Fantrax.com</li>
        <li>Click extension → Export cookies</li>
        <li>Paste here:</li>
      </ol>
      <textarea value={cookies} onChange={e => setCookies(e.target.value)} />
      <button onClick={handleSubmit}>Connect</button>
    </Modal>
  );
}
```

## Alternative: OAuth Flow (If Credentials Available)

If you can obtain Fantrax OAuth credentials:

1. Contact Fantrax API support to request OAuth app registration
2. Set environment variables in Railway:
   ```
   FANTRAX_CLIENT_ID=your_client_id
   FANTRAX_CLIENT_SECRET=your_client_secret
   FANTRAX_REDIRECT_URI=https://web-production-5cfe0.up.railway.app/auth/fantrax/callback
   ```
3. Use existing `/integrations/fantrax/auth` endpoint (already implemented)

## Selenium Status: Not Recommended

The Selenium endpoint (`/fantrax/auth/initiate`) will remain non-functional in Railway. Options:

1. **Disable the endpoint** - Return 501 Not Implemented instead of 503
2. **Keep for local development** - Works fine on local machines
3. **External Selenium service** - Use BrowserStack/Selenium Grid (expensive)

## Related Files

- Cookie Service: `apps/api/app/services/fantrax_cookie_service.py`
- Selenium Service: `apps/api/app/services/fantrax_auth_service.py` (not working in Railway)
- Frontend Modal: `apps/web/src/components/integrations/FantraxAuthModal.tsx`
- Auth Endpoints: `apps/api/app/api/api_v1/endpoints/fantrax_auth.py`

## Summary

✅ **Use cookie-based authentication** for Fantrax integration in Railway production

❌ **Selenium authentication does not work** in Railway containerized environment
