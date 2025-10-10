# Browser Automation Quickstart Guide

## TL;DR - Recommended Solution

**Use Playwright** for both FanGraphs and Baseball America scraping.

---

## Quick Setup (5 minutes)

### 1. Install Playwright
```bash
cd apps/api
pip install playwright python-dotenv
playwright install chromium
```

### 2. Create Environment File
```bash
# Create .env file in apps/api/
echo "BA_EMAIL=your_email@example.com" > .env
echo "BA_PASSWORD=your_password" >> .env
```

**IMPORTANT**: Add `.env` to `.gitignore` to avoid committing credentials!

### 3. Verify Installation
```bash
playwright --version
# Should output: Version 1.x.x
```

---

## What You'll Get

### FanGraphs Data (~1,200+ prospects)
- Player Name
- Overall Rank (per team)
- Future Value (FV) - 20-80 scale
- Tool Grades:
  - Hit Tool (contact ability)
  - Power Tool (raw + game power)
  - Run Tool (speed)
  - Field Tool (defense)
  - Arm Tool (arm strength/accuracy)
- Position
- Age
- ETA (Expected Time of Arrival to MLB)

### Baseball America Data (~1,500+ prospects)
- Player Name
- Overall Rank (Top 100 + team ranks)
- OFP (Overall Future Potential) - 20-80 scale
- Tool Grades (may differ from FanGraphs)
- Scouting Reports (text summaries)
- Risk Level (Safe/Medium/High/Extreme)

---

## Scraping Strategy

### FanGraphs Approach
**Source**: Team-by-team prospect lists (blog posts)

**URLs**:
```
https://blogs.fangraphs.com/los-angeles-angels-top-38-prospects/
https://blogs.fangraphs.com/baltimore-orioles-top-50-prospects/
https://blogs.fangraphs.com/boston-red-sox-top-45-prospects/
... (30 teams total)
```

**Scraping Method**:
1. Load each team's prospect blog post
2. Parse HTML tables or lists
3. Extract player data + grades
4. Save to database with team affiliation

**Rate Limiting**: 2-3 seconds between pages (respectful)

---

### Baseball America Approach
**Source**: Main prospect rankings (requires subscription)

**URLs**:
```
https://www.baseballamerica.com/rankings/2025-top-100-prospects/
https://www.baseballamerica.com/rankings/team/[team-name]/
```

**Scraping Method**:
1. **Login once** with your credentials
2. **Save session cookies** to file
3. **Reuse cookies** for subsequent scrapes (avoid re-login)
4. Navigate to rankings pages
5. Extract data (likely JSON embedded in page)

**Authentication Flow**:
```python
1. Load login page
2. Fill email/password
3. Click submit
4. Wait for redirect
5. Save cookies → cookies.json
6. Future runs: Load cookies.json instead of re-login
```

---

## Integration with V6 Rankings

### Expert Grade Boost Formula

```python
# Get consensus expert grade
fg_fv = fangraphs_future_value  # 40-80 scale
ba_ofp = baseball_america_ofp   # 40-80 scale

expert_consensus = (fg_fv + ba_ofp) / 2  # Average if both exist

# Convert to multiplier (50 FV = neutral 1.0x)
expert_multiplier = 1.0 + ((expert_consensus - 50) / 100)

# Examples:
# 40 FV (org player)  = 0.90x multiplier (downgrade)
# 50 FV (avg prospect) = 1.00x multiplier (neutral)
# 60 FV (all-star)     = 1.10x multiplier (upgrade)
# 70 FV (superstar)    = 1.20x multiplier (big upgrade)
# 80 FV (generational) = 1.30x multiplier (huge upgrade)

# Apply to V6 score
v6_score_final = v6_score * expert_multiplier
```

### Blended Weighting Options

**Option A: Light Touch (90% Model + 10% Experts)**
```python
v6_final = (0.90 * v6_score) + (0.10 * expert_grade_normalized)
```
**Use if**: You trust your ML model more than scouts

**Option B: Balanced (80% Model + 20% Experts)**
```python
v6_final = (0.80 * v6_score) + (0.20 * expert_grade_normalized)
```
**Use if**: You want validation but keep ML primary

**Option C: Heavy Expert Influence (70% Model + 30% Experts)**
```python
v6_final = (0.70 * v6_score) + (0.30 * expert_grade_normalized)
```
**Use if**: You trust FanGraphs/BA scouting heavily

**RECOMMENDED**: Option B (80/20) - Keeps your statistical edge while incorporating expert consensus

---

## Example Playwright Scraper (FanGraphs)

### File: `scripts/scrape_fangraphs_prospects.py`

