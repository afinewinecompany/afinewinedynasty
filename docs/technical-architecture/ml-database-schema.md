# ML Database Schema - Complete Architecture

## Executive Summary

Comprehensive PostgreSQL schema for A Fine Wine Dynasty ML prediction engine, optimized for Railway deployment. Supports 120+ ML features across game-by-game granularity.

---

## Core Design Principles

### Railway PostgreSQL Constraints
- ✅ Standard PostgreSQL 15+ (no TimescaleDB)
- ✅ Async operations via SQLAlchemy + asyncpg
- ✅ Efficient indexing for time-series queries
- ✅ JSONB for flexible feature storage
- ✅ Foreign key constraints for data integrity

### ML Requirements
- **100-120 features per prospect** from 3 data sources:
  1. Fangraphs Prospects API (scouting grades)
  2. MLB Stats API (game logs + aggregates)
  3. Fangraphs MiLB API (advanced metrics)
- **Game-by-game granularity** for temporal features
- **Multi-year history** (2010-2024, expandable)
- **Fast aggregation** for model training

---

## Complete Schema

### 1. Core Prospects Table

```sql
CREATE TABLE prospects (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- External IDs (multiple sources)
    mlb_id INTEGER UNIQUE,                    -- MLB Stats API ID
    fg_player_id VARCHAR(50),                 -- Fangraphs player ID
    fg_prospect_id VARCHAR(50),               -- Fangraphs prospect list ID
    ba_player_id VARCHAR(50),                 -- Baseball America ID (future)

    -- Bio Data
    name VARCHAR(200) NOT NULL,
    position VARCHAR(10) NOT NULL,            -- P, C, 1B, 2B, SS, 3B, OF, etc.
    bats VARCHAR(1),                          -- L, R, S (switch)
    throws VARCHAR(1),                        -- L, R

    -- Physical
    height_inches INTEGER,                    -- Total inches
    weight_lbs INTEGER,
    birth_date DATE,
    birth_country VARCHAR(100),
    birth_city VARCHAR(100),

    -- Draft Info
    draft_year INTEGER,
    draft_round INTEGER,
    draft_pick INTEGER,
    draft_team VARCHAR(100),
    signing_bonus_usd INTEGER,

    -- Current Status
    current_team VARCHAR(100),
    current_organization VARCHAR(100),
    current_level VARCHAR(20),                -- MLB, AAA, AA, A+, A, Rookie

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_stats_update TIMESTAMP,
    data_sources JSONB DEFAULT '{}'::jsonb,   -- Track which APIs have data

    -- Indexes
    CONSTRAINT valid_position CHECK (position IN (
        'P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF',
        'OF', 'IF', 'DH', 'SP', 'RP', 'RHP', 'LHP'
    )),
    CONSTRAINT valid_handedness CHECK (
        bats IN ('L', 'R', 'S') AND throws IN ('L', 'R')
    )
);

-- Indexes for performance
CREATE INDEX idx_prospects_mlb_id ON prospects(mlb_id);
CREATE INDEX idx_prospects_fg_id ON prospects(fg_player_id);
CREATE INDEX idx_prospects_organization ON prospects(current_organization);
CREATE INDEX idx_prospects_position ON prospects(position);
CREATE INDEX idx_prospects_draft_year ON prospects(draft_year);
CREATE INDEX idx_prospects_name_trgm ON prospects USING gin(name gin_trgm_ops);
```

---

### 2. Minor League Game Logs (CRITICAL for ML)

**Purpose:** Store game-by-game performance for time-series ML features

