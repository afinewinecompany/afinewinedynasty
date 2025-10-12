# Browser Automation Options for Prospect Grade Scraping

## Overview

Need to scrape prospect grades from:
1. **FanGraphs** - Public data (1,321 prospects expected)
2. **Baseball America** - Requires login/subscription

---

## Option 1: Playwright (RECOMMENDED)

### Pros
✅ Modern, fast, and actively maintained (by Microsoft)
✅ Built-in authentication support (cookies, sessions)
✅ Handles JavaScript-heavy sites (FanGraphs, BA)
✅ Headless mode for background scraping
✅ Screenshot/debugging capabilities
✅ Python API well-documented
✅ Can handle dynamic content loading

### Cons
❌ Larger dependency (~300MB browser download)
❌ Slightly slower than pure HTTP requests

### Installation
```bash
pip install playwright
playwright install chromium  # or firefox, webkit
```

### Use Cases
- ✅ **FanGraphs**: Perfect for scraping team prospect pages
- ✅ **Baseball America**: Handles login flow, session cookies
- ✅ **Future**: Can scrape MLB.com, Baseball Prospectus, etc.

### Example Code Structure
```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()

    # FanGraphs (no auth)
    await page.goto('https://www.fangraphs.com/prospects/the-board')
    prospects = await page.query_selector_all('.prospect-row')

    # Baseball America (with auth)
    await page.goto('https://www.baseballamerica.com/login')
    await page.fill('input[name="username"]', username)
    await page.fill('input[name="password"]', password)
    await page.click('button[type="submit"]')
    await page.goto('https://www.baseballamerica.com/prospects')
```

**BEST FOR**: Both FanGraphs + Baseball America

---

## Option 2: Selenium

### Pros
✅ Industry standard, very mature
✅ Extensive documentation and community
✅ Works with all major browsers
✅ Good for complex authentication flows

### Cons
❌ Slower than Playwright
❌ More verbose API
❌ Requires separate WebDriver installation
❌ Less modern features

### Installation
```bash
pip install selenium
pip install webdriver-manager  # auto-manages drivers
```

### Use Cases
- ✅ Baseball America (if Playwright has issues)
- ⚠️ FanGraphs (works but Playwright is better)

**BEST FOR**: Fallback option if Playwright doesn't work

---

## Option 3: requests-html (Lightweight)

### Pros
✅ Lightweight alternative to full browsers
✅ Renders JavaScript using Chromium
✅ Simpler API than Playwright/Selenium
✅ Built on top of requests library

### Cons
❌ Less control over browser behavior
❌ Worse at handling complex auth flows
❌ Limited debugging capabilities

### Installation
```bash
pip install requests-html
```

### Use Cases
- ⚠️ FanGraphs (might work if pages are simple)
- ❌ Baseball America (authentication likely problematic)

**BEST FOR**: Quick prototypes only

---

## Option 4: Pure HTTP + Beautiful Soup (NOT RECOMMENDED)

### Why It Won't Work
❌ FanGraphs uses React (client-side rendering)
❌ Baseball America requires session management
❌ Dynamic content won't be in initial HTML
❌ Anti-bot measures will block you

---

## Recommended Approach

### Phase 1: FanGraphs Scraping (Public)
**Use Playwright** to scrape team-by-team prospect lists:

```python
# Scrape all 30 teams
teams = ['angels', 'orioles', 'red-sox', ...]

for team in teams:
    url = f'https://blogs.fangraphs.com/{team}-top-prospects-2025'
    # Extract: Name, Rank, FV, Hit, Power, Run, Field, Arm
```

**Expected Data**:
- ~40 prospects per team × 30 teams = ~1,200 prospects
- Tool grades: Hit, Power, Run, Field, Arm (20-80 scale)
- Future Value (FV): Overall grade (40-80)
- Position, Age, ETA

### Phase 2: Baseball America Scraping (Authenticated)
**Use Playwright** with login credentials:

```python
# Login once, save session
await page.goto('https://www.baseballamerica.com/login')
await page.fill('input[name="email"]', your_email)
await page.fill('input[name="password"]', your_password)
await page.click('button.login-submit')

# Save cookies for reuse
cookies = await context.cookies()
save_cookies(cookies)  # Reuse for future scrapes

# Scrape prospect rankings
await page.goto('https://www.baseballamerica.com/rankings/2025-top-100-prospects')
```

**Expected Data**:
- Top 100 overall rankings
- Organization rankings (30 teams)
- Tool grades (may differ from FanGraphs)
- Scouting reports (text)

---

## Implementation Plan

### Step 1: FanGraphs Scraper (Playwright)
**File**: `scripts/scrape_fangraphs_playwright.py`

**Features**:
- Scrape all 30 team prospect pages
- Extract: Name, FV, Tool grades (Hit/Power/Run/Field/Arm)
- Handle pagination if needed
- Save to `fangraphs_prospect_grades` table
- Match to existing prospects by name fuzzy matching

