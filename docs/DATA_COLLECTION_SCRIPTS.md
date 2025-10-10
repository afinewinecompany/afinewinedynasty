# Data Collection Scripts Documentation

This document catalogs all data collection scripts, their locations, purposes, and usage.

## Overview

The data collection system runs multiple concurrent processes to gather:
1. **MiLB Game Logs** (2021-2025) - Minor league game-by-game stats
2. **MLB Game Logs** (2021-2025) - Major league game-by-game stats for prospects

All scripts use the MLB Stats API and implement rate limiting, error handling, and smart skipping of existing data.

---

## Core Collection Scripts

### 1. MiLB Game Log Collector
**Location**: `apps/api/scripts/collect_all_milb_gamelog.py`

**Purpose**: Collect game-by-game MiLB statistics for all players across all minor league levels.

**Key Features**:
- Collects **both hitting AND pitching** stats
- Supports all MiLB levels: AAA, AA, A+, A, DSL (Dominican Summer League), ROK (Rookie), ACL (Arizona Complex League)
- Smart skipping: Checks existing data and only fetches missing stats
- Separate tracking for hitting vs pitching data to avoid skipping pitchers who need pitching stats
- Comprehensive stats: 60+ pitching metrics, 30+ hitting metrics

**Usage**:
```bash
# Single season
python -m scripts.collect_all_milb_gamelog --season 2024 --levels AAA AA A+

# Multiple levels including rookie leagues
python -m scripts.collect_all_milb_gamelog --season 2023 --levels AAA AA "A+" A DSL ROK ACL
```

**Stats Collected**:

*Hitting Stats (30+ fields)*:
- Basic: PA, AB, R, H, 2B, 3B, HR, RBI, BB, K, SB, CS
- Advanced: HBP, SF, SH, GO, FO, AO, GIDP, TB, LOB
- Rate: AVG, OBP, SLG, OPS, BABIP

*Pitching Stats (60+ fields)*:
- Game Results: G, GS, CG, SHO, GF, W, L, SV, SVO, HLD, BS
- Volume: IP, Outs, BF, Pitches, Strikes
- Allowed: H, R, ER, HR, BB, IBB, HBP
- Strikeouts: K
- Defense: SB, CS, Balks, WP, PO
- Inherited: IR, IRS
- Batted Balls: FO, GO, AO, GIDP
- Rate: ERA, WHIP, AVG Against, OBP Against, SLG Against, OPS Against
- Per 9: K/9, BB/9, H/9, HR/9, R/9
- Ratios: K/BB, GO/AO, Strike%, Win%, Pitches/IP, SB% Against

**Database Table**: `milb_game_logs`

**Data Source**: `mlb_stats_api_gamelog`

---

### 2. MLB Game Log Collector
**Location**: `apps/api/scripts/collect_mlb_gamelogs.py`

**Purpose**: Collect MLB game-by-game hitting statistics for all players who have MiLB data (prospects who made it to the majors).

**Key Features**:
- Automatically finds all unique players from MiLB data
- Collects MLB hitting performance (currently hitting only, pitching to be added)
- Provides "Y" (outcome) data for ML models where MiLB is "X" (features)
- Tracks conversion rate from MiLB to MLB

**Usage**:
```bash
# Multiple seasons
python -m scripts.collect_mlb_gamelogs --seasons 2025 2024 2023 2022 2021

# Default runs 2024-2020 if no seasons specified
python -m scripts.collect_mlb_gamelogs
```

**Stats Collected**:

*Hitting Stats*:
- Basic: G, PA, AB, R, H, 2B, 3B, HR, RBI, BB, IBB, K, SB, CS, HBP
- Sacrifices: SF, SH
- Batted Balls: GO, FO, GIDP
- Advanced: TB, LOB
- Rate: AVG, OBP, SLG, OPS

**Database Table**: `mlb_game_logs`

**Current Limitation**: Only hitting stats (pitching to be added in future enhancement)

---

## Orchestration Scripts

### 3. Sequential Batch Runner
**Location**: `apps/api/run_all_seasons_collection.py`

**Purpose**: Run MiLB collection for multiple seasons sequentially (one after another).

**Usage**:
```bash
python run_all_seasons_collection.py
```

