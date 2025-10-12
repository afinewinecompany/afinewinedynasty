# Machine Learning Data Documentation

## Overview

This document outlines all data sources, features, and tables used for the baseball prospect prediction machine learning model. The model predicts future MLB performance for Minor League Baseball (MiLB) prospects.

---

## Data Sources

### 1. MLB Stats API
- **Base URL**: `https://statsapi.mlb.com/api`
- **Primary Endpoints**:
  - `/v1/people/{player_id}/stats` - Player statistics and game logs
  - `/v1.1/game/{game_pk}/feed/live` - Play-by-play data with Statcast metrics
  - `/v1/people/{player_id}` - Player biographical information

---


## Database Tables

### Core Tables

#### 1. `prospects`
**Purpose**: Master list of all MiLB prospects with biographical information

**Key Fields**:
- `mlb_player_id` (INTEGER, PRIMARY KEY) - MLB's unique player identifier
- `full_name` (VARCHAR) - Player's full name
- `birth_date` (DATE) - Birth date for age calculations
- `mlb_debut_date` (DATE) - Date of MLB debut (if applicable)
- `current_team` (VARCHAR) - Current team affiliation
- `primary_position` (VARCHAR) - Primary fielding position
- `bat_side` (VARCHAR) - Left/Right/Switch hitter
- `pitch_hand` (VARCHAR) - Throwing hand

**Record Count**: ~3,430 prospects
**Coverage**: 2,427/2,429 (99.9%) have birth dates

---

#### 2. `milb_game_logs`
**Purpose**: Game-by-game performance statistics for MiLB players

**Key Fields**:
- `mlb_player_id` (INTEGER) - Links to prospects table
- `game_pk` (BIGINT) - Unique game identifier
- `game_date` (DATE) - Date of game
- `season` (INTEGER) - Season year
- `level` (VARCHAR) - MiLB level (AAA, AA, A+, A, Rookie, Rookie+)
- `venue_id` (INTEGER) - Stadium identifier
- `venue_name` (VARCHAR) - Stadium name
- `opponent_team_id` (INTEGER) - Opposing team ID
- `opponent_name` (VARCHAR) - Opposing team name
- `data_source` (VARCHAR) - Always 'mlb_stats_api_gamelog'

**Counting Stats**:
- `pa` (INTEGER) - Plate Appearances
- `ab` (INTEGER) - At Bats
- `h` (INTEGER) - Hits
- `doubles` (IN
- TEGER) - Doubles (2B)
- `triples` (INTEGER) - Triples (3B)
- `hr` (INTEGER) - Home Runs
- `rbi` (INTEGER) - Runs Batted In
- `bb` (INTEGER) - Walks
- `so` (INTEGER) - Strikeouts
- `sb` (INTEGER) - Stolen Bases
- `cs` (INTEGER) - Caught Stealing
- `hbp` (INTEGER) - Hit By Pitch
- `sf` (INTEGER) - Sacrifice Flies

**Record Count**: ~164,738 game logs
**Players Covered**: ~2,140 unique players
**Seasons**: 2020-2024
**Levels**: AAA, AA, A+, A, Rookie, Rookie+

---

#### 3. `mlb_game_logs`
**Purpose**: MLB career statistics (target variables for ML model)

**Key Fields**:
- `mlb_player_id` (INTEGER) - Links to prospects table
- `game_pk` (BIGINT) - Unique game identifier
- `game_date` (DATE) - Date of game
- `season` (INTEGER) - Season year
- `team_id` (INTEGER) - MLB team ID
- `team_name` (VARCHAR) - MLB team name

**Same counting stats as milb_game_logs**

**Additional MLB Metrics** (aggregated from career stats):
- `wrc_plus` (INTEGER) - Weighted Runs Created Plus (league/park adjusted, 100 = average)
- `woba` (FLOAT) - Weighted On-Base Average
- `babip` (FLOAT) - Batting Average on Balls In Play

**Record Count**: ~9,123 game logs
**Players Covered**: ~120 players who reached MLB
**Seasons**: 2020-2024

---

#### 4. `milb_plate_appearances`
**Purpose**: Play-by-play level data with Statcast batted ball metrics

**Key Fields**:
- `mlb_player_id` (INTEGER) - Links to prospects table
- `game_pk` (BIGINT) - Unique game identifier
- `game_date` (DATE) - Date of game
- `season` (INTEGER) - Season year
- `level` (VARCHAR) - MiLB level
- `at_bat_index` (INTEGER) - Plate appearance number within game
- `inning` (INTEGER) - Inning number
- `half_inning` (VARCHAR) - 'top' or 'bottom'
- `event_type` (VARCHAR) - Outcome (single, double, strikeout, etc.)
- `event_type_desc` (VARCHAR) - Detailed event description
- `description` (TEXT) - Full play description

