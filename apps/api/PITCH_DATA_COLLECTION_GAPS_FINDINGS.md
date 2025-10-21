# MiLB Pitch-by-Pitch Data Collection Gap Analysis

**Date:** 2025-10-21
**Status:** 🔴 CRITICAL GAPS IDENTIFIED
**Impact:** Composite rankings using incomplete data

---

## Executive Summary

Investigation into pitch-by-pitch data collection has revealed **MASSIVE** gaps in our MiLB pitch tracking database. Top prospects are missing 80-90% of their expected pitch data, severely undermining the accuracy of our new pitch-based composite ranking system.

### Key Findings

1. **Bryce Eldridge**: 160 pitches collected vs **1,746 expected** (9.2% coverage)
   - Missing: CPX and AAA data entirely
   - Only has: 10 games in AA (Sept 15-28, 2025)

2. **Konnor Griffin**: 168 pitches collected vs **2,080 expected** (8.1% coverage)
   - Missing: A, A+, and most AA data
   - Incomplete cross-level tracking

3. **System-wide Impact**: The pitch-based performance modifiers in composite rankings are using severely incomplete data, leading to:
   - Inaccurate percentile calculations
   - Missing cohort comparisons
   - Unreliable performance assessments

---

## Technical Investigation Details

### Database Schema Issues Discovered

1. **Table Name Confusion**
   - Correct table: `milb_game_logs` (not `milb_batter_game_logs`)
   - Pitch table: `milb_batter_pitches`
   - Column: `mlb_batter_id` (INTEGER type, not VARCHAR)

2. **Type Casting Requirements**
   - `prospects.mlb_player_id` stored as INTEGER
   - Must cast: `int(mlb_player_id)` when querying pitch tables
   - Join syntax: `prospects.mlb_player_id = milb_batter_pitches.mlb_batter_id`

### Data Collection Evidence

**Bryce Eldridge (MLB ID: 805811)**
```sql
SELECT COUNT(*) FROM milb_batter_pitches
WHERE mlb_batter_id = 805811
  AND game_date >= '2024-01-01'
-- Result: 160 pitches

SELECT COUNT(DISTINCT level) as levels
FROM milb_batter_pitches
WHERE mlb_batter_id = 805811
-- Result: 1 level (AA only)

-- Expected: CPX, AA, AAA = 1,746 total pitches
-- Actual: AA only = 160 pitches
-- Missing: 1,586 pitches (90.8%)
```

**Date Range**
- First pitch: 2025-09-15
- Last pitch: 2025-09-28
- Games covered: 10

This represents only the **final 2 weeks of the 2024 season** for a prospect who played across multiple levels throughout the year.

---

## Root Cause Analysis

### Probable Causes

1. **Incomplete Collection Scripts**
   - Collection may have only targeted specific date ranges
   - Level-specific collection gaps (CPX, rookie ball missing)
   - Collection stopped prematurely or failed mid-season

2. **API Rate Limiting / Failures**
   - MiLB Stats API may have rate-limited requests
   - Collection scripts may not have proper retry logic
   - Errors not logged or handled gracefully

3. **Level Classification Issues**
   - CPX (Complex League) may use different level codes
   - Foreign league data (DSL, etc.) may not be captured
   - Level transitions mid-season not tracked

4. **Historical vs Real-Time Collection**
   - Scripts may have focused on current season only
   - Backfill for earlier months never completed
   - No continuous/incremental collection running

---

## Impact on Composite Rankings

### Current System Behavior

The new pitch-based ranking system (just deployed) is:

1. **Calculating percentiles from incomplete data**
   - Cohort comparisons invalid (comparing partial seasons)
   - Percentile rankings skewed by missing early-season data
   - Players with more complete data unfairly ranked higher

2. **Graceful degradation working TOO well**
   - System falls back to game logs when <50 pitches
   - Hides the severity of the collection problem
   - Users see rankings without realizing they're based on limited data

3. **Frontend showing misleading indicators**
   - "Pitch Data" badges displayed for prospects with only 160 pitches
   - No warning about incomplete coverage
   - Sample size not prominently displayed

### Affected Rankings

- **Top 100 Hitters**: Likely 60-80% with incomplete pitch data
- **Performance Modifiers**: Based on partial season snapshots
- **Level Comparisons**: Invalid (comparing full seasons vs partial)

---

## Remediation Plan

### Phase 1: Immediate Assessment (1-2 hours)