```sql
CREATE TABLE milb_game_logs (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,

    -- Foreign Keys
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,

    -- Game Context
    game_date DATE NOT NULL,
    season INTEGER NOT NULL,
    game_type VARCHAR(10),                    -- Regular, Playoffs, Spring
    team VARCHAR(100),
    opponent VARCHAR(100),
    is_home BOOLEAN,
    level VARCHAR(20) NOT NULL,               -- AAA, AA, A+, A, Rookie

    -- MLB Stats API provides 33+ fields per game
    -- Traditional Hitting Stats
    games_played INTEGER DEFAULT 1,
    plate_appearances INTEGER,
    at_bats INTEGER,
    runs INTEGER,
    hits INTEGER,
    doubles INTEGER,
    triples INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    walks INTEGER,
    intentional_walks INTEGER,
    strikeouts INTEGER,
    stolen_bases INTEGER,
    caught_stealing INTEGER,
    hit_by_pitch INTEGER,
    sacrifice_flies INTEGER,
    sacrifice_hits INTEGER,

    -- Advanced Hitting Stats
    batting_avg DECIMAL(4,3),
    on_base_pct DECIMAL(4,3),
    slugging_pct DECIMAL(4,3),
    ops DECIMAL(4,3),
    babip DECIMAL(4,3),

    -- Batted Ball Data
    ground_outs INTEGER,
    air_outs INTEGER,
    fly_outs INTEGER,
    ground_into_double_play INTEGER,

    -- Discipline
    pitches_seen INTEGER,
    left_on_base INTEGER,

    -- Derived Game Flags (for ML features)
    multi_hit_game BOOLEAN GENERATED ALWAYS AS (hits >= 2) STORED,
    extra_base_hit_game BOOLEAN GENERATED ALWAYS AS (
        (doubles + triples + home_runs) > 0
    ) STORED,
    golden_sombrero BOOLEAN GENERATED ALWAYS AS (strikeouts >= 4) STORED,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    data_source VARCHAR(50) DEFAULT 'mlb_api',

    -- Constraints
    CONSTRAINT valid_level CHECK (level IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Complex')),
    CONSTRAINT valid_game_type CHECK (game_type IN ('Regular', 'Playoffs', 'Spring', 'All-Star'))
);

-- Critical indexes for time-series queries
CREATE INDEX idx_milb_logs_prospect_date ON milb_game_logs(prospect_id, game_date DESC);
CREATE INDEX idx_milb_logs_prospect_season ON milb_game_logs(prospect_id, season, level);
CREATE INDEX idx_milb_logs_season_level ON milb_game_logs(season, level);
CREATE INDEX idx_milb_logs_date ON milb_game_logs(game_date);

-- Partitioning by year for performance (optional, if data grows large)
-- CREATE TABLE milb_game_logs_2024 PARTITION OF milb_game_logs
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

---

### 3. Minor League Season Aggregates

**Purpose:** Pre-computed season totals for fast querying

```sql
CREATE MATERIALIZED VIEW milb_season_stats AS
SELECT
    prospect_id,
    season,
    level,

    -- Aggregates
    COUNT(*) as games_played,
    SUM(plate_appearances) as total_pa,
    SUM(at_bats) as total_ab,
    SUM(hits) as total_hits,
    SUM(doubles) as total_2b,
    SUM(triples) as total_3b,
    SUM(home_runs) as total_hr,
    SUM(runs) as total_r,
    SUM(rbi) as total_rbi,
    SUM(walks) as total_bb,
    SUM(strikeouts) as total_so,
    SUM(stolen_bases) as total_sb,
    SUM(caught_stealing) as total_cs,

    -- Calculated Rates
    CASE
        WHEN SUM(at_bats) > 0
        THEN ROUND(SUM(hits)::numeric / SUM(at_bats), 3)
        ELSE NULL
    END as avg,

    CASE
        WHEN (SUM(at_bats) + SUM(walks) + SUM(hit_by_pitch) + SUM(sacrifice_flies)) > 0
        THEN ROUND(
            (SUM(hits) + SUM(walks) + SUM(hit_by_pitch))::numeric /
            (SUM(at_bats) + SUM(walks) + SUM(hit_by_pitch) + SUM(sacrifice_flies)),
            3
        )
        ELSE NULL
    END as obp,

    CASE
        WHEN SUM(at_bats) > 0
        THEN ROUND(
            (SUM(hits) + SUM(doubles) + 2*SUM(triples) + 3*SUM(home_runs))::numeric /
            SUM(at_bats),
            3
        )
        ELSE NULL
    END as slg,

    -- Discipline metrics
    CASE
        WHEN SUM(plate_appearances) > 0
        THEN ROUND(SUM(walks)::numeric / SUM(plate_appearances) * 100, 1)
        ELSE NULL
    END as bb_percent,

    CASE
        WHEN SUM(plate_appearances) > 0
        THEN ROUND(SUM(strikeouts)::numeric / SUM(plate_appearances) * 100, 1)
        ELSE NULL
    END as k_percent,

    -- Game log derived metrics
    SUM(CASE WHEN multi_hit_game THEN 1 ELSE 0 END) as multi_hit_games,
    SUM(CASE WHEN extra_base_hit_game THEN 1 ELSE 0 END) as extra_base_hit_games,

    -- Consistency (coefficient of variation for hits per game)
    STDDEV(hits) / NULLIF(AVG(hits), 0) as hit_consistency_cv,

    -- Date range
    MIN(game_date) as season_start,
    MAX(game_date) as season_end

