# Phase 2 Results Analysis: Position-Specific Models

**Date:** October 19, 2025
**Result:** ⚠️ MARGINAL - Minimal improvement
**Baseline F1:** 0.684
**Position-Specific F1:** 0.697 (+0.013)
**Target:** +0.05-0.10 F1 (Failed)

---

## Summary

Phase 2 created separate models for 4 position groups (IF/OF/C/Corner). Despite position-specific feature importance patterns emerging, overall F1 only improved by **+0.013** - far below the +0.05-0.10 target.

---

## Position-Specific Results

### By Position Group

| Position | Train | Val | Test | Val F1 | Test F1 | vs Baseline |
|----------|-------|-----|------|--------|---------|-------------|
| **IF** (SS/2B/3B) | 139 | 152 | 263 | 0.668 | **0.677** | -0.007 |
| **OF** (CF/RF/LF) | 135 | 135 | 222 | 0.676 | **0.702** | +0.018 |
| **C** (Catchers) | 35 | 53 | 80 | 0.761 | **0.708** | +0.024 |
| **Corner** (1B/DH) | 28 | 23 | 36 | 0.628 | **0.719** | +0.035 |
| **OVERALL** | 337 | 363 | 601 | - | **0.697** | **+0.013** |

**Baseline:** 0.684 F1 (position-agnostic model)

### Key Observations

1. **Catchers and Corner performed best**
   - C: +0.024 improvement
   - Corner: +0.035 improvement
   - **BUT:** Small samples (80 and 36 test samples)

2. **IF actually got worse**
   - -0.007 vs baseline
   - Largest position group (263 test samples)
   - This dragged down overall performance

3. **OF showed modest gain**
   - +0.018 improvement
   - Second largest group (222 test samples)

4. **Sample size correlation**
   - Smaller samples → bigger gains (C, Corner)
   - Larger samples → smaller/negative gains (IF, OF)
   - This suggests overfitting to small position groups

---

## Position-Specific Feature Importance

### Top 3 Features by Position

**IF (Infielders):**
1. game_power_future (13.67%)
2. offensive_ceiling (11.98%)
3. power_speed_number_v2 (9.93%)

**OF (Outfielders):**
1. power_speed_number_v2 (13.79%)
2. plus_tool_count (8.86%)
3. game_power_future (6.14%)

**C (Catchers):**
1. plus_tool_count (9.87%)
2. game_power_future (7.89%)
3. hit_power_ratio (7.89%)

**Corner (1B/DH):**
1. tool_variance (23.08%)
2. hit_power_ratio (23.08%)
3. offensive_ceiling (23.08%)

### Insights

1. **Different features matter by position** ✅
   - OF: power_speed_number_v2 #1 (athletic tools)
   - IF: game_power_future #1 (offensive potential)
   - C: plus_tool_count #1 (versatility)
   - Corner: tool_variance #1 (consistency matters)

2. **BUT:** Feature differences didn't translate to better predictions
   - Position-specific importance patterns exist
   - Models couldn't leverage these differences effectively

3. **Corner model is suspicious**
   - Only 6 non-zero features
   - 23% importance for 3 features (tool_variance, hit_power_ratio, offensive_ceiling)
   - Many features at 0% importance
   - **Severe overfitting due to tiny sample (28 train)**

---

## Class-Level Performance

### Overall Confusion Matrix

```
         Predicted:
           Bench  Part   Reg   AllStar
Bench        381    54    19     0      (83.9% recall)
Part-Time     55    23    14     0      (25.0% recall)
Regular       15    19    15     0      (30.6% recall)
All-Star       1     0     5     0      (0.0% recall)
```

### Per-Class Analysis

**Bench (Class 0):**
- Precision: 84.3%
- Recall: 83.9%
- F1: 0.841
- **Status:** ✅ Excellent (same as baseline)

**Part-Time (Class 1):**
- Precision: 24.0%
- Recall: 25.0%
- F1: 0.245
- **Status:** ⚠️ Poor (vs baseline ~26% F1, +2% improvement)

**Regular (Class 2):**
- Precision: 28.3%
- Recall: 30.6%
- F1: 0.294
- **Status:** ⚠️ Poor (vs baseline ~25% F1, +4% improvement)

