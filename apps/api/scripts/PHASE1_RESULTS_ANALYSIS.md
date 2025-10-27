# Phase 1 Results Analysis: Enhanced Feature Engineering

**Date:** October 19, 2025
**Result:** ❌ FAILED - No improvement in F1 score
**Baseline F1:** 0.684
**Enhanced F1:** 0.682 (-0.002)

---

## Summary

Phase 1 added 13 new derived features to the hitter model, increasing feature count from 35 to 49. Despite enhanced features contributing **43.5% of total feature importance**, the model's predictive performance did not improve.

---

## Key Findings

### 1. Enhanced Features Are Highly Important

**Top 5 Features:**
1. `power_speed_number_v2` - 13.75% importance [ENHANCED]
2. `game_power_future` - 8.14%
3. `offensive_ceiling` - 7.70% [ENHANCED]
4. `has_elite_tool` - 5.91% [ENHANCED]
5. `plus_tool_count` - 5.35% [ENHANCED]

**Enhanced features in top 25:** 7 out of 13 (54%)
**Total importance:** 43.5% of all feature importance

This shows the enhanced features ARE capturing important signal - the model relies on them heavily.

### 2. But Performance Didn't Improve

**Test Set Metrics:**
- **Weighted F1:** 0.682 (baseline: 0.684, change: -0.002)
- **Accuracy:** 66.7% (baseline: 68.4%, change: -1.7%)
- **Part-Time Recall:** 30.4% (baseline: ~23%, **improvement: +7%**)
- **Regular Recall:** 28.6% (baseline: ~31%, change: -2%)

**Mixed results:**
- Part-Time class improved (+7% recall)
- But Regular class declined slightly
- Overall weighted F1 stayed flat

### 3. What Went Wrong?

**Hypothesis 1: Feature Redundancy**
Enhanced features may be duplicating information already captured by original features.