FROM milb_game_logs
GROUP BY prospect_id, season, level;

-- Index for fast lookups
CREATE UNIQUE INDEX idx_milb_season_pk ON milb_season_stats(prospect_id, season, level);
CREATE INDEX idx_milb_season_lookup ON milb_season_stats(season, level);

-- Refresh strategy (run after data loads)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY milb_season_stats;
```

---

### 4. Major League Stats (Target Variables)

**Purpose:** MLB outcomes for training labels (success/failure)

```sql
CREATE TABLE mlb_stats (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    season INTEGER NOT NULL,

    -- Service Time
    mlb_debut_date DATE,
    mlb_service_days INTEGER,

    -- Hitting Stats
    games_played INTEGER,
    plate_appearances INTEGER,
    at_bats INTEGER,
    runs INTEGER,
    hits INTEGER,
    doubles INTEGER,
    triples INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    walks INTEGER,
    strikeouts INTEGER,
    stolen_bases INTEGER,
    caught_stealing INTEGER,

    -- Advanced
    batting_avg DECIMAL(4,3),
    on_base_pct DECIMAL(4,3),
    slugging_pct DECIMAL(4,3),
    ops DECIMAL(4,3),
    ops_plus INTEGER,                         -- League adjusted

    -- Batted Ball (if available)
    ground_balls INTEGER,
    fly_balls INTEGER,
    line_drives INTEGER,

    -- Value Metrics (if available)
    war DECIMAL(3,1),                         -- Wins Above Replacement

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    data_source VARCHAR(50) DEFAULT 'mlb_api',

    UNIQUE(prospect_id, season)
);

