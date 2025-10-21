# MiLB Pitch Data Backfill Strategy

**Created:** 2025-10-21
**Status:** READY TO EXECUTE

---

## Critical Bug Fixed

### The Problem

The existing collection scripts (`collect_batter_pitches_*.py`) have a CRITICAL BUG on line 101:

```python
level = 'MiLB'  # WRONG! This hardcodes all pitches as 'MiLB' instead of actual level
```

This means:
- All pitch data collected has `level = 'MiLB'` instead of `'AA'`, `'AAA'`, `'CPX'`, etc.
- Cannot calculate percentiles by level cohort
- Cannot compare AA performance vs AAA performance
- The entire pitch-based ranking system is compromised

### The Solution

**New Script Created:** `comprehensive_pitch_backfill_2024.py`

**Key Fixes:**
1. ✅ Gets ACTUAL level from MLB Stats API game log
2. ✅ Maps sport_id to correct level names (AA, AAA, A+, A, CPX, Rk, etc.)
3. ✅ Full season coverage (not just recent games)
4. ✅ Proper error handling and retry logic
5. ✅ Progress tracking and validation

**Level Mapping:**
```python
MILB_SPORT_IDS = {
    11: 'AAA',   # Triple-A
    12: 'AA',    # Double-A
    13: 'A+',    # High-A
    14: 'A',     # Single-A
    15: 'Rk',    # Rookie
    16: 'FRk',   # Rookie Advanced
    5442: 'CPX', # Complex/Arizona Complex League
}
```

---

## Execution Plan

### Phase 1: Determine Season (URGENT)

**Question:** Are we backfilling 2024 or 2025 data?

- Investigation showed Bryce Eldridge has pitches from `2025-09-15` to `2025-09-28`
- But prospects are current 2024 season players
- Need to determine: Is this October 2024 (so Sept 2024 is recent) or October 2025?

**Action:** Check prospect game logs to see what season they're in

```sql
SELECT
    season,
    COUNT(DISTINCT mlb_player_id) as prospects,
    MIN(game_date) as first_date,
    MAX(game_date) as last_date
FROM milb_game_logs
GROUP BY season
ORDER BY season DESC;
```

### Phase 2: Run Backfill

**Target:** Top 200 hitters by FV

**Command:**
```bash
cd apps/api/scripts
python comprehensive_pitch_backfill_2024.py
```

**What it does:**
1. Queries prospects with FV > 45, excluding pitchers
2. Checks existing pitch data coverage
3. Identifies prospects with <4 pitches per PA (incomplete)
4. Collects ALL games from MLB Stats API with level information
5. Processes games in batches with retry logic
6. Inserts pitches with ON CONFLICT DO NOTHING (safe to re-run)

**Expected Results:**
- Bryce Eldridge: ~1,746 pitches across CPX, AA, AAA
- Konnor Griffin: ~2,080 pitches across A, A+, AA
- Top 200: 80-90% coverage improvement

**Runtime:** ~2-4 hours for 200 prospects (depends on API speed)

### Phase 3: Validate

**Validation Query:**
```sql
WITH pitch_coverage AS (
    SELECT
        p.name,
        p.mlb_player_id,
        COUNT(DISTINCT bp.pitch_id) as pitches,
        SUM(gl.pa) as total_pa,
        STRING_AGG(DISTINCT bp.level, ', ' ORDER BY bp.level) as levels,
        ROUND((COUNT(DISTINCT bp.pitch_id)::numeric / NULLIF(SUM(gl.pa), 0)) * 100, 1) as coverage_pct
    FROM prospects p
    LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id = bp.mlb_batter_id
        AND bp.season = 2024
    LEFT JOIN milb_game_logs gl ON p.mlb_player_id = gl.mlb_player_id
        AND gl.season = 2024
    WHERE p.fangraphs_fv_latest > 50
    GROUP BY p.name, p.mlb_player_id
)
SELECT
    name,
    pitches,
    total_pa,
    levels,
    coverage_pct
FROM pitch_coverage
WHERE total_pa > 0
ORDER BY coverage_pct DESC NULLS LAST
LIMIT 50;
```

**Success Criteria:**
- Top 100 prospects: >80% have 300+ pitches
- Level distribution: At least 3-4 different levels represented
- Coverage ratio: 4-5 pitches per PA average
- No more hardcoded `'MiLB'` levels