**Configuration**:
- Seasons: 2024, 2023, 2022, 2021 (hardcoded in script)
- Levels: AAA, AA, A+, A, DSL, ROK, ACL (configurable in `main()`)

**Features**:
- Runs seasons one at a time
- Provides summary report at end
- Continues to next season even if one fails

**Note**: Use this for lower-resource environments. For faster collection, use concurrent runner.

---

### 4. Concurrent Multi-Season Runner
**Location**: `apps/api/run_concurrent_seasons.py`

**Purpose**: Start multiple season collections running in parallel (concurrent).

**Usage**:
```bash
python run_concurrent_seasons.py
```

**What It Does**:
- Starts 2023, 2022, 2021 collections concurrently (each in background)
- Creates separate log files: `collection_2023.log`, `collection_2022.log`, `collection_2021.log`
- Staggers starts by 2 seconds to avoid overwhelming API
- Does NOT restart 2024 (assumes already running)

**Benefits**:
- ~4x faster than sequential (all finish in time of slowest vs sum of all)
- Better resource utilization
- Each season runs independently

---

## Currently Running Collections (as of 2025-10-07)

### Active Processes & Log Files:

| Collection | Log File | Command | PID | Status |
|------------|----------|---------|-----|--------|
| 2024 MiLB | `collection_batch.log` | Manual start | 943400 | Running |
| 2023 MiLB | `collection_2023.log` | concurrent_seasons.py | 3044 | Running |
| 2022 MiLB | `collection_2022.log` | concurrent_seasons.py | 18508 | Running |
| 2021 MiLB | `collection_2021.log` | concurrent_seasons.py | 23548 | Running |
| 2025 MiLB | `collection_2025.log` | Manual start | 25db7c | Running |
| MLB Data | `collection_mlb.log` | Manual start | 0cbea2 | Running |

### Monitoring Collections:

Check progress:
```bash
# View recent activity for a season
tail -f apps/api/collection_2024.log

# Check all collections at once
tail -n 5 apps/api/collection_*.log

# Count players processed
grep -c "Player" apps/api/collection_2024.log
```

---

## Database Schema

### milb_game_logs Table

**Primary Columns**:
- `id` - Primary key
- `prospect_id` - Link to prospects table (nullable)
- `mlb_player_id` - MLB Stats API player ID
- `season` - Year (2021-2025)
- `game_pk` - Unique game identifier
- `game_date` - Date of game
- `level` - MiLB level (AAA, AA, A+, A, DSL, ROK, ACL)
- `game_type` - 'Regular' (vs preseason, playoffs)
- `team_id`, `opponent_id` - Team identifiers

**Hitting Columns** (~30 fields):
- `games_played`, `plate_appearances`, `at_bats`, `runs`, `hits`
- `doubles`, `triples`, `home_runs`, `rbi`, `total_bases`
- `walks`, `intentional_walks`, `strikeouts`
- `stolen_bases`, `caught_stealing`, `hit_by_pitch`
- `sacrifice_flies`, `sac_bunts`, `ground_outs`, `fly_outs`, `air_outs`
- `ground_into_double_play`, `number_of_pitches`, `left_on_base`
- `batting_avg`, `on_base_pct`, `slugging_pct`, `ops`, `babip`

**Pitching Columns** (~60 fields):
- `games_pitched`, `games_started`, `complete_games`, `shutouts`, `games_finished`
- `wins`, `losses`, `saves`, `save_opportunities`, `holds`, `blown_saves`
- `innings_pitched`, `outs`, `batters_faced`, `number_of_pitches_pitched`, `strikes`
- `hits_allowed`, `runs_allowed`, `earned_runs`, `home_runs_allowed`
- `walks_allowed`, `intentional_walks_allowed`, `strikeouts_pitched`, `hit_batsmen`
- `stolen_bases_allowed`, `caught_stealing_allowed`, `balks`, `wild_pitches`, `pickoffs`
- `inherited_runners`, `inherited_runners_scored`
- `fly_outs_pitched`, `ground_outs_pitched`, `air_outs_pitched`
- `ground_into_double_play_pitched`, `total_bases_allowed`
- `sac_bunts_allowed`, `sac_flies_allowed`, `catchers_interference_pitched`
- `era`, `whip`, `avg_against`, `obp_against`, `slg_against`, `ops_against`
- `win_percentage`, `strike_percentage`, `pitches_per_inning`, `strikeout_walk_ratio`
- `strikeouts_per_9inn`, `walks_per_9inn`, `hits_per_9inn`, `runs_scored_per_9`, `home_runs_per_9`
- `stolen_base_percentage_against`, `ground_outs_to_airouts_pitched`

