# Next Steps Recommendation: Hitter Model Improvement

**Current Status:** Phase 1 Complete (Enhanced Features)
**Result:** 0.682 F1 (no improvement from 0.684 baseline)
**Root Cause:** Feature redundancy + class imbalance

---

## Phase 1 Post-Mortem: What We Learned

### ✅ What Worked

1. **Enhanced features captured important signals**
   - `power_speed_number_v2`: #1 feature (13.75% importance) - **10x better than original**
   - `offensive_ceiling`: #3 feature (7.70% importance)
   - `has_elite_tool`: #4 feature (5.91% importance)
   - `plus_tool_count`: #5 feature (5.35% importance)

2. **Part-Time recall improved**
   - Baseline: ~23%
   - Enhanced: 30.4% (+7% improvement)
   - This IS the minority class we wanted to help

3. **Identified redundant features**
   - `power_speed_number` (1.42%) vs `power_speed_number_v2` (13.75%)
   - Contact profile one-hot features likely redundant

### ❌ What Didn't Work

1. **Overall F1 stayed flat** (-0.002 change)
   - Despite enhanced features being important
   - Redundancy may have caused overfitting

2. **Class imbalance still dominant**
   - 0 All-Star training examples
   - Only 30 Regular training examples
   - All-Star recall: 0% (same as baseline)

3. **Model still too conservative**
   - All 4 All-Stars in validation misclassified as Regular/Part-Time
   - 20+ Regulars downgraded to Part-Time/Bench
   - Same conservative bias as baseline

---

## Recommended Path Forward

### OPTION A: Quick Fix - Remove Redundant Features (1 day)

**What:** Train model with only best version of each feature

**Remove:**
- `power_speed_number` (keep v2)
- `contact_profile_*` one-hot features (low importance)
- Any other features with correlation > 0.9

**Expected gain:** +0.01-0.02 F1 (reduce overfitting)

**Pros:**
- Fast (1 day)
- Low risk
- May reduce overfitting gap (training: 0.806, validation: 0.656)

**Cons:**
- Won't solve class imbalance issue
- Unlikely to reach 0.72-0.75 F1 target

---

### OPTION B: Skip to Phase 2 - Position-Specific Models (1 week) ⭐ RECOMMENDED

**What:** Train separate models for each position group

**Position groups:**
- Infielders (SS, 2B, 3B): High variance, defense matters
- Outfielders (CF, RF, LF): Athletic tools important
- Catchers (C): Defensive focus, small sample
- Corner (1B): Power-focused

**Expected gain:** +0.05-0.10 F1

**Why this is the best option:**

1. **Addresses fundamental issue:** Hitters are NOT position-agnostic
   - First basemen need power, not speed
   - Shortstops need defense, can have lower hit tool
   - Catchers valued for defense + game-calling
   - Current model can't capture these differences

2. **Industry standard approach:**
   - Baseball Prospectus: Position-specific PECOTAs
   - FanGraphs: Position adjustments in projections
   - Steamer/ZiPS: Position-specific models

3. **May help with class imbalance:**
   - More All-Stars likely in OF/SS groups (athletic positions)
   - Fewer in C/1B (less athletic)
   - Position-specific models can learn these patterns

4. **Can combine with Option A:**
   - Use cleaned feature set for each position model
   - Best of both approaches

**Implementation:**

```python
# Week 2 Implementation Plan

# Day 1: Create position-specific datasets
position_groups = {
    'IF': ['SS', '2B', '3B'],  # Middle infielders
    'OF': ['CF', 'RF', 'LF'],  # Outfielders
    'C': ['C'],                 # Catchers
    'Corner': ['1B']            # Corner infielders
}

# Day 2-3: Train 4 separate models
for group in position_groups:
    # Use cleaned feature set (remove redundant features)
    # Train Random Forest with SMOTE
    # Evaluate on position-specific validation set

# Day 4: Ensemble prediction system
def predict_expectation(prospect):
    position_group = map_to_group(prospect['position'])
    model = position_models[position_group]
    return model.predict(prospect_features)

# Day 5: Evaluate overall performance
# Combine predictions across all position groups
# Compare to baseline (0.684) and enhanced (0.682)
```

**Expected results by position:**
- **IF (SS/2B/3B):** 0.70-0.75 F1
  - High variance (elite SS vs bench utility)
  - Speed and fielding features more important
  - Expected All-Stars: 40% of total

- **OF (CF/RF/LF):** 0.72-0.78 F1
  - Power-speed combo important
  - `power_speed_number_v2` likely #1 feature
  - Expected All-Stars: 40% of total

- **C (Catchers):** 0.60-0.70 F1
  - Small sample size issue
  - Defense dominates (game-calling not in data)
  - Expected All-Stars: 10% of total

- **Corner (1B):** 0.68-0.73 F1
  - Power-focused position
  - Lower variance (either mash or bust)
  - Expected All-Stars: 10% of total

**Overall weighted F1:** 0.72-0.76 (+0.04-0.08 from baseline)

---

### OPTION C: Better Class Imbalance Handling (3 days)

**What:** More aggressive SMOTE + alternative algorithms

**Changes:**
1. Use ADASYN instead of SMOTE
   - Adaptive synthetic sampling
   - Focuses on hard-to-learn examples

2. More aggressive oversampling
   - Current: Regular to 20% of Bench
   - New: Regular to 50% of Bench, Part-Time to 40%

