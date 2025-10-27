# MLB Stat Projection System - Final Report

**Date:** October 20, 2025
**Status:** ✅ MVP Complete | ⚠️ Performance Needs Improvement

---

## Executive Summary

Successfully built an end-to-end ML pipeline for projecting MLB stats from MiLB performance data:

- ✅ **Populated prospects table** with 1,010 MLB players (2021-2025)
- ✅ **Collected MLB pitcher data** - 462 appearances from 62 pitchers
- ✅ **Built training datasets** - 399 hitter samples ready
- ✅ **Trained hitter model** - XGBoost multi-output regressor
- ⚠️ **Model performance** - Poor generalization (overfitting)
- ❌ **Pitcher model** - Insufficient data (only 1 pitcher with 20+ games)

**Key Finding:** Sample size (399) is too small for reliable multi-output regression with 35 features → 13 targets. Model overfits dramatically.

---

## Data Collection Results

### 1. Prospects Table Population

| Metric | Before | After | Change |
|--------|--------|-------|---------|
| Total Prospects | 1,349 | 2,359 | +1,010 (+75%) |
| With MLB Player IDs | 1,326 | 2,336 | +76% |
| Missing MLB Players (2021-2025) | 1,010 | 0 | ✅ Complete |

**Success Rate:** 100% (0 failures during API collection)

### 2. MLB Pitcher Data Collection

**Collection Summary:**
- Pitchers queried: 428
- Pitchers with MLB data: 62 (14.5%)
- Total pitcher appearances collected: 462
- Pitchers with 20+ appearances: **1** (insufficient for training)

**Breakdown by Season:**
| Season | Games | Pitchers |
|--------|-------|----------|
| 2022 | 4 | 2 |
| 2023 | 11 | 4 |
| 2024 | 87 | 22 |
| 2025 | 360 | 52 |

**Why so few?** Most prospects in our database are still in MiLB or just debuted. The 20+ games threshold filters down to only 1 pitcher.

### 3. Training Data Extraction

**Hitters:**
- MiLB→MLB transitions found: 1,040
- Training samples extracted: **399** (38% extraction rate)
- Features: 35 (MiLB stats + derived metrics + Fangraphs grades)
- Targets: 13 MLB career stats

**Extraction Rate Analysis:**
- 38% is reasonable given:
  - Not all prospects have pre-debut MiLB data
  - Some debuted without significant MiLB time (international FAs)
  - Missing Fangraphs grades for non-top prospects

**Pitchers:**
- With both MiLB and 20+ MLB games: **1**
- Insufficient for training

---

## Model Training Results

### Hitter Projection Model

**Architecture:**
- Algorithm: XGBoost Multi-Output Regressor
- Base Estimators: 200 trees per target
- Max Depth: 6
- Learning Rate: 0.05
- Features: 35
- Targets: 13

**Dataset Split:**
- Training: 319 samples (80%)
- Validation: 80 samples (20%)

### Performance Metrics

| Target Stat | Train R² | Val R² | Val MAE | Assessment |
|-------------|----------|---------|---------|------------|
| target_avg | 0.993 | **-0.172** | 0.0289 | Poor |
| target_obp | 0.993 | **-0.295** | 0.0327 | Poor |
| target_slg | 0.992 | **-0.210** | 0.0885 | Poor |
| target_ops | 0.991 | **-0.217** | 0.1332 | Poor |
| target_bb_rate | 0.997 | **0.050** | 0.0205 | Weak |
| target_k_rate | 0.997 | **0.305** | 0.0417 | Moderate |
| target_hr_per_600 | 0.996 | **0.219** | 5.2605 | Weak |
| target_sb_per_600 | 0.996 | **0.050** | 8.7222 | Weak |
| target_rbi_per_600 | 0.996 | **0.020** | 13.8508 | Poor |
| target_r_per_600 | 0.990 | **-0.063** | 10.4062 | Poor |
| target_career_games | 0.996 | **0.324** | 7.0547 | Moderate |
| target_career_pa | 0.994 | **-0.024** | 502.2343 | Poor |
| target_iso | 0.990 | **-0.154** | 0.0708 | Poor |
| **AVERAGE** | **0.994** | **-0.013** | - | **POOR** |

### Key Observations

