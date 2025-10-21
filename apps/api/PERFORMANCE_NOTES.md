# API Performance Issues and Recommendations

## Composite Rankings Endpoint Performance Issue

**Endpoint:** `/api/v1/prospects/composite-rankings`

**Current Status:** Working but slow (~48 seconds for initial request)

### Problem Description

The composite rankings endpoint executes complex SQL queries with multiple lateral joins to combine FanGraphs grades with recent MiLB performance data. Without proper database indexing, this query takes 45-50 seconds on first execution.

### Current Mitigation

1. **Backend caching:** Results are cached for 30 minutes in Redis
2. **Frontend timeout:** Increased to 60 seconds to accommodate initial slow query
3. Subsequent requests are fast (<1 second) due to caching

### Recommended Long-Term Fixes

#### 1. Add Database Indexes

Add the following indexes to improve query performance:

```sql
-- Index for prospects table
CREATE INDEX IF NOT EXISTS idx_prospects_fg_player_id ON prospects(fg_player_id);
CREATE INDEX IF NOT EXISTS idx_prospects_mlb_player_id ON prospects(mlb_player_id);
CREATE INDEX IF NOT EXISTS idx_prospects_position ON prospects(position);

-- Index for fangraphs_hitter_grades
CREATE INDEX IF NOT EXISTS idx_fg_hitter_player_year
  ON fangraphs_hitter_grades(fangraphs_player_id, data_year);

-- Index for fangraphs_pitcher_grades
CREATE INDEX IF NOT EXISTS idx_fg_pitcher_player_year
  ON fangraphs_pitcher_grades(fangraphs_player_id, data_year);

-- Index for milb_game_logs (critical for lateral joins)
CREATE INDEX IF NOT EXISTS idx_milb_logs_player_date
  ON milb_game_logs(mlb_player_id, game_date DESC);
CREATE INDEX IF NOT EXISTS idx_milb_logs_date
  ON milb_game_logs(game_date DESC);
```

#### 2. Optimize Query Strategy

**Current approach:** Lateral joins for each prospect to calculate recent stats
**Better approach:** Pre-aggregate recent stats in a materialized view

```sql
-- Create materialized view for recent performance (refresh daily)
CREATE MATERIALIZED VIEW mv_recent_prospect_stats AS
SELECT
    mlb_player_id,
    AVG(CASE WHEN at_bats > 0 THEN ops END) as recent_60d_ops,
    AVG(CASE WHEN innings_pitched > 0 THEN era END) as recent_60d_era,
    COUNT(*) as games_played_60d,
    MAX(level) as recent_level
FROM milb_game_logs
WHERE game_date > CURRENT_DATE - INTERVAL '60 days'
GROUP BY mlb_player_id;

CREATE INDEX idx_mv_recent_stats ON mv_recent_prospect_stats(mlb_player_id);

-- Refresh daily via cron job
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_recent_prospect_stats;
```

#### 3. Query Optimization

Replace lateral joins with materialized view joins:

```sql
-- Instead of expensive lateral joins, use pre-aggregated view
LEFT JOIN mv_recent_prospect_stats recent
    ON CAST(recent.mlb_player_id AS VARCHAR) = p.mlb_player_id
```

### Expected Performance Improvement

With these optimizations:
- **Initial query time:** 48s → 2-5s (90% improvement)
- **Cached query time:** <1s (unchanged)
- **Database load:** Significantly reduced

### Implementation Priority

**Priority:** High
**Effort:** Medium (2-3 hours)
**Impact:** High (critical user experience improvement)

### Related Files

- Backend: `apps/api/app/services/prospect_ranking_service.py`
- Frontend: `apps/web/src/hooks/useCompositeRankings.ts`
- API Client: `apps/web/src/lib/api/client.ts`

### Monitoring

Add performance monitoring to track query execution time:

```python
import time
import logging

logger = logging.getLogger(__name__)

start_time = time.time()
result = await self.db.execute(query)
duration = time.time() - start_time

logger.info(f"Composite rankings query took {duration:.2f}s")

if duration > 10:
    logger.warning(f"Slow query detected: {duration:.2f}s - Consider adding indexes")
```

---

**Last Updated:** 2025-10-21
**Status:** Temporary fix deployed (frontend timeout increased)
**Next Steps:** Implement database indexes and materialized views