**Statcast Metrics** (when available, ~30-35% of batted balls):
- `launch_speed` (FLOAT) - Exit velocity in mph
- `launch_angle` (FLOAT) - Launch angle in degrees
- `total_distance` (FLOAT) - Distance traveled in feet
- `trajectory` (VARCHAR) - 'ground_ball', 'line_drive', 'fly_ball', 'popup'
- `hardness` (VARCHAR) - 'soft', 'medium', 'hard'
- `location` (INTEGER) - Spray chart zone (1-9)
- `coord_x` (FLOAT) - X coordinate on field
- `coord_y` (FLOAT) - Y coordinate on field

**Record Count**: ~8,582+ plate appearances (growing)
**Batted Balls with Statcast**: ~2,929+
**Players Covered**: ~1,049+ unique players
**Statcast Coverage**: ~30-35% (typical for MiLB)
**Status**: ⏳ Collections in progress for 2024, 2023, 2022

---

#### 5. `milb_statcast_metrics`
**Purpose**: Aggregated Statcast metrics by player-season-level

**Key Fields**:
- `mlb_player_id` (INTEGER) - Links to prospects table
- `season` (INTEGER) - Season year
- `level` (VARCHAR) - MiLB level
- `batted_balls` (INTEGER) - Total batted balls with Statcast data

**Exit Velocity Metrics**:
- `avg_ev` (FLOAT) - Average exit velocity (mph)
- `max_ev` (FLOAT) - Maximum exit velocity (mph)
- `ev_90th` (FLOAT) - 90th percentile exit velocity (mph)
- `hard_hit_pct` (FLOAT) - Percentage of batted balls ≥95 mph

**Launch Angle Metrics**:
- `avg_la` (FLOAT) - Average launch angle (degrees)
- `avg_la_hard` (FLOAT) - Average launch angle on hard-hit balls only

**Contact Quality Metrics**:
- `fb_ev` (FLOAT) - **Fly Ball Exit Velocity** - Average EV on fly balls only
- `barrel_pct` (FLOAT) - Barrel percentage (optimal EV + LA combinations)

**Batted Ball Distribution**:
- `gb_pct` (FLOAT) - Ground ball percentage
- `ld_pct` (FLOAT) - Line drive percentage
- `fb_pct` (FLOAT) - Fly ball percentage
- `pu_pct` (FLOAT) - Popup percentage

**Distance Metrics**:
- `avg_distance` (FLOAT) - Average batted ball distance (feet)
- `max_distance` (FLOAT) - Maximum batted ball distance (feet)

**Barrel Definition**:
- EV ≥ 98 mph AND LA 26-30°, OR
- EV ≥ 99 mph AND LA 24-33°, OR
- EV ≥ 100 mph AND LA 22-35°, OR
- EV ≥ 101 mph AND LA 20-37°

**Record Count**: 42 player-season-level combinations
**Status**: ✅ Created, will grow as PBP collection continues

---

#### 6. `milb_league_factors`
**Purpose**: Calculate level-specific averages to normalize player performance across different MiLB levels

**What This Solves**: Different MiLB levels have vastly different offensive environments. A .800 OPS at AAA (hardest level) is much more impressive than .800 OPS at A (easier level). This table provides the baseline statistics at each level to properly contextualize player performance.

**Key Fields**:
- `season` (INTEGER) - Season year (e.g., 2024)
- `level` (VARCHAR) - MiLB level: AAA, AA, A+, A, ROK, ACL, DSL
- `total_pa` (INTEGER) - Total plate appearances across all players at this level
- `unique_players` (INTEGER) - Number of unique players at this level
- `players_with_age` (INTEGER) - Players with birth date data available

**League Average Performance Statistics**:
- `lg_avg` (FLOAT) - League batting average
- `lg_obp` (FLOAT) - League on-base percentage
- `lg_slg` (FLOAT) - League slugging percentage
- `lg_ops` (FLOAT) - League OPS (OBP + SLG)
- `lg_iso` (FLOAT) - League isolated power (SLG - AVG)
- `lg_hr_rate` (FLOAT) - Home runs per 100 plate appearances
- `lg_bb_rate` (FLOAT) - Walks per 100 plate appearances
- `lg_so_rate` (FLOAT) - Strikeouts per 100 plate appearances
- `lg_sb_rate` (FLOAT) - Stolen base attempts per 100 plate appearances
- `lg_sb_success_pct` (FLOAT) - Stolen base success rate (SB / (SB + CS))

**League Average Age Statistics** (Critical for Prospect Evaluation):
- `lg_avg_age` (FLOAT) - Mean age of players at this level
- `lg_median_age` (FLOAT) - Median age (less affected by outliers)
- `lg_age_std` (FLOAT) - Standard deviation of age distribution
- `lg_age_25th_percentile` (FLOAT) - 25th percentile age (75% of players are older)
- `lg_age_75th_percentile` (FLOAT) - 75th percentile age (25% of players are older)

**How It's Used in ML**:

1. **Level-Adjusted Performance**:
   ```
   Player OPS: 0.820 at AA
   League OPS at AA: 0.720
   OPS+ = 0.820 / 0.720 = 1.139 (14% above league average)
   ```

2. **Age Context** (Most Important for Prospects):
   ```
   Player Age: 21.5 at AA
   League Avg Age at AA: 23.8
   Age Difference: -2.3 years (player is 2.3 years younger than average)
   Interpretation: ELITE age for level - younger players are higher-ceiling prospects
   ```

3. **Combined Context**:
   ```
   A 21yo hitting .800 OPS at AA is a TOP prospect
   A 26yo hitting .800 OPS at AA is an organizational player
   The stats are identical, but age context changes everything
   ```

**Real-World Example**:
- **Player A**: 22yo, .850 OPS at AA (league avg: .720, avg age: 23.8)
  - OPS+: 118 (18% above average)
  - Age: 1.8 years younger than average
  - **Verdict**: Strong prospect with age advantage

- **Player B**: 22yo, .850 OPS at AAA (league avg: .690, avg age: 25.2)
  - OPS+: 123 (23% above average)
  - Age: 3.2 years younger than average
  - **Verdict**: ELITE prospect - performing well at hardest level while very young

**Status**: ✅ Script ready ([calculate_league_factors_with_age.py](../apps/api/scripts/calculate_league_factors_with_age.py))

**Related Documentation**: See [LEAGUE_FACTORS_DOCUMENTATION.md](LEAGUE_FACTORS_DOCUMENTATION.md) for complete details

---

#### 7. `milb_position_factors`
**Purpose**: Calculate position-specific offensive averages to account for defensive demands

**What This Solves**: Players at different defensive positions have different offensive expectations. Catchers spend enormous energy on defense, game-calling, and handling pitchers - so they typically hit less than DHs who focus only on offense. Without position adjustments, we'd undervalue good-hitting catchers and overvalue poor-hitting DHs.

**Key Fields**:
- `season` (INTEGER) - Season year (e.g., 2024)
- `level` (VARCHAR) - MiLB level (AAA, AA, A+, etc.)
- `position_group` (VARCHAR) - Simplified position groups: C, IF, OF, DH, TWP
- `total_pa` (INTEGER) - Total plate appearances for this position at this level
- `unique_players` (INTEGER) - Number of unique players in this position group

**Position Average Statistics**:
- `pos_avg` (FLOAT) - Position group batting average
- `pos_obp` (FLOAT) - Position group on-base percentage
- `pos_slg` (FLOAT) - Position group slugging percentage
- `pos_ops` (FLOAT) - Position group OPS
- `pos_iso` (FLOAT) - Position group isolated power
- `pos_hr_rate` (FLOAT) - Position group home run rate
- `pos_bb_rate` (FLOAT) - Position group walk rate
- `pos_so_rate` (FLOAT) - Position group strikeout rate
- `pos_sb_rate` (FLOAT) - Position group stolen base rate
- `pos_avg_age` (FLOAT) - Average age at this position/level

**Position Groupings Explained**:

| Group | Positions | Defensive Demand | Offensive Expectation | Why? |
|-------|-----------|------------------|----------------------|------|
| **C** | Catcher | HIGHEST | LOWEST | Squat 150+ times/game, manage pitchers, most physically demanding |
| **IF** | SS, 2B, 3B, 1B | HIGH | MODERATE | Constant fielding, quick reactions, SS/2B most athletic |
| **OF** | LF, CF, RF | MODERATE | HIGHER | Less demanding than infield, CF most athletic |
| **DH** | Designated Hitter | NONE | HIGHEST | Offense-only, no defensive fatigue |
| **TWP** | Two-Way Player | VARIES | VARIES | Rare players who pitch and hit (like Shohei Ohtani) |

**Position Hierarchy (Offensive Expectations - Easiest to Hardest)**:
1. **DH** - Expected to rake (.780+ OPS typical at AA)
2. **OF** - Expected to hit well (.750 OPS typical)
3. **IF** - Mixed bag depending on specific position (.720 OPS typical)
4. **C** - Allowed to hit poorly if defense is good (.680 OPS typical)

**How It's Used in ML**:

1. **Position-Relative Performance**:
   ```
   Catcher at AA:
   - Player OPS: 0.720
   - Catcher Avg OPS at AA: 0.680
   - Position OPS+ = 0.720 / 0.680 = 1.059 (6% above position average)
   - Verdict: Above-average hitting catcher
   ```

2. **Avoiding Undervaluation**:
   ```
   Same .720 OPS vs League Avg:
   - League Avg OPS at AA: 0.750
   - League OPS+ = 0.720 / 0.750 = 0.960 (4% below league average)
   - Verdict WITHOUT position adjustment: Below average hitter
   - Verdict WITH position adjustment: Above average for a catcher

   The catcher looks BAD without position context, but is actually GOOD
   ```