```python
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import text
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

async def scrape_team_prospects(page, team_slug):
    """Scrape one team's prospect list."""
    url = f'https://blogs.fangraphs.com/{team_slug}'

    await page.goto(url, wait_until='networkidle')

    # Wait for content
    await page.wait_for_selector('.entry-content')

    # Extract prospects from table or list
    # (Exact selectors depend on FanGraphs HTML structure)
    prospects = await page.query_selector_all('.prospect-entry')

    results = []
    for prospect in prospects:
        try:
            name = await prospect.query_selector('.name').inner_text()
            fv = await prospect.query_selector('.fv').inner_text()
            position = await prospect.query_selector('.pos').inner_text()
            # ... extract other fields

            results.append({
                'name': name,
                'fv': int(fv),
                'position': position,
                'team': team_slug
            })
        except:
            continue

    return results

async def main():
    teams = [
        'los-angeles-angels-top-38-prospects',
        'baltimore-orioles-top-50-prospects',
        'boston-red-sox-top-45-prospects',
        # ... all 30 teams
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        all_prospects = []

        for team_slug in teams:
            print(f'Scraping {team_slug}...')
            prospects = await scrape_team_prospects(page, team_slug)
            all_prospects.extend(prospects)

            # Be respectful - wait between requests
            await asyncio.sleep(2)

        await browser.close()

        # Save to database
        async with engine.begin() as conn:
            for prospect in all_prospects:
                await conn.execute(text('''
                    INSERT INTO fangraphs_prospect_grades
                    (player_name, future_value, position, organization)
                    VALUES (:name, :fv, :pos, :team)
                    ON CONFLICT (player_name) DO UPDATE SET
                        future_value = EXCLUDED.future_value
                '''), prospect)

        print(f'Collected {len(all_prospects)} prospects!')

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Example Playwright Scraper (Baseball America)

### File: `scripts/scrape_baseball_america_prospects.py`

```python
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os
import json

load_dotenv()

async def save_cookies(context, filepath='ba_cookies.json'):
    """Save session cookies for reuse."""
    cookies = await context.cookies()
    with open(filepath, 'w') as f:
        json.dump(cookies, f)

async def load_cookies(context, filepath='ba_cookies.json'):
    """Load saved cookies."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        return True
    return False

async def login(page):
    """Login to Baseball America."""
    await page.goto('https://www.baseballamerica.com/login')

    # Fill login form
    await page.fill('input[name="email"]', os.getenv('BA_EMAIL'))
    await page.fill('input[name="password"]', os.getenv('BA_PASSWORD'))

    # Submit
    await page.click('button[type="submit"]')

    # Wait for redirect (adjust URL pattern as needed)
    await page.wait_for_url('**/dashboard**', timeout=10000)

async def scrape_top_100(page):
    """Scrape BA Top 100."""
    await page.goto('https://www.baseballamerica.com/rankings/2025-top-100-prospects')

    # Wait for prospect list
    await page.wait_for_selector('.prospect-list')

    # Extract data (adjust selectors based on actual HTML)
    prospects = await page.query_selector_all('.prospect-card')

    results = []
    for prospect in prospects:
        name = await prospect.query_selector('.name').inner_text()
        rank = await prospect.query_selector('.rank').inner_text()
        ofp = await prospect.query_selector('.ofp').inner_text()
        # ...

        results.append({
            'name': name,
            'rank': int(rank),
            'ofp': int(ofp)
        })

    return results

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Try to load saved cookies first
        cookies_loaded = await load_cookies(context)

        if not cookies_loaded:
            # First time - need to login
            await login(page)
            await save_cookies(context)
            print('Logged in and saved cookies')

        # Scrape data
        top_100 = await scrape_top_100(page)

        print(f'Collected {len(top_100)} prospects from BA Top 100')

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Best Practices

### 1. Respectful Scraping
```python
# Add delays between requests
await asyncio.sleep(2)  # 2 seconds

# Use realistic user agent
context = await browser.new_context(
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
)

# Limit concurrent requests
# Don't open 30 tabs simultaneously - do sequentially
```

### 2. Error Handling
```python
try:
    await page.goto(url, timeout=15000)
except TimeoutError:
    print(f'Timeout loading {url} - skipping')
    continue
except Exception as e:
    print(f'Error: {e}')
    continue
```

### 3. Save Progress
```python
# Save after each team in case of failure
async with engine.begin() as conn:
    for prospect in team_prospects:
        await conn.execute(text('INSERT ...'), prospect)
# Don't wait until all 30 teams are scraped to save
```

### 4. Cookie Management (BA)
```python
# Check if cookies expired
if not cookies_loaded or await page.title() == 'Login':
    await login(page)
    await save_cookies(context)
```

---

## Troubleshooting

### Issue: "Playwright not found"
```bash
# Reinstall
pip uninstall playwright
pip install playwright
playwright install chromium
```

### Issue: "Login failed" (BA)
- Check credentials in `.env` file
- Try manual login in browser to verify account works
- Check if BA changed login form HTML

### Issue: "Can't find elements"
- Use `page.screenshot(path='debug.png')` to see what page looks like
- Inspect HTML in browser DevTools
- Adjust CSS selectors

### Issue: "Rate limited / blocked"
- Increase delay between requests
- Use `slow_mo` parameter: `browser.launch(slow_mo=100)`
- Rotate user agents

---

## Next Steps

**Ready to start?** I can create:

1. ✅ **FanGraphs scraper** (no auth needed)
2. ✅ **Baseball America scraper** (with your login)
3. ✅ **Grade integration script** (blend with V6)
4. ✅ **Updated V6 rankings** (with expert boost)

Let me know which one to build first!
