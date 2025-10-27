# MiLB Game Log Collection - Fixed Script Deployed

**Date:** October 22, 2025
**Status:** ✅ DEPLOYED - Running in background

---

## Problem Identified

The original `collect_milb_game_logs.py` script was **NOT querying by sport level**, causing the MLB Stats API to only return MLB games instead of MiLB games at specific levels (AA, AAA, A+, A, etc.).

**Root Cause:** Missing `sportId` parameter in API calls

---

## Solution Implemented

### New Script Created

**File:** [collect_milb_game_logs_fixed.py](collect_milb_game_logs_fixed.py)

**Key Changes:**

1. **Queries each sport level separately using sportId parameter:**
   ```python
   SPORT_LEVELS = {
       11: 'AAA',
       12: 'AA',
       13: 'A+',
       14: 'A',
       16: 'FRk',  # Foreign Rookie
   }
   ```

2. **Fixed API call to include sportId:**
   ```python
   url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
   params = {
       'stats': 'gameLog',
       'group': 'hitting',
       'season': season,
       'sportId': sport_id,  # ← CRITICAL FIX
       'gameType': 'R'
   }
   ```

3. **Fixed database connection:**
   - Changed from SQLAlchemy (`get_db_sync()`) to direct psycopg2
   - Connects to Railway database directly
   - Uses correct ON CONFLICT constraint: `(game_pk, mlb_player_id)`

4. **Proper error handling:**
   - Catches IntegrityError for constraint violations
   - Warns about invalid level values
   - Commits each game individually

---

## Deployment Status

### Currently Running

```bash
cd apps/api/scripts
nohup python collect_milb_game_logs_fixed.py --seasons 2025 > gamelog_collection_2025.log 2>&1 &
```

**Process:** Running in background
**Log File:** `apps/api/scripts/gamelog_collection_2025.log`
**Estimated Time:** ~2-3 hours for all prospects

### What It's Collecting

- **Sport Levels:** AAA (11), AA (12), A+ (13), A (14), FRk (16)
- **Season:** 2025
- **Prospects:** All prospects with MLB player IDs (~400+ prospects)
- **Game Type:** Regular season (R)

---

## Expected Results

Based on Bryce Eldridge test run:

| Level | Games Expected | Notes |
|-------|----------------|-------|
| AAA | 60-70 per player | Top prospects |
| AA | 30-40 per player | Mid-level prospects |
| A+ | 40-50 per player | Younger prospects |
| A | 50-60 per player | Entry level |
| FRk | 2-5 per player | Complex League (may fail due to constraint) |

**Total Expected:** 10,000-15,000 game logs for 2025 season

---

## Verification

After completion, verify with:

```sql
-- Check total game logs collected
SELECT COUNT(*) FROM milb_game_logs WHERE season = 2025;

-- Check by level
SELECT level, COUNT(*) as games
FROM milb_game_logs
WHERE season = 2025
GROUP BY level
ORDER BY level;

-- Check prospects with no data
SELECT p.name, p.mlb_player_id
FROM prospects p
LEFT JOIN milb_game_logs gl
    ON p.mlb_player_id::integer = gl.mlb_player_id
    AND gl.season = 2025
WHERE p.mlb_player_id IS NOT NULL
  AND gl.id IS NULL
ORDER BY p.name;
```

---

## Known Issues

### 1. FRk (Foreign Rookie) Level

**Issue:** Database constraint doesn't include 'FRk' in valid_level CHECK
**Impact:** FRk games will fail to insert with IntegrityError
**Workaround:** Script logs warning and continues

**Fix (Optional):**
```sql
ALTER TABLE milb_game_logs DROP CONSTRAINT valid_level;
ALTER TABLE milb_game_logs ADD CONSTRAINT valid_level CHECK (
    level IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Rookie+', 'Complex',
              'Winter', 'DSL', 'ACL', 'FCL', 'FRk', 'Rk')
);
```

### 2. Graduated MLB Players

**Issue:** Players who graduated to MLB in 2025 won't have MiLB games
**Impact:** Expected - these players will have 0 game logs
**Solution:** No action needed - this is correct behavior

---

## Next Steps

### 1. Monitor Progress

Check log file periodically:
```bash
tail -f apps/api/scripts/gamelog_collection_2025.log
```

### 2. After Completion

Run verification queries to ensure data quality

### 3. Collect Pitch Data

Once game logs are complete, run pitch-by-pitch collection:
```bash
cd apps/api/scripts
python backfill_from_gamelogs_2025.py
```

### 4. Update Main Script (Future)

Update the original `collect_milb_game_logs.py` to use the same sportId approach for future collections

---

## Success Metrics

**Test Run (Bryce Eldridge):**
- ✅ 218 game logs collected (2024-2025)
- ✅ Correct level attribution (AA, AAA, A+, A, Complex)
- ✅ 1,763 pitches collected from game logs
- ✅ 101% of expected data

**Expected for Full Run:**
- 10,000+ game logs for 2025
- 400+ prospects covered
- All MiLB levels represented
- Ready for pitch data collection

---

## Files Created

- [collect_milb_game_logs_fixed.py](collect_milb_game_logs_fixed.py) - Fixed collection script
- [collect_bryce_all_gamelogs_fixed.py](../collect_bryce_all_gamelogs_fixed.py) - Test script (Bryce only)
- [GAME_LOG_COLLECTION_FIX_SUMMARY.md](../GAME_LOG_COLLECTION_FIX_SUMMARY.md) - Detailed investigation
- [gamelog_collection_2025.log](gamelog_collection_2025.log) - Current run log

---

**Status:** ✅ Deployed and Running
**ETA:** 2-3 hours
**Monitor:** `tail -f apps/api/scripts/gamelog_collection_2025.log`
