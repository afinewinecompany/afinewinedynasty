# Fantrax Authentication Setup

## Current Status

The Fantrax integration uses **two authentication methods**:

1. **OAuth Flow** (`/api/v1/integrations/fantrax/auth`) - Legacy, requires Fantrax API credentials
2. **In-Browser Auth** (`/api/v1/fantrax/auth/initiate`) - Selenium-based, requires Chrome/ChromeDriver

## Issue: 503 Service Unavailable on /fantrax/auth/initiate

The in-browser authentication endpoint is currently returning 503 errors because **Selenium and Chrome are not installed in the Railway deployment**.

### Required Dependencies

The Selenium-based auth requires:

1. **System packages** (in Railway Nixpacks):
   - `google-chrome-stable` or `chromium`
   - `chromium-chromedriver` or `chromedriver`
   - X11 libraries for headless mode

2. **Python packages** (already in requirements.txt):
   - `selenium`
   - `webdriver-manager`
   - `psutil`

3. **Environment configuration**:
   - Sufficient memory (~500MB per concurrent auth session)
   - Process limits to handle multiple ChromeDriver instances

### Solution Options

#### Option 1: Install Chrome in Railway (Recommended for Production)

Add a `nixpacks.toml` file to install Chrome:

```toml
[phases.setup]
aptPkgs = ["chromium", "chromium-driver"]

[phases.install]
cmds = ["pip install -r requirements.txt"]
```

#### Option 2: Use Cookie-Based Auth (Simpler Alternative)

Instead of Selenium, use the existing cookie-based authentication flow:

1. User provides Fantrax cookies manually
2. Store encrypted cookies in database
3. Use cookies to make API requests

See `FantraxCookieService` for implementation.

#### Option 3: OAuth Flow (If Fantrax API Credentials Available)

If you have Fantrax OAuth credentials:

1. Set `FANTRAX_CLIENT_ID` and `FANTRAX_CLIENT_SECRET` in Railway
2. Use the `/integrations/fantrax/auth` endpoint instead
3. This is the standard OAuth 2.0 flow

### Current Workaround

For now, the **500 error on /leagues** has been fixed by making the connection check fail gracefully. The 503 error on Selenium auth will persist until Chrome is installed or an alternative auth method is used.

### Recommendations

1. **Short-term**: Use cookie-based auth or disable the Selenium auth feature
2. **Long-term**: Implement proper Chrome installation in Railway for production use
3. **Alternative**: Consider using a third-party service like BrowserStack or Selenium Grid for browser automation

## Related Files

- Backend: `apps/api/app/services/fantrax_auth_service.py`
- Frontend: `apps/web/src/components/integrations/FantraxAuthModal.tsx`
- Endpoint: `apps/api/app/api/api_v1/endpoints/fantrax_auth.py`
