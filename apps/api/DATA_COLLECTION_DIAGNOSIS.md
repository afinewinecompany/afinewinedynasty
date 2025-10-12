# MiLB Data Collection Issues - Diagnosis Report

## Critical Issues Found

### 1. **PITCHERS NOT COLLECTED** ✅ FIXED
**Location**: `scripts/collect_all_milb_gamelog.py`

**Problem**: The script ONLY requested hitting stats with `group=hitting` parameter:
```python
url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={self.season}&group=hitting&sportId={sport_id}"
```

**Impact**:
- Zero pitching game logs collected
- `games_pitched` field always 0 in database
- Pitchers appear to have no professional experience
- Cannot properly filter prospects by MLB IP threshold

**Solution Implemented**:
1. ✅ Modified `get_player_game_logs()` to accept a `group` parameter ('hitting' or 'pitching')
2. ✅ Created separate `save_hitting_game_log()` and `save_pitching_game_log()` methods
3. ✅ Updated `process_player()` to:
   - Always fetch hitting stats for all players
   - For pitchers (P, SP, RP positions), also fetch pitching stats
   - Properly save both types of data to database
4. ✅ Added college/amateur team filtering to `get_milb_teams()` to exclude non-professional players
5. ✅ Updated statistics tracking to show both hitting and pitching games collected

---

### 2. **Missing MiLB Levels** ⚠️

IGNORE


### 3. **Data Quality Issues**

**From Database Analysis**:
- 386,262 total MiLB game log rows
- 0 rows with `games_pitched > 0`
- 502 prospects in rankings with 0 games and no organization
- Only 96 position players have game logs vs 244 pitchers with predictions

**Root Cause**: Hitting-only data collection means pitchers' professional experience is invisible

---

## Next Steps

### To Collect Pitching Data

Run the updated collection script:

```bash
cd apps/api
python scripts/collect_all_milb_gamelog.py --season 2024 --levels AAA AA A+
```

This will:
- Discover all players from professional MiLB team rosters
- Filter out college/amateur teams automatically
- Collect hitting stats for all players
- Collect pitching stats for pitchers (P, SP, RP positions)
- Save both types of data to the `milb_game_logs` table

### Verification Steps

After running collection:

1. **Check pitching data in database**:
```sql
SELECT
    COUNT(*) as total_rows,
    COUNT(CASE WHEN games_pitched > 0 THEN 1 END) as pitching_rows,
    COUNT(CASE WHEN games_played > 0 THEN 1 END) as hitting_rows
FROM milb_game_logs
WHERE season = 2024;
```

2. **Verify pitcher stats**:
```sql
SELECT mlb_player_id, level,
    SUM(games_pitched) as total_games_pitched,
    SUM(innings_pitched) as total_ip
FROM milb_game_logs
WHERE games_pitched > 0 AND season = 2024
GROUP BY mlb_player_id, level
LIMIT 10;
```

3. **Re-run prospect rankings** to confirm pitchers now have proper game counts

---

## Impact on Rankings

**Current State**:
- 256 prospects in rankings
- 93 pitchers (36%)
- 160 prospects with 0 games (likely many are pitchers)

**After Fix**:
- Pitchers will have proper game counts
- Can filter by both MLB AB and IP thresholds
- Better data quality for ML training