3. Try XGBoost with `scale_pos_weight`
   - Better than Random Forest for imbalanced data
   - Built-in class weighting

4. Focal loss
   - Penalizes easy examples (Bench)
   - Focuses on hard examples (All-Star, Regular)

**Expected gain:** +0.02-0.04 F1

**Pros:**
- Directly addresses class imbalance
- XGBoost may outperform Random Forest
- Can combine with Option B

**Cons:**
- More complex (3 techniques to try)
- May not solve All-Star problem (0 training examples)
- Still position-agnostic

---

### OPTION D: Import 2020-2021 Historical Data (1-2 weeks)

**What:** Get more training examples

**If we can import 2020-2021 Fangraphs grades:**
- Estimated: +500-800 training samples
- Expected: +5-10 All-Star examples
- Expected: +40-60 Regular examples (currently only 30)

**Expected gain:** +0.05-0.08 F1

**Pros:**
- Solves root cause (class imbalance)
- More data = better models
- Would help ALL future improvements

**Cons:**
- **Unknown availability:** Do we have 2020-2021 data?
- **Unknown compatibility:** Schema may be different
- **Time investment:** 1-2 weeks of data engineering
- **Risk:** May not be feasible

**Decision:** Investigate feasibility first

---

## My Recommendation: **Option B + A** (Combined Approach)

### Week 2 Plan: Position-Specific Models with Cleaned Features

**Why combine B + A?**
1. Remove redundant features (1 day)
2. Use cleaned feature set for position models (4 days)
3. Best of both approaches

**Timeline:**
- **Day 1:** Remove redundant features, retrain baseline
  - Remove `power_speed_number` (keep v2)
  - Remove low-importance contact profile features
  - Expected: 0.69-0.70 F1 (small gain from reducing overfitting)

- **Day 2:** Create position-specific datasets
  - Split by position group (IF/OF/C/Corner)
  - Verify class distribution per position
  - Generate 12 CSV files (4 groups × 3 splits)

- **Day 3:** Train position-specific models
  - 4 separate Random Forest models
  - Position-specific feature importance
  - Position-specific SMOTE strategies

- **Day 4:** Evaluate and tune
  - Test each position model
  - Compare feature importance across positions
  - Adjust SMOTE strategy per position

- **Day 5:** Ensemble and final evaluation
  - Combine predictions
  - Overall test set evaluation
  - **Target: 0.72-0.76 F1**

**Expected final performance:**
- Best case: 0.76 F1 (+0.08 from baseline)
- Expected: 0.73-0.74 F1 (+0.05 from baseline)
- Worst case: 0.70-0.71 F1 (+0.02 from baseline)

**Even worst case achieves Phase 1 target** (we wanted +0.03 F1)

---

## Alternative: Investigate Option D First

**If we're unsure about timeline**, we could:

1. **Spend 1 day investigating 2020-2021 data availability**
   - Check if data exists
   - Check schema compatibility
   - Estimate import effort

2. **Make informed decision:**
   - If available: Do Option D first (more training data)
   - If not available: Do Option B+A (position-specific)

**This is lower risk** - we don't commit to Option B until we know Option D isn't feasible.

---

## Summary Table

| Option | Timeline | Expected F1 Gain | Risk | Effort |
|--------|----------|------------------|------|--------|
| A: Remove redundant features | 1 day | +0.01-0.02 | Low | Low |
| B: Position-specific models ⭐ | 5 days | +0.05-0.10 | Medium | Medium |
| C: Better class imbalance | 3 days | +0.02-0.04 | Medium | Medium |
| D: 2020-2021 data | 1-2 weeks | +0.05-0.08 | High | High |
| **B+A: Combined** ⭐⭐ | 5 days | **+0.05-0.10** | Medium | Medium |

---

## My Final Recommendation

### Primary Path: **Option B+A (Position-Specific + Cleaned Features)**

**Reasoning:**
1. Highest expected gain (+0.05-0.10 F1)
2. Addresses fundamental issue (position-agnostic modeling)
3. Medium risk, medium effort (5 days)
4. Industry-standard approach
5. Can combine with Option C later if needed

### Alternative Path: Investigate Option D feasibility first

**If unsure about 5-day commitment:**
1. Spend Day 1 investigating 2020-2021 data
2. If available: Pursue Option D
3. If not: Pursue Option B+A

---

## What to Do Next?

**Ask the user:**

> "Phase 1 enhanced features showed that our new features (like `power_speed_number_v2`) are highly important, but overall F1 stayed flat due to redundancy and class imbalance.
>
> I recommend **Option B+A: Position-specific models with cleaned features** (5 days, expected +0.05-0.10 F1).
>
> This is the industry-standard approach and addresses the core issue: treating all hitters the same.
>
> Alternatively, I can first **investigate if 2020-2021 historical data is available** (1 day), which could give us +500-800 more training samples and solve the class imbalance directly.
>
> Which path would you like to pursue?"

---

## Key Takeaways from Phase 1

1. ✅ **Enhanced features work** - `power_speed_number_v2` is now #1 most important feature
2. ✅ **Part-Time recall improved** - From ~23% to 30.4%
3. ❌ **Feature redundancy hurt us** - Having both original and v2 versions caused issues
4. ❌ **Class imbalance is the real problem** - 0 All-Star training examples, only 30 Regulars
5. 💡 **Position-specific modeling is the answer** - Hitters are not position-agnostic

**We learned valuable lessons and are now ready for a better Phase 2.**