**Indexes**:
- `idx_milb_game_logs_unique_game` - UNIQUE(game_pk, mlb_player_id)
- Additional indexes on player_id, season, date (for query performance)

### mlb_game_logs Table

**Primary Columns**:
- `id` - Primary key
- `mlb_player_id` - MLB Stats API player ID
- `season`, `game_pk`, `game_date`, `game_type`
- `team_id`, `opponent_id`, `is_home`, `is_win`

**Hitting Columns** (~30 fields):
- Same as MiLB hitting stats
- Additional: `games_played` always 1 (game-by-game)

**Indexes**:
- UNIQUE(game_pk, mlb_player_id)
- idx_mlb_logs_player, idx_mlb_logs_season, idx_mlb_logs_date

**Note**: Pitching columns to be added in future enhancement

---

## Key Implementation Details

### Smart Skipping Logic

The MiLB collector implements intelligent skipping to avoid redundant API calls:

```python
# Load existing data at startup
async def load_existing_data(self):
    # Get players with hitting data (games_played > 0)
    self.existing_hitting = {player_ids with hitting stats}

    # Get players with pitching data (games_pitched > 0)
    self.existing_pitching = {player_ids with pitching stats}

# Check before processing
async def process_player(self, player):
    need_hitting = player_id not in self.existing_hitting
    need_pitching = is_pitcher and (player_id not in self.existing_pitching)

    if not need_hitting and not need_pitching:
        skip_player()  # Already have all needed data
```

**Why This Matters**:
- 2023: Has 2,225 players with hitting, only 24 with pitching → Collects pitching for ~2,200 pitchers
- 2022: Has 2,258 players with hitting, only 24 with pitching → Collects pitching for ~2,234 pitchers
- 2021: Has 512 players with hitting, only 13 with pitching → Collects pitching for ~499 pitchers

**Result**: Saves ~5,000 redundant hitting API calls while collecting critical missing pitching data.

### Safe Float Conversion

Many MLB API stats return `.---` for undefined values (e.g., ERA when 0 innings pitched):

```python
def safe_float(value) -> Optional[float]:
    if value in ('.---', '-.--', '∞', 'Infinity', ''):
        return None
    return float(value)
```

### Error Handling

All scripts use:
- Try/except blocks around API calls
- Logging of errors without stopping collection
- ON CONFLICT clauses in SQL for duplicate prevention
- Rate limiting (0.5s between requests)

---

## Collection Performance

### Typical Rates:
- **MiLB Collection**: 8-12 seconds per player
  - Depends on: number of games played, API response time, pitching vs hitting
  - Pitchers with 40+ games take longer than bench players with 5 games

- **MLB Collection**: 15-25 seconds per player
  - Checking 5 seasons per player (2021-2025)
  - Most prospects have 0 MLB games (quick)
  - Veterans with 500+ MLB games take longer

### Expected Completion Times (6 concurrent collections):
- **2024 MiLB**: ~12 hours (4,101 players, 3 levels)
- **2023 MiLB**: ~13 hours (5,463 players, 7 levels, smart skipping)
- **2022 MiLB**: ~13 hours (5,534 players, 7 levels, smart skipping)
- **2021 MiLB**: ~14 hours (5,357 players, 7 levels, smart skipping)
- **2025 MiLB**: ~15 hours (3,286 players, 7 levels, new data)
- **MLB Data**: ~26 hours (4,842 players × 5 seasons, many with 0 MLB games)

**Total Wall Time**: ~26 hours (limited by slowest collection)

**Sequential Would Take**: ~90+ hours (sum of all)

**Speedup from Concurrency**: ~3.5x faster

---

## Troubleshooting

### Common Issues