3. **Real-World Example**:
   ```
   Player A (Catcher): .700 OPS at AA
   - Position avg: .680 → 103 position OPS+ (above average)
   - League avg: .750 → 93 league OPS+ (below average)
   - ML Feature: Use position-adjusted (103) not league (93)

   Player B (DH): .750 OPS at AA
   - Position avg: .780 → 96 position OPS+ (below average for DH)
   - League avg: .750 → 100 league OPS+ (average)
   - ML Feature: Use position-adjusted (96) shows DH is actually weak
   ```

**Why This Matters for Prospect Evaluation**:
- A .700 OPS **catcher** who can hit is MORE valuable than a .750 OPS **DH**
- Catchers are scarce and defensive value is huge
- DHs have no defensive value and must hit significantly better
- Without position factors, the ML model would incorrectly rank the DH higher

**Minimum Sample Size**:
- 50 games minimum per position group at each level
- Prevents noise from small samples
- Some rare positions (DH at Rookie levels) may not have enough data

**Status**: ✅ Script ready, integrated with league factors ([calculate_league_factors_with_age.py](../apps/api/scripts/calculate_league_factors_with_age.py))

**Related Documentation**: See [LEAGUE_FACTORS_DOCUMENTATION.md](LEAGUE_FACTORS_DOCUMENTATION.md) for complete details

---

## Machine Learning Features

### Feature Categories

#### 1. Basic Performance Stats (Aggregated from game logs)

**Rate Stats**:
- `avg_ops` - On-base plus slugging percentage
- `avg_obp` - On-base percentage
- `avg_slg` - Slugging percentage
- `avg_ba` - Batting average
- `iso` - Isolated power (SLG - AVG)
- `bb_rate` - Walk rate (BB/PA)
- `so_rate` - Strikeout rate (SO/PA)
- `hr_rate` - Home run rate (HR/PA)

**Counting Stats** (aggregated):
- `total_pa` - Total plate appearances
- `total_games` - Total games played
- `total_hr` - Total home runs
- `total_sb` - Total stolen bases

---

#### 2. Age-Adjusted Features

**Purpose**: Account for age-relative performance at each level

**Age Baselines by Level**:
- AAA: 25 years old (average)
- AA: 23 years old
- A+: 22 years old
- A: 21 years old
- Rookie: 20 years old

**Age-Adjusted Metrics**:
- `age_at_level` - Player's age during season at level
- `age_diff` - Difference from level average age
- `age_adj_ops` - OPS + (age_diff × 0.010)
- `age_adj_iso` - ISO + (age_diff × 0.005)
- `age_adj_bb_rate` - BB% + (age_diff × 0.005)
- `age_adj_so_rate` - SO% - (age_diff × 0.008)

**Rationale**:
- 19-year-old in A+ is more impressive than 24-year-old
- Younger players at advanced levels show higher potential
- Adjustments based on empirical aging curves

**Example**:
```
Player A: .750 OPS, Age 21 at AA (2 years younger than average)
Age-adjusted OPS = .750 + (2 × 0.010) = .770

Player B: .750 OPS, Age 25 at AA (2 years older than average)
Age-adjusted OPS = .750 + (-2 × 0.010) = .730
```

---

#### 3. Progression Features

**Purpose**: Measure improvement trajectory over time

**Metrics**:
- `ops_improvement_per_year` - Annual OPS growth rate
- `ops_progression_rate` - Percentage improvement from previous level
- `seasons_active` - Number of seasons played
- `levels_played` - Number of distinct levels played

**Calculation Example**:
```
Season 1 (A+): .700 OPS
Season 2 (AA): .750 OPS
ops_improvement_per_year = (.750 - .700) / 1 = 0.050
```

**ML Importance**: 6.5% feature importance (validated in age-adjusted model)

---

#### 4. Level Performance Features

**Highest Level Stats**:
- `highest_level` - Highest MiLB level reached
- `highest_level_ops` - OPS at highest level
- `highest_level_pa` - PAs at highest level
- `highest_level_bb_rate` - BB% at highest level
- `highest_level_so_rate` - SO% at highest level

**Most Recent Level Stats**:
- `recent_level` - Most recent MiLB level
- `recent_ops` - Recent OPS
- `recent_pa` - Recent PAs

**Rationale**: Performance at highest/most recent level is most predictive

---

#### 5. Statcast Features (NEW - In Progress)

**Exit Velocity Metrics**:
- `avg_ev` - Average exit velocity
- `max_ev` - Maximum exit velocity
- `ev_90th` - 90th percentile exit velocity (consistency)
- `hard_hit_pct` - Hard-hit percentage (≥95 mph)

**Launch Angle Metrics**:
- `avg_la` - Average launch angle
- `avg_la_hard` - Average launch angle on hard contact
- `fb_ev` - **Fly ball exit velocity** (power indicator)

