# Statcast Data Collection Plan

## Current Status

### Existing Data (as of 2025-10-07)

**MiLB Statcast Data**:
- **Total**: 72,058 plate appearances with Statcast data
- **Players**: 386 unique players
- **Coverage**: AAA only, seasons 2022-2025
- **Aggregated Metrics**: 662 player-season-level combinations

| Season | Level | Players | Plate Appearances |
|--------|-------|---------|-------------------|
| 2025   | AAA   | 167     | 18,891           |
| 2024   | AAA   | 195     | 21,703           |
| 2023   | AAA   | 198     | 22,269           |
| 2022   | AAA   | 105     | 9,195            |

**MLB Statcast Data**: Not yet collected

---

## What is Statcast Data?

Statcast is MLB's advanced tracking technology that provides:

### For Hitters:
- **Exit Velocity (EV)**: Speed of ball off bat (mph)
- **Launch Angle (LA)**: Vertical angle of ball trajectory (degrees)
- **Distance**: How far the ball traveled (feet)
- **Spray Angle**: Horizontal direction (pull/center/oppo)
- **Trajectory**: GB (ground ball), LD (line drive), FB (fly ball), PU (popup)
- **Hardness**: Soft, medium, hard classification

### Calculated Metrics:
- **Barrel %**: Optimal EV/LA combinations most likely to produce extra bases
- **Hard Hit %**: Percentage of balls hit 95+ mph
- **Average EV**: Mean exit velocity on all batted balls
- **90th Percentile EV**: Shows ceiling/maximum bat speed
- **Fly Ball EV**: Average EV on fly balls specifically
- **Batted Ball Distribution**: GB%, LD%, FB%, PU%

---

## Scripts & Tables

### Collection Scripts

#### 1. MiLB Play-by-Play Statcast Collector
**Location**: `apps/api/scripts/collect_milb_pbp_statcast.py`

**Purpose**: Collect raw plate appearance data with Statcast metrics from MLB API play-by-play feeds.

**How It Works**:
1. Gets player's game log for a season/level
2. For each game, fetches full play-by-play data
3. Extracts batted ball events with `hitData` (Statcast metrics)
4. Saves to `milb_plate_appearances` table

**Usage**:
```bash
# Not currently parameterized - needs enhancement
python -m scripts.collect_milb_pbp_statcast
```

**Current Limitations**:
- Hardcoded for specific players/seasons
- No command-line arguments
- Slow (must fetch entire game PBP for each player)

**Data Collected** (per plate appearance):
- `mlb_player_id`, `season`, `level`, `game_pk`, `game_date`
- `launch_speed` (exit velocity)
- `launch_angle`
- `total_distance`
- `trajectory` (fly_ball, ground_ball, line_drive, popup)
- `hardness` (soft, medium, hard)
- `location_x`, `location_y` (spray chart coordinates)

#### 2. Statcast Metrics Aggregator
**Location**: `apps/api/scripts/aggregate_statcast_metrics.py`

**Purpose**: Aggregate raw plate appearances into player-season-level metrics.

**Usage**:
```bash
python -m scripts.aggregate_statcast_metrics
```

**What It Calculates**:
- Average/Max/90th percentile Exit Velocity
- Hard Hit % (95+ mph)
- Barrel % (specific EV/LA combinations)
- Launch Angle metrics (overall and on hard hits)
- Fly Ball Exit Velocity
- Batted Ball Distribution (GB%, LD%, FB%, PU%)
- Distance metrics

**Output**: Populates `milb_statcast_metrics` table

---

### Database Tables

#### milb_plate_appearances
Raw play-by-play data for each batted ball.

**Key Columns**:
- `mlb_player_id`, `season`, `level`, `game_pk`, `game_date`
- `launch_speed` - Exit velocity in mph
- `launch_angle` - Launch angle in degrees
- `total_distance` - Distance in feet
- `trajectory` - GB/LD/FB/PU
- `hardness` - soft/medium/hard
- `location_x`, `location_y` - Spray chart coordinates

**Current Rows**: 145,519 total PAs (72,058 with Statcast data)

#### milb_statcast_metrics
Aggregated metrics by player-season-level.

**Columns**:
- `mlb_player_id`, `season`, `level`
- `batted_balls` - Count of batted balls with Statcast data
- **Exit Velocity**: `avg_ev`, `max_ev`, `ev_90th`, `hard_hit_pct`
- **Launch Angle**: `avg_la`, `avg_la_hard`, `fb_ev`
- **Advanced**: `barrel_pct`
- **Distribution**: `gb_pct`, `ld_pct`, `fb_pct`, `pu_pct`
- **Distance**: `avg_distance`, `max_distance`

**Current Rows**: 662 (being updated by aggregation)

---

## What We Need to Collect

### Priority 1: Complete MiLB Coverage

**Missing Levels for Existing Seasons**:
- 2025: AA, A+, A, DSL, ROK, ACL
- 2024: AA, A+, A, DSL, ROK, ACL
- 2023: AA, A+, A, DSL, ROK, ACL
- 2022: AA, A+, A, DSL, ROK, ACL

