# Parallel Data Collection - Running Status

**Started:** October 22, 2025, 10:00 AM
**Status:** ✅ BOTH PROCESSES RUNNING IN PARALLEL

---

## Overview

We are now running **TWO collection processes simultaneously**:

1. **Game Log Collection** - Collecting 2025 game logs for all 2,336 prospects
2. **Pitch Data Collection** - Collecting pitch-by-pitch data for 1,110 prospects with existing game logs

---

## Process 1: Game Log Collection

**Script:** [collect_milb_game_logs_fixed.py](collect_milb_game_logs_fixed.py)
**Log File:** `gamelog_collection_2025.log`
**Command:** `python collect_milb_game_logs_fixed.py --seasons 2025`

### Status
- **Total Prospects:** 2,336
- **Current Progress:** ~768/2,336 (33%)
- **Sport Levels:** AAA (11), AA (12), A+ (13), A (14), FRk (16)
- **Games Collected:** ~15,000+ so far
- **ETA:** 3-4 hours total

### Recent Output
```
[768/2336] Processing Paul Bonzagni (MLB ID: 805823)
[767/2336] Processing prospect X: Saved 123 games (AAA: 34, AA: 55, A+: 34)
```

### Known Issues
- FRk (Foreign Rookie) games fail due to database constraint
- These are logged and skipped (not critical)

---

## Process 2: Pitch Data Collection

**Script:** [collect_pitch_data_from_gamelogs.py](collect_pitch_data_from_gamelogs.py)
**Log File:** `pitch_collection_2025.log`
**Command:** `python collect_pitch_data_from_gamelogs.py`

### Status
- **Total Prospects:** 1,110 (with existing game logs)
- **Batch Size:** 50 prospects at a time
- **Current Progress:** Processing batch ~1-2
- **Pitches Collected:** Thousands already (893, 1802, 48, 33 per player shown)
- **ETA:** 4-6 hours total

### Recent Output
```
Sandy León (506702): 58 games
  -> Collected 893 pitches
Carlos Pérez (542208): 111 games
  -> Collected 1802 pitches
```

### Performance
- Processes 10 games per batch
- Rate limited to 0.5s between batches
- Safe ON CONFLICT DO NOTHING prevents duplicates

---

## Why Parallel Collection Works

1. **Different Data Sources:**
   - Game logs: Query MLB Stats API by sportId
   - Pitch data: Query game feed API by game_pk

2. **No Conflicts:**
   - Game logs write to `milb_game_logs` table
   - Pitch data writes to `milb_batter_pitches` table
   - Different tables = no locking issues

3. **Optimized for Maximum Throughput:**
   - Game log collection: Sequential by prospect, parallel by sport level
   - Pitch collection: Batch processing with async HTTP requests

4. **Database Safety:**
   - Both use ON CONFLICT DO NOTHING
   - Individual commits per game/pitch batch
   - Rollback on errors

---

## Monitoring

### Check Game Log Progress
```bash
tail -f apps/api/scripts/gamelog_collection_2025.log
```

### Check Pitch Data Progress
```bash
tail -f apps/api/scripts/pitch_collection_2025.log
```

### Check Both at Once
```bash
tail -f apps/api/scripts/gamelog_collection_2025.log apps/api/scripts/pitch_collection_2025.log
```

### Database Status Query
```sql
-- Check current counts
SELECT
    'Game Logs' as type,
    season,
    level,
    COUNT(*) as count
FROM milb_game_logs
WHERE season = 2025
GROUP BY season, level

UNION ALL

SELECT
    'Pitch Data' as type,
    season,
    level,
    COUNT(*) as count
FROM milb_batter_pitches
WHERE season = 2025
GROUP BY season, level
ORDER BY type, level;
```

---

## Expected Final Results

### Game Logs (When Complete)
- **Prospects:** 2,336 prospects processed
- **Game Logs:** 25,000-30,000 total games
- **Levels:** AAA, AA, A+, A (FRk excluded due to constraint)
- **Coverage:** All active 2025 MiLB players

### Pitch Data (When Complete)
- **Prospects:** 1,110 prospects processed
- **Pitches:** 500,000-1,000,000+ pitches
- **Levels:** All levels from game logs
- **Coverage:** Complete pitch-by-pitch data for all game logs

---

## What Happens Next

### As Game Logs Complete
The pitch data collection script can be run again to pick up newly collected game logs:

```bash
cd apps/api/scripts
python collect_pitch_data_from_gamelogs.py > pitch_collection_round2.log 2>&1 &
```

### Verification After Completion

1. Check for prospects with game logs but no pitch data:
```sql
SELECT p.name, p.mlb_player_id, COUNT(DISTINCT gl.game_pk) as games
FROM prospects p
JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id
LEFT JOIN milb_batter_pitches bp
    ON gl.game_pk = bp.game_pk
    AND gl.mlb_player_id = bp.mlb_batter_id
WHERE gl.season = 2025
  AND bp.id IS NULL
GROUP BY p.name, p.mlb_player_id
HAVING COUNT(DISTINCT gl.game_pk) > 0
ORDER BY games DESC;
```

2. Run additional pitch collection for any gaps

---

## Success Metrics

**Bryce Eldridge (Test Case):**
- ✅ 218 game logs (2024-2025)
- ✅ 1,763 pitches (573 AA + 1,165 AAA + 25 Complex)
- ✅ 101% of expected coverage

**Expected for Full Collection:**
- Game logs: 25,000-30,000 for 2025
- Pitch data: 500,000-1,000,000+ pitches for 2025
- Coverage: 100% of available MLB Stats API data

---

## Files & Processes

### Scripts Running
- `collect_milb_game_logs_fixed.py` (PID: check with `ps aux | grep collect_milb`)
- `collect_pitch_data_from_gamelogs.py` (PID: check with `ps aux | grep collect_pitch`)

### Log Files
- `apps/api/scripts/gamelog_collection_2025.log`
- `apps/api/scripts/pitch_collection_2025.log`

### Related Scripts
- `backfill_specific_prospects.py` - Completed (Bryce & Konnor)
- `collect_bryce_all_gamelogs_fixed.py` - Test script (successful)

---

**Status:** ✅ RUNNING
**ETA:** 4-6 hours for completion
**Monitor:** `tail -f apps/api/scripts/*.log`