**1. Column Name Mismatches**
- **Error**: `column "sac_flies" does not exist`
- **Cause**: Database uses `sacrifice_flies` but script used `sac_flies`
- **Fix**: Check actual DB column names with:
  ```sql
  SELECT column_name FROM information_schema.columns
  WHERE table_name = 'milb_game_logs' ORDER BY column_name;
  ```

**2. Check Constraint Violations**
- **Error**: `violates check constraint "valid_game_type"`
- **Cause**: Database expects 'Regular' but script sends 'R'
- **Fix**: Query existing values first:
  ```sql
  SELECT DISTINCT game_type FROM milb_game_logs LIMIT 10;
  ```

**3. Python Cache Issues**
- **Symptom**: Code changes not taking effect
- **Fix**: Clear cache before restarting:
  ```bash
  cd apps/api
  find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
  find . -name "*.pyc" -delete
  ```

**4. Process Already Running**
- **Symptom**: "Address already in use" or duplicate data
- **Fix**: Check running processes:
  ```bash
  # Windows
  tasklist | findstr python

  # Kill specific PID
  taskkill /F /PID <pid>
  ```

### Verifying Data Collection

**Check hitting vs pitching breakdown**:
```sql
SELECT
    season,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN games_played > 0 THEN 1 END) as hitting_rows,
    COUNT(CASE WHEN games_pitched > 0 THEN 1 END) as pitching_rows,
    COUNT(DISTINCT mlb_player_id) as unique_players
FROM milb_game_logs
GROUP BY season
ORDER BY season DESC;
```

**Check data quality**:
```sql
-- Pitchers with complete stats
SELECT
    mlb_player_id,
    COUNT(*) as games,
    SUM(innings_pitched) as total_ip,
    AVG(era) as avg_era,
    SUM(strikeouts_pitched) as total_k
FROM milb_game_logs
WHERE games_pitched > 0 AND season = 2024
GROUP BY mlb_player_id
HAVING COUNT(*) >= 10
ORDER BY total_ip DESC
LIMIT 20;
```

**Check for missing data**:
```sql
-- Players with hitting but no pitching (should be position players)
SELECT COUNT(DISTINCT mlb_player_id)
FROM milb_game_logs
WHERE games_played > 0
AND mlb_player_id NOT IN (
    SELECT DISTINCT mlb_player_id
    FROM milb_game_logs
    WHERE games_pitched > 0
);
```

---

## Future Enhancements

### Planned Improvements:

1. **MLB Pitching Stats** (High Priority)
   - Add pitching data collection to `collect_mlb_gamelogs.py`
   - Mirror MiLB implementation with 60+ pitching metrics
   - Create separate `save_pitching_game_log()` method

2. **Incremental Updates**
   - Add `--incremental` flag to only collect recent games
   - Store last collection date per player
   - Reduce API calls for ongoing season updates

3. **Parallel Player Processing**
   - Use asyncio.gather() to process multiple players concurrently
   - Could reduce collection time by 2-3x
   - Need to respect API rate limits