**Missing Season**:
- 2021: All levels (AAA, AA, A+, A, DSL, ROK, ACL)

**Estimated Data Volume**:
- AAA has ~20K PAs per season
- AA/A+ typically have ~15K each
- Lower levels have less (fewer Statcast-equipped stadiums)
- **Total estimate**: ~300K-500K additional plate appearances

### Priority 2: MLB Statcast for Prospects

**What**: Collect MLB Statcast data for all players who have MiLB data (prospects who made it).

**Why**:
- Compare MiLB Statcast to MLB Statcast
- See if MiLB power metrics predict MLB success
- Identify players whose tools translate to MLB

**Data to Collect**:
- Same metrics as MiLB (EV, LA, distance, barrel%, etc.)
- Seasons 2021-2025
- ~4,842 players to check

**Source**: MLB Savant / Statcast Search API (different from game logs API)

**Challenge**: MLB Statcast is typically accessed via:
- Baseball Savant CSV downloads
- Statcast Search API (requires different approach than gameLog)
- May need to use `pybaseball` library

---

## Collection Challenges

### 1. API Limitations

**MiLB Statcast Availability**:
- Only available at AAA and AA levels (Statcast equipment exists)
- Some ballparks don't have full Statcast (especially A-ball and below)
- Data quality varies by stadium

**API Access**:
- Play-by-play feeds are slow (entire game for each player)
- No direct "Statcast search" API for MiLB like MLB has
- Must fetch game-by-game

### 2. MLB Statcast Access

**MLB Statcast NOT in GameLog API**:
- `gameLog` API we're using doesn't include Statcast
- Need different endpoint or data source

