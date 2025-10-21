# Pitch-Level Data Enhanced Composite Rankings

**Created:** 2025-10-21
**By:** BMad Party Mode Team
**Status:** Design Complete → Implementation Pending

---

## Executive Summary

Enhance the composite prospect ranking system to utilize granular pitch-level data for more accurate performance modifiers based on percentile rankings within level cohorts.

### Key Changes
1. **Replace simple OPS/ERA** with **weighted pitch-level metrics**
2. **Calculate true percentiles** against all players at each level
3. **Position-specific weights** for different statistics
4. **Graceful degradation** when pitch data unavailable

---

## Current State Analysis

### Limitations
- ❌ Uses only OPS (hitters) and ERA (pitchers) - too simplistic
- ❌ Estimated percentiles via hardcoded thresholds - inaccurate
- ❌ Ignores rich pitch-level data (1.5M pitches tracked)
- ❌ No cohort-based comparison (only threshold-based)
- ❌ One-size-fits-all approach (no position specificity)

### Available Data
- ✅ **621 batters** with pitch-level tracking
- ✅ **363 pitchers** with pitch-level tracking
- ✅ **16,196 total MiLB players** for cohort percentiles
- ✅ **45+ pitch metrics** (velocity, spin, location, results)
- ✅ **Batted ball data** (exit velo, launch angle, etc.)

---

## New System Architecture

### 1. Weighted Performance Metrics

#### For Hitters (Batters)

| Metric | Weight | Data Source | Description |
|--------|--------|-------------|-------------|
| **Exit Velocity (90th %)** | 25% | `milb_batter_pitches.launch_speed` | 90th percentile of batted balls - barrel rate proxy |
| **Hard Hit Rate** | 20% | `launch_speed >= 95 mph` | Percentage of hard-hit balls (95+ mph) |
| **Contact Rate** | 15% | `contact / swings` | Ability to make contact when swinging |
| **Whiff Rate** | 15% | `swing_and_miss / swings` | Swing-and-miss rate (inverse - lower is better) |
| **Chase Rate** | 10% | `swing / out_of_zone_pitches` | Swings at pitches outside zone (inverse) |
| **OPS** | 15% | `milb_game_logs.ops` | Traditional fallback metric |

**Formula:**
```python
hitter_score = (
    exit_velo_percentile * 0.25 +
    hard_hit_percentile * 0.20 +
    contact_percentile * 0.15 +
    (100 - whiff_percentile) * 0.15 +  # Inverted
    (100 - chase_percentile) * 0.10 +   # Inverted
    ops_percentile * 0.15
)
```

#### For Pitchers

| Metric | Weight | Data Source | Description |
|--------|--------|-------------|-------------|
| **Whiff Rate** | 25% | `swing_and_miss / swings` | Swing-and-miss rate - stuff indicator |
| **Zone Rate** | 20% | `zone 1-9 / total pitches` | Strike zone command |
| **Avg FB Velocity** | 15% | `AVG(start_speed) WHERE pitch_type IN ('FF', 'SI')` | Fastball velocity |
| **Hard Contact Rate** | 15% | `launch_speed >= 95 / balls_in_play` | Hard contact allowed (inverse) |
| **Chase Rate** | 10% | `swing_out_of_zone / pitches_out_of_zone` | Inducing chases |
| **K% - BB%** | 15% | `milb_game_logs` | Strikeout rate minus walk rate |

**Formula:**
```python
pitcher_score = (
    whiff_percentile * 0.25 +
    zone_percentile * 0.20 +
    velo_percentile * 0.15 +
    (100 - hard_contact_percentile) * 0.15 +  # Inverted
    chase_percentile * 0.10 +
    k_minus_bb_percentile * 0.15
)
```

---

## 2. Percentile Calculation System

### Level-Based Cohorts

Calculate percentiles **within each level** (not across all levels):

```python
MILB_LEVELS = ['AAA', 'AA', 'A+', 'A', 'Rookie', 'Complex', 'DSL']
```

### Percentile Views (Materialized)

Create materialized views that refresh daily with league-wide percentiles:

