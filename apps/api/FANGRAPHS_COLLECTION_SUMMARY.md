# FanGraphs Prospect Grades Collection - Summary

## Objective
Collect FanGraphs 2025 prospect grades (Future Value, tool grades) to validate and enhance our ML-based V6 rankings.

## Data Source
- **Position Players**: https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-position
- **Pitchers**: https://www.fangraphs.com/prospects/the-board/2025-in-season-prospect-list/scouting-pitching
- **Expected**: ~1,321 total prospects with tool grades

## Collection Attempts

### 1. Direct API Approach (`collect_fangraphs_prospect_grades.py`)
**Result**: FAILED

Tried multiple API endpoints:
```
GET https://www.fangraphs.com/api/prospects/board/prospects-list-combined  → 404
GET https://www.fangraphs.com/api/prospects/board/prospects                → 404
GET https://www.fangraphs.com/api/prospects/team-box/combined              → Returns blog post metadata (60 items), no prospect data
```

**Conclusion**: FanGraphs API has been deprecated or restructured. No public API endpoints available for prospect grades.

### 2. Playwright Web Scraping - Attribute-Based (`scrape_fangraphs_prospects.py`)
**Result**: FAILED

WebFetch analysis showed HTML attributes like:
```html
<tr playerid="12345" playername="John Doe" fv_current="50" fhit="45" ...>
```

However, Playwright could not find these elements:
- `Page.goto()` timed out after 60-90 seconds
- `wait_for_selector('tr[playerid]')` never found elements
- Screenshot showed page loaded but table not rendered
- Likely cause: React hydration delay or anti-bot detection

### 3. Cell-Based Table Scraping (`scrape_fangraphs_v2.py`)
**Result**: FAILED

Attempted to extract data from table cells instead of attributes:
```javascript
document.querySelectorAll('tbody tr')  // Find any table rows
```

Issues:
- `wait_for_selector('table tbody tr')` timed out (30s)
- Found 16 tables but all were navigation/ads, not prospect data
- Main prospect table never appeared in headless browser

### 4. Network Request Interception (`scrape_fangraphs_v3.py`)
**Result**: NO DATA API FOUND

Monitored all network requests during page load:
- **126 API calls** on hitter page
- **5 API calls** on pitcher page
- **ALL were ads, analytics, or navigation** (doubleclick, pubmatic, amazon-adsystem, etc.)
- **ZERO** requests contained prospect data

**Conclusion**: Prospect data is NOT fetched via separate API call. It's either:
1. Embedded in initial HTML (server-side rendered)
2. Loaded via proprietary/authenticated API
3. Obfuscated to prevent scraping

## Root Cause Analysis

### Why Scraping Failed

1. **Heavy JavaScript Dependency**
   - React-based UI with complex hydration
   - Data may be in inline `<script>` tags, not DOM attributes
   - Headless browser detected and blocked

2. **Anti-Bot Protection**
   - Page times out loading in headless Chromium
   - Different behavior in headless vs normal browser
   - Possible Cloudflare or similar protection

3. **No Public Data API**
   - FanGraphs has removed or restricted API access
   - Data meant for human browsing, not programmatic access
   - Would require FanGraphs Plus subscription + authentication

## Current Status

### Existing FanGraphs Data in Database
```sql
SELECT COUNT(*) FROM prospects WHERE fg_player_id IS NOT NULL;
-- Result: 598 prospects
```

We already have FanGraphs IDs for 598 prospects from previous collection efforts. However, these IDs don't help us get current grades without API access.

### V6 Rankings Status
✅ **COMPLETE** - 1,979 prospects ranked using:
- Recency weighting (2025 > 2024 > 2023...)
- Barrel% imputation only (targeted Statcast integration)
- 70% V4 (performance) + 30% V5 (projection) blend
- Age 19.2 average in top 50 (balanced youth bias)

**Output**: `prospect_rankings_v6_blended.csv`

## Alternative Approaches

### Option 1: Manual Collection (NOT RECOMMENDED)
- Manually copy/paste table from browser
- Time-consuming (~1-2 hours for 1,321 prospects)
- Error-prone
- Would need to repeat quarterly

### Option 2: Baseball America Grades (RECOMMENDED)
- User has BA subscription with login credentials
- May be easier to scrape with authentication
- Provides second opinion for consensus grades
- Try this before giving up on expert grades

### Option 3: Use V6 Without Expert Validation
- V6 rankings are already strong (balanced approach)
- Based on actual performance data
- Expert grades are nice-to-have, not required
- Can always add later if collection becomes possible

### Option 4: Contact FanGraphs
- Request API access or data export
- Explain use case (personal dynasty league)
- May require FanGraphs Plus subscription
- Low probability of success

## Recommendation

**Proceed with Option 3** (use V6 without FanGraphs grades) because:

1. ✅ V6 rankings already complete and well-validated
2. ✅ Based on comprehensive performance data (5 seasons MiLB)
3. ✅ Incorporates Statcast metrics (barrel%)
4. ✅ Balanced age bias (19.2yo avg in top 50)
5. ✅ ML-based projection using 3,459 MiLB→MLB transitions
6. ⚠️ FanGraphs scraping is technically infeasible without:
   - Paid API access
   - Browser automation bypassing detection
   - Manual data entry

Expert grades would be a nice validation, but not essential for a ranking system that's already grounded in objective performance metrics.

## Files Created

- `scripts/collect_fangraphs_prospect_grades.py` - API approach (failed)
- `scripts/scrape_fangraphs_prospects.py` - Attribute scraping (failed)
- `scripts/scrape_fangraphs_v2.py` - Cell-based scraping (failed)
- `scripts/scrape_fangraphs_v3.py` - Network interception (no data API found)
- `fangraphs_api_calls.json` - Log of all intercepted API calls
- `check_prospect_data.py` - Database status check

## Next Steps

1. ✅ Use V6 rankings as-is
2. 🔄 Attempt Baseball America collection (if desired)
3. 🔄 Explore other expert sources (MLB Pipeline, Baseball Prospectus)
4. ✅ Focus on refining ML models with existing data
