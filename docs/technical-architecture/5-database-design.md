# 5. Database Design

## Core Schema

**Prospects Table:**
```sql
CREATE TABLE prospects (
    id SERIAL PRIMARY KEY,
    mlb_id VARCHAR(10) UNIQUE,
    name VARCHAR(100) NOT NULL,
    position VARCHAR(10) NOT NULL,
    organization VARCHAR(50),
    level VARCHAR(20),
    age INTEGER,
    eta_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_prospects_organization ON prospects(organization);
CREATE INDEX idx_prospects_position ON prospects(position);
CREATE INDEX idx_prospects_eta ON prospects(eta_year);
```

**Time-Series Performance Data (TimescaleDB):**
```sql
-- Hypertable for time-series data
CREATE TABLE prospect_stats (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    season INTEGER NOT NULL,
    level VARCHAR(20) NOT NULL,
    date_recorded DATE NOT NULL,

    -- Hitting statistics
    games_played INTEGER,
    at_bats INTEGER,
    hits INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    stolen_bases INTEGER,
    walks INTEGER,
    strikeouts INTEGER,
    batting_avg DECIMAL(4,3),
    on_base_pct DECIMAL(4,3),
    slugging_pct DECIMAL(4,3),

    -- Pitching statistics
    innings_pitched DECIMAL(5,1),
    earned_runs INTEGER,
    era DECIMAL(4,2),
    whip DECIMAL(4,3),
    strikeouts_per_nine DECIMAL(4,2),
    walks_per_nine DECIMAL(4,2),

    -- Performance metrics
    woba DECIMAL(4,3),
    wrc_plus INTEGER,

    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('prospect_stats', 'date_recorded');
```

**ML Features & Predictions:**
```sql
CREATE TABLE ml_predictions (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    model_version VARCHAR(20) NOT NULL,
    success_probability DECIMAL(4,3),
    confidence_level VARCHAR(10) CHECK (confidence_level IN ('High', 'Medium', 'Low')),
    feature_importance JSONB, -- SHAP values
    narrative TEXT, -- Generated explanation
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Composite index for latest predictions
CREATE INDEX idx_predictions_latest ON ml_predictions(prospect_id, generated_at DESC);
```

**Scouting Grades (Multi-Source):**
```sql
CREATE TABLE scouting_grades (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    source VARCHAR(50) NOT NULL, -- 'fangraphs', 'mlb_pipeline', etc.
    overall_grade INTEGER, -- 20-80 scale
    hit_grade INTEGER,
    power_grade INTEGER,
    speed_grade INTEGER,
    field_grade INTEGER,
    arm_grade INTEGER,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for efficient source-based queries
CREATE INDEX idx_scouting_grades_prospect ON scouting_grades(prospect_id);
CREATE INDEX idx_scouting_grades_source ON scouting_grades(source, updated_at);
```

**User Management:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    subscription_tier VARCHAR(20) DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'premium')),
    stripe_customer_id VARCHAR(50),
    fantrax_user_id VARCHAR(50),
    fantrax_refresh_token TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id),
    access_token_hash VARCHAR(255),
    refresh_token_hash VARCHAR(255),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Data Relationships

```
prospects (1) ←→ (∞) prospect_stats [Time-series performance data]
prospects (1) ←→ (∞) scouting_grades [Multi-source scouting data]
prospects (1) ←→ (∞) ml_predictions [ML model outputs]
users (1) ←→ (∞) user_watchlists [Prospect tracking]
users (1) ←→ (∞) fantrax_rosters [League integration]
```

## Database Performance Strategy

**Partitioning Strategy:**
- **prospect_stats**: Partitioned by date_recorded (monthly partitions)
- **ml_predictions**: Partitioned by generated_at (monthly partitions)
- **user_sessions**: Automatic cleanup of expired sessions

**Indexing Strategy:**
```sql
-- Critical performance indexes
CREATE INDEX idx_stats_prospect_season ON prospect_stats(prospect_id, season);
CREATE INDEX idx_stats_date_recorded ON prospect_stats(date_recorded);
CREATE INDEX idx_scouting_source_updated ON scouting_grades(source, updated_at);
CREATE INDEX idx_users_subscription ON users(subscription_tier);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

---