#### Hitter Percentiles by Level
```sql
CREATE MATERIALIZED VIEW mv_hitter_percentiles_by_level AS
WITH recent_stats AS (
    SELECT
        mlb_batter_id,
        level,
        season,

        -- Exit Velocity (90th percentile)
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
            FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

        -- Hard Hit Rate
        COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

        -- Contact Rate
        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

        -- Whiff Rate
        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

        -- Chase Rate
        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

        -- Sample size
        COUNT(*) as pitches_seen,
        COUNT(*) FILTER (WHERE swing = TRUE) as swings,
        COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play

    FROM milb_batter_pitches
    WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY mlb_batter_id, level, season
    HAVING COUNT(*) >= 50  -- Minimum 50 pitches
),
level_percentiles AS (
    SELECT
        level,
        season,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY exit_velo_90th) as exit_velo_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY hard_hit_rate) as hard_hit_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY contact_rate) as contact_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY whiff_rate) as whiff_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY chase_rate) as chase_percentiles,
        COUNT(*) as cohort_size
    FROM recent_stats
    GROUP BY level, season
)
SELECT * FROM level_percentiles;

CREATE INDEX idx_hitter_perc_level_season ON mv_hitter_percentiles_by_level(level, season);
```

#### Pitcher Percentiles by Level
```sql
CREATE MATERIALIZED VIEW mv_pitcher_percentiles_by_level AS
WITH recent_stats AS (
    SELECT
        mlb_pitcher_id,
        level,
        season,

        -- Whiff Rate
        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

        -- Zone Rate
        COUNT(*) FILTER (WHERE zone BETWEEN 1 AND 9) * 100.0 /
            NULLIF(COUNT(*), 0) as zone_rate,

        -- Avg FB Velocity
        AVG(start_speed) FILTER (WHERE pitch_type IN ('FF', 'FA', 'SI')
            AND start_speed IS NOT NULL) as avg_fb_velo,

        -- Hard Contact Rate
        COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_contact_rate,

        -- Chase Rate
        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

        -- Sample size
        COUNT(*) as pitches_thrown,
        COUNT(*) FILTER (WHERE swing = TRUE) as swings_induced,
        COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play_allowed

    FROM milb_pitcher_pitches
    WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY mlb_pitcher_id, level, season
    HAVING COUNT(*) >= 100  -- Minimum 100 pitches
),
level_percentiles AS (
    SELECT
        level,
        season,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY whiff_rate) as whiff_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY zone_rate) as zone_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY avg_fb_velo) as velo_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY hard_contact_rate) as hard_contact_percentiles,
        PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
            WITHIN GROUP (ORDER BY chase_rate) as chase_percentiles,
        COUNT(*) as cohort_size
    FROM recent_stats
    GROUP BY level, season
)
SELECT * FROM level_percentiles;

CREATE INDEX idx_pitcher_perc_level_season ON mv_pitcher_percentiles_by_level(level, season);
```

### Refresh Strategy
```sql
-- Refresh daily at 3 AM
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hitter_percentiles_by_level;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pitcher_percentiles_by_level;
```

---

## 3. Implementation: New Service Classes

### PitchDataAggregator Service