### Phase 4: Re-calculate Percentiles

After backfill completes:

1. **Refresh materialized views:**
```sql
REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;
REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;
```

2. **Clear rankings cache:**
```bash
cd apps/api
python clear_rankings_cache.py
```

3. **Verify frontend display:**
- Check Bryce Eldridge's composite ranking
- Should show pitch data from multiple levels
- Performance breakdown should show CPX, AA, AAA stats

---

## Script Features

### Error Handling

- **Retry Logic:** 3 attempts with exponential backoff
- **Timeout Protection:** 45s per game, 600s per batch
- **Connection Pooling:** Auto-reconnect on database failures
- **Graceful Degradation:** Continues on individual game failures

### Progress Tracking

- **Real-time Logging:** Game-by-game progress
- **Batch Summaries:** Every batch shows total pitches
- **Checkpoints:** Every 5 batches with cumulative stats
- **Final Report:** Complete summary with timing

### Safety Features

- **ON CONFLICT DO NOTHING:** Safe to re-run, won't duplicate
- **Confirmation Prompt:** Must type "yes" to proceed
- **Connection Limits:** Max 5 concurrent, 3 per host (respects API limits)
- **Rate Limiting:** 0.3s delay between games, 1.0s between players

---

## Expected Output

```
================================================================================
COMPREHENSIVE 2024 MILB PITCH DATA BACKFILL
Started: 2025-10-21 15:45:00
================================================================================

Fixes:
  1. Collects ACTUAL levels (A, A+, AA, AAA, CPX, Rk) - not hardcoded 'MiLB'
  2. Full season coverage across all levels
  3. Proper error handling and retry logic
  4. Validates against game logs
================================================================================

Found 187 prospects needing pitch data backfill

Top 20:
    1. Bryce Eldridge (ID: 805811)
    2. Konnor Griffin (ID: 123456)
    ...

 Ready to collect data for 187 prospects
Continue? (yes/no): yes

################################################################################
BATCH 1/19: 10 players
################################################################################

================================================================================
Player: Bryce Eldridge (ID: 805811)
Games Found: 47 | Total PAs: 212
Levels: CPX(12), AA(20), AAA(15)
================================================================================
Existing pitches: AA:160

  Level CPX: 12 games
    CPX: 542 pitches from 12/12 games
  Level AA: 20 games
    AA: 876 pitches from 20/20 games
  Level AAA: 15 games
    AAA: 328 pitches from 15/15 games

  Summary: 1,746 pitches | 47/47 games OK | 0 failed | 32.4s

...

================================================================================
BACKFILL COMPLETE
================================================================================
Prospects Processed: 187
Total Pitches Collected: 287,432
Total Games Processed: 6,234
Total Games Failed: 142
Total Time: 127.3 minutes
Completed: 2025-10-21 17:52:18
================================================================================
```

---

## Post-Backfill Actions

1. **Update Frontend Warnings** (if data still incomplete)
   - Add sample size badges
   - Show coverage percentages
   - Flag prospects with <200 pitches

2. **Monitor Data Quality**
   - Daily validation queries
   - Alert on new collection gaps
   - Track API failures

3. **Incremental Collections**
   - Set up daily cron for new games
   - Backfill 2023, 2022, 2021 (lower priority)
   - Monitor for mid-season promotions/demotions

---

## Files Created

1. **`comprehensive_pitch_backfill_2024.py`** - Main backfill script
2. **`test_backfill_bryce_eldridge.py`** - Test script for single prospect
3. **`PITCH_DATA_COLLECTION_GAPS_FINDINGS.md`** - Investigation findings
4. **`BACKFILL_STRATEGY.md`** - This file

---

## Next Steps

1. ✅ Script created with bug fixes
2. ⬜ Determine correct season (2024 vs 2025)
3. ⬜ Test with Bryce Eldridge
4. ⬜ Run full backfill for top 200
5. ⬜ Validate results
6. ⬜ Refresh percentile views
7. ⬜ Clear cache
8. ⬜ Verify frontend display

---

**Ready to Execute:** YES
**Estimated Time:** 2-4 hours
**Risk:** LOW (safe to re-run, won't duplicate)
**Impact:** CRITICAL (fixes entire pitch-based ranking system)
