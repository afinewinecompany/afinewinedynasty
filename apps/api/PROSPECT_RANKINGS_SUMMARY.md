# Prospect Rankings Summary

## Overview

Created advanced prospect ranking system using machine learning to impute MLB performance based on actual MiLB→MLB transitions.

---

## Ranking Versions

### **V4 Rankings** - Simple Translation Model
**File**: [prospect_rankings_hitters.csv](prospect_rankings_hitters.csv)

**Methodology**:
- Uses fixed level translation factors (AAA=0.90, AA=0.80, A+=0.70, etc.)
- Applies Statcast boosts (exit velo, hard hit%, barrel%)
- Age curves favor youth (exponential decay after age 21.5)
- All players get imputed Statcast (ML-predicted for fairness)

**Prospects**: 1,832 hitters

**Top 3**:
1. Leo De Vries (19yo SS) - .785 OPS at AA
2. Colt Emerson (20yo SS) - .822 OPS at AAA
3. Nelson Rada (20yo CF) - .698 OPS at AAA

---

### **V5 Rankings** - ML-Projected MLB Performance
**File**: [prospect_rankings_v5_hitters_mlb_projected.csv](prospect_rankings_v5_hitters_mlb_projected.csv)

**Methodology**:
- **Uses actual MiLB→MLB transitions** to predict future MLB stats
- Trained on 3,459 transition records from 614 players
- Age-aware model: "If Player A did X at age 20 in AA and produced Y in MLB, what will Player B do?"
- Random Forest + Gradient Boosting ensemble
- Best predictions: ISO (R²=0.346), K-rate (R²=0.538)

**Prospects**: 1,934 hitters

**Top 3**:
1. Andrew Salas (18yo SS) - .557 OPS at A → Projected 88 wRC+ in MLB
2. Juneiker Caceres (18yo OF) - .637 OPS at A → Projected 87 wRC+ in MLB
3. Jorge Quintana (19yo SS) - .572 OPS at A → Projected 88 wRC+ in MLB

---

## V4 vs V5 Comparison

### Major Differences

| Metric | V4 | V5 |
|--------|----|----|
| **Total Prospects** | 1,832 | 1,934 |
| **Avg. Age (Top 50)** | 20.4 years | **18.2 years** |
| **Top 50 Turnover** | - | **78% (39 new, 39 dropped)** |
| **Avg. Rank Change** | - | **341 spots** |

### Biggest Movers in V5

**Improved** (using ML projection):
- Solomon Maguire: #1434 → #515 (+919 spots)
- Javier Mora: #1428 → #510 (+918 spots)
- Willmer De La Cruz: #1413 → #497 (+916 spots)

**Dropped**:
- Established AAA players with good stats but older age
- V5 heavily penalizes age >21

### Philosophy Difference

**V4**: "Who's performing best right now?"
- Values high-level performance (AAA/AA)
- Current stats matter most
- Conservative on youth

**V5**: "Who will be best in MLB based on similar players' trajectories?"
- Values development curve
- Extremely aggressive on youth (18-19 year olds dominate)
- Learns from actual MLB outcomes

---

## Training Data Analysis

### MiLB→MLB Transitions

**Dataset**: 3,459 season-to-season transitions

**Age Distribution at MiLB Level**:
- Age 18-20: 138 transitions (4%)
- Age 21-23: 1,151 transitions (33%)
- Age 24-26: 1,609 transitions (47%)
- Age 27+: 561 transitions (16%)

**Level Distribution**:
- AAA: 2,155 transitions (62%)
- AA: 856 transitions (25%)
- A+: 322 transitions (9%)
- A: 121 transitions (4%)

**Sample Transitions** (AA age 21 → MLB):
| Player | MiLB OPS | MLB Age | MLB OPS | Gap |
|--------|----------|---------|---------|-----|
| Triston Casas | .887 | 22 | .766 | 1 yr |
| Gabriel Moreno | 1.063 | 22 | .733 | 1 yr |
| Oswald Peraza | .803 | 22 | .797 | 1 yr |
| Brayan Rocchio | .835 | 22 | .600 | 2 yrs |

---

## Model Performance

### Predictive Accuracy

| Target Stat | R² Score | MAE | Top Predictor |
|-------------|----------|-----|---------------|
| **ISO** | 0.346 | 0.036 | MiLB ISO (0.449) |
| **K-Rate** | 0.538 | 0.033 | MiLB K-Rate (0.645) |
| **BB-Rate** | 0.254 | 0.017 | MiLB BB-Rate (0.554) |
| SLG | 0.154 | 0.054 | MiLB ISO (0.289) |
| OPS | 0.067 | 0.073 | MiLB OPS (0.195) |
| wRC+ | 0.018 | 1.641 | MiLB BB-Rate (0.165) |

**Key Insights**:
- **Strikeout rate** is most predictable (R²=0.538)
- **Power (ISO)** translates better than average
- **Walk rate** is moderately predictable
- **Overall performance (wRC+)** is hard to predict (R²=0.018) - lots of variance!

---

## Statcast Integration

### Imputation Model

**Problem**: Only 386 of 4,409 hitters (8.8%) have actual Statcast data