```python
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class PitchDataAggregator:
    """Aggregates pitch-level data into weighted performance metrics."""

    # Minimum sample sizes
    MIN_PITCHES_BATTER = 50
    MIN_PITCHES_PITCHER = 100

    # Metric weights
    HITTER_WEIGHTS = {
        'exit_velo_90th': 0.25,
        'hard_hit_rate': 0.20,
        'contact_rate': 0.15,
        'whiff_rate': 0.15,  # Inverted
        'chase_rate': 0.10,  # Inverted
        'ops': 0.15
    }

    PITCHER_WEIGHTS = {
        'whiff_rate': 0.25,
        'zone_rate': 0.20,
        'avg_fb_velo': 0.15,
        'hard_contact_rate': 0.15,  # Inverted
        'chase_rate': 0.10,
        'k_minus_bb': 0.15
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_hitter_pitch_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate hitter pitch-level metrics for recent performance.

        Returns:
            Dict with raw metrics and percentiles, or None if insufficient data
        """
        query = text("""
            WITH player_stats AS (
                SELECT
                    -- Exit Velocity (90th percentile)
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                        FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                    -- Hard Hit Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                    -- Contact Rate
                    COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_seen

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND level = :level
                    AND game_date >= CURRENT_DATE - INTERVAL ':days days'
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)

        result = await self.db.execute(
            query,
            {
                'mlb_player_id': int(mlb_player_id),
                'level': level,
                'days': days,
                'min_pitches': self.MIN_PITCHES_BATTER
            }
        )

        row = result.fetchone()

        if not row:
            logger.info(f"Insufficient pitch data for hitter {mlb_player_id} at {level}")
            return None

        metrics = {
            'exit_velo_90th': row[0],
            'hard_hit_rate': row[1],
            'contact_rate': row[2],
            'whiff_rate': row[3],
            'chase_rate': row[4],
            'pitches_seen': row[5]
        }

        # Calculate percentiles against level cohort
        percentiles = await self._calculate_hitter_percentiles(metrics, level)

        return {
            'metrics': metrics,
            'percentiles': percentiles,
            'sample_size': row[5]
        }

    async def get_pitcher_pitch_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate pitcher pitch-level metrics for recent performance.

        Returns:
            Dict with raw metrics and percentiles, or None if insufficient data
        """
        query = text("""
            WITH player_stats AS (
                SELECT
                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Zone Rate
                    COUNT(*) FILTER (WHERE zone BETWEEN 1 AND 9) * 100.0 /
                        NULLIF(COUNT(*), 0) as zone_rate,

                    -- Avg FB Velocity
                    AVG(start_speed) FILTER (WHERE pitch_type IN ('FF', 'FA', 'SI')
                        AND start_speed IS NOT NULL) as avg_fb_velo,

                    -- Hard Contact Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_contact_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_thrown

                FROM milb_pitcher_pitches
                WHERE mlb_pitcher_id = :mlb_player_id
                    AND level = :level
                    AND game_date >= CURRENT_DATE - INTERVAL ':days days'
            )
            SELECT * FROM player_stats
            WHERE pitches_thrown >= :min_pitches
        """)

        result = await self.db.execute(
            query,
            {
                'mlb_player_id': int(mlb_player_id),
                'level': level,
                'days': days,
                'min_pitches': self.MIN_PITCHES_PITCHER
            }
        )

        row = result.fetchone()

        if not row:
            logger.info(f"Insufficient pitch data for pitcher {mlb_player_id} at {level}")
            return None

        metrics = {
            'whiff_rate': row[0],
            'zone_rate': row[1],
            'avg_fb_velo': row[2],
            'hard_contact_rate': row[3],
            'chase_rate': row[4],
            'pitches_thrown': row[5]
        }

        # Calculate percentiles against level cohort
        percentiles = await self._calculate_pitcher_percentiles(metrics, level)

        return {
            'metrics': metrics,
            'percentiles': percentiles,
            'sample_size': row[5]
        }

    async def _calculate_hitter_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """Calculate percentile rank for each hitter metric vs level cohort."""
        # Query materialized view for level percentiles
        query = text("""
            SELECT
                exit_velo_percentiles,
                hard_hit_percentiles,
                contact_percentiles,
                whiff_percentiles,
                chase_percentiles
            FROM mv_hitter_percentiles_by_level
            WHERE level = :level
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        result = await self.db.execute(query, {'level': level})
        row = result.fetchone()

        if not row:
            logger.warning(f"No percentile data for level {level}, using defaults")
            return self._default_percentiles()

        # Calculate percentile rank for each metric
        percentiles = {}
        percentiles['exit_velo_90th'] = self._find_percentile(
            metrics['exit_velo_90th'], row[0]
        )
        percentiles['hard_hit_rate'] = self._find_percentile(
            metrics['hard_hit_rate'], row[1]
        )
        percentiles['contact_rate'] = self._find_percentile(
            metrics['contact_rate'], row[2]
        )
        percentiles['whiff_rate'] = self._find_percentile(
            metrics['whiff_rate'], row[3]
        )
        percentiles['chase_rate'] = self._find_percentile(
            metrics['chase_rate'], row[4]
        )

        return percentiles

    async def _calculate_pitcher_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """Calculate percentile rank for each pitcher metric vs level cohort."""
        query = text("""
            SELECT
                whiff_percentiles,
                zone_percentiles,
                velo_percentiles,
                hard_contact_percentiles,
                chase_percentiles
            FROM mv_pitcher_percentiles_by_level
            WHERE level = :level
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        result = await self.db.execute(query, {'level': level})
        row = result.fetchone()

        if not row:
            logger.warning(f"No percentile data for level {level}, using defaults")
            return self._default_percentiles()

        percentiles = {}
        percentiles['whiff_rate'] = self._find_percentile(
            metrics['whiff_rate'], row[0]
        )
        percentiles['zone_rate'] = self._find_percentile(
            metrics['zone_rate'], row[1]
        )
        percentiles['avg_fb_velo'] = self._find_percentile(
            metrics['avg_fb_velo'], row[2]
        )
        percentiles['hard_contact_rate'] = self._find_percentile(
            metrics['hard_contact_rate'], row[3]
        )
        percentiles['chase_rate'] = self._find_percentile(
            metrics['chase_rate'], row[4]
        )

        return percentiles

    def _find_percentile(self, value: float, percentile_array: List[float]) -> float:
        """
        Find percentile rank of value within distribution.

        Args:
            value: The value to rank
            percentile_array: [p10, p25, p50, p75, p90] from materialized view

        Returns:
            Estimated percentile (0-100)
        """
        if value is None:
            return 50.0  # Default to median

        p10, p25, p50, p75, p90 = percentile_array

        if value <= p10:
            return 5.0
        elif value <= p25:
            return 10 + ((value - p10) / (p25 - p10)) * 15  # Interpolate 10-25
        elif value <= p50:
            return 25 + ((value - p25) / (p50 - p25)) * 25  # Interpolate 25-50
        elif value <= p75:
            return 50 + ((value - p50) / (p75 - p50)) * 25  # Interpolate 50-75
        elif value <= p90:
            return 75 + ((value - p75) / (p90 - p75)) * 15  # Interpolate 75-90
        else:
            return 95.0

    def _default_percentiles(self) -> Dict:
        """Return default 50th percentile for all metrics when data unavailable."""
        return {key: 50.0 for key in self.HITTER_WEIGHTS.keys()}

    async def calculate_weighted_composite(
        self,
        percentiles: Dict,
        is_hitter: bool
    ) -> float:
        """
        Calculate weighted composite score from percentiles.

        Args:
            percentiles: Dict of metric_name -> percentile_rank
            is_hitter: True for hitters, False for pitchers

        Returns:
            Weighted composite score (0-100 scale)
        """
        weights = self.HITTER_WEIGHTS if is_hitter else self.PITCHER_WEIGHTS

        composite = 0.0

        for metric, weight in weights.items():
            percentile = percentiles.get(metric, 50.0)

            # Invert negative metrics (lower is better)
            if metric in ['whiff_rate', 'chase_rate', 'hard_contact_rate']:
                if is_hitter and metric in ['whiff_rate', 'chase_rate']:
                    percentile = 100 - percentile  # Invert for hitters
                elif not is_hitter and metric == 'hard_contact_rate':
                    percentile = 100 - percentile  # Invert for pitchers

            composite += percentile * weight

        return composite
```