**Challenges**:
- Name matching (e.g., "José" vs "Jose")
- Multiple prospects with same name
- Organizational vs overall rankings

### Step 2: Baseball America Scraper (Playwright)
**File**: `scripts/scrape_baseball_america_playwright.py`

**Features**:
- Login with credentials (environment variables)
- Save session cookies for reuse
- Scrape Top 100 + team rankings
- Extract: Name, Rank, OFP (Overall Future Potential), Tools
- Save to `baseball_america_prospect_grades` table

**Challenges**:
- Paywall/subscription validation
- Rate limiting (be respectful)
- Session expiration (re-login logic)
- CAPTCHA (unlikely but possible)

### Step 3: Grade Integration
**File**: `scripts/integrate_expert_grades.py`

**Features**:
- Match FanGraphs/BA grades to our prospects
- Create consensus grade (average of available sources)
- Flag prospects in expert lists but missing from our data
- Create "expert boost" multiplier for V6 rankings

**Blending Formula**:
```python
# Weighted average
expert_consensus = (FG_FV + BA_OFP) / 2

# Boost V6 score based on expert consensus
expert_multiplier = 1.0 + ((expert_consensus - 50) / 100)  # 50 FV = 1.0x, 60 FV = 1.1x

v6_score_final = v6_score * expert_multiplier
```

---

## Security Considerations

### FanGraphs (Public)
- ✅ No authentication needed
- ✅ Respect robots.txt
- ✅ Add delays between requests (1-2 seconds)
- ✅ Use User-Agent header

### Baseball America (Authenticated)
- ⚠️ **Store credentials in environment variables** (NOT in code)
- ⚠️ **Session cookies** - save and reuse to minimize logins
- ⚠️ **Rate limiting** - 1 page per 2-3 seconds
- ⚠️ **Terms of Service** - ensure scraping is allowed for personal use
- ⚠️ **Headless mode** - less detectable than visible browser

**Environment Variables**:
```bash
# .env file (NEVER commit to git)
BA_EMAIL=your_email@example.com
BA_PASSWORD=your_password
```

---

## Code Example: Playwright Setup

### Installation Script
```bash
# Install dependencies
pip install playwright python-dotenv

# Install browser
playwright install chromium

# Verify installation
playwright --version
```

### Basic Scraper Template
```python
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()

async def scrape_fangraphs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # Run in background
            slow_mo=50       # Slow down for stability
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        try:
            # Navigate to FanGraphs
            await page.goto('https://www.fangraphs.com/prospects/the-board',
                          wait_until='networkidle')

            # Wait for content to load
            await page.wait_for_selector('.prospect-table')

            # Extract data
            prospects = await page.query_selector_all('.prospect-row')

            for prospect in prospects:
                name = await prospect.query_selector('.name').inner_text()
                fv = await prospect.query_selector('.fv').inner_text()
                # ... extract other fields

        finally:
            await browser.close()

async def scrape_baseball_america():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Login
            await page.goto('https://www.baseballamerica.com/login')
            await page.fill('input[name="email"]', os.getenv('BA_EMAIL'))
            await page.fill('input[name="password"]', os.getenv('BA_PASSWORD'))
            await page.click('button[type="submit"]')

            # Wait for redirect after login
            await page.wait_for_url('**/dashboard**')

            # Save cookies for future use
            cookies = await context.cookies()
            # ... save cookies to file

            # Navigate to prospects
            await page.goto('https://www.baseballamerica.com/rankings/prospects')

            # Extract data
            # ...

        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(scrape_fangraphs())
    asyncio.run(scrape_baseball_america())
```

---

## Next Steps

1. **Install Playwright**:
   ```bash
   cd apps/api
   pip install playwright python-dotenv
   playwright install chromium
   ```

2. **Create FanGraphs scraper** - No authentication needed, can start immediately

3. **Create Baseball America scraper** - Requires your credentials

4. **Test scrapers** on a few teams first before full collection

5. **Integrate grades** into V6 rankings with expert boost multiplier

---

## Estimated Timeline

- **FanGraphs scraper**: 2-3 hours (coding + testing)
- **Baseball America scraper**: 3-4 hours (auth flow + scraping)
- **Grade integration**: 1-2 hours
- **Full data collection**: 30-60 minutes (30 teams + rate limiting)

**Total**: ~1 day of development, then automated collection in ~1 hour

---

## Alternative: Manual Collection

If automation is blocked:
1. **FanGraphs**: Copy-paste from team pages into CSV
2. **Baseball America**: Export if available, otherwise manual entry
3. **Time**: ~3-4 hours manual work vs ~1 day automation setup

**Recommendation**: Automation worth it if you'll refresh grades seasonally (2-3 times/year)

---

Would you like me to:
1. ✅ **Create the Playwright FanGraphs scraper now?**
2. ✅ **Create the Baseball America scraper with login?**
3. ✅ **Set up environment variables for BA credentials?**
4. ✅ **All of the above?**

Let me know and I'll start building!
