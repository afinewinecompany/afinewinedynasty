# Composite Rankings Display Update Guide

**Date:** 2025-10-21
**Issue:** Composite rankings not showing pitch-level data updates
**Status:** ✅ **RESOLVED**

---

## Problem Identified

The composite rankings page wasn't displaying the new pitch-based performance data because:

1. **Missing API field:** The `performance_breakdown` field wasn't included in the `CompositeRankingResponse` model
2. **Cached data:** Old rankings were cached (30-min TTL) without the new breakdown data
3. **No frontend integration:** Frontend wasn't consuming the new field (yet)

---

## Solution Implemented

### 1. Updated API Response Model ✅

**File:** `apps/api/app/api/api_v1/endpoints/prospects.py`

**Changes:**
```python
class CompositeRankingResponse(BaseModel):
    # ... existing fields ...

    # NEW: Detailed performance breakdown
    performance_breakdown: Optional[Dict] = Field(
        None,
        description="Detailed performance metrics breakdown (pitch data or game logs)"
    )
```

### 2. Updated Endpoint to Include Breakdown ✅

**File:** `apps/api/app/api/api_v1/endpoints/prospects.py`

**Changes:**
```python
response_prospects.append(CompositeRankingResponse(
    # ... existing fields ...
    performance_breakdown=ranked_prospect['scores'].get('performance_breakdown'),  # NEW
    # ... remaining fields ...
))
```

### 3. Created Cache Clearing Script ✅

**File:** `apps/api/clear_rankings_cache.py`

Run this to force regeneration:
```bash
cd apps/api
python clear_rankings_cache.py
```

---

## What the API Now Returns

### Before (Missing Data)
```json
{
  "rank": 1,
  "name": "Jesús Made",
  "composite_score": 66.0,
  "base_fv": 65.0,
  "performance_modifier": 0.0,
  "trend_adjustment": 2.0,
  "age_adjustment": 3.0
}
```

### After (With Performance Breakdown)
```json
{
  "rank": 1,
  "name": "Jesús Made",
  "composite_score": 66.0,
  "base_fv": 65.0,
  "performance_modifier": 0.0,
  "performance_breakdown": {
    "source": "pitch_data",
    "composite_percentile": 56.8,
    "metrics": {
      "exit_velo_90th": 98.5,
      "hard_hit_rate": 42.3,
      "contact_rate": 78.2,
      "whiff_rate": 22.1,
      "chase_rate": 28.5
    },
    "percentiles": {
      "exit_velo_90th": 85.2,
      "hard_hit_rate": 78.5,
      "contact_rate": 82.0,
      "whiff_rate": 75.0,
      "chase_rate": 68.0
    },
    "weighted_contributions": {
      "exit_velo_90th": 21.30,
      "hard_hit_rate": 15.70,
      "contact_rate": 12.30,
      "whiff_rate": 11.25,
      "chase_rate": 6.80,
      "ops": 8.45
    },
    "sample_size": 234,
    "days_covered": 60,
    "level": "AA"
  },
  "trend_adjustment": 2.0,
  "age_adjustment": 3.0
}
```

---

## Steps to See Updates

### Backend (API Server)

1. **Ensure materialized views are refreshed:**
   ```bash
   psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;"
   psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;"
   ```

2. **Clear cached rankings:**
   ```bash
   cd apps/api
   python clear_rankings_cache.py
   ```

   OR wait 30 minutes for cache to expire naturally.

3. **Restart API server** (if needed):
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Test endpoint:**
   ```bash
   curl "http://localhost:8000/v1/prospects/composite-rankings?page=1&page_size=5" | python -m json.tool
   ```

### Frontend (Next Steps)

The API now provides the data. To display it in the UI:

#### Option 1: Simple Display
Show the data source and composite percentile:

```tsx
{prospect.performance_breakdown && (
  <div className="performance-details">
    <span className="badge">
      {prospect.performance_breakdown.source === 'pitch_data' ? '📊 Pitch Data' : '📈 Game Logs'}
    </span>
    <span>
      {prospect.performance_breakdown.composite_percentile.toFixed(1)}th percentile
    </span>
  </div>
)}
```

#### Option 2: Detailed Breakdown
Show individual metrics in a tooltip or expandable section:

