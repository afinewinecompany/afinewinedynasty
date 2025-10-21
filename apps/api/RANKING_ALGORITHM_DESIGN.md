# A Fine Wine Dynasty - Prospect Ranking Algorithm Design

**Version:** 1.0
**Created:** 2025-10-20
**Status:** Design Complete - Ready for Implementation

---

## Executive Summary

This document defines the **Composite Prospect Ranking Algorithm** that combines FanGraphs expert scouting grades with recent MiLB performance data to generate dynamic prospect rankings for the A Fine Wine Dynasty platform.

**Core Philosophy:** Leverage proven expert evaluations (FanGraphs) as the foundation, enhanced with real-time performance signals from our comprehensive MiLB database.

---

## Algorithm Overview

### Formula

```
Composite Score = Base FV + (Performance Modifier × 0.5) + (Trend Adjustment × 0.3) + (Age Bonus × 0.2)

Where:
- Base FV: FanGraphs Future Value (40-70 scale)
- Performance Modifier: Recent MiLB stats vs level peers (±10)
- Trend Adjustment: 30-day vs 60-day comparison (±5)
- Age Bonus: Young for level premium (0 to +5)
- Total Adjustment Cap: ±10 points
```

### Score Range
- **Maximum:** 80 (FV 70 + 10 adjustment)
- **Typical Top Prospect:** 70-75
- **Average Prospect:** 50-55
- **Minimum:** 30 (FV 40 - 10 adjustment)

---

## Component Algorithms

### 1. Base Score (70% Weight)

**Source:** FanGraphs Future Value (FV) from 2025 grades

```python
def get_base_score(prospect):
    '''
    Base score comes directly from FanGraphs FV
    FV Scale: 40-70
    - 70 = Elite (future perennial all-star)
    - 65 = Plus-plus (all-star level)
    - 60 = Plus player (solid regular)
    - 55 = Above average regular
    - 50 = Average regular
    - 45 = Role player
    - 40 = Fringe player
    '''
    if prospect.is_hitter:
        return fangraphs_hitter_grades.fv
    else:
        return fangraphs_pitcher_grades.fv
```

**Data Source:**
- Table: `fangraphs_hitter_grades` or `fangraphs_pitcher_grades`
- Filter: `data_year = 2025`
- Join: `prospects.fg_player_id = fangraphs_*.fangraphs_player_id`

---

### 2. Performance Modifier (30% Weight)

**Purpose:** Adjust ranking based on recent MiLB performance relative to level peers

```python
def calculate_performance_modifier(prospect):
    '''
    Adjust FV based on recent MiLB performance
    Modifier Range: -10 to +10 points
    Lookback: Last 60 days
    Min Sample: 50 PA (hitters) or 20 IP (pitchers)
    '''

    recent_stats = get_recent_milb_stats(prospect, days=60)

    # Insufficient data check
    if not recent_stats or insufficient_sample_size(recent_stats):
        return 0

    # Calculate percentile vs level-mates
    if prospect.is_hitter:
        metric = recent_stats.ops  # Primary hitter metric
        level_percentile = get_percentile_at_level(
            stat=metric,
            level=recent_stats.level,
            season=2024
        )
    else:
        metric = recent_stats.era  # Primary pitcher metric (inverted)
        level_percentile = 100 - get_percentile_at_level(
            stat=metric,
            level=recent_stats.level,
            season=2024
        )

    # Percentile to modifier conversion
    if level_percentile >= 90:
        return +10  # Elite performance
    elif level_percentile >= 75:
        return +5   # Above average
    elif level_percentile >= 60:
        return +2   # Slightly above average
    elif level_percentile >= 40:
        return 0    # Average
    elif level_percentile >= 25:
        return -5   # Below average
    else:
        return -10  # Poor performance
```

**Hitter Metrics:**
- Primary: OPS (On-base Plus Slugging)
- Secondary: wRC+, ISO, BB%, K%

**Pitcher Metrics:**
- Primary: ERA (Earned Run Average)
- Secondary: FIP, K/9, BB/9, WHIP

**Level Adjustments:**
Performance is compared against ALL players at the same level (not just prospects), providing true peer comparison.

---

