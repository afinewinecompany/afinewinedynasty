# Fantrax Cookie-Based Authentication Guide

**Updated:** 2025-10-03
**Authentication Method:** Cookie-based (using FantraxAPI library)

---

## Overview

A Fine Wine Dynasty now uses **cookie-based authentication** to connect with Fantrax, replacing the previous OAuth approach. This is necessary because Fantrax does not provide a public OAuth developer portal.

### How It Works

1. Users run a cookie generation script that opens a browser
2. Users log in to their Fantrax account
3. The script captures their login cookies
4. Users upload the cookie file to the app
5. The app uses these cookies to access their Fantrax leagues

---

## For End Users

### Step 1: Generate Your Fantrax Cookie File

**Prerequisites:**
- Google Chrome browser installed
- Python 3.8+ installed
- Internet connection

**Instructions:**

1. **Download the cookie generation script:**
   - Get `generate_fantrax_cookie.py` from your app administrator
   - Or download from the app's support page

2. **Install required packages:**
   ```bash
   pip install selenium webdriver-manager
   ```

3. **Run the script:**
   ```bash
   python generate_fantrax_cookie.py
   ```

4. **Follow the prompts:**
   - A Chrome browser window will open
   - Log in to your Fantrax account
   - Wait for the countdown to complete
   - The script will save `fantrax_login.cookie`

5. **Cookie file generated!**
   - File location will be displayed
   - Keep this file secure (it contains your login)

### Step 2: Upload Cookie File to App

1. Log in to A Fine Wine Dynasty
2. Navigate to **Settings > Integrations > Fantrax**
3. Click **"Connect Fantrax Account"**
4. Upload your `fantrax_login.cookie` file
5. Click **"Connect"**

### Step 3: Add Your Leagues

1. Go to **My Leagues**
2. Click **"Add Fantrax League"**
3. Enter your Fantrax league ID
   - Found in your league URL: `fantrax.com/fantasy/.../LEAGUE_ID`
4. Click **"Connect League"**
5. Your roster and league data will sync!

---

## For Developers

### Architecture

The cookie-based authentication system consists of:

1. **FantraxAPI Library** (`fantraxapi`) - Unofficial Python wrapper
2. **Cookie Service** (`fantrax_cookie_service.py`) - Manages cookie storage
3. **Integration Service** (`fantrax_integration_service.py`) - Fantrax API calls
4. **API Endpoints** (`fantrax_v2.py`) - REST API for frontend

### Installation

Add to `requirements.txt`:
```
fantraxapi>=1.0.0
selenium>=4.0.0
webdriver-manager>=4.0.0
```

Install:
```bash
pip install fantraxapi selenium webdriver-manager
```

### Database Schema

```sql
-- Users table (updated)
ALTER TABLE users DROP COLUMN fantrax_user_id;
ALTER TABLE users DROP COLUMN fantrax_refresh_token;
ALTER TABLE users ADD COLUMN fantrax_cookies TEXT;  -- Encrypted JSON
```

Migration file: `010_update_fantrax_cookie_auth.py`

### API Endpoints

#### Connect Fantrax Account
```http
POST /api/integrations/fantrax/connect
Content-Type: multipart/form-data
Authorization: Bearer {jwt_token}

{
  "cookie_file": <file>
}
```

#### Connect League
```http
POST /api/integrations/fantrax/leagues/{league_id}/connect
Authorization: Bearer {jwt_token}
```

#### Sync Roster
```http
POST /api/integrations/fantrax/leagues/{league_id}/teams/{team_id}/roster/sync
Authorization: Bearer {jwt_token}
```

#### Get Standings
```http
GET /api/integrations/fantrax/leagues/{league_id}/standings?week={week}
Authorization: Bearer {jwt_token}
```

#### Get Transactions
```http
GET /api/integrations/fantrax/leagues/{league_id}/transactions?count=100
Authorization: Bearer {jwt_token}
```

### Usage Example

```python
from app.services.fantrax_integration_service import FantraxIntegrationService

# Initialize service
service = FantraxIntegrationService(db, user_id)

# Connect league
result = await service.connect_league("your_league_id")

# Sync roster
roster = await service.sync_roster("league_id", "team_id")

# Get standings
standings = await service.get_standings("league_id", week=5)
```

### Security Considerations

1. **Cookie Encryption**: Cookies are encrypted using Fernet (AES-128) before storage
2. **Premium Only**: Fantrax integration requires premium subscription
3. **Session Management**: Cookies reused for multiple requests
4. **HTTPS Required**: All connections must use HTTPS in production

---

## Troubleshooting

### Cookie Generation Issues

**Browser doesn't open:**
- Check Chrome is installed
- Try running with administrator privileges
- Check firewall settings

**No cookies saved:**
- Make sure you actually log in within 30 seconds
- Check you're on the Fantrax website
- Try running script again

**Script crashes:**
- Update Chrome to latest version
- Reinstall selenium: `pip install --upgrade selenium`
- Check Python version (3.8+ required)

### Connection Issues

**"User not authenticated with Fantrax":**
- Upload cookie file via `/connect` endpoint
- Check cookie file is valid (not corrupted)
- Re-generate cookie file if expired

**"Failed to connect league":**
- Verify league ID is correct
- Make sure you're a member of the league
- Check if league is public or private
- Ensure cookies haven't expired

**"API request failed":**
- Check internet connection
- Verify Fantrax website is accessible
- Cookie may have expired - regenerate

### Cookie Expiration

Cookies typically expire after 30 days or when:
- You change your Fantrax password
- You log out from all devices on Fantrax
- Fantrax security policy forces re-authentication

**To refresh cookies:**
1. Run the cookie generation script again
2. Upload the new cookie file
3. Reconnect your leagues

---

## Migration from OAuth

If you previously used the OAuth-based authentication:

1. **Run database migration:**
   ```bash
   cd apps/api
   alembic upgrade head
   ```

2. **Users need to reconnect:**
   - Old OAuth tokens will be removed
   - Users must generate and upload cookie files
   - Leagues need to be reconnected

3. **Update frontend:**
   - Change OAuth flow to cookie upload
   - Update integration UI
   - Add instructions for cookie generation

---

## FAQs

**Q: Is this secure?**
A: Yes, cookies are encrypted before storage and transmitted over HTTPS. However, users should keep their cookie files private.

**Q: Why not use OAuth?**
A: Fantrax doesn't provide a public OAuth developer portal, so cookie-based auth is the only viable option.

**Q: How often do cookies expire?**
A: Typically 30 days, but can vary based on Fantrax's security policies.

**Q: Can I use this for multiple leagues?**
A: Yes! Once connected, you can add multiple leagues using the same cookie.

**Q: What data can the app access?**
A: Only leagues you're a member of, including rosters, standings, transactions, and trade blocks.

---

## Support

For issues or questions:
- GitHub Issues: [Your Repository]
- Documentation: [docs/deployment/fantrax-cookie-auth-guide.md](fantrax-cookie-auth-guide.md)
- Email: support@afinewinedynasty.com

---

## Related Files

- **Cookie Generation Script**: `generate_fantrax_cookie.py`
- **Cookie Service**: `apps/api/app/services/fantrax_cookie_service.py`
- **Integration Service**: `apps/api/app/services/fantrax_integration_service.py`
- **API Endpoints**: `apps/api/app/api/api_v1/endpoints/fantrax_v2.py`
- **Database Migration**: `apps/api/alembic/versions/010_update_fantrax_cookie_auth.py`
- **FantraxAPI Docs**: https://fantraxapi.kometa.wiki/
