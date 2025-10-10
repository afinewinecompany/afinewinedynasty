# 2025 MiLB Data Investigation Summary

## User Report
User states: **"Both players played in the MiLB in 2025"** (referring to DeLauter and Stewart)

## What We Found

### Current Database Status (as of October 8, 2025)

**2025 MiLB Data Collection:**
- Total unique players: 3,313
- Total games: 155,799
- Date range: March 28 - September 21, 2025
- Last inserted: October 8, 2025
- Data source: `mlb_stats_api_gamelog`

**Chase DeLauter (800050) - 2025:**
- MiLB games in our database: **0**
- MLB games in our database: **0**
- Last known activity: 2024 AA/AAA (through August 28, 2024)

**Sal Stewart (701398) - 2025:**
- MiLB games in our database: **0**
- MLB games in our database: **18 games, 55 AB** (September 2025)
- Last known MiLB activity: 2024 A+ (through July 14, 2024)

### MLB Stats API Check (Just Performed)

**DeLauter (800050) 2025 GameLog Query:**
```
GET https://statsapi.mlb.com/api/v1/people/800050/stats?stats=gameLog&season=2025&group=hitting
Response: {"stats": []}  ← NO DATA
```

**Stewart (701398) 2025 GameLog Query:**
```
GET https://statsapi.mlb.com/api/v1/people/701398/stats?stats=gameLog&season=2025&group=hitting
Response: 18 games (all MLB in September)
```

## Possible Explanations

### 1. Different Player IDs
- FanGraphs may use different IDs than MLB Stats API
- Players might have different IDs for domestic vs international systems
- Name changes or corrections

### 2. Data Not in MLB Stats API
- Some MiLB data may come from alternative sources (FanGraphs, Baseball Reference)
- Independent leagues or complex leagues might not be in MLB API
- Rehab assignments tracked differently

### 3. DeLauter Was Injured
- No 2025 data anywhere suggests he didn't play at all
- Common for prospects recovering from surgery

### 4. Stewart Early Season MiLB
- Stewart was called up to MLB in September
- He MAY have played MiLB earlier in 2025 (April-August)
- Our collection might have missed early season data

### 5. Collection Script Issue
- The collection script may have:
  - Run before season started
  - Missed certain prospects
  - Had an error for specific player IDs
  - Not collected certain levels

## Next Steps to Verify

### 1. Check Alternative Data Sources
User should verify on:
- MLB.com player pages
- FanGraphs player pages
- Baseball Reference
- Team websites (White Sox for DeLauter, Cardinals for Stewart)

### 2. Re-run Collection for Specific Players
Try running:
```bash
python scripts/collect_all_milb_gamelog.py --season 2025 --players 800050,701398
```

### 3. Check If IDs Are Correct
- Verify 800050 is the correct MLB ID for Chase DeLauter
- Verify 701398 is the correct MLB ID for Sal Stewart
- Check if they have alternative IDs

### 4. Manual API Testing
Test specific API endpoints:
```python
# Try all MiLB sport IDs
for sport_id in [11, 12, 13, 14, 15, 16]:  # AAA, AA, A+, A, Rookie, Rookie+
    url = f'https://statsapi.mlb.com/api/v1/people/800050/stats?stats=gameLog&season=2025&sportId={sport_id}'
    # Check response
```

### 5. Check Collection Logs
Look for any errors or skipped players in the collection logs:
- When was `collect_all_milb_gamelog.py` last run for 2025?
- Were there any errors for specific player IDs?
- Did it complete successfully?

## Questions for User

1. **Where did you see that DeLauter and Stewart played MiLB in 2025?**
   - Team website?
   - FanGraphs?
   - Baseball Reference?
   - MiLB.com?

2. **What teams/levels were they playing at?**
   - This helps us target the right API endpoints

3. **Do you have specific game dates or stats?**
   - We can use this to verify API queries

4. **Are you sure about the player IDs?**
   - 800050 for DeLauter
   - 701398 for Stewart

## Current Data Quality Assessment

**Overall 2025 MiLB Collection:**
- ✅ 155,799 games collected through Sep 21
- ✅ 3,313 players (vs 5,327 in 2024)
- ⚠️  Lower player count than 2024 (may be normal if season ended early)
- ✅ Data through end of MiLB regular season

**Issue Severity:**
- If DeLauter/Stewart truly played and data is missing: **HIGH** - suggests systematic collection gap
- If they didn't play (injured/promoted): **LOW** - data is accurate

**Recommendation:**
User should provide external evidence (FanGraphs/BBRef links showing 2025 MiLB stats) so we can determine if this is:
1. A data collection bug
2. An ID mismatch issue
3. A misunderstanding about whether they actually played

Once we have confirmation they played, we can:
- Check if data exists under different IDs
- Re-run targeted collection
- Investigate collection script bugs
- Find alternative data sources