---

## 4. Updated ProspectRankingService

Modify existing service to use pitch data when available:

```python
async def calculate_performance_modifier(
    self,
    prospect_data: Dict,
    recent_stats: Optional[Dict],
    is_hitter: bool
) -> Tuple[float, Optional[Dict]]:
    """
    Calculate performance modifier with pitch data if available.

    Returns:
        Tuple of (modifier_score, detailed_breakdown)
    """
    level = recent_stats.get('recent_level') or prospect_data.get('current_level')
    mlb_player_id = prospect_data.get('mlb_player_id')

    # Try pitch-level data first
    pitch_aggregator = PitchDataAggregator(self.db)

    if is_hitter:
        pitch_metrics = await pitch_aggregator.get_hitter_pitch_metrics(
            mlb_player_id, level, days=60
        )
    else:
        pitch_metrics = await pitch_aggregator.get_pitcher_pitch_metrics(
            mlb_player_id, level, days=60
        )

    # Use pitch data if available, otherwise fall back to game logs
    if pitch_metrics:
        composite_percentile = await pitch_aggregator.calculate_weighted_composite(
            pitch_metrics['percentiles'],
            is_hitter
        )

        # Convert percentile (0-100) to modifier (-10 to +10)
        modifier = self._percentile_to_modifier(composite_percentile)

        breakdown = {
            'source': 'pitch_data',
            'composite_percentile': composite_percentile,
            'metrics': pitch_metrics['metrics'],
            'percentiles': pitch_metrics['percentiles'],
            'sample_size': pitch_metrics['sample_size']
        }

        return modifier, breakdown

    else:
        # Fallback to existing OPS/ERA logic
        logger.info(f"Using game log fallback for {mlb_player_id}")
        modifier = await self._calculate_game_log_modifier(
            recent_stats, is_hitter
        )

        breakdown = {
            'source': 'game_logs',
            'metric': 'OPS' if is_hitter else 'ERA',
            'value': recent_stats.get('recent_ops' if is_hitter else 'recent_era')
        }

        return modifier, breakdown

def _percentile_to_modifier(self, percentile: float) -> float:
    """
    Convert percentile rank (0-100) to performance modifier (-10 to +10).

    Mapping:
    - 95th+ percentile: +10
    - 90th percentile: +8
    - 75th percentile: +5
    - 60th percentile: +2
    - 40-60th: 0 (average)
    - 25th percentile: -5
    - 10th percentile: -8
    - <10th percentile: -10
    """
    if percentile >= 95:
        return 10.0
    elif percentile >= 90:
        return 8.0
    elif percentile >= 75:
        return 5.0
    elif percentile >= 60:
        return 2.0
    elif percentile >= 40:
        return 0.0
    elif percentile >= 25:
        return -2.0
    elif percentile >= 10:
        return -5.0
    else:
        return -10.0
```