**Contact Quality**:
- `barrel_pct` - Barrel percentage (elite contact)
- `gb_pct`, `ld_pct`, `fb_pct` - Batted ball distribution

**Why These Matter**:
- Exit velocity predicts power output
- Launch angle + EV = barrels (highest-value contacts)
- Fly ball EV shows ability to drive ball in air (HR potential)
- 90th percentile EV shows best-case ability

**Status**: ⏳ Data collection 2-5% complete, ~8,500+ PAs collected

---

#### 6. League & Position Adjustment Features

**Purpose**: Create context-aware features that normalize player performance across different levels, ages, and positions

**What This Category Does**: Transforms raw stats into relative performance metrics that account for:
1. **Level difficulty** (AAA vs AA vs A)
2. **Age context** (young players at high levels are more valuable)
3. **Position demands** (catchers vs DHs have different offensive expectations)

---

**6a. Level-Adjusted Features** (from `milb_league_factors`)

Normalize stats relative to the average at each MiLB level:

- `ops_vs_league` - Player OPS / League OPS at level
- `iso_vs_league` - Player ISO / League ISO at level
- `bb_rate_vs_league` - Player BB% / League BB% at level
- `so_rate_vs_league` - Player SO% / League SO% at level
- `hr_rate_vs_league` - Player HR% / League HR% at level
- `sb_rate_vs_league` - Player SB rate / League SB rate

**Example - Level Adjustment**:
```
Player: .800 OPS at AA
League Average at AA: .720 OPS
ops_vs_league = .800 / .720 = 1.111

Interpretation: Player is 11% better than average AA hitter
This is MORE impressive than .800 OPS at Rookie ball where league avg might be .820
```

---

**6b. Age-Adjusted Features** (from `milb_league_factors` age statistics)

Account for player age relative to level average:

- `age_at_level` - Player's age during season at level
- `age_vs_league_avg` - Player age minus league average age
- `age_percentile` - Player's age percentile at level (younger = better)
- `age_adj_ops` - OPS adjusted for age relative to peers
- `age_adj_iso` - ISO adjusted for age relative to peers

**Example - Age Adjustment**:
```
Player: 21.5 years old at AA
League Avg Age at AA: 23.8 years
age_vs_league_avg = 21.5 - 23.8 = -2.3 years

Interpretation: Player is 2.3 years YOUNGER than typical AA player
This is ELITE - young players at high levels have higher ceilings

Age-adjusted OPS formula:
age_adj_ops = ops * (1 + (age_vs_league_avg * -0.02))
= .800 * (1 + (-2.3 * -0.02))
= .800 * 1.046
= .837

The younger age boosts the adjusted value by 4.6%
```

**Why Age Matters**:
- 20yo hitting .750 at AA = Future star potential
- 26yo hitting .750 at AA = Career minor leaguer
- Same stats, completely different prospect value

---

**6c. Position-Adjusted Features** (from `milb_position_factors`)

Normalize stats relative to positional peers:

- `ops_vs_position` - Player OPS / Position average OPS
- `iso_vs_position` - Player ISO / Position average ISO
- `bb_rate_vs_position` - Player BB% / Position BB%
- `so_rate_vs_position` - Player SO% / Position SO%

**Example - Position Adjustment**:
```
Catcher at AA:
- Player OPS: .720
- Catcher Avg at AA: .680
- League Avg at AA: .750

ops_vs_position = .720 / .680 = 1.059 (6% above position peers)
ops_vs_league = .720 / .750 = 0.960 (4% below league)

Without position adjustment: Looks below average
With position adjustment: Above average for a catcher (correct!)
```

**Why Position Matters**:
- Catchers: Hardest defensive position → lowest offensive expectations
- DHs: No defense → must hit significantly better
- .700 OPS catcher is MORE valuable than .750 OPS DH
- ML model needs this context to properly rank prospects

---

**6d. Combined Adjustment Features**

Bring it all together for comprehensive context:

- `fully_adjusted_ops` - OPS adjusted for level + age + position
- `position_age_adjusted_iso` - ISO with all adjustments applied
- `comprehensive_context_score` - Multi-factor prospect value indicator

**Example - Full Adjustment**:
```
Player: 21yo Catcher hitting .720 OPS at AA

Step 1 - Level adjustment:
League avg at AA: .750
Level factor = .720 / .750 = 0.960

Step 2 - Age adjustment:
League avg age at AA: 23.8, player is 21 (-2.8 years younger)
Age factor = 1 + (-2.8 * -0.02) = 1.056

Step 3 - Position adjustment:
Catcher avg at AA: .680
Position factor = .750 / .680 = 1.103

Fully adjusted OPS = .720 * (level) * age_factor * position_factor
                   = .720 * 1.0 * 1.056 * 1.103
                   = .839

Raw OPS: .720 (looks mediocre)
Fully adjusted: .839 (actually very good prospect!)
```