**Solution**: Train Random Forest to predict Statcast from traditional stats

**Results**:
| Metric | R² | MAE | Top Predictor |
|--------|-----|-----|---------------|
| Exit Velocity | 0.015 | 3.01 mph | ISO |
| Hard Hit % | 0.133 | 9.04% | ISO |
| Barrel % | 0.099 | 3.58% | HR Rate |

**Imputed Stats**: All 3,575 hitters now have Statcast metrics (actual or predicted)

**Statcast Boosts**:
- Exit Velo ≥90: 1.10x multiplier
- Exit Velo ≥87: 1.05x multiplier
- Hard Hit% ≥40: 1.08x multiplier
- Barrel% ≥10: 1.10x multiplier

---

## Age Curves

### Hitter Age Curve
- **Optimal age**: 21.5 years
- **Hard cutoff**: 26.5 years (age factor = 0)
- **Formula**: `exp((21.5 - age) / 2.5)`

**Age Factors**:
| Age | Factor | Tier |
|-----|--------|------|
| 19 | 3.26x | Elite Youth |
| 20 | 2.39x | Elite Youth |
| 21 | 1.75x | Elite Youth |
| 22 | 1.28x | Premium Prospect |
| 23 | 0.94x | Standard Prospect |
| 24 | 0.69x | Standard Prospect |
| 25 | 0.50x | Standard Prospect |
| 26 | 0.37x | Marginal |
| 27+ | 0.00x | Ineligible |

---

## FanGraphs Integration Status

**Table**: `fangraphs_prospect_grades` ✅ Created

**Status**: 🔴 Empty (0 rows)

**Issue**: FanGraphs API endpoints changed (all return 404)

**Attempted Endpoints**:
- `/api/prospects/board/prospects-list-combined` ❌
- `/api/prospects/board/prospects` ❌
- `/api/prospects/list` ❌
- `/api/leaders/minor-league/prospects` ❌

**Next Steps**:
- Manual scraping from https://www.fangraphs.com/prospects/the-board
- Web scraping with browser automation
- Or use rankings without FanGraphs blending

---

## Recommendations

### Which Rankings To Use?

**Use V4 if you want**:
- Conservative, stats-based rankings
- To value proven high-level performance
- Traditional prospect list feel

**Use V5 if you want**:
- Aggressive, upside-based rankings
- To bet on youth and development
- MLB projection-focused approach

**Create Blended Version** (Recommended):
```
Blended Score = (0.6 × V5 Projection) + (0.4 × V4 Performance)
```

This balances:
- ML-projected upside (V5)
- Current demonstrated ability (V4)
- Reduces extreme youth bias

---

## Files Generated

### Core Rankings
- `prospect_rankings_hitters.csv` - V4 rankings (1,832 hitters)
- `prospect_rankings_pitchers.csv` - V4 rankings (823 pitchers)
- `prospect_rankings_v3_unified.csv` - V4 combined (2,655 total)
- `prospect_rankings_v5_hitters_mlb_projected.csv` - V5 rankings (1,934 hitters)

### Training Data
- `milb_to_mlb_transitions.csv` - 3,459 transition records
- `age_aware_mlb_predictor.pkl` - ML models (Random Forest + Gradient Boosting)
- `statcast_imputation_models.pkl` - Statcast prediction models

### Analysis
- `compare_v4_vs_v5.py` - Comparison script
- `PROSPECT_RANKINGS_SUMMARY.md` - This document

---

## Technical Details

### Database Tables
- `milb_game_logs` - MiLB performance data
- `mlb_game_logs` - MLB performance data
- `prospects` - Player metadata
- `milb_statcast_metrics_imputed` - Imputed Statcast for all hitters
- `fangraphs_prospect_grades` - Empty (API unavailable)

### Model Architecture
- **Ensemble**: Random Forest (200 trees) + Gradient Boosting (150 trees)
- **Features**: MiLB stats, age, level quality, interactions
- **Targets**: 7 MLB stats (OPS, OBP, SLG, ISO, wRC+, BB%, K%)
- **Training**: 901 quality transitions (200+ MiLB PA, 150+ MLB PA)

### Age-Aware Features
- `age_squared` - Captures non-linear age effects
- `is_young` - Binary flag for age ≤22
- `is_elite_age` - Binary flag for age ≤21
- `ops_x_level` - Performance × level quality interaction
- `iso_x_level` - Power × level quality interaction
- `bb_rate_x_level` - Discipline × level quality interaction

---

## Future Enhancements

1. **Collect FanGraphs data** - Manual scraping or browser automation
2. **Pitcher v5 rankings** - Apply ML projection to pitchers
3. **Positional adjustments** - SS/C/CF worth more than 1B/DH
4. **Injury flags** - Identify players who missed significant time
5. **Recency weighting** - 2025 stats > 2024 > 2023
6. **League quality tiers** - Strong vs weak AA/AAA leagues
7. **Performance trajectory** - Improving vs declining players
8. **Defense metrics** - Incorporate fielding ability
9. **Speed/athleticism** - SB%, sprint speed
10. **Ensemble blending** - Combine V4 + V5 with optimal weights

---

Generated: October 8, 2025