1. **Severe Overfitting:**
   - Train R²: 0.994 (near perfect)
   - Val R²: -0.013 (worse than mean baseline)
   - Gap: **1.007** (massive overfit)

2. **Best Performing Targets:**
   - target_career_games (R² = 0.324)
   - target_k_rate (R² = 0.305)
   - target_hr_per_600 (R² = 0.219)

3. **Worst Performing Targets:**
   - target_obp (R² = -0.295)
   - target_slg (R² = -0.210)
   - target_ops (R² = -0.217)

4. **Why Negative R²?**
   - R² can go negative when predictions are worse than simply predicting the mean
   - Indicates the model learned spurious patterns from training data that don't generalize

---

## Root Cause Analysis

### Why Is Performance Poor?

1. **Insufficient Sample Size**
   - 399 samples is very small for multi-output regression
   - Rule of thumb: Need 10-20 samples per feature
   - We have: 399 samples ÷ 35 features = **11.4 samples/feature** (borderline)
   - With 13 outputs, effective requirement is higher

2. **High Model Capacity vs. Data**
   - XGBoost with 200 trees × 13 outputs = 2,600 decision trees
   - Too much capacity for 399 samples → memorizes noise

3. **Inherent Task Difficulty**
   - Projecting MLB success from MiLB is fundamentally hard
   - Many confounding factors (injuries, opportunity, development, luck)
   - Even professional scouts struggle with this

4. **Missing Signal in Features**
   - May need more sophisticated features (pitch quality, batted ball data, etc.)
   - Fangraphs grades only available for top prospects

---

## Recommendations

### Short-Term Fixes (Estimated 2-4 hours)

1. **Reduce Model Complexity**
   ```python
   base_estimator = xgb.XGBRegressor(
       n_estimators=50,        # Down from 200
       max_depth=3,            # Down from 6
       learning_rate=0.1,      # Up from 0.05
       min_child_weight=5,     # Add regularization
       subsample=0.7,
       colsample_bytree=0.7,
       reg_alpha=0.1,          # L1 regularization
       reg_lambda=1.0,         # L2 regularization
   )
   ```

2. **Single-Output Models**
   - Train 13 separate models (one per target) instead of multi-output
   - Allows each model to find its own optimal hyperparameters

3. **Feature Selection**
   - Drop low-importance features (reduce from 35 → 15-20)
   - Focus on core stats: PA, AVG, OBP, SLG, BB%, K%, SB

4. **Simpler Targets**
   - Start with 3-class classification (Elite/Average/Bust)
   - Only predict rate stats (AVG, OBP, SLG) not counting stats

### Medium-Term Improvements (Estimated 1-2 weeks)

1. **Collect More Data**
   - Expand to 2018-2025 (currently 2021-2025)
   - Lower threshold: 10+ MLB games instead of 20+
   - Expected: 600-800 samples

2. **Better Feature Engineering**
   - Add age-adjusted stats
   - Include level-specific performance (AAA vs AA vs A+)
   - Aggregate multiple MiLB seasons (not just pre-debut)
   - Add plate discipline metrics (chase rate, zone contact)

3. **Temporal Validation**
   - Train on 2018-2021, validate on 2022-2023, test on 2024-2025
   - More realistic performance estimate

4. **Ensemble Methods**
   - Combine XGBoost + Random Forest + Linear Regression
   - Use stacking or voting

### Long-Term Strategy (Estimated 1+ months)

1. **Hierarchical Modeling**
   - First predict MLB success tier (classification)
   - Then predict stats conditional on tier (regression)

2. **Deep Learning**
   - Neural networks can learn feature interactions
   - Requires 1,000+ samples

3. **External Data Sources**
   - Statcast data (exit velocity, launch angle)
   - Scouting grades from multiple sources
   - Minor league pitch-by-pitch data

4. **Transfer Learning**
   - Pre-train on all MiLB→MiLB level transitions
   - Fine-tune on MiLB→MLB

---

## What We Delivered (MVP)

Despite poor performance, we successfully built the **complete infrastructure**:

### ✅ Data Pipeline
1. Prospects table with 2,359 prospects
2. MLB pitcher appearances table (462 games)
3. Training data extraction script
4. Automated data collection from MLB Stats API

### ✅ ML Pipeline
1. Feature engineering (35 features)
2. Multi-output XGBoost model
3. Training/evaluation scripts
4. Model serialization (saved as .joblib)

