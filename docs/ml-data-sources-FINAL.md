# ML Data Sources - FINAL DECISION

## Executive Summary

After comprehensive testing, **MLB Stats API provides the most granular minor league data** and should be the **primary source** for all statistics (both MLB and MiLB). Fangraphs should be used for **supplemental advanced analytics**.

---

## Data Source Comparison - COMPLETE

### MLB Stats API (PRIMARY) ⭐⭐⭐⭐⭐

**Minor League Stats:**
- **Endpoint:** `https://statsapi.mlb.com/api/v1/people/{playerId}/stats`
- **Granularity:** GAME-BY-GAME logs available!
- **Parameters:**
  - `stats=gameLog` - Individual game stats
  - `stats=season` - Season totals
  - `stats=career` - Career totals
  - `sportId=11` - All minor leagues
  - `sportId=12,13,14,15,16` - Specific levels (AAA, AA, A+, A, Rookie)

**Stats Available (33+ fields per game):**
- Traditional: AB, H, 2B, 3B, HR, R, RBI, BB, SO, SB, CS
- Advanced: AVG, OBP, SLG, OPS, BABIP
- Batted Ball: Ground outs, air outs, fly outs, GB/AO ratio
- Discipline: IBB, HBP, SF, SH, pitch count
- Situational: LOB, GIDP, GITP

**Major League Stats:**
- Same endpoint, `sportId=1`
- Identical stat structure
- Consistent tracking from minors → majors

**Advantages:**
- ✅ Official MLB data (authoritative)
- ✅ GAME-BY-GAME granularity (most detailed)
- ✅ Consistent player IDs (MLB ID works everywhere)
- ✅ Free, stable, well-documented API
- ✅ Covers both MiLB and MLB with same structure
- ✅ Historical data available (2010+)
- ✅ Real-time updates during season

**Rate Limits:**
- 1000 requests/day (generous for our needs)

**Example Response:**
```json
{
  "date": "2024-08-11",
  "opponent": {"name": "Syracuse Mets"},
  "isHome": false,
  "stat": {
    "gamesPlayed": 1,
    "atBats": 2,
    "hits": 0,
    "homeRuns": 0,
    "rbi": 1,
    "baseOnBalls": 1,
    "strikeOuts": 1,
    "avg": ".000",
    "obp": ".333",
    "slg": ".000",
    "ops": ".333",
    "numberOfPitches": 10,
    // ... 33 total fields
  }
}
```

---

### Fangraphs MiLB API (SUPPLEMENTAL) ⭐⭐⭐⭐

**Endpoint:** `https://www.fangraphs.com/api/leaders/minor-league/data`

**Stats Available (50+ fields):**
- Everything MLB API has PLUS:
- **Advanced Sabermetrics:**
  - wRC, wRAA, wOBA, wRC+ (weighted runs created metrics)
  - ISO (isolated power)
- **Detailed Batted Ball:**
  - GB%, LD%, FB%, IFFB%, HR/FB ratio
  - Pull%, Oppo%, Cent% (spray angle)
- **Plate Discipline:**
  - SwStr% (swinging strike rate)
  - Contact%, Zone%, O-Swing%, Z-Swing%
- **Speed/Baserunning:**
  - Spd (speed score)
  - wBsR (weighted baserunning runs)
- **Quality Metrics:**
  - Hard%, Soft%, Med% (contact quality)

**Advantages:**
- ✅ Advanced analytics not in MLB API
- ✅ Sabermetric community standard (wRC+, wOBA)
- ✅ Batted ball profiles
- ✅ Plate discipline deep metrics

**Limitations:**
- ❌ Season aggregates only (no game logs)
- ❌ Requires name matching (less reliable)
- ❌ Only qualified players (min PA threshold)

---

### Fangraphs Prospects API (SCOUTING) ⭐⭐⭐⭐⭐

**Endpoint:** `https://www.fangraphs.com/api/prospects/board/prospects-list-combined`

**Unique Value:**
- Professional scouting grades (20-80 scale)
- Future Value projections
- Risk assessments
- Expert evaluations