Evidence:
- `power_speed_number_v2` (#1) highly correlated with `power_speed_number` (#22)
- `offensive_ceiling` (max of hit/power) correlated with `game_power_future` (#2) and `hit_future` (#11)
- `plus_tool_count` likely correlated with individual tool grades

**Hypothesis 2: Overfitting to Training Data**
- Training F1: 0.806
- Validation F1: 0.656
- Test F1: 0.682

The 15-point gap between training and validation suggests some overfitting. More features = more opportunities to overfit.

**Hypothesis 3: Wrong Features for Hitters**
We borrowed the `plus_pitch_count` concept from pitchers (where it's 8.9% important). But hitters may not follow the same "need one plus tool" logic:
- Pitchers: Need at least one 60+ pitch to succeed
- Hitters: Need BALANCE across hit/power/speed/defense?

Evidence from error analysis:
- All 4 All-Star prospects in validation set misclassified as Regular/Part-Time
- 20+ Regular prospects downgraded to Part-Time/Bench
- Model is still too conservative (same issue as baseline)

**Hypothesis 4: Class Imbalance Still Dominant**
Enhanced features can't overcome fundamental class imbalance:
- Training: 0 All-Star examples (218 Bench, 90 Part-Time, 30 Regular)
- Test: 6 All-Star examples (454 Bench, 92 Part-Time, 49 Regular)

SMOTE only resampled Regular class (30 → 43), which isn't enough.

---

## What We Learned

### Positive Insights

1. **Feature engineering CAN identify important signals**
   - 7 of our 13 enhanced features ranked in top 25
   - `power_speed_number_v2` is now the #1 most important feature
   - Enhanced features contribute 43.5% of importance

2. **Part-Time recall improved** (+7%)
   - This is the class we most wanted to improve
   - Shows enhanced features ARE helping with minority classes

3. **Some features worked well:**
   - `power_speed_number_v2` (blends stats + grades)
   - `offensive_ceiling` (max offensive tool)
   - `has_elite_tool` (any 60+ grade)
   - `plus_tool_count` (# of 55+ tools)

### Negative Insights

1. **Feature redundancy is a real problem**
   - Adding more features ≠ better predictions
   - Need to check correlation matrix before adding features

2. **Hitters ≠ Pitchers**
   - We can't just copy pitcher feature logic
   - Hitters may need different types of features

3. **Class imbalance is the root cause**
   - 0 All-Star training examples
   - Only 30 Regular training examples
   - Enhanced features can't fix this fundamental issue

---

## Recommended Next Steps

### Option A: Fix Feature Redundancy (Quick Win)

**Action:** Remove redundant features, keep only best version

Remove these duplicates:
- `power_speed_number` (keep `power_speed_number_v2`)
- Contact profile one-hot features if not helping

**Expected gain:** +0.01-0.02 F1 (reduce overfitting)

**Timeline:** 1 day

---

### Option B: Skip to Phase 2 (Recommended)

**Rationale:** Class imbalance is the root problem, not feature quality.

**Action:** Create position-specific models
- Separate models for IF/OF/C/1B/3B
- Each position has different predictive features
- May find more All-Stars in specific positions (OF, SS)

**Expected gain:** +0.05-0.10 F1

**Timeline:** 1 week

---

### Option C: Better Class Imbalance Handling

**Action:** More aggressive SMOTE + alternative algorithms

Changes:
1. Use ADASYN instead of SMOTE (adaptive synthetic sampling)
2. Oversample Regular to 50% of Bench (not 20%)
3. Try XGBoost with `scale_pos_weight` parameter
4. Focal loss for minority classes

**Expected gain:** +0.02-0.04 F1

**Timeline:** 3 days

---

### Option D: Import 2020-2021 Historical Data

**Action:** Get more training examples, especially All-Stars

If we can import 2020-2021 Fangraphs grades:
- Estimated +500-800 additional training samples
- May include 5-10 All-Star examples
- More Regular examples (currently only 30)

**Expected gain:** +0.05-0.08 F1

**Timeline:** 1 week (if data available)

**Risk:** May not be available / compatible

---

## Recommendation: **Option B (Position-Specific Models)**

### Why?

1. **Highest expected gain** (+0.05-0.10 F1)
2. **Addresses fundamental issue:** Position-agnostic model treats all hitters the same
   - Catchers valued differently than outfielders
   - First basemen need power, shortstops need defense
   - Current model can't capture these nuances

3. **Proven approach:** Industry standard for prospect modeling
   - Baseball Prospectus uses position-specific PECOTAs
   - FanGraphs adjusts projections by position
   - Steamer/ZiPS have position adjustments

4. **Can combine with Option C:** Position-specific + better SMOTE

### Implementation Plan (Week 2)

**Day 1-2:** Create position-specific datasets
```python
# Group positions
positions = {
    'IF': ['SS', '2B', '3B'],
    'OF': ['CF', 'RF', 'LF'],
    'C': ['C'],
    'Corner': ['1B']
}

# Extract features by position group
for group, pos_list in positions.items():
    df_group = df[df['position'].isin(pos_list)]
    # Save ml_data_hitters_{group}_train.csv
```

**Day 3-4:** Train 4 separate models (IF/OF/C/Corner)
- Same Random Forest + SMOTE approach
- Position-specific feature importance
- May find different top features per position

**Day 5:** Ensemble predictions
```python
def predict_by_position(prospect):
    position_group = get_position_group(prospect['position'])
    model = position_models[position_group]
    return model.predict(prospect_features)
```

**Expected Results:**
- IF model: 0.70-0.75 F1 (high variance in outcomes)
- OF model: 0.72-0.78 F1 (athletic tools important)
- C model: 0.65-0.70 F1 (small sample, defensive focus)
- Corner model: 0.68-0.73 F1 (power-focused)
- **Overall:** 0.72-0.76 F1 (+0.04-0.08 from baseline)

---

## Lessons Learned

1. **More features ≠ better model**
   - Check correlation before adding features
   - Remove redundant features
   - Quality > quantity

2. **Domain knowledge is crucial**
   - What works for pitchers may not work for hitters
   - Need position-specific modeling
   - Baseball is not position-agnostic

3. **Class imbalance is hard to overcome**
   - 0 All-Star training examples = 0% recall
   - SMOTE helps but has limits
   - Need more training data OR simpler class system

4. **Incremental testing is valuable**
   - We learned enhanced features capture signal (43.5% importance)
   - But redundancy and overfitting canceled out gains
   - Now we know what works (PSN_v2, offensive_ceiling) for Phase 2

---

## Phase 1 Final Status

**Result:** ❌ Failed to achieve +0.03 F1 improvement target
**Actual:** -0.002 F1 change (essentially flat)

**But valuable learnings:**
- Enhanced features DO capture important signal
- Feature redundancy is a problem
- Class imbalance is the root cause
- Position-specific modeling is the next step

**Recommendation:** Proceed to Phase 2 (Position-Specific Models)

**Revised Timeline:**
- ~~Week 1: Enhanced features (+0.03 F1)~~ ❌ Failed
- **Week 2: Position-specific models (+0.05-0.10 F1)** ← Do this next
- Week 3: XGBoost hyperparameter tuning (+0.03-0.05 F1)
- Week 4: Ensemble + polish (+0.01-0.03 F1)

**Revised Target:** 0.72-0.78 F1 (vs original 0.74-0.82 range)