### 3. Trend Adjustment (20% Weight)

**Purpose:** Reward improving players, penalize declining players

```python
def calculate_trend_adjustment(prospect):
    '''
    Bonus/penalty for improving/declining performance
    Adjustment Range: -5 to +5 points
    Comparison: Last 30 days vs previous 30 days (30-60 days ago)
    '''

    recent_30 = get_milb_stats(prospect, days=30)
    previous_30 = get_milb_stats(prospect, days_start=30, days_end=60)

    if not recent_30 or not previous_30:
        return 0

    # Calculate improvement rate
    if prospect.is_hitter:
        improvement = (recent_30.ops - previous_30.ops) / previous_30.ops
    else:
        improvement = (previous_30.era - recent_30.era) / previous_30.era

    # Convert to adjustment
    if improvement > 0.15:      # 15%+ improvement
        return +5
    elif improvement > 0.05:    # 5-15% improvement
        return +2
    elif improvement < -0.15:   # 15%+ decline
        return -5
    elif improvement < -0.05:   # 5-15% decline
        return -2
    else:
        return 0                # Stable
```

**Trend Indicators (for UI):**
- 🔥 **Hot** (+5): 15%+ improvement
- ↗️ **Surging** (+2): 5-15% improvement
- → **Stable** (0): Within ±5%
- ↘️ **Cooling** (-2): 5-15% decline
- ❄️ **Cold** (-5): 15%+ decline

---

### 4. Age-Relative-to-Level Bonus (10% Weight)

**Purpose:** Premium for prospects performing at advanced levels while young

```python
def calculate_age_bonus(prospect):
    '''
    Bonus for being young at advanced levels
    Adjustment Range: 0 to +5 points
    '''

    level = prospect.current_level
    age = prospect.age

    # Age benchmarks by level
    age_benchmarks = {
        'AAA': 24,
        'AA': 23,
        'A+': 22,
        'A': 21,
        'Rookie': 20
    }

    if level not in age_benchmarks:
        return 0

    age_difference = age_benchmarks[level] - age

    # Years younger than typical
    if age_difference >= 3:     # 3+ years young
        return +5
    elif age_difference >= 2:   # 2 years young
        return +3
    elif age_difference >= 1:   # 1 year young
        return +1
    else:
        return 0                # At or above typical age
```

**Rationale:**
A 20-year-old performing well at AA is far more valuable than a 24-year-old with similar stats. Age-relative performance is one of the strongest predictors of MLB success.

---

## Composite Score Calculation

### Final Formula

```python
def calculate_composite_score(prospect):
    '''
    Final composite score combining all factors
    Returns: Dictionary with breakdown
    '''

    base_score = get_base_score(prospect)  # FV: 40-70

    # Calculate individual modifiers
    performance_mod = calculate_performance_modifier(prospect)  # ±10
    trend_mod = calculate_trend_adjustment(prospect)            # ±5
    age_bonus = calculate_age_bonus(prospect)                   # 0 to +5

    # Weighted composite
    composite = (
        base_score +
        (performance_mod * 0.5) +
        (trend_mod * 0.3) +
        (age_bonus * 0.2)
    )

    # Apply adjustment cap (±10 points max)
    total_adjustment = composite - base_score

    if total_adjustment > 10:
        composite = base_score + 10
    elif total_adjustment < -10:
        composite = base_score - 10

    return {
        'composite_score': round(composite, 1),
        'base_fv': base_score,
        'performance_modifier': performance_mod,
        'trend_adjustment': trend_mod,
        'age_bonus': age_bonus,
        'total_adjustment': round(composite - base_score, 1)
    }
```

---

## Ranking Generation

### Process Flow