```tsx
{prospect.performance_breakdown?.source === 'pitch_data' && (
  <div className="metric-breakdown">
    <h4>Performance Metrics</h4>
    <div className="metrics-grid">
      {Object.entries(prospect.performance_breakdown.percentiles).map(([metric, percentile]) => (
        <div key={metric} className="metric-item">
          <span className="metric-name">{formatMetricName(metric)}</span>
          <div className="percentile-bar">
            <div style={{ width: `${percentile}%` }} className="percentile-fill" />
          </div>
          <span className="percentile-value">{percentile.toFixed(1)}%ile</span>
        </div>
      ))}
    </div>
    <div className="meta">
      Based on {prospect.performance_breakdown.sample_size} pitches at {prospect.performance_breakdown.level}
    </div>
  </div>
)}
```

#### Option 3: Visual Indicators
Use color-coded badges:

```tsx
const getPercentileColor = (percentile: number) => {
  if (percentile >= 90) return 'elite';
  if (percentile >= 75) return 'great';
  if (percentile >= 60) return 'good';
  if (percentile >= 40) return 'average';
  return 'below-average';
};

{prospect.performance_breakdown && (
  <div className={`performance-badge ${getPercentileColor(prospect.performance_breakdown.composite_percentile)}`}>
    {prospect.performance_breakdown.composite_percentile.toFixed(0)}th %ile
  </div>
)}
```

---

## Cache Management

### Manual Cache Clear
```bash
cd apps/api
python clear_rankings_cache.py
```

### Automatic Cache Expiration
- Cache TTL: 30 minutes
- Rankings automatically regenerate on next request after expiration

### When to Clear Cache
- After materialized view refresh
- After changing ranking algorithm
- For immediate testing/debugging

---

## Monitoring

### Check if Pitch Data is Being Used

```bash
curl -s "http://localhost:8000/v1/prospects/composite-rankings?page=1&page_size=10" | \
  python -c "import sys, json; data = json.load(sys.stdin); print(f\"Prospects with pitch data: {sum(1 for p in data['prospects'] if p.get('performance_breakdown', {}).get('source') == 'pitch_data')} / {len(data['prospects'])}\")"
```

### Check Breakdown Details

```bash
curl -s "http://localhost:8000/v1/prospects/composite-rankings?page=1&page_size=1" | \
  python -c "import sys, json; data = json.load(sys.stdin); p = data['prospects'][0]; print(json.dumps(p.get('performance_breakdown'), indent=2))"
```

---

## Troubleshooting

### Issue: Rankings haven't changed

**Solution:**
1. Clear cache: `python clear_rankings_cache.py`
2. Refresh materialized views
3. Restart API server
4. Verify materialized views have data: `test_pitch_ranking_system.py`

### Issue: performance_breakdown is null for all prospects

**Possible causes:**
1. No pitch data in database (check `milb_batter_pitches`, `milb_pitcher_pitches`)
2. Materialized views not populated (run refresh)
3. Player IDs don't match (check `mlb_player_id` consistency)
4. Recent data outside 60-day window

**Debug:**
```bash
cd apps/api
python test_pitch_ranking_system.py
```

### Issue: Only some prospects have breakdowns

**This is expected!**
- Not all prospects have pitch-level data
- System gracefully falls back to game logs or FV
- Coverage: ~47% batters, ~27% pitchers

---

## Performance Considerations

### API Response Size
- With breakdowns: ~2-3KB per prospect
- Without breakdowns: ~500B per prospect
- Consider pagination for large lists

### Cache Strategy
- Full rankings cached for 30 min
- Materialized views refreshed daily (recommended)
- Individual prospect lookups not cached currently

---

## Summary of Changes

### Commits
1. `e0e4a81` - Initial pitch ranking system implementation
2. `50f9ddc` - Added performance_breakdown to API response

### Files Changed
- ✅ `apps/api/app/api/api_v1/endpoints/prospects.py` - Updated response model
- ✅ `apps/api/clear_rankings_cache.py` - Cache clearing utility

### Still TODO
- [ ] Frontend UI updates to display breakdown data
- [ ] Set up daily cron job for materialized view refresh
- [ ] Optional: Add admin dashboard for monitoring

---

## Testing Checklist

After deployment:

- [ ] API returns performance_breakdown field
- [ ] Breakdown contains expected fields (source, percentiles, metrics)
- [ ] Pitch data source shows for prospects with data
- [ ] Game logs fallback works for prospects without pitch data
- [ ] Cache clears successfully
- [ ] Rankings regenerate with new data
- [ ] Frontend displays updates (when implemented)

---

**Status:** ✅ Backend complete, ready for frontend integration
**Next:** Update UI to display performance_breakdown data