---

## 5. Data Quality & Graceful Degradation

### Handling Missing Data

**Priority Waterfall:**
1. **Pitch-level metrics** (preferred) - most granular
2. **Game log aggregates** (fallback) - OPS/ERA
3. **FanGraphs FV only** (no recent data) - base score only

### Sample Size Requirements

| Data Type | Minimum Sample | Reason |
|-----------|----------------|--------|
| Hitter pitch data | 50 pitches | ~2 weeks of play |
| Pitcher pitch data | 100 pitches | ~2-3 starts or 5 relief apps |
| Game logs | 10 games (hitters) | Enough for trend |
| Game logs | 5 games (pitchers) | Enough for trend |

### Missing Data Scenarios

```python
# Scenario 1: Full pitch data available
{
    'source': 'pitch_data',
    'composite_percentile': 87.5,
    'sample_size': 234,
    'confidence': 'high'
}

# Scenario 2: Partial pitch data (some metrics missing)
{
    'source': 'pitch_data_partial',
    'composite_percentile': 78.2,
    'sample_size': 67,
    'confidence': 'medium',
    'missing_metrics': ['spin_rate', 'exit_velocity']
}

# Scenario 3: No pitch data, use game logs
{
    'source': 'game_logs',
    'ops': 0.875,
    'confidence': 'low'
}

# Scenario 4: No recent data at all
{
    'source': 'none',
    'modifier': 0.0,
    'note': 'Using FV only'
}
```

---

## 6. Performance Optimization

### Database Indexes (Already exist, verify)
```sql
-- Batter pitches
CREATE INDEX IF NOT EXISTS idx_batter_pitches_batter_date
    ON milb_batter_pitches(mlb_batter_id, game_date DESC);
CREATE INDEX IF NOT EXISTS idx_batter_pitches_level_season
    ON milb_batter_pitches(level, season);

-- Pitcher pitches
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher_date
    ON milb_pitcher_pitches(mlb_pitcher_id, game_date DESC);
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_level_season
    ON milb_pitcher_pitches(level, season);
```