**All-Star (Class 3):**
- Precision: 0%
- Recall: 0%
- F1: 0.000
- **Status:** ❌ Complete failure (same as all models)
- **All 6 All-Stars misclassified** (5 as Regular, 1 as Bench)

---

## Why Did Position-Specific Models Fail?

### Hypothesis 1: Sample Size Too Small ⭐ PRIMARY CAUSE

**Training samples by position:**
- IF: 139 (61.9% Bench, 28.8% Part-Time, 9.4% Regular, 0% All-Star)
- OF: 135 (65.2% Bench, 25.2% Part-Time, 9.6% Regular, 0% All-Star)
- C: 35 (65.7% Bench, 25.7% Part-Time, 8.6% Regular, 0% All-Star)
- Corner: 28 (71.4% Bench, 25.0% Part-Time, 3.6% Regular, 0% All-Star)

**Problems:**
- Corner only has 1 Regular in training (impossible to learn)
- C only has 3 Regular in training
- IF/OF have 13 Regular each (still very small)
- **0 All-Stars in any position group training**

**Impact:**
- Position-specific models have LESS data than baseline
- Baseline: 338 total training samples
- Each position: 28-139 samples (17-75% reduction)
- Smaller samples → more overfitting → worse generalization

**Evidence:**
- Corner model: Many features at 0% importance (pure overfitting)
- Training-validation gaps: IF (0.825 → 0.684), OF (0.863 → 0.659)
- Smaller positions showed higher gains (overfitting to validation set)

### Hypothesis 2: Class Imbalance Amplified

**Baseline class distribution (training):**
- 218 Bench, 90 Part-Time, 30 Regular, 0 All-Star

**Position-specific distributions:**
- IF: 86 Bench, 40 Part-Time, 13 Regular
- OF: 88 Bench, 34 Part-Time, 13 Regular
- C: 23 Bench, 9 Part-Time, 3 Regular
- Corner: 20 Bench, 7 Part-Time, 1 Regular