**Options**:
1. **Baseball Savant** (https://baseballsavant.mlb.com/statcast_search)
   - Web interface with CSV export
   - Can filter by player, date range
   - Rate limits unknown

2. **Statcast Search API**
   - Undocumented but exists
   - Used by Baseball Savant
   - Likely has rate limits

3. **pybaseball Library**
   - Python library wrapping Statcast access
   - `statcast()` function for date ranges
   - `statcast_batter()` for specific players
   - Handles caching and rate limiting

### 3. Data Volume & Time

**MiLB Collection Estimate**:
- 4,000+ players across 5 seasons
- Each player needs PBP for each game (slow API calls)
- **Estimated time**: 100-200 hours if sequential

**Optimization Strategies**:
- Concurrent collection (multiple seasons in parallel)
- Skip players with existing Statcast data
- Focus on AAA/AA where Statcast is reliable

---

## Recommended Collection Strategy

### Phase 1: Expand MiLB Statcast (CURRENT)

**Focus**: AAA and AA for 2021-2025 (where Statcast is reliable)

**Approach**:
1. Enhance `collect_milb_pbp_statcast.py` to:
   - Accept command-line arguments (season, levels, player IDs)
   - Check existing data and skip
   - Run concurrently for multiple seasons

2. Collect in batches:
   - 2025 AAA/AA (to complete current season)
   - 2024 AAA/AA (to complete last full season)
   - 2023 AAA/AA
   - 2022 AAA/AA
   - 2021 AAA/AA (new season)

3. After each batch, run aggregation

**Command Structure** (needs to be implemented):
```bash
# Collect statcast for season/level
python -m scripts.collect_milb_pbp_statcast --season 2024 --levels AA --players-from-db

# Or collect for specific prospect list
python -m scripts.collect_milb_pbp_statcast --season 2024 --levels AA --players 12345 67890
```

### Phase 2: MLB Statcast for Prospects

**Use pybaseball Library**:

```python
from pybaseball import statcast_batter, playerid_lookup

# Get statcast data for a player
data = statcast_batter('2024-03-01', '2024-10-01', player_id=12345)

# Returns DataFrame with:
# - launch_speed, launch_angle, hit_distance_sc
# - barrel, bat_speed, swing_length
# - And 80+ other fields!
```

**Collection Script** (needs to be created):
```python
# apps/api/scripts/collect_mlb_statcast.py

1. Get all MLB player IDs from milb_game_logs
2. For each player, for each season (2021-2025):
   - Check if MLB Statcast already collected
   - If not, fetch with pybaseball.statcast_batter()
   - Save to mlb_plate_appearances table
3. Aggregate to mlb_statcast_metrics table
```

### Phase 3: Lower Levels (Optional)

**A+, A, DSL, ROK, ACL**:
- Statcast coverage is spotty
- Many stadiums don't have equipment
- Collect if time permits, but expect lots of NULL values

---

## Implementation Plan

### Step 1: Check pybaseball Installation

```bash
pip install pybaseball
```

### Step 2: Create MLB Statcast Collector

**File**: `apps/api/scripts/collect_mlb_statcast.py`

**Pseudo-code**:
```python
import pybaseball
from datetime import datetime

# Get prospects who made MLB
players = get_prospects_with_mlb_games()

for player_id in players:
    for season in [2021, 2022, 2023, 2024, 2025]:
        # Check if already have data
        if has_statcast_data(player_id, season):
            continue

        # Fetch from Savant
        start_date = f'{season}-03-01'
        end_date = f'{season}-11-01'

        try:
            df = pybaseball.statcast_batter(start_date, end_date, player_id)

            if len(df) > 0:
                save_mlb_statcast(player_id, season, df)

        except Exception as e:
            log_error(player_id, season, e)

        sleep(1)  # Rate limiting
```

### Step 3: Enhance MiLB PBP Collector

Add command-line arguments to existing script:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--season', type=int, required=True)
parser.add_argument('--levels', nargs='+', choices=['AAA', 'AA', 'A+', 'A'])
parser.add_argument('--players-from-db', action='store_true',
                   help='Collect for all players in milb_game_logs')
parser.add_argument('--players', nargs='+', type=int,
                   help='Specific player IDs')
```

### Step 4: Concurrent Collection

**File**: `apps/api/run_statcast_collection.py`

```python
# Start concurrent collections
collections = [
    {'season': 2025, 'levels': ['AAA', 'AA']},
    {'season': 2024, 'levels': ['AAA', 'AA']},
    {'season': 2023, 'levels': ['AAA', 'AA']},
    {'season': 2022, 'levels': ['AAA', 'AA']},
    {'season': 2021, 'levels': ['AAA', 'AA']},
]

for config in collections:
    subprocess.Popen([
        'python', '-m', 'scripts.collect_milb_pbp_statcast',
        '--season', str(config['season']),
        '--levels', *config['levels'],
        '--players-from-db'
    ], stdout=open(f'statcast_{config["season"]}.log', 'w'))
```

---

## Aggregated Metrics Definitions

### Barrel
A batted ball with optimal exit velocity and launch angle combination that historically produces a minimum .500 batting average and 1.500 slugging percentage.

**Criteria** (simplified):
- EV ≥ 98 mph AND 26° ≤ LA ≤ 30°, OR
- EV ≥ 99 mph AND 24° ≤ LA ≤ 33°, OR
- EV ≥ 100 mph AND 22° ≤ LA ≤ 35°, OR
- EV ≥ 101 mph AND 20° ≤ LA ≤ 37°

### Hard Hit %
Percentage of batted balls with exit velocity ≥ 95 mph.

**Why 95 mph**: Historically the threshold where contact quality significantly improves outcomes.

### 90th Percentile EV
The exit velocity that 90% of a player's batted balls fall below. Shows maximum power ceiling.

**Why useful**: More stable than max EV (which can be a fluke). Shows consistent top-end power.

### Fly Ball Exit Velocity
Average exit velocity on fly balls only (excluding ground balls and line drives).

**Why useful**: Predicts home run power better than overall EV. Hard-hit fly balls are more likely to go over the fence.

### Average LA on Hard Hits
Average launch angle on batted balls hit 95+ mph.

**Why useful**: Shows if a player's power is optimized (ideal is 20-30°). High EV + low LA = wasted power (ground outs).

---

## Expected Timeline

### Immediate (Next 24 hours):
- ✅ Aggregate existing MiLB Statcast data (RUNNING)
- ✅ Document current state and plan (THIS FILE)
- ⏳ Install pybaseball
- ⏳ Create MLB Statcast collector

### Short Term (1-3 days):
- Enhance MiLB PBP collector with command-line args
- Collect 2024 AAA/AA Statcast (complete current season)
- Collect 2025 AA Statcast (complete current season)
- Start MLB Statcast collection for top prospects

### Medium Term (1-2 weeks):
- Collect 2023, 2022, 2021 AAA/AA Statcast
- Complete MLB Statcast for all prospects
- Aggregate all new data
- Generate reports/visualizations

### Optional (Future):
- Collect A+, A, DSL, ROK, ACL (limited Statcast availability)
- Create Statcast-based prospect rankings
- Build predictive models using Statcast features

---

## Success Metrics

### Data Completeness:
- **Target**: 80%+ of AAA/AA PAs with Statcast (where equipment exists)
- **Current**: ~72K PAs for AAA only
- **Goal**: ~300K+ PAs across AAA/AA for 2021-2025

### Player Coverage:
- **Target**: Statcast metrics for all top prospects
- **Current**: 386 players
- **Goal**: 2,000+ players across all seasons/levels

### MLB Comparison:
- **Target**: MLB Statcast for 100% of prospects who made majors
- **Current**: 0%
- **Goal**: Complete MLB Statcast for ~1,000 players who played both MiLB and MLB

---

## Related Documentation

- [DATA_COLLECTION_SCRIPTS.md](./DATA_COLLECTION_SCRIPTS.md) - Game log collection
- [ML_DATA_DOCUMENTATION.md](./ML_DATA_DOCUMENTATION.md) - ML features and models
- [PROSPECT_RANKINGS_PLAN.md](./PROSPECT_RANKINGS_PLAN.md) - Ranking methodology

---

## Changelog

### 2025-10-07 - Initial Plan
- Documented current Statcast data status (72K AAA PAs, 2022-2025)
- Identified gaps (AA, A+, A, lower levels, 2021 season, MLB)
- Proposed collection strategy using pybaseball for MLB
- Created implementation roadmap