### Caching Strategy

```python
# Cache percentile views for 24 hours
PERCENTILE_CACHE_TTL = 86400  # 24 hours

# Cache individual prospect calculations for 1 hour
PROSPECT_CACHE_TTL = 3600  # 1 hour
```

---

## 7. API Response Schema

### Enhanced Response

```json
{
  "rank": 1,
  "prospect_id": 12345,
  "name": "Jackson Holliday",
  "position": "SS",
  "composite_score": 69.5,
  "base_fv": 65.0,
  "performance_modifier": 4.5,
  "performance_breakdown": {
    "source": "pitch_data",
    "composite_percentile": 92.3,
    "sample_size": 234,
    "days_covered": 60,
    "metrics": {
      "exit_velo_90th": 105.2,
      "hard_hit_rate": 48.5,
      "contact_rate": 82.1,
      "whiff_rate": 18.3,
      "chase_rate": 24.7
    },
    "percentiles": {
      "exit_velo_90th": 95,
      "hard_hit_rate": 92,
      "contact_rate": 88,
      "whiff_rate": 85,
      "chase_rate": 90
    },
    "weighted_contribution": {
      "exit_velo_90th": 23.75,
      "hard_hit_rate": 18.4,
      "contact_rate": 13.2,
      "whiff_rate": 12.75,
      "chase_rate": 9.0,
      "ops": 15.13
    }
  },
  "trend_adjustment": 2.0,
  "age_adjustment": 3.0,
  "total_adjustment": 9.5
}
```

---

## 8. Testing Strategy

### Unit Tests
- [ ] Percentile calculation accuracy
- [ ] Weighted composite formula
- [ ] Graceful degradation logic
- [ ] Sample size filtering

### Integration Tests
- [ ] Materialized view refresh
- [ ] Query performance (<5s for rankings)
- [ ] Data consistency checks

### Validation Tests
- [ ] Compare old vs new rankings
- [ ] Verify percentiles add value
- [ ] User acceptance testing

---

## 9. Rollout Plan

### Phase 1: Development (Week 1)
- [ ] Create materialized views
- [ ] Implement PitchDataAggregator
- [ ] Update ProspectRankingService
- [ ] Add unit tests

### Phase 2: Testing (Week 2)
- [ ] Validate against historical data
- [ ] Performance testing
- [ ] Edge case verification
- [ ] Documentation

### Phase 3: Deployment (Week 3)
- [ ] Deploy materialized views
- [ ] Run initial refresh
- [ ] Deploy service updates
- [ ] Monitor performance

### Phase 4: Monitoring (Ongoing)
- [ ] Track query performance
- [ ] Monitor data coverage
- [ ] Gather user feedback
- [ ] Iterate on weights

---

## 10. Success Metrics

### Technical Metrics
- Query performance: <5s for full rankings
- Data coverage: >40% prospects with pitch data
- Cache hit rate: >80%

### Business Metrics
- User engagement with rankings page
- Feedback on ranking accuracy
- Differentiation of similar FV prospects

---

## Appendix: Configuration

```yaml
# config/ranking_weights.yaml
hitter_weights:
  exit_velo_90th: 0.25
  hard_hit_rate: 0.20
  contact_rate: 0.15
  whiff_rate: 0.15
  chase_rate: 0.10
  ops: 0.15

pitcher_weights:
  whiff_rate: 0.25
  zone_rate: 0.20
  avg_fb_velo: 0.15
  hard_contact_rate: 0.15
  chase_rate: 0.10
  k_minus_bb: 0.15

sample_sizes:
  min_pitches_batter: 50
  min_pitches_pitcher: 100
  min_games_batter: 10
  min_games_pitcher: 5

percentile_refresh:
  schedule: "0 3 * * *"  # Daily at 3 AM
  concurrently: true
```

---

**Next Steps:**
1. Review and approve design
2. Create database migration for materialized views
3. Implement PitchDataAggregator service
4. Update ProspectRankingService
5. Deploy and test

---

**Contributors:** Orchestrator, Analyst, Architect, Developer, QA, PM, PO
**Status:** ✅ Design Complete → Ready for Implementation