**Real-World Impact on ML**:
- Without adjustments: Model sees .720 OPS as below average
- With adjustments: Model correctly identifies this as a top prospect
- This is the difference between ranking #50 vs #5 in your system

---

**Status**: ✅ Script ready with age and position factors ([calculate_league_factors_with_age.py](../apps/api/scripts/calculate_league_factors_with_age.py))

**Next Steps**:
1. Run league/position factors calculation after birth date collection completes
2. Retrain ML model with these new features
3. Expect significant improvement in model accuracy for catchers and young players

---

## ML Target Variables (MLB Performance)

### Regression Targets

From `mlb_game_logs`, aggregated to career totals:

1. **wRC+ (Weighted Runs Created Plus)**
   - Scale: 100 = league average, >100 = above average
   - Park and league adjusted offensive metric
   - Best overall measure of hitting value

2. **wOBA (Weighted On-Base Average)**
   - Scale: ~.320 = league average
   - Weights events by run value (HR > 3B > 2B > 1B > BB)
   - Best rate stat for offensive value

3. **OPS (On-Base Plus Slugging)**
   - Scale: ~.750 = average, .900+ = elite
   - Simple but effective overall metric

4. **OBP (On-Base Percentage)**
   - Getting on base ability
   - Highly correlated with team wins

5. **SLG (Slugging Percentage)**
   - Power metric
   - Total bases per at-bat

6. **HR Rate**
   - Home runs per plate appearance
   - Power output

7. **SO Rate**
   - Strikeouts per plate appearance
   - Contact ability (inverse)

8. **BB Rate**
   - Walks per plate appearance
   - Plate discipline

### Classification Target