**Status:** Essential for ML model, no alternative source

---

## FINAL RECOMMENDATION

### Optimal Data Collection Strategy

```
1. MLB STATS API (Primary for all stats)
   └─> Minor League Stats
       - Use game logs for granular data
       - Aggregate to season/career as needed
       - Track by level (AAA, AA, A+, A, Rookie)
   └─> Major League Stats
       - Same API, consistent structure
       - Use for outcome variables

2. FANGRAPHS PROSPECTS API (Scouting grades)
   └─> Professional evaluations
   └─> Future Value, tools, risk

3. FANGRAPHS MiLB API (Optional enrichment)
   └─> Add advanced metrics (wRC+, wOBA, etc.)
   └─> Only if needed for specific ML features
   └─> Can calculate some from MLB API data
```

---

## ML Feature Set - UPDATED

### Total Features Per Prospect: 120-150 fields

**1. Bio/Draft (10 fields)**
- From MLB/Fangraphs APIs

**2. Scouting Grades (25 fields)**
- From Fangraphs Prospects API

**3. Minor League Stats (60-80 fields)**
- **From MLB API (primary):**
  - Season aggregates by level
  - Career totals
  - Game log derived metrics:
    - Consistency scores
    - Hot/cold streaks
    - Performance trends
    - Clutch performance (late innings)

- **From Fangraphs (supplemental):**
  - wRC+, wOBA (if not calculated)
  - Detailed batted ball %
  - Advanced plate discipline

**4. Major League Stats (35 fields)**
- From MLB API
- For prospects who reached MLB
- Used for target variable creation

**5. Derived Features (30+ fields)**
- MiLB → MLB progression metrics
- Age-adjusted performance
- Level promotion velocity
- Tool grade vs performance alignment
- Consistency metrics from game logs

---

## Implementation Changes

### Updated Collection Script

```python
async def collect_complete_prospect_data(player_id: int, years: list):
    """
    Collect all data for ML training using optimal sources.

    Args:
        player_id: MLB player ID
        years: List of years to collect
    """

    # 1. Get MLB minor league stats (PRIMARY)
    mlb_milb_stats = []
    for year in years:
        # Game logs for granular data
        game_log = await fetch_mlb_game_log(player_id, year, sport_id=11)
        mlb_milb_stats.append({
            'year': year,
            'games': game_log,
            'season_totals': aggregate_season(game_log),
            'derived': calculate_game_log_features(game_log)
        })

    # 2. Get MLB major league stats (if applicable)
    mlb_mlb_stats = await fetch_mlb_stats(player_id, sport_id=1)

    # 3. Get Fangraphs scouting grades
    fg_scouting = await fetch_fangraphs_scouting(player_name, year)

    # 4. Optional: Enrich with Fangraphs advanced metrics
    fg_advanced = await fetch_fangraphs_milb(player_name, year)

    # 5. Merge all sources
    complete_data = {
        'player_id': player_id,
        'mlb_milb_stats': mlb_milb_stats,
        'mlb_mlb_stats': mlb_mlb_stats,
        'scouting_grades': fg_scouting,
        'advanced_metrics': fg_advanced
    }

    return complete_data
```

### Database Schema Updates

```sql
-- Add game log table for granular MiLB data
CREATE TABLE milb_game_logs (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    game_date DATE,
    opponent VARCHAR(100),
    is_home BOOLEAN,
    level VARCHAR(10),
    -- All 33 stat fields from MLB API
    at_bats INTEGER,
    hits INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    stolen_bases INTEGER,
    -- ... etc

    -- Game log derived metrics
    multi_hit_game BOOLEAN,
    extra_base_hit_game BOOLEAN,
    strikeout_game BOOLEAN
);

-- Aggregate tables can be views or materialized views
CREATE MATERIALIZED VIEW milb_season_stats AS
SELECT
    prospect_id,
    season,
    level,
    COUNT(*) as games,
    SUM(at_bats) as total_ab,
    SUM(hits) as total_hits,
    AVG(hits::float / NULLIF(at_bats, 0)) as avg,
    -- ... aggregate all stats
FROM milb_game_logs
GROUP BY prospect_id, season, level;
```