1. **Query all prospects with FanGraphs grades** (data_year = 2025)
2. **Calculate composite scores** for each prospect
3. **Sort by composite score** (descending)
4. **Assign sequential ranks** (#1, #2, #3...)
5. **Tie-breaking:** Use base FV, then age (younger wins)

```python
def generate_prospect_rankings(position_filter=None, organization_filter=None):
    '''
    Generate final ranked list with optional filters
    '''

    # Get prospects with FanGraphs grades
    prospects = get_prospects_with_fangraphs_grades(
        year=2025,
        position=position_filter,
        organization=organization_filter
    )

    # Calculate composite scores
    ranked_prospects = []
    for prospect in prospects:
        scores = calculate_composite_score(prospect)
        ranked_prospects.append({
            'prospect': prospect,
            'scores': scores
        })

    # Sort by composite score
    ranked_prospects.sort(
        key=lambda x: (
            x['scores']['composite_score'],  # Primary: composite
            x['scores']['base_fv'],          # Tiebreak 1: base FV
            -x['prospect'].age               # Tiebreak 2: age (younger)
        ),
        reverse=True
    )

    # Assign ranks
    for i, item in enumerate(ranked_prospects):
        item['rank'] = i + 1

    return ranked_prospects
```

---

## Database Query Strategy

### Primary Query

```sql
SELECT
    p.id,
    p.name,
    p.position,
    p.organization,
    p.age,
    p.current_level,
    p.fg_player_id,
    p.mlb_player_id,

    -- FanGraphs base scores
    COALESCE(h.fv, pit.fv) as fangraphs_fv,

    -- Hitter tool grades
    h.hit_future,
    h.game_power_future,
    h.speed_future,
    h.fielding_future,

    -- Pitcher tool grades
    pit.fb_future,
    pit.sl_future,
    pit.cb_future,
    pit.ch_future,
    pit.cmd_future,

    -- Recent MiLB stats (last 60 days)
    recent.ops as recent_ops,
    recent.era as recent_era,
    recent.games_played as recent_games,
    recent.level as recent_level,

    -- Previous period stats (30-60 days ago)
    previous.ops as previous_ops,
    previous.era as previous_era

FROM prospects p

-- Join FanGraphs hitter grades
LEFT JOIN fangraphs_hitter_grades h
    ON p.fg_player_id = h.fangraphs_player_id
    AND h.data_year = 2025

-- Join FanGraphs pitcher grades
LEFT JOIN fangraphs_pitcher_grades pit
    ON p.fg_player_id = pit.fangraphs_player_id
    AND pit.data_year = 2025

-- Recent performance (last 60 days)
LEFT JOIN LATERAL (
    SELECT
        AVG(CASE WHEN at_bats > 0 THEN ops END) as ops,
        AVG(CASE WHEN innings_pitched > 0 THEN era END) as era,
        COUNT(*) as games_played,
        MAX(level) as level
    FROM milb_game_logs
    WHERE CAST(mlb_player_id AS VARCHAR) = p.mlb_player_id
        AND game_date > CURRENT_DATE - INTERVAL '60 days'
) recent ON true

-- Previous period (30-60 days ago)
LEFT JOIN LATERAL (
    SELECT
        AVG(CASE WHEN at_bats > 0 THEN ops END) as ops,
        AVG(CASE WHEN innings_pitched > 0 THEN era END) as era
    FROM milb_game_logs
    WHERE CAST(mlb_player_id AS VARCHAR) = p.mlb_player_id
        AND game_date BETWEEN CURRENT_DATE - INTERVAL '90 days'
            AND CURRENT_DATE - INTERVAL '60 days'
) previous ON true

WHERE (h.fv IS NOT NULL OR pit.fv IS NOT NULL)
ORDER BY COALESCE(h.fv, pit.fv) DESC;
```

### Percentile Calculation Query

```sql
-- Calculate percentile for a stat at a specific level
WITH level_stats AS (
    SELECT
        AVG(ops) as stat_value,
        mlb_player_id
    FROM milb_game_logs
    WHERE season = 2024
        AND level = :level
        AND at_bats > 50
    GROUP BY mlb_player_id
)
SELECT
    percentile_cont(:prospect_stat_value)
    WITHIN GROUP (ORDER BY stat_value) as percentile
FROM level_stats;
```

---

## Edge Cases & Handling

### 1. No Recent MiLB Data (Injured/Offseason)

**Scenario:** Prospect has FanGraphs grade but no MiLB games in last 60 days

**Solution:**
- Use base FV only
- Set all modifiers to 0
- Display "No recent data" indicator in UI

```python
if not recent_stats or recent_stats.games_played < minimum_threshold:
    return {
        'composite_score': base_fv,
        'base_fv': base_fv,
        'performance_modifier': 0,
        'trend_adjustment': 0,
        'age_bonus': 0,
        'total_adjustment': 0,
        'note': 'No recent MiLB data'
    }
```

### 2. Insufficient Sample Size

**Scenario:** Recent data exists but sample too small (<50 PA or <20 IP)

**Solution:**
- Don't apply performance modifier
- Can still apply trend and age adjustments if prior period has data

```python
def insufficient_sample_size(stats, is_hitter):
    if is_hitter:
        return stats.plate_appearances < 50
    else:
        return stats.innings_pitched < 20
```

### 3. Level Change Mid-Period

**Scenario:** Prospect promoted from AA to AAA during 60-day window

**Solution:**
- Use most recent level only
- Weight stats by games at each level
- Note: "Recently promoted" in UI

```python
if recent_stats.level_changes > 0:
    # Use weighted average by games at each level
    # Or use most recent level only (simpler)
    recent_level = recent_stats.most_recent_level
```

### 4. Missing FanGraphs Grade

**Scenario:** Prospect in database but no FanGraphs grade (not ranked by FG)

**Solution:**
- Separate ranking tier: "Deep Sleepers"
- Rank by MiLB performance only
- Display differently in UI (gray badge)

---

## UI Display Guidelines

### Ranking Badge

```
┌─────────────────────────┐
│  #12  ★★★              │  <- Rank + Tier stars
│  FV: 55 (+3.2)         │  <- Base FV + adjustment
│  🔥 Trending Up        │  <- Trend indicator
└─────────────────────────┘
```

### Tier Classification

- **Tier 1 (★★★★★):** Rank 1-10 (Elite)
- **Tier 2 (★★★★):** Rank 11-25 (Top Prospects)
- **Tier 3 (★★★):** Rank 26-50 (Strong Prospects)
- **Tier 4 (★★):** Rank 51-100 (Solid Prospects)
- **Tier 5 (★):** Rank 101+ (Deep Prospects)

### Score Breakdown Tooltip

```
Composite Score: 58.2
├─ Base FV: 55.0 (FanGraphs)
├─ Performance: +2.0 (75th percentile at AA)
├─ Trend: +1.5 (Improving last 30d)
└─ Age Bonus: +1.2 (Young for level)
```

### Tool Grades Display

**Hitters:**
```
Hit: 60  Power: 55  Speed: 50  Field: 45
```

**Pitchers:**
```
FB: 70  SL: 60  CB: 55  CH: 50  CMD: 45
```

**Color Coding:**
- 70-80: Gold (#FFD700)
- 60-69: Blue (#4A90E2)
- 50-59: Green (#7ED321)
- 40-49: Gray (#9B9B9B)

---

## Implementation Checklist

### Phase 1: Core Algorithm (Days 1-2)
- [ ] Create `ranking_service.py`
- [ ] Implement `get_base_score()`
- [ ] Implement `calculate_performance_modifier()`
- [ ] Create `percentile_calculator.py`
- [ ] Unit tests for each function

### Phase 2: Modifiers (Day 3)
- [ ] Implement `calculate_trend_adjustment()`
- [ ] Implement `calculate_age_bonus()`
- [ ] Implement `calculate_composite_score()`
- [ ] Integration tests

### Phase 3: Ranking Generation (Day 4)
- [ ] Implement `generate_prospect_rankings()`
- [ ] Add filtering (position, org, tier)
- [ ] Add sorting options
- [ ] Performance optimization

### Phase 4: API & Caching (Day 5)
- [ ] Create `/v1/prospects/rankings` endpoint
- [ ] Implement response serialization
- [ ] Add Redis caching (1 hour TTL)
- [ ] API documentation

---

## Performance Considerations

### Caching Strategy

1. **Full Rankings Cache**
   - Key: `rankings:full:{date}`
   - TTL: 1 hour
   - Refresh: On-demand or scheduled

2. **Filtered Rankings Cache**
   - Key: `rankings:{position}:{org}:{date}`
   - TTL: 30 minutes
   - Max cache size: 100 variations

3. **Percentile Cache**
   - Key: `percentiles:{level}:{season}`
   - TTL: 24 hours (static historical data)

### Query Optimization

- Use LATERAL joins for subqueries
- Index on `prospects.fg_player_id`
- Index on `milb_game_logs(mlb_player_id, game_date)`
- Materialize percentile tables for each level

---

## Testing Strategy

### Unit Tests

1. **Base Score:** Verify FV retrieval for hitters/pitchers
2. **Performance Modifier:** Test percentile conversions
3. **Trend Adjustment:** Test improvement calculations
4. **Age Bonus:** Test age-to-level mappings
5. **Composite:** Test weighting and capping

### Integration Tests

1. **Full Ranking:** Generate rankings for test dataset
2. **Edge Cases:** Missing data, insufficient samples
3. **Filters:** Position, org filtering works correctly
4. **Sorting:** Multiple sort keys work

### Performance Tests

1. **Load Test:** Rank 1,000+ prospects in <5 seconds
2. **Concurrent:** Handle 10+ simultaneous requests
3. **Cache Hit Rate:** >90% for repeated queries

---

## Success Metrics

### Algorithm Quality

✅ **Top 20 Alignment:** 80%+ overlap with FanGraphs Top 100
✅ **Adjustment Reasonability:** 90%+ of adjustments within ±5 points
✅ **Coverage:** 100% of prospects with FG grades ranked
✅ **Stability:** Rankings don't swing wildly day-to-day (<5 spot changes)

### User Engagement

✅ **Sort Usage:** Users sort by different columns
✅ **Breakdown Views:** Users hover/click to see score breakdown
✅ **Filter Usage:** Users filter by position/org
✅ **Detail Views:** Users click through to prospect details

---

## Future Enhancements (v2.0)

1. **Multi-Year FV Trends**
   - Show FV progression (2022 → 2025)
   - Identify rising/falling stocks

2. **Advanced Metrics**
   - Batted ball data (exit velo, launch angle)
   - Pitch arsenal metrics (spin, movement)
   - Plate discipline (BB%, K%, Chase%)

3. **Predictive Models**
   - MLB ETA predictions
   - Peak WAR projections
   - Bust risk assessment

4. **User Customization**
   - Adjust weighting (FV vs performance)
   - Choose lookback period (30/60/90 days)
   - Custom tier breakpoints

---

## Appendix: Algorithm Examples

### Example 1: Elite Prospect (Konnor Griffin)

**Input:**
- FV: 65
- Position: SS
- Age: 20
- Level: AA
- Recent OPS (60d): 0.920 (90th percentile)
- Previous OPS (30-60d): 0.850
- Improvement: +8.2%

**Calculation:**
```
Base: 65
Performance: +10 (90th percentile)
Trend: +2 (8.2% improvement)
Age: +3 (2 years young for AA)

Weighted: 65 + (10×0.5) + (2×0.3) + (3×0.2) = 65 + 5 + 0.6 + 0.6 = 71.2
Capped: 71.2 (within ±10 cap)
```

**Result:** Rank #3, Composite 71.2

---

### Example 2: Slumping Prospect

**Input:**
- FV: 55
- Position: SP
- Age: 24
- Level: AAA
- Recent ERA (60d): 5.20 (30th percentile)
- Previous ERA (30-60d): 3.80
- Decline: -36.8%

**Calculation:**
```
Base: 55
Performance: -5 (30th percentile)
Trend: -5 (36.8% decline)
Age: 0 (typical age for AAA)

Weighted: 55 + (-5×0.5) + (-5×0.3) + (0×0.2) = 55 - 2.5 - 1.5 + 0 = 51.0
Capped: 51.0 (within ±10 cap)
```

**Result:** Rank ~75, Composite 51.0

---

### Example 3: No Recent Data

**Input:**
- FV: 60
- Position: CF
- Age: 22
- Level: A+
- Recent games: 0 (injured)

**Calculation:**
```
Base: 60
Performance: 0 (no data)
Trend: 0 (no data)
Age: 0 (can't verify without games)

Composite: 60 + 0 + 0 + 0 = 60.0
```

**Result:** Rank ~40, Composite 60.0, Note: "No recent data"

---

**End of Algorithm Design Document**