1. **Create comprehensive audit script**
   ```python
   # Count prospects by pitch data completeness
   SELECT
       CASE
           WHEN pitch_count = 0 THEN 'No Data'
           WHEN pitch_count < 100 THEN 'Critical (<100)'
           WHEN pitch_count < 500 THEN 'Partial (100-500)'
           WHEN pitch_count < 1000 THEN 'Good (500-1000)'
           ELSE 'Complete (1000+)'
       END as coverage_tier,
       COUNT(*) as prospects
   FROM (
       SELECT
           p.mlb_player_id,
           COUNT(bp.pitch_id) as pitch_count
       FROM prospects p
       LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id = bp.mlb_batter_id
       WHERE p.fangraphs_fv_latest > 45
       GROUP BY p.mlb_player_id
   ) coverage
   GROUP BY coverage_tier
   ```

2. **Identify collection gaps by level**
   - Which levels have data: A, A+, AA, AAA, CPX, Rk, etc.
   - Which levels are completely missing
   - Date range gaps within each level

3. **Export missing data manifest**
   - List of top 200 prospects
   - Expected vs actual pitch counts
   - Specific levels/date ranges to collect

### Phase 2: Collection Fix (2-5 days)

1. **Update collection scripts**
   - Add comprehensive level coverage (CPX, Rk, FRk, etc.)
   - Implement full-season backfill (April-September)
   - Add proper error handling and retry logic
   - Log missing data for manual review

2. **Run targeted collections**
   - Priority 1: Top 100 prospects, all levels, full 2024 season
   - Priority 2: Top 200 prospects, all levels
   - Priority 3: All prospects with >45 FV

3. **Validate completeness**
   - Cross-reference with game logs (PA count vs pitch count)
   - Expected ratio: ~4-5 pitches per PA
   - Flag outliers for manual inspection

### Phase 3: System Updates (1 day)

1. **Frontend indicators**
   - Add sample size warnings ("Based on 160 pitches")
   - Show coverage percentage vs expected
   - Flag incomplete data with yellow/red indicators

2. **Ranking adjustments**
   - Temporarily increase minimum pitch threshold
   - Add confidence scores based on sample size
   - Consider disabling pitch-based modifiers until data complete

3. **Monitoring dashboard**
   - Track collection progress
   - Alert on new gaps
   - Daily data quality reports

---

## Recommended Actions

### Immediate (Today)

1. ✅ **Document findings** (this file)
2. ⬜ **Run comprehensive audit** (create script based on Phase 1)
3. ⬜ **Brief stakeholders** on incomplete data
4. ⬜ **Decide**: Disable pitch-based rankings temporarily OR add prominent warnings

### Short-term (This Week)

1. ⬜ **Fix collection scripts** to gather all levels
2. ⬜ **Backfill 2024 season** for top 200 prospects
3. ⬜ **Update frontend** to show data quality indicators
4. ⬜ **Re-run percentile calculations** with complete data

### Long-term (Ongoing)

1. ⬜ **Daily incremental collections** for new games
2. ⬜ **Data quality monitoring** dashboard
3. ⬜ **Automated alerts** for collection failures
4. ⬜ **Historical backfill** for 2023, 2022, 2021

---

## Technical Debt Created

1. **Deployed ranking system** before validating data completeness
2. **No data quality checks** in the ingestion pipeline
3. **Missing monitoring** for collection health
4. **No alerting** on incomplete prospect coverage

---

## Files to Review/Update

### Collection Scripts
- `apps/api/scripts/collect_batter_pitches_*.py`
- `apps/api/scripts/collect_2024_pitches_robust.py`
- Need to verify level coverage and date ranges

### Database Queries
- `apps/api/app/services/pitch_data_aggregator.py` - Works correctly
- `apps/api/app/services/prospect_ranking_service.py` - Using incomplete data
- Frontend components - Need data quality indicators

### Frontend Updates Needed
- `apps/web/src/components/rankings/PerformanceBreakdown.tsx` - Add warnings
- `apps/web/src/components/rankings/CompositeRankingsTable.tsx` - Show coverage %
- Add "Data Quality" column or tooltip

---

## Next Steps

**Priority:** Create audit script to quantify the full extent of the gap across all top prospects, then determine whether to:

A) **Pause pitch-based rankings** until data is complete
B) **Add prominent warnings** and continue with incomplete data
C) **Emergency collection sprint** to backfill critical prospects this week

**Recommendation:** Option C (emergency sprint) + Option B (warnings) in parallel.

---

**Investigation Lead:** Claude Code Agent
**Date Completed:** 2025-10-21
**Status:** Findings documented, remediation pending
**Next Review:** After audit script results