---

## Advantages of MLB API Approach

### 1. Maximum Granularity
- Game-by-game logs enable:
  - Consistency metrics (variance in performance)
  - Streak detection (hot/cold periods)
  - Clutch performance (high leverage situations)
  - Developmental trajectory (improvement over time)
  - Injury impact analysis (before/after gaps)

### 2. Unified Data Source
- Same API for MiLB and MLB
- Consistent player IDs
- No name matching issues
- Same stat definitions

### 3. ML Model Benefits
- Time series features from game logs
- Performance trend analysis
- Volatility/consistency as predictive features
- Better signal for "late bloomer" prospects

### 4. Operational Simplicity
- One primary API vs multiple sources
- Official, stable, well-maintained
- Free with reasonable rate limits

---

## Collection Timeline (Updated)

### With MLB API as Primary:

**Single Prospect (5 year history):**
- MLB API calls: ~10-15 requests
  - 5 game logs (1 per year)
  - 5 season summaries
  - 1 MLB stats check
- Fangraphs: 2 requests
  - 1 for scouting grades
  - 1 for advanced metrics (optional)
- **Total time: ~30 seconds per prospect**

**600 Prospects (full year cohort):**
- MLB API: ~6,000-9,000 requests
  - Within 1000/day limit: 6-9 days
  - Or use multiple API keys if available
- Fangraphs: 600-1200 requests
  - At 1 req/sec: 10-20 minutes
- **Total time: 1-2 weeks for complete historical collection**

**Optimization:**
- Batch similar requests
- Parallel processing where possible
- Cache aggressively
- Request only what's needed (levels where player actually played)

---

## Final Decision Matrix

| Criterion | MLB API | Fangraphs MiLB |
|-----------|---------|----------------|
| Granularity | ⭐⭐⭐⭐⭐ Game logs | ⭐⭐⭐ Season only |
| Data Authority | ⭐⭐⭐⭐⭐ Official | ⭐⭐⭐⭐ Calculated |
| Coverage | ⭐⭐⭐⭐⭐ All players | ⭐⭐⭐ Qualified only |
| Consistency | ⭐⭐⭐⭐⭐ Same as MLB | ⭐⭐⭐ Different |
| Advanced Metrics | ⭐⭐⭐ Basic | ⭐⭐⭐⭐⭐ Deep |
| Rate Limits | ⭐⭐⭐⭐ 1000/day | ⭐⭐⭐⭐⭐ None found |
| Reliability | ⭐⭐⭐⭐⭐ Very stable | ⭐⭐⭐⭐ Stable |

**Winner: MLB Stats API for primary stats collection**

Use Fangraphs MiLB API only for:
- Advanced sabermetrics (wRC+, wOBA) if not calculating ourselves
- Batted ball profiles (GB%, FB%, Pull%)
- Elite plate discipline metrics (SwStr%, Contact%)

---

## Next Steps

1. ✅ Update collection scripts to use MLB API as primary
2. ✅ Add game log collection and aggregation
3. ✅ Create derived features from game logs
4. ✅ Keep Fangraphs Prospects API for scouting grades
5. ✅ Optionally add Fangraphs MiLB for specific advanced metrics
6. ✅ Update database schema for game logs
7. ✅ Test on 2024 prospects
8. ✅ Run full historical collection (2010-2024)

---

## Conclusion

**MLB Stats API is the superior choice for minor league statistics:**
- Most granular (game-by-game)
- Official and authoritative
- Consistent with MLB data
- Free and stable
- Enables advanced time-series features

**Combined with Fangraphs scouting grades, we have the optimal ML dataset:**
- Professional scout evaluations (Fangraphs)
- Granular performance data (MLB API)
- Advanced analytics (Fangraphs, optional)
- Complete player tracking (MLB IDs)

**This is a world-class data foundation for prospect prediction!** 🚀
