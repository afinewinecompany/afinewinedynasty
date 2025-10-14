# Google Trends Integration for HYPE Feature

## Overview

The Google Trends integration adds search interest data to player HYPE scores, providing a 15% weight component that reflects real-world public interest in players.

## Features

- **Search Interest Tracking**: 0-100 scale search interest from Google Trends
- **Growth Rate Analysis**: Percentage change in search interest over time
- **Regional Interest**: Geographic breakdown showing where players are searched most
- **Related Queries**: Top searches related to the player
- **Rising Queries**: Breakout search terms indicating trending topics

## Important Limitations

### Google Trends Rate Limiting

**Google Trends does not provide an official API** and aggressively rate-limits automated requests:

- **HTTP 429 errors are common** - Google will block requests after a few queries
- **IP-based throttling** - Multiple requests from the same IP trigger blocks
- **Temporary bans** - Can last minutes to hours
- **No workarounds** - Google intentionally limits programmatic access

### Implications

1. **Limited Collection**: Can only collect data for a small number of players at a time
2. **Delays Required**: Need 5-10 second delays between requests (sometimes longer)
3. **Unreliable**: Collection may fail at any time due to rate limiting
4. **Not Real-time**: Cannot collect trends data frequently

## Recommended Usage

### Production Strategy

**Option 1: Manual Collection** (Current Approach)
- Collect trends data manually for specific high-profile players
- Run collection during off-peak hours
- Use long delays (10+ seconds) between requests
- Accept that most players won't have trends data

**Option 2: Alternative Data Sources**
Consider these alternatives for more reliable search data:
- **Google Trends Official API** (Alpha) - Apply for access at https://developers.google.com/search/blog/2025/07/trends-api
- **SerpAPI** - Paid service that handles Google Trends scraping: https://serpapi.com/google-trends-api
- **Social Media APIs** - Twitter/X, Reddit, etc. provide more reliable engagement metrics
- **News APIs** - Track media mentions as a proxy for public interest

### Current Demo Data

For demonstration purposes, we've created mock Google Trends data for the top 10 players. This allows the frontend UI to function and showcases the feature's capabilities.

To create demo data:
```bash
python create_demo_trends_data.py
```

## API Endpoints

### Collect Trends (Manual)

```bash
POST /api/v1/hype/admin/collect-trends?player_id={player_id}
```

Collect Google Trends data for a specific player. Use sparingly due to rate limiting.

### Batch Collection

```bash
POST /api/v1/hype/admin/collect-trends?limit=5
```

Collect trends for top 5 players. Includes automatic rate limiting (3-second delays).

**Warning**: Even with delays, batch collection often triggers Google's rate limits.

## Technical Details

### Data Model

```python
class SearchTrend:
    search_interest: float  # 0-100 Google Trends score
    search_interest_avg_7d: float
    search_interest_avg_30d: float
    search_growth_rate: float  # Percentage change
    regional_interest: dict  # State/region breakdown
    related_queries: list  # Top related searches
    rising_queries: list  # Breakout searches
    collected_at: datetime
```

### HYPE Score Integration

Search Trends contributes 15% to the overall HYPE score:
- **Base Interest**: 50% of component (current search interest)
- **Growth Rate**: 25% (positive growth adds, negative subtracts)
- **Regional Spread**: 15% (number of regions with interest)
- **Query Diversity**: 10% (related/rising queries count)

## Troubleshooting

### Error: "Request failed: Google returned response with code 429"

This is expected. Google is rate-limiting your requests. Solutions:
1. Wait 10-30 minutes before trying again
2. Use a different IP address (VPN, proxy)
3. Reduce collection frequency
4. Consider alternative data sources

### No Data for Players

Minor league prospects typically have very low search volume:
- Google Trends filters out low-volume searches
- Data only available for players with significant public interest
- MLB stars will have data, most prospects won't

### Frontend Shows "No Google Trends data available"

This is normal if:
1. Trends data hasn't been collected for that player
2. Player has insufficient search volume
3. Collection failed due to rate limiting

## Future Enhancements

1. **Official Google Trends API**: Apply for alpha access when available
2. **Alternative Data Sources**: Integrate more reliable APIs (SerpAPI, social media)
3. **Caching**: Store trends data longer (30+ days) since collection is expensive
4. **Selective Collection**: Only collect for high-profile players likely to have data
5. **Proxy Rotation**: Use proxy services to work around IP-based rate limiting (paid solution)

## Conclusion

While Google Trends integration provides valuable search interest data, the unreliable nature of pytrends and Google's rate limiting makes it impractical for production use at scale.

**Recommendation**: Use this feature sparingly for high-profile players, or invest in alternative data sources (SerpAPI, official APIs) for reliable production usage.
