# MiLB Pitch Data Backfill - Execution Guide

**Date:** 2025-10-21
**Status:** READY TO EXECUTE
**Priority:** CRITICAL

---

## Problem Summary

**Current State:**
- Konnor Griffin: 168 pitches collected, but should have ~2,533 pitches (6.6% coverage)
- Bryce Eldridge: Very limited pitch data
- Many prospects have game logs but missing pitch-by-pitch data

**Root Causes:**
1. Old collection scripts hardcoded `level = 'MiLB'` instead of extracting actual levels (AA, AAA, A+, etc.)
2. Limited games collected - only recent games, not full season
3. MLB Stats API gameLog endpoint doesn't return all MiLB games for all players

---

## Solution: Two Backfill Scripts

### Option 1: backfill_from_gamelogs_2025.py (RECOMMENDED)

**Use this script for 2025 data backfill.**

**Why this works better:**
- Uses existing `game_pk` values from `milb_game_logs` table
- Doesn't rely on MLB Stats API gameLog endpoint
- Processes all games we already know about
- Tested and confirmed working with Konnor Griffin

**Command:**
```bash
cd apps/api/scripts
python backfill_from_gamelogs_2025.py
```

**What it does:**
1. Queries `milb_game_logs` for all 2025 games with plate appearances
2. For each game, fetches play-by-play data from MLB API
3. Extracts all pitches where the prospect was batting
4. Inserts pitches with correct level from game log
5. Uses `ON CONFLICT DO NOTHING` (safe to re-run)

**Expected Results:**
- Konnor Griffin: ~2,400 more pitches across A, A+, AA
- Top 200 hitters: 80-90% coverage improvement
- Correct level attribution for all pitches

**Runtime:** ~2-4 hours for 200 prospects

---

### Option 2: comprehensive_pitch_backfill_2024.py

**Use this if you need to backfill historical data (2024 or earlier).**

**Note:** Currently configured for SEASON = 2025, but can be changed.

**Limitation:** The MLB Stats API gameLog endpoint doesn't return games for all players, so this script may not collect complete data.

**Command:**
```bash
cd apps/api/scripts
python comprehensive_pitch_backfill_2024.py  # Note: Currently uses SEASON = 2025
```

---

## Recommended Execution Plan

### Step 1: Run the Game Logs Backfill (2025 Data)

```bash
cd apps/api/scripts
python backfill_from_gamelogs_2025.py
```

**Interactive Prompts:**
- Shows prospects needing backfill
- Lists top 20 by expected pitch count
- Asks for confirmation (type "yes")

**Progress:**
- Real-time logging per game
- Batch summaries every 10 players
- Final summary report

### Step 2: Validate Results

After backfill completes, check specific prospects:

```python
cd apps/api
python check_konnor_griffin.py  # Should show ~2,400+ pitches
```

Or run SQL validation:

```sql
SELECT
    p.name,
    STRING_AGG(DISTINCT bp.level, ', ' ORDER BY bp.level) as levels,
    COUNT(DISTINCT bp.pitch_id) as pitches,
    COUNT(DISTINCT bp.game_pk) as games
FROM prospects p
JOIN milb_batter_pitches bp ON p.mlb_player_id = bp.mlb_batter_id
WHERE bp.season = 2025
  AND p.name IN ('Konnor Griffin', 'Bryce Eldridge')
GROUP BY p.name;
```

**Success Criteria:**
- [ ] Konnor Griffin has 2,000+ pitches
- [ ] Multiple levels represented (A, A+, AA - not just 'MiLB')
- [ ] Top 100 hitters have >300 pitches each
- [ ] Coverage ratio: 4-5 pitches per PA

### Step 3: Refresh Percentile Views

```sql
REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;
REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;
```

### Step 4: Clear Rankings Cache

```bash
cd apps/api
python clear_rankings_cache.py
```

### Step 5: Verify Frontend

Check composite rankings page:
- Performance breakdowns should show correct levels
- Pitch data should be available for top prospects
- Percentiles should be calculated by level cohort

---

## Troubleshooting

### Issue: Script fails to connect to database

**Solution:** Check that the database URL is correct and accessible.

### Issue: Many games return 404 errors

**Possible Causes:**
- Games may not have play-by-play data available in MLB Stats API
- Some minor league games (especially Complex League) may not be recorded

**Expected:** 10-20% of games may not have detailed play-by-play data. This is normal.

### Issue: Script runs very slowly

**Causes:**
- MLB Stats API rate limiting
- Large batch size

**Solutions:**
- Reduce BATCH_SIZE in the script
- Increase delay between API calls (adjust `asyncio.sleep` values)

---

## Safety Features

Both scripts include:

1. **Non-destructive:** Uses `ON CONFLICT DO NOTHING` - won't overwrite existing data
2. **Safe to re-run:** Can restart if interrupted
3. **Connection pooling:** Auto-reconnects on failures
4. **Rate limiting:** Respects MLB Stats API limits
5. **Error isolation:** Individual game failures don't stop collection
6. **Progress preservation:** Database commits after each player

---

## Files Created

**Backfill Scripts:**
- ✅ `apps/api/scripts/backfill_from_gamelogs_2025.py` (RECOMMENDED)
- ✅ `apps/api/scripts/comprehensive_pitch_backfill_2024.py`

**Test Scripts:**
- ✅ `apps/api/scripts/test_gamelogs_backfill.py`
- ✅ `apps/api/scripts/test_backfill_bryce_eldridge.py`

**Diagnostic Scripts:**
- ✅ `apps/api/check_konnor_griffin.py`
- ✅ `apps/api/check_bryce_all_seasons.py`
- ✅ `apps/api/check_pitch_seasons.py`

**Documentation:**
- ✅ `apps/api/BACKFILL_EXECUTION_GUIDE.md` (this file)
- ✅ `apps/api/COLLECTION_SCRIPTS_UPDATE_SUMMARY.md`
- ✅ `apps/api/BACKFILL_STRATEGY.md`
- ✅ `apps/api/PITCH_DATA_COLLECTION_GAPS_FINDINGS.md`

---

## Next Steps

1. ✅ Test script verified working (Konnor Griffin - 5 games collected successfully)
2. ⬜ Run `backfill_from_gamelogs_2025.py` for all prospects
3. ⬜ Validate results
4. ⬜ Refresh percentile views
5. ⬜ Clear cache
6. ⬜ Verify frontend display

---

**Ready to Execute:** YES
**Estimated Time:** 2-4 hours
**Risk:** LOW (safe to re-run, won't duplicate)
**Impact:** CRITICAL (fixes entire pitch-based ranking system)
