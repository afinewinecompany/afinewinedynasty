# Pitch-Based Ranking System Implementation Summary

**Date:** 2025-10-21
**Team:** BMad Party Mode (Orchestrator, Analyst, Architect, Developer, QA, PM, PO, UX Expert)
**Status:** ✅ **DESIGN & CORE IMPLEMENTATION COMPLETE**

---

## 🎯 Mission Accomplished

Successfully designed and implemented an enhanced composite ranking system that leverages **granular pitch-level MiLB data** to calculate performance modifiers based on **weighted percentile rankings** within level cohorts.

---

## 📦 Deliverables

### 1. Design Documentation
**File:** [`PITCH_BASED_RANKING_DESIGN.md`](./PITCH_BASED_RANKING_DESIGN.md)

**Contents:**
- Complete system architecture
- Weighted metric definitions (hitters & pitchers)
- Percentile calculation methodology
- Graceful degradation strategy
- API response schema
- Testing & rollout plan

### 2. Database Migration
**File:** [`alembic/versions/018_add_pitch_percentile_views.py`](./alembic/versions/018_add_pitch_percentile_views.py)

**Creates:**
- `mv_hitter_percentiles_by_level` - Materialized view for hitter percentiles by level
- `mv_pitcher_percentiles_by_level` - Materialized view for pitcher percentiles by level
- Required indexes for performance optimization

**Refresh Strategy:**
- Daily at 3 AM (configurable via cron)
- Concurrent refresh to avoid blocking reads

### 3. Core Service Implementation
**File:** [`app/services/pitch_data_aggregator.py`](./app/services/pitch_data_aggregator.py)

**Class:** `PitchDataAggregator`

**Key Methods:**
- `get_hitter_pitch_metrics()` - Aggregates batter pitch data (exit velo, contact rate, whiff rate, etc.)
- `get_pitcher_pitch_metrics()` - Aggregates pitcher data (whiff rate, zone rate, velocity, etc.)
- `calculate_weighted_composite()` - Combines metrics into weighted percentile score
- `percentile_to_modifier()` - Converts percentile (0-100) to ranking modifier (-10 to +10)

**Weighted Metrics:**

#### Hitters
| Metric | Weight | Description |
|--------|--------|-------------|
| Exit Velocity (90th %) | 25% | Barrel rate proxy |
| Hard Hit Rate | 20% | % of balls hit 95+ mph |
| Contact Rate | 15% | Contact / swings |
| Whiff Rate | 15% | Swing-and-miss (inverted) |
| Chase Rate | 10% | Swings outside zone (inverted) |
| OPS | 15% | Traditional fallback |

#### Pitchers
| Metric | Weight | Description |
|--------|--------|-------------|
| Whiff Rate | 25% | Stuff indicator |
| Zone Rate | 20% | Command metric |
| Avg FB Velocity | 15% | Fastball velo |
| Hard Contact Rate | 15% | Hard contact allowed (inverted) |
| Chase Rate | 10% | Inducing chases |
| K% - BB% | 15% | Traditional fallback |

### 4. Enhanced Ranking Service
**File:** [`app/services/prospect_ranking_service.py`](./app/services/prospect_ranking_service.py)

**Updates:**
- Imported `PitchDataAggregator`
- Updated `calculate_performance_modifier()` to:
  - **Try pitch-level data first** (preferred)
  - **Fall back to game logs** (OPS/ERA) if no pitch data
  - **Return detailed breakdown** of metrics used
- Updated `calculate_composite_score()` to include performance breakdown in response

**Return Structure:**
```python
{
    'composite_score': 69.5,
    'base_fv': 65.0,
    'performance_modifier': 4.5,
    'performance_breakdown': {
        'source': 'pitch_data',  # or 'game_logs', 'insufficient_data'
        'composite_percentile': 92.3,
        'metrics': {
            'exit_velo_90th': 105.2,
            'hard_hit_rate': 48.5,
            ...
        },
        'percentiles': {
            'exit_velo_90th': 95,
            'hard_hit_rate': 92,
            ...
        },
        'weighted_contributions': {
            'exit_velo_90th': 23.75,
            'hard_hit_rate': 18.4,
            ...
        },
        'sample_size': 234,
        'days_covered': 60,
        'level': 'AA'
    },
    'trend_adjustment': 2.0,
    'age_adjustment': 3.0,
    'total_adjustment': 9.5
}
```

---

## 🏗️ System Architecture

### Data Flow

```
1. Request for Prospect Rankings
   ↓
2. ProspectRankingService.generate_prospect_rankings()
   ↓
3. For each prospect:
   ├─ Get FanGraphs FV (base score)
   ├─ Calculate performance modifier
   │  ├─ Try PitchDataAggregator (preferred)
   │  │  ├─ Query milb_batter/pitcher_pitches (last 60 days)
   │  │  ├─ Calculate raw metrics (exit velo, whiff rate, etc.)
   │  │  ├─ Query mv_*_percentiles_by_level (cohort comparison)
   │  │  ├─ Convert to percentiles
   │  │  └─ Return weighted composite + breakdown
   │  └─ Fall back to game log OPS/ERA if no pitch data
   ├─ Calculate trend adjustment
   ├─ Calculate age adjustment
   └─ Compute final composite score
   ↓
4. Sort by composite score
   ↓
5. Return ranked list with detailed breakdowns
```