- **made_mlb** - Binary (0 or 1) whether player reached MLB
- Used only for exploratory analysis, NOT for main model
- Reason: Creates label leakage (current prospects aren't "failures")

---

## ML Model Architecture

### Current Approach: Zero-Label Regression

**Training Set**: ALL MiLB players (1,626 total)
- 194 players with MLB experience (have stats)
- 1,432 prospects/players without MLB experience (get zeros)

**Rationale**:
- Avoids survivorship bias (training only on MLB players)
- Avoids label leakage (treating prospects as "failures")
- Zero represents "no MLB stats yet" baseline
- Model learns patterns that differentiate MLB players from prospects

**Algorithm**: Random Forest Regressor
- Handles non-linear relationships
- Feature importance analysis
- Robust to outliers

### Model Performance (Current Best)

**Training Results**:
- wRC+ R²: 0.309 (huge improvement from -0.12)
- OBP R²: 0.311 (improvement from 0.02)
- wOBA R²: 0.282 (improvement from -0.23)
- OPS R²: 0.237

**Top Features by Importance**:
1. `avg_ops` - 31.4%
2. `recent_ops` - 17.0%
3. `highest_level_ops` - 9.5%
4. `ops_improvement_per_year` - 6.5%
5. `ops_progression_rate` - 6.0%
6. `age_adj_ops` - 4.8%

---

## Data Collection Status

### Completed ✅

1. **MiLB Game Logs**: 164,738 games, 2,140 players
2. **MLB Game Logs**: 9,123 games, 120 players
3. **Birth Dates**: 2,427/2,429 players (99.9%)
4. **Age-Adjusted ML Model**: Trained and validated
5. **Comprehensive ML Model**: Trained on all 1,626 players
6. **Statcast Aggregation Script**: Created and tested

### In Progress ⏳

1. **Statcast PBP Collection**:
   - 2024 season: 50/2,864 players (1.7%)
   - 2023 season: 40/2,947 players (1.4%)
   - 2022 season: 20/2,949 players (0.7%)
   - Current: 8,582 PAs, 2,929 batted balls, 1,049 players
   - Estimated completion: Several hours

### Planned 📝

1. **League Adjustment Factors**: Script ready, needs database setup
2. **Park Factors**: Requires home/away game designation (not in current data)
3. **Retrain with Statcast Features**: Once PBP collection completes
4. **Level Translation Models**: Predict performance at next level

---

## Feature Engineering Pipeline

### Step 1: Load Raw Data
```python
# Load MiLB game logs
milb_games = load_milb_game_logs()

# Load MLB career stats (targets)
mlb_targets = load_mlb_career_stats()

# Load birth dates
birth_dates = load_prospect_birth_dates()

# Load Statcast metrics
statcast_metrics = load_statcast_metrics()

# Load league factors
league_factors = load_league_factors()
```

### Step 2: Calculate Basic Stats
```python
# Aggregate by player
player_stats = milb_games.groupby('mlb_player_id').agg({
    'pa': 'sum',
    'ab': 'sum',
    'h': 'sum',
    'hr': 'sum',
    'bb': 'sum',
    'so': 'sum',
    # ... etc
})

# Calculate rates
player_stats['obp'] = (h + bb + hbp) / (ab + bb + hbp + sf)
player_stats['slg'] = tb / ab
player_stats['ops'] = obp + slg
player_stats['bb_rate'] = bb / pa
player_stats['so_rate'] = so / pa
```

### Step 3: Calculate Age-Adjusted Stats
```python
# Merge birth dates
player_stats = player_stats.merge(birth_dates, on='mlb_player_id')

# Calculate age at each level
player_stats['age_at_level'] = calculate_age(birth_date, season_start)

# Apply age adjustments
player_stats['age_adj_ops'] = ops + (age_diff * 0.010)
```

### Step 4: Calculate Progression Features
```python
# Sort by season
player_seasons = player_stats.sort_values(['mlb_player_id', 'season'])

# Calculate year-over-year improvement
player_seasons['ops_improvement'] = ops.diff()
player_seasons['ops_improvement_per_year'] = ops_improvement / years_diff
```

### Step 5: Merge Statcast Features
```python
# Join aggregated Statcast metrics
features = features.merge(
    statcast_metrics[['mlb_player_id', 'avg_ev', 'max_ev', 'barrel_pct']],
    on='mlb_player_id',
    how='left'
)
```

### Step 6: Apply League Adjustments
```python
# Merge league factors
features = features.merge(
    league_factors[['season', 'level', 'lg_ops']],
    on=['season', 'level']
)

# Calculate league-relative stats
features['ops_vs_league'] = features['ops'] / features['lg_ops']
```

### Step 7: Join Targets (LEFT Join)
```python
# LEFT JOIN to keep ALL MiLB players
dataset = features.merge(mlb_targets, on='mlb_player_id', how='left')

# Fill missing MLB stats with zeros
mlb_cols = ['mlb_wrc_plus', 'mlb_woba', 'mlb_ops', 'mlb_obp', 'mlb_slg']
dataset[mlb_cols] = dataset[mlb_cols].fillna(0)
```

---

## Data Quality Metrics

### Coverage Statistics

**Player Coverage**:
- Total prospects in database: 3,430
- With MiLB game logs: 2,140 (62.4%)
- With birth dates: 2,427 (70.8%)
- With MLB game logs: 120 (3.5%)
- Complete feature set: 1,626 (47.4%)

**Statcast Coverage**:
- MiLB games with Statcast: ~30-35% (typical)
- Players with any Statcast data: 1,049+ (growing)
- Minimum batted balls for reliability: 50

**Temporal Coverage**:
- MiLB seasons: 2020-2024
- MLB seasons: 2020-2024
- Statcast collection: 2022-2024 (in progress)

### Data Quality Checks

**Implemented Validations**:
1. PA > 0 (exclude empty games)
2. Birth dates parsed correctly
3. Date ranges valid (no future dates)
4. Numeric fields converted from Decimal
5. Duplicate games handled (UNIQUE constraints)

**Missing Data Handling**:
- Missing MLB stats → filled with 0
- Missing Statcast → NULL (handled separately)
- Missing birth dates → excluded from age-adjusted features
- Missing league factors → use overall average

---

## Scripts and Tools

### Data Collection Scripts

1. **[collect_all_milb_gamelog.py](../apps/api/scripts/collect_all_milb_gamelog.py)**
   - Collects MiLB game logs from MLB Stats API
   - Populates `milb_game_logs` table
   - Status: ✅ Complete

2. **[collect_mlb_gamelogs.py](../apps/api/scripts/collect_mlb_gamelogs.py)**
   - Collects MLB career stats
   - Populates `mlb_game_logs` table
   - Status: ✅ Complete

3. **[collect_player_birth_dates.py](../apps/api/scripts/collect_player_birth_dates.py)**
   - Collects player biographical info
   - Updates `prospects` table with birth_date
   - Status: ✅ Complete (99.9% success)

4. **[collect_milb_pbp_statcast.py](../apps/api/scripts/collect_milb_pbp_statcast.py)**
   - Collects play-by-play with Statcast metrics
   - Populates `milb_plate_appearances` table
   - Status: ⏳ In progress (2-5% complete)

### Feature Engineering Scripts

5. **[aggregate_statcast_metrics.py](../apps/api/scripts/aggregate_statcast_metrics.py)**
   - Aggregates PBP data into player-level metrics
   - Creates `milb_statcast_metrics` table
   - Calculates: EV, LA, Hard Hit%, Barrel%, FB EV
   - Status: ✅ Created and tested

6. **[calculate_league_factors.py](../apps/api/scripts/calculate_league_factors.py)**
   - Calculates league-average stats by level
   - Creates `milb_league_factors` table
   - Status: 📝 Ready, awaiting database

### ML Training Scripts

7. **[train_age_adjusted_predictor.py](../apps/api/scripts/train_age_adjusted_predictor.py)**
   - First ML model with age adjustments
   - Status: ✅ Complete (132 players, survivorship bias)

8. **[train_comprehensive_predictor.py](../apps/api/scripts/train_comprehensive_predictor.py)**
   - Classification approach (MLB vs non-MLB)
   - Status: ⚠️ Flawed (label leakage issue)

9. **[train_all_players_predictor.py](../apps/api/scripts/train_all_players_predictor.py)**
   - **CURRENT BEST MODEL**
   - Trains on all 1,626 players with zero-label approach
   - Status: ✅ Complete and validated

---

## Next Steps

### Immediate (Once Statcast Collection Completes)

1. **Re-aggregate Statcast metrics** with full dataset
2. **Retrain ML model** with Statcast features added
3. **Feature importance analysis** with Statcast included
4. **Test league adjustment factors** in model

### Short Term

1. **Implement ensemble models** (combine multiple algorithms)
2. **Cross-validation** with temporal splits (train on older seasons, test on recent)
3. **Position-specific models** (1B/DH vs OF vs MI)
4. **Create prediction API endpoint** for real-time prospect evaluation

### Long Term

1. **Level translation models** - predict stats at next level
2. **Injury data integration** - account for injury history
3. **Player similarity engine** - find comparable prospects
4. **Interactive dashboard** - visualize predictions and feature importance
5. **Collect park factors** - requires home/away designation in data
6. **Add defensive metrics** - UZR, DRS, OAA from Statcast

---

## Data Update Schedule

**Automated Daily Updates** (planned):
- New game logs from previous day
- Birth dates for new prospects
- Statcast data for recent games

**Seasonal Updates**:
- Full season data collection after playoffs
- Model retraining with new season data
- Feature importance re-evaluation

**Model Retraining Triggers**:
- New season begins
- Significant new feature added (Statcast, park factors)
- Model performance degrades
- Schema changes

---

## References

### API Documentation
- [MLB Stats API](https://statsapi.mlb.com)
- [Statcast Search](https://baseballsavant.mlb.com)

### Baseball Analytics Resources
- [FanGraphs](https://fangraphs.com) - wRC+, wOBA definitions
- [Baseball Savant](https://baseballsavant.mlb.com) - Statcast metrics
- [Baseball Reference](https://baseball-reference.com) - Historical stats

### ML Resources
- Scikit-learn Random Forest Documentation
- Feature Engineering for Baseball Analytics
- Prospect Development Aging Curves

---

## Contact & Maintenance

**Last Updated**: 2025-10-07

**Data Steward**: Development Team

**Update Frequency**: This document should be updated when:
- New tables are added
- New features are engineered
- ML model architecture changes
- Data collection scripts are created/modified
- Significant data quality issues discovered

---

## Appendix: SQL Schema Examples

### Query: Get player with all features
```sql
SELECT
    p.mlb_player_id,
    p.full_name,
    p.birth_date,
    p.mlb_debut_date,
    COUNT(DISTINCT mg.game_pk) as milb_games,
    COUNT(DISTINCT mlb.game_pk) as mlb_games,
    sm.avg_ev,
    sm.barrel_pct,
    lf.lg_ops
FROM prospects p
LEFT JOIN milb_game_logs mg ON p.mlb_player_id = mg.mlb_player_id
LEFT JOIN mlb_game_logs mlb ON p.mlb_player_id = mlb.mlb_player_id
LEFT JOIN milb_statcast_metrics sm ON p.mlb_player_id = sm.mlb_player_id
LEFT JOIN milb_league_factors lf ON mg.season = lf.season AND mg.level = lf.level
WHERE p.birth_date IS NOT NULL
GROUP BY p.mlb_player_id, p.full_name, p.birth_date, p.mlb_debut_date,
         sm.avg_ev, sm.barrel_pct, lf.lg_ops;
```

### Query: Calculate age-adjusted OPS
```sql
WITH player_ages AS (
    SELECT
        mg.mlb_player_id,
        mg.season,
        mg.level,
        EXTRACT(YEAR FROM AGE(mg.game_date, p.birth_date)) as age,
        SUM(mg.h + mg.bb + mg.hbp) / NULLIF(SUM(mg.ab + mg.bb + mg.hbp + mg.sf), 0) as obp,
        SUM(mg.singles + mg.doubles*2 + mg.triples*3 + mg.hr*4) / NULLIF(SUM(mg.ab), 0) as slg
    FROM milb_game_logs mg
    JOIN prospects p ON mg.mlb_player_id = p.mlb_player_id
    WHERE p.birth_date IS NOT NULL
    GROUP BY mg.mlb_player_id, mg.season, mg.level, age
)
SELECT
    mlb_player_id,
    season,
    level,
    age,
    obp + slg as ops,
    CASE level
        WHEN 'AAA' THEN (obp + slg) + (25 - age) * 0.010
        WHEN 'AA' THEN (obp + slg) + (23 - age) * 0.010
        WHEN 'A+' THEN (obp + slg) + (22 - age) * 0.010
        ELSE obp + slg
    END as age_adj_ops
FROM player_ages;
```

---

*End of ML Data Documentation*
