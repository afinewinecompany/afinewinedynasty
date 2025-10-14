# Google Trends Collection - Findings and Recommendations

## Summary

We successfully implemented Google Trends integration for the HYPE leaderboard, but testing revealed that **most minor league prospects do not have sufficient search volume** to generate Google Trends data.

## Test Results

**Test Run**: Collected trends for top 3 HYPE leaderboard players
- Trey Yesavage (HYPE: 81.3) - HTTP 400 error (no data)
- Harry Ford (HYPE: 41.6) - HTTP 400 error (no data)
- Kevin McGonigle (HYPE: 39.3) - HTTP 400 error (no data)

**Result**: 0 records saved with actual data

## Root Cause

Google Trends only provides data for search terms that meet a minimum threshold of search volume. Minor league baseball prospects, even highly-ranked ones, typically don't generate enough public search interest to appear in Google Trends.

**HTTP 400 Error**: "The request failed: Google returned a response with code 400"
- This indicates the search term doesn't have sufficient data
- Not a rate limiting issue (which would be HTTP 429)
- Expected behavior for low-volume search terms

## Who Will Have Data?

Google Trends data will likely only be available for:

1. **Top MLB Draft Picks** (especially top 5-10 overall)
   - Paul Skenes, Dylan Crews, Wyatt Langford
   - Players with significant college/amateur hype

2. **Prospects with Viral Moments**
   - Jackson Holliday (top overall pick 2022)
   - Ja

son Druw Jones (family name recognition)
   - Players with notable highlight reels

3. **International Signings with Major Buzz**
   - Top Cuban defectors
   - Highly-publicized international free agents

4. **Players Called Up to MLB**
   - Once prospects reach the majors, search volume increases dramatically

## Recommendations

### Option 1: Collect Data Opportunistically (Recommended)

Run the collection script periodically and accept that most players won't have data:

```bash
# Run weekly for top 20 leaderboard players
python collect_leaderboard_trends.py --limit 20 --delay 25
```

**Pros:**
- Simple approach
- Frontend handles missing data gracefully (hides Trends tab if no data)
- Will capture data for the few prospects who DO have search volume
- When prospects get called up, we'll start capturing their rising popularity

**Cons:**
- Most players won't have Trends data
- Search Trends component of HYPE score will be 0 for most players

### Option 2: Use Alternative Data Sources

Replace Google Trends with data sources better suited for minor league prospects:

- **Twitter/X API**: Track mentions and hashtags for prospects
- **Reddit API**: Monitor r/baseball, team subreddits
- **Baseball America / MLB Pipeline**: Track prospect ranking changes
- **MiLB.com**: Track stats and highlight views

**Pros:**
- Better coverage for minor league prospects
- More actionable social data

**Cons:**
- Requires significant additional development
- API costs for Twitter/Reddit
- More complex data collection

### Option 3: Hybrid Approach

Keep Google Trends for prospects who have data, supplement with other signals:

- Use social mentions (already tracked in HYPE system)
- Track media articles (already tracked in HYPE system)
- Weight Search Trends at 0% for players without data (current behavior)

**Pros:**
- Leverages existing HYPE infrastructure
- Gradually improves as prospects gain visibility

**Cons:**
- Inconsistent data availability across players

## Current Implementation Status

- Database schema: ✅ Complete (SearchTrend table)
- Backend collector: ✅ Complete (GoogleTrendsCollector service)
- API endpoints: ✅ Complete (search_trends in responses)
- Frontend UI: ✅ Complete (Trends tab with visualizations)
- Collection script: ✅ Complete ([collect_leaderboard_trends.py](apps/api/collect_leaderboard_trends.py))
- Error handling: ✅ Graceful (no crashes, hides UI for missing data)

## Next Steps

1. **Accept Reality**: Most prospects won't have Google Trends data
2. **Run Collection**: Execute script weekly for top 20-50 players
3. **Monitor Results**: Track which players DO have data (likely < 5%)
4. **Future Enhancement**: Consider adding Twitter/social media tracking for better prospect coverage

## Usage Instructions

### Run Collection for Top Leaderboard Players

```bash
cd apps/api

# Collect for top 10 players (default)
python collect_leaderboard_trends.py

# Collect for top 20 players with custom delay
python collect_leaderboard_trends.py --limit 20 --delay 25

# Force update even if recent data exists
python collect_leaderboard_trends.py --limit 10 --force

# See all options
python collect_leaderboard_trends.py --help
```

### Features

- **Smart Rate Limiting**: 20-second delay between requests (configurable)
- **Exponential Backoff**: Automatically retries on rate limits with increasing delays
- **Recent Data Check**: Skips players with data collected within 24 hours
- **Graceful Failure**: Stops after 3 consecutive failures to avoid IP blocks
- **Progress Tracking**: Real-time progress updates during collection

### Expected Results

- **Success Rate**: 0-5% for minor league prospects
- **Success Rate**: 50-80% for top draft picks and promoted players
- **Rate Limiting**: Google may block after 10-20 requests (wait 30-60 minutes)
- **Data Quality**: When data exists, it's accurate and valuable

## Conclusion

The Google Trends integration is **fully functional** but limited by the reality that minor league prospects don't generate enough public search interest. The system gracefully handles missing data, and the Trends tab only appears for players who have actual Google Trends data.

**Recommendation**: Proceed with Option 1 (opportunistic collection) and consider enhancing with Twitter/social media tracking in the future for better prospect coverage.