4. **Data Validation**
   - Add sanity checks (e.g., ERA shouldn't be negative)
   - Flag suspicious data for manual review
   - Track API data quality issues

5. **Progress Tracking**
   - Web dashboard showing collection progress
   - Real-time stats on games collected
   - Error rate monitoring

6. **Resume Capability**
   - Save checkpoint every N players
   - Ability to resume interrupted collection
   - Skip already-processed players in current run

---

## API Reference

### MLB Stats API Endpoints Used

**Game Logs - Hitting**:
```
GET /api/v1/people/{playerId}/stats
  ?stats=gameLog
  &season={year}
  &group=hitting
  &sportId={sportId}
```

**Game Logs - Pitching**:
```
GET /api/v1/people/{playerId}/stats
  ?stats=gameLog
  &season={year}
  &group=pitching
  &sportId={sportId}
```

**Teams for Season/Level**:
```
GET /api/v1/teams
  ?sportId={sportId}
  &season={year}
```

**Team Roster**:
```
GET /api/v1/teams/{teamId}/roster
  ?rosterType=fullSeason
  &season={year}
```

### Sport IDs
- `1` - MLB (Major League Baseball)
- `11` - AAA (Triple-A)
- `12` - AA (Double-A)
- `13` - A+ (High-A)
- `14` - A (Single-A)
- `15` - Rookie
- `16` - ROK (Rookie Advanced)

**Note**: DSL and ACL may use different IDs - check API documentation

### Rate Limiting
- **Current**: 0.5 seconds between requests
- **Recommended**: Stay under 2 requests/second
- **MLB API Limit**: Undocumented but generous for reasonable use

---

## Statcast Data Collection

### Overview

In addition to game log stats, we collect **Statcast data** - advanced tracking metrics from Trackman/Hawkeye systems:
- **MiLB Statcast**: Play-by-play batted ball data (exit velocity, launch angle, distance)
- **MLB Statcast**: Both hitting and pitching metrics via Baseball Savant

**See [STATCAST_COLLECTION_PLAN.md](./STATCAST_COLLECTION_PLAN.md) for comprehensive documentation.**

### Scripts

#### 1. MiLB Play-by-Play Statcast Collector
**Location**: `apps/api/scripts/collect_milb_pbp_statcast.py`

Collects raw plate appearance data with Statcast metrics from game play-by-play feeds.

**Current Data**:
- 72,058 plate appearances with Statcast (145K total PAs)
- AAA only, seasons 2022-2025
- 386 unique players

**Tables**: `milb_plate_appearances`

#### 2. MLB Statcast Collector
**Location**: `apps/api/scripts/collect_mlb_statcast.py`

Collects MLB Statcast for prospects using `pybaseball` library.

**Usage**:
```bash
python -m scripts.collect_mlb_statcast --seasons 2024 2023 2022 2021
```

**Data Collected**:
- **Hitting**: Exit velocity, launch angle, barrel%, hard hit%, estimated wOBA
- **Pitching**: Velocity, spin rate, movement, release point, pitch type usage

**Tables**: `mlb_statcast_hitting`, `mlb_statcast_pitching`

**Currently Running**: Collecting for 5,239 prospects across 4 seasons (2021-2024)

#### 3. Statcast Metrics Aggregator
**Location**: `apps/api/scripts/aggregate_statcast_metrics.py`

Aggregates raw plate appearances into player-season-level metrics.

**Usage**:
```bash
python -m scripts.aggregate_statcast_metrics
```

**Metrics Calculated**:
- Exit Velocity: avg, max, 90th percentile
- Hard Hit % (95+ mph), Barrel %
- Launch Angle metrics (overall and on hard hits)
- Fly Ball Exit Velocity
- Batted Ball Distribution (GB%, LD%, FB%, PU%)

**Output Table**: `milb_statcast_metrics` (662 player-season-level combinations)

---

## Related Documentation

- [STATCAST_COLLECTION_PLAN.md](./STATCAST_COLLECTION_PLAN.md) - **Comprehensive Statcast strategy and gaps**
- [ML_DATA_DOCUMENTATION.md](./ML_DATA_DOCUMENTATION.md) - Feature engineering and ML models
- [PROSPECT_RANKINGS_PLAN.md](./PROSPECT_RANKINGS_PLAN.md) - Prospect ranking system
- [DATA_COLLECTION_DIAGNOSIS.md](../apps/api/DATA_COLLECTION_DIAGNOSIS.md) - Original problem analysis
- [PITCHING_DATA_FIX_SUMMARY.md](../apps/api/PITCHING_DATA_FIX_SUMMARY.md) - Pitching data fix details

---

## Changelog

### 2025-10-07 - Major Enhancement
- ✅ Added pitching data collection to MiLB script
- ✅ Implemented smart skipping (separate hitting vs pitching)
- ✅ Added 4 advanced pitching metrics (K/BB ratio, pitches/IP, GO/AO, SB% against)
- ✅ Fixed column name mismatches (sacrifice_flies, on_base_pct, slugging_pct)
- ✅ Started concurrent collection for 5 MiLB seasons (2021-2025)
- ✅ Started MLB game log collection (2021-2025)
- ✅ Created MLB Statcast collector (hitting & pitching via pybaseball)
- ✅ Aggregated existing MiLB Statcast data (662 metrics)
- ✅ Started MLB Statcast collection for 5,239 prospects
- ✅ Created comprehensive Statcast collection plan

### Previous
- Original hitting-only MiLB collection
- MLB game log collection (hitting only)
- Sequential batch runner
- MiLB play-by-play Statcast collector (AAA only)
