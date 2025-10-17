# Google Trends Collection Strategy for All Prospects

## Current Situation

**Database Stats:**
- Total Prospects: **1,274**
- Players with HYPE data: **103** (mix of prospects and MLB players)
- Current SearchTrend records: **10** (demo data)

## The Reality of Google Trends Rate Limiting

### What We Discovered
Google Trends aggressively rate-limits automated requests:
- **HTTP 429 errors** occur after just 10-50 requests
- **IP-based blocking** lasts 30-60 minutes (sometimes hours)
- **No official API** - only unofficial pytrends library
- **Unreliable for automation** at scale

### Time Requirements (Theoretical)

With 15-second delays between requests:
- **Top 20 players**: 5 minutes
- **Top 50 players**: 12.5 minutes
- **Top 100 players**: 25 minutes
- **All 1,274 prospects**: 5.3 hours

**BUT**: You'll likely be rate-limited after 20-50 players, making full collection impossible in one session.

## Recommended Production Strategy

### Option 1: Tiered Collection (Hybrid Approach) ⭐ RECOMMENDED

```bash
# Tier 1: Top 20 prospects - Run DAILY
python scheduled_trends_collection.py --tier 1
# Time: ~5 minutes
# Risk: Medium (might work)

# Tier 2: Top 50 prospects - Run WEEKLY
python scheduled_trends_collection.py --tier 2
# Time: ~12 minutes
# Risk: High (likely to get blocked)

# Tier 3: Top 100 prospects - Run MONTHLY
python scheduled_trends_collection.py --tier 3
# Time: ~25 minutes
# Risk: Very High (will get blocked)
```

**Benefits:**
- Focus on high-priority players
- Distribute collection over time
- Most users care about top prospects anyway
- Lower-tier prospects rarely have search data

**Schedule:**
```
Daily (automated):    Tier 1 (top 20)
Weekly (semi-auto):   Tier 2 (top 50)
Monthly (manual):     Tier 3 (top 100)
Remaining prospects:  Use demo data or don't collect
```

### Option 2: Selective Collection Based on Criteria

Only collect trends for prospects meeting certain thresholds:
- **Future Value 50+** (higher-grade prospects)
- **Recent performance surges** (hot prospects)
- **Existing social buzz** (players with mentions)

This could reduce collection to 200-300 prospects.

### Option 3: Alternative Data Sources 💰

**Problem**: Google Trends is unreliable
**Solution**: Use paid alternatives or social media APIs

1. **SerpAPI** ($50-200/month)
   - Reliable Google Trends access
   - No rate limiting
   - Production-ready

2. **Google Trends Official API** (Alpha)
   - Apply at: https://developers.google.com/search/blog/2025/07/trends-api
   - More reliable than pytrends
   - May have usage limits

3. **Social Media APIs** (Better Alternative)
   - Twitter/X API: Track mentions, engagement
   - Reddit API: Track subreddit discussions
   - News APIs: Track media coverage
   - **More reliable** and **more relevant** than search data

### Option 4: Accept Limited Coverage 🎯 PRAGMATIC

**Reality Check:**
- Most prospects don't have meaningful search volume
- Google filters low-volume searches
- Only top 50-100 prospects likely to have data
- Demo data works fine for UI demonstration

**Recommendation:**
- Collect for top 20-50 players only
- Use demo data for visualization
- Focus development on social media integration instead

## Implementation Scripts

### Daily Collection (Automated)
```bash
# Add to cron/scheduler
0 2 * * * python /path/to/scheduled_trends_collection.py --tier 1
```

### Weekly Collection (Semi-automated)
```bash
# Run manually or schedule for low-traffic hours
0 3 * * 0 python /path/to/scheduled_trends_collection.py --tier 2
```

### Manual Collection (Specific Player)
```bash
python scheduled_trends_collection.py --player-id paul-skenes
```

## Data Freshness Guidelines

| Tier | Players | Frequency | Why |
|------|---------|-----------|-----|
| 1 | Top 20 | Daily | Breaking news, trades, call-ups |
| 2 | Top 50 | Weekly | Performance trends, rankings changes |
| 3 | Top 100 | Monthly | Seasonal updates |
| Rest | 1,174 | Never/Demo | Low search volume, not worth it |

## Migration to Production

### Phase 1: Current State (Demo Data)
- ✅ 10 players with demo data
- ✅ Frontend working
- ✅ Feature demonstrated

### Phase 2: Limited Real Data (Week 1)
```bash
# Start with top 10 players, increase delay to avoid blocks
python scheduled_trends_collection.py --tier 1
```

### Phase 3: Expand Coverage (Week 2-4)
- Monitor for rate limiting
- Adjust delays as needed
- If blocked, wait 24 hours
- Consider VPN/proxy rotation

### Phase 4: Evaluate Alternatives (Month 2)
Based on success rate:
- **If working**: Continue tiered approach
- **If blocked often**: Switch to SerpAPI or social media APIs
- **If no data**: Accept limited coverage, focus on social

## Cost-Benefit Analysis

### Free (pytrends)
- **Cost**: $0
- **Reliability**: 20-30%
- **Coverage**: Top 20-50 players
- **Effort**: High (manual intervention for blocks)

### SerpAPI
- **Cost**: $50-200/month
- **Reliability**: 95%+
- **Coverage**: All 1,274 prospects
- **Effort**: Low (set and forget)

### Social Media APIs
- **Cost**: $0-100/month
- **Reliability**: 90%+
- **Coverage**: All prospects with mentions
- **Data Quality**: Better (actual engagement vs. search)

## Final Recommendation 🏆

**For MVP/Current Phase:**
1. Keep demo data for most prospects
2. Collect top 10-20 players manually/weekly
3. Accept that coverage will be limited
4. **Focus on social media integration** (more reliable)

**For Production (Month 2+):**
1. Evaluate if trends data is providing value
2. If yes: Invest in SerpAPI ($50/month)
3. If no: Remove feature or make it "premium MLB players only"
4. Prioritize social media APIs over Google Trends

## The Honest Truth

**Google Trends is NOT suitable for:**
- Automated collection at scale
- Real-time updates
- Reliable production systems
- Minor league prospects (low search volume)

**Google Trends IS suitable for:**
- Manual research (1-5 players)
- High-profile MLB stars
- Occasional spot checks
- Marketing/research purposes

**Bottom Line:**
- Use demo data for now
- Collect top 20 manually
- Plan to migrate to social media APIs or SerpAPI
- Don't invest heavily in Google Trends automation

---

## Additional User Request: Prospects-Only Leaderboard

**Issue**: Hype leaderboard currently shows mix of prospects and MLB players

**Solution**: Filter PlayerHype to only show prospects from the prospects table

See `FIX_HYPE_PROSPECTS_ONLY.md` for implementation details.
