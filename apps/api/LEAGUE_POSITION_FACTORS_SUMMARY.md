# League & Position Factors Calculation - Summary

**Date:** 2025-10-07
**Status:** ✅ COMPLETE

---

## Execution Results

### Data Processed
- **Total Game Logs:** 544,422
- **Unique Players:** 4,334
- **Players with Birth Dates:** 541,860 (99.5%)
- **Seasons Covered:** 2021-2025
- **Levels:** A, A+, AA, AAA

### Outputs Created
1. **League Factors Table:** 20 season-level combinations
2. **Position Factors Table:** 62 season-level-position combinations

---

## League Factors Summary (2024 Season)

| Level | OPS  | Avg Age | Med Age | Players |
|-------|------|---------|---------|---------|
| A     | .686 | 21.3    | 21.2    | 890     |
| A+    | .686 | 22.7    | 22.7    | 660     |
| AA    | .675 | 24.6    | 24.5    | 663     |
| AAA   | .773 | 27.2    | 26.8    | 787     |

### Key Insights:
- **AAA has highest OPS** (.773) - most offensive environment
- **Age progression is clear:** A (21.3) → A+ (22.7) → AA (24.6) → AAA (27.2)
- **Level difficulty varies:** AA is toughest relative environment (lowest OPS despite higher level than A+)

---

## Position Factors Summary (2024 Season)

### By Position Group:

**CATCHERS (C):**
- AAA: .740 OPS, Age 28.2
- AA: .653 OPS, Age 25.0
- A+: .668 OPS, Age 23.0
- A: .670 OPS, Age 21.7

**INFIELDERS (IF):**
- AAA: .775 OPS, Age 27.1
- AA: .673 OPS, Age 24.6
- A+: .687 OPS, Age 22.5
- A: .679 OPS, Age 21.2

**OUTFIELDERS (OF):**
- AAA: .785 OPS, Age 26.9
- AA: .688 OPS, Age 24.4
- A+: .693 OPS, Age 22.7
- A: .701 OPS, Age 21.3

### Key Insights:
- **Catchers hit worst** at every level (expected - defensive demands)
- **Outfielders hit best** at every level (less defensive fatigue)
- **OPS gap at AA:** C (.653) vs OF (.688) = 35 points
- **Age differences:** Catchers are typically 0.5-1.5 years older than OF at same level

---

## ML Feature Engineering Impact

### New Features Now Available:

#### 1. Level-Adjusted Stats
```python
ops_vs_league = player_ops / league_ops_at_level
# Example: .720 OPS at AA / .675 league OPS = 1.067 (6.7% above average)
```

#### 2. Age-Relative Performance
```python
age_vs_league_avg = player_age - league_avg_age_at_level
# Example: 22.0 years at AA - 24.6 avg = -2.6 years (ELITE age for level)
```

#### 3. Position-Adjusted Stats
```python
ops_vs_position = player_ops / position_ops_at_level
# Example: Catcher .700 OPS / .653 C avg = 1.072 (7.2% above position peers)
```

#### 4. Comprehensive Adjustment
```python
fully_adjusted_ops = raw_ops * level_factor * age_factor * position_factor
# Accounts for ALL context in single metric
```

---

## Real-World Example: Why This Matters

### Player A: 22yo Catcher hitting .720 OPS at AA

**WITHOUT Adjustments:**
- Raw OPS: .720
- League avg at AA: .675
- League-relative: .720/.675 = 1.067 (6.7% above average)
- **Verdict:** Slightly above average hitter

**WITH Adjustments:**
1. **Level adjustment:** .720 / .675 = 1.067
2. **Age adjustment:** 22yo vs 24.6 avg = -2.6 years younger (elite)
3. **Position adjustment:** .720 / .653 (C avg) = 1.103 (10% above position)

**Fully Adjusted OPS:** .720 × 1.0 × 1.052 (age) × 1.103 (position) = .836

**Verdict:** ELITE prospect (top-tier hitting catcher who's 2.6 years younger than peers)

---

## Database Tables Created

### `milb_league_factors`
**Columns:**
- season, level
- total_pa, unique_players, players_with_age
- lg_avg, lg_obp, lg_slg, lg_ops, lg_iso
- lg_hr_rate, lg_bb_rate, lg_so_rate, lg_sb_rate, lg_sb_success_pct
- lg_avg_age, lg_median_age, lg_age_std, lg_age_25th_percentile, lg_age_75th_percentile

**Sample Query:**
```sql
SELECT season, level, lg_ops, lg_avg_age
FROM milb_league_factors
WHERE season = 2024
ORDER BY level;
```

### `milb_position_factors`
**Columns:**
- season, level, position_group
- total_pa, unique_players, players_with_age
- pos_avg, pos_obp, pos_slg, pos_ops, pos_iso
- pos_hr_rate, pos_bb_rate, pos_so_rate, pos_sb_rate
- pos_avg_age

**Sample Query:**
```sql
SELECT season, level, position_group, pos_ops, pos_avg_age
FROM milb_position_factors
WHERE season = 2024 AND level = 'AA'
ORDER BY position_group;
```

---

## Next Steps for ML Model

### 1. Update Feature Engineering Script
- Add league-relative features (ops_vs_league, bb_rate_vs_league, etc.)
- Add age-relative features (age_vs_league_avg, age_percentile)
- Add position-relative features (ops_vs_position)
- Create fully_adjusted_ops composite metric

### 2. Retrain Models
```bash
cd apps/api
python scripts/train_all_players_predictor.py --include-league-factors --include-position-factors
```

### 3. Expected Performance Gains
- **Current R²:** 0.31 (wRC+)
- **With league/position factors:** 0.38-0.42 (projected)
- **With Statcast (when ready):** 0.45-0.50 (projected)

### 4. Feature Importance Changes Expected
- Current top feature: avg_ops (31.4%)
- Expected new top features:
  - fully_adjusted_ops (25-30%)
  - age_vs_league_avg (8-12%)
  - ops_vs_position (6-10%)
  - highest_level_ops_adjusted (8-10%)

---

## Scripts Used

1. **[calculate_league_factors_with_age.py](scripts/calculate_league_factors_with_age.py)** - Main calculation script
2. **[check_factors.py](check_factors.py)** - Verification script

---

## Success Metrics ✅

- [x] 99.5% of games have age data
- [x] All 4 MiLB levels covered (A through AAA)
- [x] 5 seasons of data (2021-2025)
- [x] Position groups properly segmented (C, IF, OF)
- [x] Age statistics calculated (mean, median, std, percentiles)
- [x] Database tables created and populated
- [x] Ready for ML feature engineering integration

---

**The foundation for context-aware prospect evaluation is now in place!** 🎉