### Graceful Degradation

```
Priority 1: Pitch-level metrics (preferred)
   ↓ (if unavailable)
Priority 2: Game log aggregates (fallback)
   ↓ (if unavailable)
Priority 3: FanGraphs FV only (base score)
```

---

## 📊 Data Coverage

Based on audit ([`PROSPECT_DATA_AUDIT_SUMMARY.md`](./scripts/PROSPECT_DATA_AUDIT_SUMMARY.md)):

- **621 batters** with pitch-level data (47.1% of prospects)
- **363 pitchers** with pitch-level data (27.5% of prospects)
- **1.5M+ pitch tracking points** (2023-2025)
- **16,196 total MiLB players** for cohort percentiles
- **~31% of pitches** have velocity/spin data (gracefully handled)

---

## 🔬 Technical Highlights

### Performance Optimization
1. **Materialized views** - Pre-aggregated percentiles refresh daily
2. **Indexed queries** - Fast lookups by player_id, level, season
3. **Cached results** - Redis cache (30 min TTL) for rankings endpoint
4. **Async execution** - Non-blocking database queries

### Error Handling
- Missing pitch data → Falls back to game logs
- Missing game logs → Uses FV only
- Missing percentile data → Defaults to median (50th percentile)
- Sample size validation → Minimum 50 pitches (batters) / 100 pitches (pitchers)

### Logging & Observability
- Logs data source used (pitch_data vs game_logs)
- Logs percentile calculations
- Logs fallback scenarios
- Tracks performance metrics

---

## ✅ Next Steps (Implementation Phase 2)

### 1. Database Setup
```bash
# Run migration
alembic upgrade head

# Initial materialized view refresh
psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;"
psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;"

# Verify views created
psql "postgresql://..." -c "\d+ mv_hitter_percentiles_by_level"
```

### 2. Schedule Daily Refresh
**Cron job (3 AM daily):**
```bash
0 3 * * * psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hitter_percentiles_by_level;"
0 3 * * * psql "postgresql://..." -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pitcher_percentiles_by_level;"
```

### 3. Testing
- [ ] Unit tests for `PitchDataAggregator`
- [ ] Integration tests for percentile calculations
- [ ] Performance tests (< 5s for rankings query)
- [ ] Validation tests (compare old vs new rankings)

### 4. API Response Updates
- [ ] Update API endpoint schemas to include `performance_breakdown`
- [ ] Frontend changes to display new metrics
- [ ] User documentation

### 5. Monitoring
- [ ] Track % of prospects using pitch data vs fallback
- [ ] Monitor query performance
- [ ] Gather user feedback on ranking accuracy

---

## 🎓 Key Learnings

### What Worked Well
✅ **Multi-agent collaboration** - Each specialist contributed unique expertise
✅ **Iterative design** - Design doc before implementation prevented rework
✅ **Data-driven decisions** - Leveraged comprehensive data audit
✅ **Graceful degradation** - System works with partial data

### Design Decisions
1. **Weighted metrics over single stat** - More robust, less volatile
2. **Level-based cohorts** - AA is different from Rookie ball
3. **Percentile-based** - More meaningful than absolute values
4. **Materialized views** - Pre-compute for performance
5. **Fallback chain** - Always return *something* meaningful

---

## 📚 Related Documentation

- [Design Document](./PITCH_BASED_RANKING_DESIGN.md) - Full technical specification
- [Data Audit](./scripts/PROSPECT_DATA_AUDIT_SUMMARY.md) - Data availability analysis
- [Current System](./app/services/prospect_ranking_service.py) - Original implementation
- [Performance Notes](./PERFORMANCE_NOTES.md) - Known issues & optimizations
- [Pitch Data Schema](./scripts/create_batter_pitcher_pitch_tables.sql) - Database schema

---

## 🤝 Contributors

**BMad Party Mode Team:**
- 🎭 **Orchestrator** - Coordination & workflow management
- 📊 **Analyst** - Requirements analysis & data investigation
- 🏗️ **Architect** - System design & technical architecture
- 👨‍💻 **Developer** - Code implementation & integration
- 🧪 **QA** - Quality assurance & edge case validation
- 👨‍💼 **PM** - Project planning & task management
- 👨‍💼 **PO** - Business value & user requirements
- 🎨 **UX Expert** - User experience considerations

---

## 🎉 Impact

### Before
- Simple OPS/ERA thresholds
- Estimated percentiles (inaccurate)
- No granular data usage
- Limited differentiation

### After
- **6 weighted metrics** for hitters, pitchers
- **True cohort percentiles** (level-based)
- **1.5M+ pitch data points** leveraged
- **Detailed breakdowns** for transparency
- **Graceful fallbacks** for missing data
- **Performance optimized** (materialized views)

---

**Status:** ✅ Core implementation complete
**Ready for:** Database migration → Testing → Deployment

---

*Generated by BMad Party Mode Team - 2025-10-21*