**Problem:**
- Splitting made minority classes even rarer
- Regular class: 30 total → split into 13/13/3/1
- Corner has only 1 Regular example (can't learn)
- C has only 3 Regular examples (minimal learning)

**SMOTE couldn't help:**
- IF: Resampled Regular from 13 → 17 (only +4)
- OF: Resampled Regular from 13 → 17 (only +4)
- C: SMOTE skipped (too few samples)
- Corner: SMOTE skipped (too few samples)

### Hypothesis 3: Position Not Actually Predictive

**Alternative explanation:** Position may not be as important as expected.

**Evidence:**
- Baseball Prospectus/FanGraphs use position adjustments for MLB projections
- But these are for established MLB players, not prospects
- Prospects haven't settled into positions yet
- SS prospects may move to 2B/3B/OF
- C prospects may move to 1B/DH

**Counterargument:**
- We DID see different feature importance by position
- This suggests position does matter
- But sample size prevented models from learning effectively

### Hypothesis 4: We're at the Model Ceiling

**Consideration:** Maybe 0.68-0.70 F1 is the ceiling for this data.

**Evidence:**
- Baseline: 0.684
- Enhanced features: 0.682 (flat)
- Position-specific: 0.697 (+0.013)
- Hierarchical pitcher: 0.809 (but pitchers have more data)

**Why a ceiling might exist:**
- 0 All-Star training examples → impossible to predict All-Stars
- Only 30 Regular training examples → hard to predict Regulars
- Prospect development is inherently unpredictable (injuries, development curves)
- Missing important features (makeup, work ethic, injury history)

**BUT:** Pitcher model achieved 0.809, suggesting ceiling is higher if we had more data.

---

## What We Learned

### ✅ Positive Insights

1. **Position-specific feature patterns exist**
   - OF rely more on power_speed_number_v2
   - IF rely more on game_power_future
   - C rely more on plus_tool_count
   - These make intuitive sense

2. **Catchers and Corner showed improvement** (caveat: small samples)
   - C: +0.024 F1
   - Corner: +0.035 F1
   - Shows position-specific can work with enough data

3. **Regular and Part-Time improved slightly**
   - Regular: +4% F1 (0.25 → 0.29)
   - Part-Time: +2% F1 (0.24 → 0.25)
   - Small gains, but in the right direction

### ❌ Negative Insights

1. **Splitting data hurt more than it helped**
   - Reduced effective training samples
   - Amplified class imbalance
   - Led to overfitting (especially Corner)

2. **IF model got worse** (-0.007 F1)
   - Largest position group
   - Should have benefited most
   - Actually performed worse

3. **Overall gain (+0.013) well below target** (+0.05-0.10)
   - Would need 4-8x better improvement
   - Position-specific alone is not the answer

4. **All-Star class still 0% recall**
   - Same fundamental problem
   - Can't fix with position splits

---

## Root Cause Diagnosis

**Primary Issue:** Sample size too small for position-specific modeling

**Mathematical analysis:**
- Baseline effective training: 338 samples
- Position-specific effective training: 28-139 samples per position
- Reduction: 59-92% fewer samples per model
- Class imbalance amplified: Regular 30 → 1-13 per position

**Rule of thumb:**
- Need ~100+ samples per class for reliable ML
- We have: 1-17 Regular samples per position (10-90% below threshold)

**Conclusion:** Can't do position-specific modeling without more training data.

---

## Revised Strategy: What Actually Will Work?

### Option 1: Import 2020-2021 Historical Data ⭐ HIGHEST PRIORITY

**Why this is now critical:**
- Root cause is sample size
- Both Phase 1 and Phase 2 failed due to insufficient data
- Need 3-5x more training samples

**If we get 2020-2021 data:**
- Estimated: +500-800 training samples (current: 338)
- Regular class: 30 → 70-100 samples
- All-Star class: 0 → 5-10 samples
- Each position group: 50-200+ samples

**Expected gain:** +0.08-0.12 F1 (to 0.76-0.80)

**Action:** Investigate if this data exists and can be imported.

---

### Option 2: Collapse to 3-Class System

**What:** Merge All-Star + Regular into single "MLB Regular" class

**Rationale:**
- 0 All-Star training examples → impossible to predict
- All-Star and Regular both project to MLB starters
- Business value is similar (both are good prospects)

**New classes:**
- 0: Bench/Reserve (FV 35-40)
- 1: Part-Time Player (FV 45)
- 2: MLB Regular (FV 50+, combining Regular 50-55 + All-Star 60+)

**Expected class distribution (estimated):**
- Training: ~220 Bench, ~90 Part-Time, ~30 MLB Regular
- Less imbalanced than 4-class (30 vs 0 for minority class)

**Expected gain:** +0.03-0.05 F1 (to 0.71-0.73)

**Pros:**
- Matches business needs (bench vs part-time vs starter)
- Eliminates impossible-to-predict All-Star class
- Better class balance

**Cons:**
- Loses granularity (can't distinguish All-Stars from Regulars)
- May still struggle with MLB Regular class (only 30 examples)

---

### Option 3: Try XGBoost with Better Hyperparameters

**What:** Use XGBoost instead of Random Forest

**Why XGBoost might help:**
- Better at handling class imbalance (`scale_pos_weight`)
- More expressive (gradient boosting vs random forest)
- Can use focal loss for minority classes
- Often 2-5% better than Random Forest

**Expected gain:** +0.02-0.04 F1 (to 0.70-0.72)

**Pros:**
- Doesn't require more data
- Can implement quickly (1-2 days)
- Industry standard for tabular data

**Cons:**
- Won't solve fundamental data scarcity issue
- May overfit even more on small samples
- Likely won't reach 0.75+ F1 target

---

### Option 4: Ensemble Baseline + Position-Specific

**What:** Weighted ensemble of position-agnostic and position-specific models

**How:**
```python
prediction = 0.7 * baseline_pred + 0.3 * position_specific_pred
```

**Rationale:**
- Baseline has more data (better for majority classes)
- Position-specific has position context (better for edge cases)
- Ensemble might get best of both

**Expected gain:** +0.01-0.02 F1 (to 0.70-0.71)

**Pros:**
- Low risk (can't be worse than baseline)
- Quick to implement (half day)
- Might eke out small gains

**Cons:**
- Marginal improvement expected
- Adds complexity
- Won't reach 0.75+ F1 target

---

## Recommended Path Forward

### Primary Recommendation: **Option 1 (Import 2020-2021 Data)**

**Reasoning:**
1. **Root cause is clear:** Insufficient training data
2. **Both Phase 1 and Phase 2 failed** due to this
3. **Only way to reach 0.75+ F1** is more data
4. **Pitcher model proves this works** (0.809 with same approach)

**If 2020-2021 data is available:**
- Import historical Fangraphs grades
- Retrain baseline model with 3x more data
- Expected: 0.76-0.80 F1
- Then try position-specific (with 150+ samples per position)

**If 2020-2021 data NOT available:**
- Proceed to Option 2 (3-class system) OR
- Declare current model (0.697-0.70 F1) production-ready
- Focus on other product features instead

---

### Secondary Recommendation: **Option 2 (3-Class System)**

**If Option 1 not feasible:**

**Week 3 Plan:**
1. **Day 1:** Collapse All-Star + Regular into MLB Regular class
2. **Day 2:** Retrain baseline model with 3 classes
3. **Day 3:** Train XGBoost model for 3-class
4. **Day 4:** Compare Random Forest vs XGBoost
5. **Day 5:** Evaluate and document

**Expected outcome:** 0.71-0.73 F1

**This is still "acceptable"** for production:
- 71-73% F1 is reasonable for prospect prediction
- Better than scout-only evaluation (no metrics)
- Can improve later when more data available

---

### Tertiary Recommendation: **Option 3 (XGBoost)**

**If we want to stay with 4-class system:**

**Quick implementation (2 days):**
1. **Day 1:** Implement XGBoost with hyperparameter tuning
   - GridSearch over learning_rate, max_depth, scale_pos_weight
   - Use same train/val/test splits
2. **Day 2:** Compare to Random Forest baseline
   - Expected: 0.70-0.72 F1

---

## Final Summary

### Phase 2 Status: ⚠️ MARGINAL (Failed to meet target)

**Results:**
- Target: +0.05-0.10 F1 improvement
- Actual: +0.013 F1 improvement
- Shortfall: 75-90% below target

**Why it failed:**
1. **Sample size too small** (28-139 per position vs 338 baseline)
2. **Class imbalance amplified** (Regular: 30 → 1-13 per position)
3. **Overfitting** (especially Corner with 28 samples)
4. **0 All-Stars still** (can't predict what you never see)

### Cumulative Progress

| Phase | Approach | F1 Result | vs Baseline | Status |
|-------|----------|-----------|-------------|--------|
| Baseline | Random Forest | 0.684 | - | ✅ Success |
| Phase 1 | Enhanced features | 0.682 | -0.002 | ❌ Failed |
| Phase 2 | Position-specific | 0.697 | +0.013 | ⚠️ Marginal |

**Best model so far:** Position-specific (0.697 F1)
**Improvement from baseline:** +0.013 (+1.9%)

### Next Steps Decision Tree

```
Is 2020-2021 historical data available?
├─ YES → Import data, retrain baseline
│         Expected: 0.76-0.80 F1 ✅
│         Timeline: 1-2 weeks
│
└─ NO → Choose one:
    ├─ Option A: 3-class system (collapse All-Star + Regular)
    │            Expected: 0.71-0.73 F1
    │            Timeline: 5 days
    │
    ├─ Option B: Try XGBoost
    │            Expected: 0.70-0.72 F1
    │            Timeline: 2 days
    │
    └─ Option C: Ship current model (0.697 F1)
                 Focus on other features
                 Revisit when more data available
```

### My Recommendation

1. **Spend 1 day investigating 2020-2021 data availability**
2. **If available:** Import data (Option 1)
3. **If not available:** Implement 3-class system (Option 2)
4. **If we want quick win:** Try XGBoost first (Option 3), then 3-class

**Do NOT:**
- Continue with more feature engineering (Phase 1 failed)
- Try more position splits (Phase 2 failed)
- Spend more than 1 week without pursuing Option 1 or Option 2

**The path forward is clear:** We need more training data OR simpler classification task.