### ✅ Code Artifacts
- `populate_prospects_from_mlb_debuts.py` - ✅ Working
- `collect_mlb_pitcher_data.py` - ✅ Working
- `build_stat_projection_training_data.py` - ✅ Working (hitters)
- `train_hitter_projection_model.py` - ✅ Working
- `hitter_projection_model_20251020_132528.joblib` - ✅ Saved

---

## Next Steps Decision Tree

### Option A: Ship with Disclaimer (1-2 days)
**Deploy current model with prominent disclaimer:**
- "Experimental projections - use with caution"
- Show confidence intervals (wide bounds)
- Useful for relative comparisons, not absolute predictions

**Pros:** Ship feature quickly, get user feedback
**Cons:** Poor accuracy may damage credibility

---

### Option B: Improve Model First (3-5 days)
**Implement short-term fixes, then deploy:**
1. Reduce model complexity
2. Train single-output models
3. Feature selection
4. Simpler targets (rate stats only)

**Expected Improvement:** Val R² from -0.013 → 0.15-0.25
**Pros:** Better accuracy before launch
**Cons:** Delays feature by a week

---

### Option C: Collect More Data (1-2 weeks)
**Expand dataset to 600-800 samples:**
1. Include 2018-2020 debuts
2. Lower threshold to 10+ games
3. Re-train with more data

**Expected Improvement:** Val R² from -0.013 → 0.25-0.40
**Pros:** Addresses root cause (sample size)
**Cons:** Significant time investment

---

### Option D: Pivot to Classification (2-3 days)
**Change to 3-class MLB outcome prediction:**
- Elite (Top 30% of MLB players)
- Average (Middle 40%)
- Below Average (Bottom 30%)

**Expected Accuracy:** 50-60% (vs. 33% baseline)
**Pros:** Easier problem, better performance with small data
**Cons:** Less granular than stat projections

---

## Recommended Path Forward

**Hybrid Approach: Option B + D**

### Phase 1 (3-4 days):
1. Build 3-class outcome classifier (Option D)
2. Deploy classification model first
3. Show probability distribution (e.g., "65% Elite, 30% Average, 5% Below Average")

### Phase 2 (1 week):
1. Implement short-term fixes for regression model (Option B)
2. Train separate models for rate stats (AVG, OBP, SLG only)
3. Deploy stat projections as "Beta" feature

### Phase 3 (2-3 weeks):
1. Collect more historical data (Option C)
2. Re-train both models with larger dataset
3. Move stat projections from "Beta" to stable

---

## Files Created

### Scripts
| File | Status | Purpose |
|------|--------|---------|
| `populate_prospects_from_mlb_debuts.py` | ✅ Complete | Add 1,010 MLB players to prospects |
| `collect_mlb_pitcher_data.py` | ✅ Complete | Collect 462 MLB pitcher appearances |
| `build_stat_projection_training_data.py` | ✅ Complete | Extract MiLB→MLB training data |
| `train_hitter_projection_model.py` | ✅ Complete | Train XGBoost multi-output model |

### Data Files
| File | Samples | Purpose |
|------|---------|---------|
| `stat_projection_hitters_train_20251020_124431.csv` | 399 | Hitter training data |
| `hitter_projection_model_20251020_132528.joblib` | - | Trained XGBoost model |
| `hitter_projection_features_20251020_132528.txt` | 35 | Feature names |
| `hitter_projection_targets_20251020_132528.txt` | 13 | Target names |

### Documentation
| File | Purpose |
|------|---------|
| `STAT_PROJECTION_PROGRESS_SUMMARY.md` | Mid-project status |
| `ML_STAT_PROJECTION_FINAL_REPORT.md` | This document |

---

## Conclusion

We successfully built the **complete ML infrastructure** for stat projections, from data collection to model training. However, the **model performance is poor** due to insufficient training data (399 samples is too small for this complex task).

**The good news:** We have a working pipeline and can iterate rapidly.

**The path forward:** Either:
1. Ship with disclaimer and iterate based on user feedback
2. Improve model with short-term fixes before shipping
3. Collect more data for better performance
4. Pivot to classification for better accuracy with small data

**Recommended:** Start with classification model (easier problem), then add stat projections as data grows.

---

*Report generated: October 20, 2025 13:30*