CREATE INDEX idx_mlb_stats_prospect ON mlb_stats(prospect_id);
CREATE INDEX idx_mlb_stats_season ON mlb_stats(season);
```

---

### 5. Scouting Grades (Multi-Source)

**Purpose:** Professional scout evaluations (20-80 scale)

```sql
CREATE TABLE scouting_grades (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,

    -- Source Info
    source VARCHAR(50) NOT NULL,              -- 'fangraphs', 'ba', 'mlb_pipeline'
    ranking_year INTEGER NOT NULL,            -- Year of ranking (e.g., 2024)
    rank_overall INTEGER,                     -- Overall rank (e.g., #45)

    -- Future Value (Fangraphs)
    future_value INTEGER,                     -- 20-80 scale (FV)

    -- Risk Assessment
    risk_level VARCHAR(10),                   -- 'Safe', 'Medium', 'Extreme', 'High'

    -- ETA
    eta_year INTEGER,                         -- Projected MLB debut
    eta_season VARCHAR(20),                   -- 'Early 2025', 'Mid 2026'

    -- Tool Grades - PRESENT (current ability)
    hit_present INTEGER,                      -- 20-80
    power_present INTEGER,                    -- 20-80 (game power)
    raw_power_present INTEGER,                -- 20-80 (batting practice)
    speed_present INTEGER,                    -- 20-80
    field_present INTEGER,                    -- 20-80
    arm_present INTEGER,                      -- 20-80

    -- Tool Grades - FUTURE (projected at peak)
    hit_future INTEGER,                       -- 20-80
    power_future INTEGER,                     -- 20-80
    raw_power_future INTEGER,                 -- 20-80
    speed_future INTEGER,                     -- 20-80
    field_future INTEGER,                     -- 20-80
    arm_future INTEGER,                       -- 20-80

    -- Pitcher-Specific Tools (if applicable)
    fastball_grade INTEGER,                   -- 20-80
    slider_grade INTEGER,                     -- 20-80
    curveball_grade INTEGER,                  -- 20-80
    changeup_grade INTEGER,                   -- 20-80
    control_grade INTEGER,                    -- 20-80
    command_grade INTEGER,                    -- 20-80

    -- Fantasy Rankings
    dynasty_rank INTEGER,
    redraft_rank INTEGER,

    -- Narrative
    scouting_report TEXT,

    -- Metadata
    date_recorded DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_grades CHECK (
        (future_value IS NULL OR (future_value >= 20 AND future_value <= 80))
        AND (risk_level IS NULL OR risk_level IN ('Safe', 'Medium', 'High', 'Extreme'))
    )
);

CREATE INDEX idx_scouting_prospect ON scouting_grades(prospect_id);
CREATE INDEX idx_scouting_source_year ON scouting_grades(source, ranking_year);
CREATE INDEX idx_scouting_fv ON scouting_grades(future_value DESC NULLS LAST);
CREATE UNIQUE INDEX idx_scouting_unique ON scouting_grades(prospect_id, source, ranking_year);
```

---

### 6. Advanced MiLB Metrics (Fangraphs Supplement)

**Purpose:** Advanced sabermetrics not in MLB API

```sql
CREATE TABLE milb_advanced_stats (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    season INTEGER NOT NULL,
    level VARCHAR(20) NOT NULL,

    -- Advanced Offensive Metrics
    wrc INTEGER,                              -- Weighted Runs Created
    wraa INTEGER,                             -- Weighted Runs Above Average
    woba DECIMAL(4,3),                        -- Weighted On-Base Average
    wrc_plus INTEGER,                         -- League/park adjusted wRC
    iso DECIMAL(4,3),                         -- Isolated Power (SLG - AVG)

    -- Batted Ball Profile
    gb_percent DECIMAL(4,1),                  -- Ground ball %
    fb_percent DECIMAL(4,1),                  -- Fly ball %
    ld_percent DECIMAL(4,1),                  -- Line drive %
    iffb_percent DECIMAL(4,1),                -- Infield fly ball %
    hr_per_fb DECIMAL(4,1),                   -- HR/FB ratio

    -- Spray Angle
    pull_percent DECIMAL(4,1),
    oppo_percent DECIMAL(4,1),
    cent_percent DECIMAL(4,1),

    -- Plate Discipline
    swing_strike_percent DECIMAL(4,1),        -- SwStr%
    contact_percent DECIMAL(4,1),             -- Contact%
    zone_percent DECIMAL(4,1),                -- % pitches in zone
    o_swing_percent DECIMAL(4,1),             -- Outside swing %
    z_swing_percent DECIMAL(4,1),             -- Zone swing %

    -- Speed/Baserunning
    speed_score DECIMAL(3,1),                 -- Spd
    wbsr DECIMAL(4,1),                        -- Weighted baserunning runs

    -- Contact Quality (if available)
    hard_contact_percent DECIMAL(4,1),
    soft_contact_percent DECIMAL(4,1),
    medium_contact_percent DECIMAL(4,1),

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    data_source VARCHAR(50) DEFAULT 'fangraphs',

    UNIQUE(prospect_id, season, level)
);

CREATE INDEX idx_milb_advanced_prospect ON milb_advanced_stats(prospect_id);
CREATE INDEX idx_milb_advanced_season ON milb_advanced_stats(season, level);
```

---

### 7. ML Features Cache

**Purpose:** Store engineered features for fast model training

```sql
CREATE TABLE ml_features (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    feature_set_version VARCHAR(20) NOT NULL, -- 'v1.0', 'v2.0' for tracking

    -- Reference Year (e.g., features as of 2020 to predict 2024 outcome)
    as_of_year INTEGER NOT NULL,

    -- Feature Categories (stored as JSONB for flexibility)
    bio_features JSONB,                       -- Age, draft, physical
    scouting_features JSONB,                  -- Tool grades, deltas, averages
    milb_performance JSONB,                   -- Career/best season stats
    milb_progression JSONB,                   -- Level advancement, improvement
    milb_consistency JSONB,                   -- Variance, streaks from game logs
    derived_features JSONB,                   -- Calculated combinations

    -- Pre-computed Feature Vector (for fast model serving)
    feature_vector JSONB,                     -- All 120 features as flat JSON

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(prospect_id, as_of_year, feature_set_version)
);

CREATE INDEX idx_ml_features_prospect ON ml_features(prospect_id);
CREATE INDEX idx_ml_features_year ON ml_features(as_of_year);
CREATE INDEX idx_ml_features_version ON ml_features(feature_set_version);

-- GIN index for JSONB queries
CREATE INDEX idx_ml_features_vector ON ml_features USING gin(feature_vector);
```

---

### 8. ML Labels (Target Variables)

**Purpose:** Ground truth for training (did they succeed in MLB?)

```sql
CREATE TABLE ml_labels (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,

    -- Training Configuration
    prospect_year INTEGER NOT NULL,           -- Year they were a prospect (e.g., 2020)
    evaluation_year INTEGER NOT NULL,         -- Year we evaluate success (e.g., 2024)
    years_to_evaluate INTEGER DEFAULT 4,      -- Window (typically 4 years)

    -- Success Metrics
    reached_mlb BOOLEAN,
    mlb_debut_date DATE,
    years_to_mlb INTEGER,                     -- Time from prospect year to debut

    -- Performance Thresholds (configurable)
    total_pa INTEGER,                         -- Plate appearances in window
    total_games INTEGER,                      -- Games played in window
    total_innings_pitched DECIMAL(5,1),       -- For pitchers
    peak_war DECIMAL(3,1),                    -- Best single season WAR
    cumulative_war DECIMAL(4,1),              -- Total WAR in window

    -- Binary Label (primary target)
    is_success BOOLEAN,                       -- TRUE if >= 500 PA or 100 IP in window

    -- Multi-Class Label (alternative targets)
    success_tier VARCHAR(20),                 -- 'Star', 'Solid', 'Marginal', 'Failed'

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(prospect_id, prospect_year, evaluation_year)
);

CREATE INDEX idx_ml_labels_prospect ON ml_labels(prospect_id);
CREATE INDEX idx_ml_labels_year ON ml_labels(prospect_year);
CREATE INDEX idx_ml_labels_success ON ml_labels(is_success);
```

---

### 9. ML Predictions (Model Outputs)

**Purpose:** Store model predictions for serving and monitoring

```sql
CREATE TABLE ml_predictions (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,

    -- Model Info
    model_version VARCHAR(20) NOT NULL,       -- 'v1.0', 'xgboost_v2', etc.
    prediction_date DATE NOT NULL,

    -- Predictions
    success_probability DECIMAL(4,3),         -- 0.000 to 1.000
    predicted_class BOOLEAN,                  -- Binary prediction
    confidence_level VARCHAR(10),             -- 'High', 'Medium', 'Low'

    -- Multi-class predictions (if applicable)
    prob_star DECIMAL(4,3),
    prob_solid DECIMAL(4,3),
    prob_marginal DECIMAL(4,3),
    prob_failed DECIMAL(4,3),

    -- Explainability (SHAP values)
    feature_importance JSONB,                 -- Top N feature contributions
    shap_values JSONB,                        -- Full SHAP vector

    -- Generated Narrative
    prediction_narrative TEXT,                -- Human-readable explanation
    key_strengths TEXT[],                     -- Array of strengths
    key_concerns TEXT[],                      -- Array of concerns
    comparable_players TEXT[],                -- Similar historical prospects

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(prospect_id, model_version, prediction_date)
);

CREATE INDEX idx_predictions_prospect ON ml_predictions(prospect_id);
CREATE INDEX idx_predictions_model ON ml_predictions(model_version);
CREATE INDEX idx_predictions_date ON ml_predictions(prediction_date DESC);
CREATE INDEX idx_predictions_prob ON ml_predictions(success_probability DESC);
```

---

## Database Relationships

```
prospects (1) ←→ (∞) milb_game_logs         [Game-by-game performance]
prospects (1) ←→ (∞) mlb_stats              [MLB outcomes]
prospects (1) ←→ (∞) scouting_grades        [Multi-source scouting]
prospects (1) ←→ (∞) milb_advanced_stats    [Fangraphs metrics]
prospects (1) ←→ (∞) ml_features            [Engineered features]
prospects (1) ←→ (∞) ml_labels              [Training labels]
prospects (1) ←→ (∞) ml_predictions         [Model outputs]

milb_game_logs (∞) → (1) milb_season_stats [Materialized view aggregation]
```

---

## Storage Estimates (Railway PostgreSQL)

**For 600 prospects × 15 years × 100 games/year:**

| Table | Rows | Row Size | Total Size |
|-------|------|----------|------------|
| prospects | 9,000 | 1 KB | ~9 MB |
| milb_game_logs | 900,000 | 500 bytes | ~450 MB |
| milb_season_stats | 27,000 | 300 bytes | ~8 MB |
| mlb_stats | 4,500 | 400 bytes | ~2 MB |
| scouting_grades | 3,000 | 1 KB | ~3 MB |
| milb_advanced_stats | 27,000 | 600 bytes | ~16 MB |
| ml_features | 9,000 | 10 KB | ~90 MB |
| ml_labels | 5,400 | 300 bytes | ~2 MB |
| ml_predictions | 1,000 | 5 KB | ~5 MB |

**Total: ~585 MB** (well within Railway's limits)

---

## Indexing Strategy Summary

### Critical Indexes (Always Create)
1. **Foreign Keys** - All `prospect_id` references
2. **Time-series** - `(prospect_id, game_date)` for game logs
3. **Aggregation** - `(season, level)` for stats queries
4. **Lookups** - Unique constraints on natural keys

### Optional Indexes (Create if needed)
1. **Full-text** - `name` with trigram for fuzzy search
2. **JSONB** - GIN indexes on feature vectors
3. **Partitioning** - Year-based partitions if > 10M rows

---

## Migration Strategy

### Phase 1: Core Tables
1. prospects
2. milb_game_logs
3. mlb_stats
4. scouting_grades

### Phase 2: Advanced Analytics
5. milb_advanced_stats
6. milb_season_stats (materialized view)

### Phase 3: ML Infrastructure
7. ml_features
8. ml_labels
9. ml_predictions

---

## Railway-Specific Optimizations

### Connection Pooling
```python
# Already configured in database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,              # Railway default
    max_overflow=10,
    pool_pre_ping=True,       # Handle connection drops
)
```

### Async Operations
```python
# All models use AsyncSession
async with AsyncSessionLocal() as session:
    await session.execute(...)
```

### Backup Strategy
- Railway provides automatic daily backups
- Use `pg_dump` for manual backups before schema changes

---

## Next Steps

1. ✅ **Create SQLAlchemy ORM models** matching this schema
2. ✅ **Generate Alembic migrations** for versioned deployment
3. ✅ **Test with sample data** from collection scripts
4. ✅ **Validate query performance** with EXPLAIN ANALYZE
5. ✅ **Deploy to Railway** staging environment

---

**Architecture Status:** ✅ Complete and Railway-ready
