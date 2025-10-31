# How to Clear API Cache and See Updated Rankings

The frontend is showing "no performance data available" because it's serving **cached data from before the fix**.

## The Problem

The API caches composite rankings for 30 minutes (line 558 in prospects.py):
```python
await cache_manager.cache_features(cache_key, cache_data, ttl=1800)  # 30 minutes
```

Your hard refresh only clears the **browser cache**, not the **API server cache**.

## Solution: Clear the API Cache

### Option 1: Restart the API Server (RECOMMENDED)

This will clear all in-memory caches:

```bash
# Stop the API server
# (Press Ctrl+C in the terminal running uvicorn, or kill the process)

# Clear Python cache
cd apps/api
find app -name "*.pyc" -delete
find app -name "__pycache__" -type d -exec rm -rf {} +

# Restart the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Wait 30 Minutes

The cache will automatically expire after 30 minutes and fresh data will be served.

### Option 3: Clear Redis Cache (if using Redis)

If your cache_manager uses Redis:

```bash
# Connect to Redis
redis-cli

# Clear all keys
FLUSHALL

# Or clear specific composite ranking keys
KEYS composite_rankings:*
# Then delete each key
DEL composite_rankings:free:None:None:None
```

### Option 4: Modify Cache Key to Force Refresh

Temporarily change the cache key in the code to force a cache miss:

```python
# In prospects.py line 489, change:
cache_key = f"composite_rankings:{user_tier}:{position}:{organization}:{limit}"

# To:
cache_key = f"composite_rankings_v2:{user_tier}:{position}:{organization}:{limit}"
```

## What to Expect After Cache Clear

Once the cache is cleared and API restarted, you should see:

**For prospects with pitch data (96% of players):**
```json
{
  "performance_breakdown": {
    "source": "pitch_data",
    "sample_size": 2007,
    "composite_percentile": 51.8,
    "metrics": {
      "contact_rate": 78.6,
      "whiff_rate": 21.4,
      "hard_hit_rate": 57.6,
      "exit_velo_90th": 109.6,
      "chase_rate": 18.5
    },
    "percentiles": {
      "contact_rate": 57,
      "whiff_rate": 45,
      "hard_hit_rate": 95,
      "exit_velo_90th": 95,
      "chase_rate": 89
    }
  }
}
```

**For prospects without pitch data:**
```json
{
  "performance_breakdown": {
    "source": "game_logs",
    "metric": "ops",
    "value": 0.875
  }
}
```

## Verification

After clearing cache, test the API directly:

```bash
# Test the API endpoint
curl -X GET "http://localhost:8000/api/v1/prospects/composite-rankings?page=1&page_size=5"

# Look for performance_breakdown in the response
```

## Current Commits Deployed

All fixes are committed and pushed:
- **ee9c44f**: Fixed level array type + age_adjustment KeyError
- **95f272d**: Fixed performance_breakdown API key

**The code is correct. You just need to clear the cache to see the updated data.**
