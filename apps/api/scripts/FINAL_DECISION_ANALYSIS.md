# Final Decision Analysis: Path Forward for Hitter Model

**Date:** October 19, 2025
**Current Best F1:** 0.697 (position-specific models)
**Target:** 0.75+ F1

---

## Investigation Results: 2020-2021 Data

###  Status: NOT USABLE ❌

**Findings:**
1. **Schema incompatibility:** 2020-2021 uses old schema:
   - Columns: Hit, Game Pwr, Raw Pwr, Spd, Fld, Arm (6 tools)
   - FV format: "45+" instead of just "45"

2. **Current schema (2022+):**
   - Columns: Hit, Pitch Sel, Bat Ctrl, Game Pwr, Raw Pwr, Spd, Fld, Avg EV, Hard Hit%, Max EV
   - More granular scouting grades
   - Different column names

3. **Migration effort:** Would require:
   - Mapping old columns to new schema
   - Handling missing columns (Pitch Sel, Bat Ctrl, etc.)
   - FV parsing changes
   - 1-2 weeks of work with high risk

**Decision:** NOT worth the effort given incompatibility

---

## Current Data Status

### What We Actually Have

**From database (already imported):**
- 2022: 242 labeled prospects (1 All-Star, 16 Regular, 46 Part-Time, 179 Bench)
- 2023: 429 labeled prospects (1 All-Star, 26 Regular, 95 Part-Time, 307 Bench)
- 2024: 710 labeled prospects (5 All-Stars, 60 Regular, 123 Part-Time, 522 Bench)
- 2025: 1,268 labeled prospects (7 All-Stars, 88 Regular, 177 Part-Time, 995 Bench)

**What ML training uses:**
- Train (2022-2023): 338 hitters **(we're using ALL available data)**
  - 0 All-Stars
  - 30 Regular
  - 90 Part-Time
  - 218 Bench

- Validation (2024): 363 hitters
  - 4 All-Stars
  - 37 Regular
  - 72 Part-Time
  - 250 Bench

- Test (2025): 601 hitters
  - 6 All-Stars
  - 49 Regular
  - 92 Part-Time
  - 454 Bench

### The Fundamental Problem

**We already have all usable data**, and it's not enough:
- **0 All-Star training examples** → impossible to predict All-Stars
- **Only 30 Regular training examples** → hard to predict Regulars
- **90 Part-Time, 218 Bench** → these classes work fine

**This explains why every approach failed:**
- Phase 1 (Enhanced features): -0.002 F1 (flat)
- Phase 2 (Position-specific): +0.013 F1 (marginal)

**You can't predict what you've never seen.**

---

## Available Options (Revised)

### ❌ Option 1: More Training Data (NOT AVAILABLE)

**Status:** Investigated and ruled out
- 2020-2021 data has incompatible schema
- Migration would take 1-2 weeks with high risk
- No guarantee of success

---

### ⭐ Option 2: 3-Class System (RECOMMENDED)

**What:** Collapse All-Star + Regular into "MLB Regular" class

**New class system:**
- **Class 0: Bench/Reserve** (FV 35-40)
  - Projects to MLB bench role
  - Training examples: 218

- **Class 1: Part-Time Player** (FV 45)
  - Projects to MLB part-time/platoon role
  - Training examples: 90

- **Class 2: MLB Regular+** (FV 50+)
  - Projects to MLB starter or better
  - Combines Regular (50-55) + All-Star (60+)
  - Training examples: 30 (vs 0 for All-Star alone!)

**Why this works:**
1. **Eliminates impossible task:** Can't predict 0-example All-Star class
2. **Better class balance:** 30 examples (vs 0) for top class
3. **Business alignment:**
   - Bench: "Pass, don't draft/trade for"
   - Part-Time: "Useful depth piece"
   - MLB Regular+: "Core piece, high value"
4. **Matches decision-making:** Teams care more about "will they be a starter?" than "starter vs All-Star"

**Expected improvement:**
- Current (4-class): 0.697 F1
- Expected (3-class): 0.72-0.75 F1 (+0.02-0.05)
- Regular+ class should hit 35-40% F1 (vs 0% for All-Star now)

**Timeline:** 2 days
- Day 1: Modify label generation, regenerate datasets
- Day 2: Train and evaluate

**Pros:**
- Solves core problem (0 All-Star examples)
- Quick to implement
- Aligns with business needs
- Achieves acceptable 0.72-0.75 F1

**Cons:**
- Loses All-Star granularity
- Won't reach 0.80+ F1 (that needs more data)

---

### Option 3: Try XGBoost (Supplementary)

**What:** Use XGBoost instead of Random Forest

**Can combine with Option 2:**
1. Implement 3-class system (0.72-0.75 F1)
2. Then try XGBoost (+0.02-0.03 additional)
3. Final: 0.74-0.78 F1

**Timeline:** +1 day after Option 2

**XGBoost advantages:**
- `scale_pos_weight` for class imbalance
- Gradient boosting (more expressive)
- Typically 2-5% better than Random Forest

**Expected gain:** +0.02-0.03 F1 on top of 3-class

---

### Option 4: Ship Current Model (0.697 F1)

**What:** Declare position-specific model production-ready

**Rationale:**
- 0.697 F1 is "acceptable" for prospect prediction
- Better than no model (scout-only evaluation)
- Can improve later when more data available

**Pros:**
- No additional work
- Move on to other features
- Revisit when 2026 data available

**Cons:**
- Leaves performance on table
- 0% All-Star recall (bad optics)
- Part-Time/Regular still weak (24-30% F1)

---

## Recommendation: **Option 2 + Option 3**

### Week 3 Plan: 3-Class System + XGBoost

**Day 1: Implement 3-Class System**
1. Modify label generation:
   ```python
   # New mapping
   if fv >= 50:  # Regular or All-Star
       label = 2  # MLB Regular+
   elif fv == 45:
       label = 1  # Part-Time
   else:  # fv <= 40
       label = 0  # Bench
   ```

2. Regenerate ML datasets with 3 classes
3. Train Random Forest baseline with 3-class
4. Expected: 0.72-0.75 F1

**Day 2: XGBoost Implementation**
1. Implement XGBoost with hyperparameter tuning:
   - GridSearch: learning_rate, max_depth, scale_pos_weight
   - Focal loss for minority classes
2. Compare to 3-class Random Forest
3. Expected: 0.74-0.78 F1

**Day 3: Evaluation and Documentation**
1. Test on validation + test sets
2. Compare to baseline (0.684) and position-specific (0.697)
3. Document improvements
4. Create production deployment plan

**Expected Final Result:**
- **Baseline:** 0.697 F1 (current best)
- **3-class RF:** 0.72-0.75 F1 (+0.02-0.05)
- **3-class XGBoost:** 0.74-0.78 F1 (+0.04-0.08)

**This achieves our revised target of 0.75 F1!**

---

## Why This is the Right Path

### 1. Solves Root Cause
- **Problem:** 0 All-Star training examples
- **Solution:** Merge with Regular class (30 examples)
- **Result:** Can actually learn the top tier

### 2. Aligns with Business
Baseball teams care about:
- "Will they be a bench player?" ✅ (Class 0)
- "Will they be a part-time player?" ✅ (Class 1)
- "Will they be a regular/star?" ✅ (Class 2)

They care less about:
- "Will they be a 4-WAR vs 6-WAR player?" ❌ (too granular)

### 3. Achieves Target
- 0.74-0.78 F1 is "Good" tier
- Exceeds baseline by 7-12%
- Production-ready performance

### 4. Realistic Timeline
- 3 days total
- Low risk (proven techniques)
- Can ship by end of week

---

## Alternative: If Time-Constrained

**Quick path (1 day):**
1. Just implement 3-class system (skip XGBoost)
2. Expected: 0.72-0.75 F1
3. Ship it

**This still achieves acceptable performance** and can add XGBoost later if needed.

---

## Summary

| Approach | F1 Expected | Timeline | Risk | Status |
|----------|-------------|----------|------|--------|
| Current best | 0.697 | - | - | ✅ Complete |
| 2020-2021 data | 0.76-0.80 | 2 weeks | High | ❌ Not feasible |
| **3-class system** | **0.72-0.75** | **2 days** | **Low** | **⭐ Recommended** |
| 3-class + XGBoost | 0.74-0.78 | 3 days | Low | ⭐⭐ Best option |
| Ship current | 0.697 | 0 days | None | ⚠️ Acceptable |

---

## Next Steps

**If proceeding with Option 2+3:**

1. **Confirm with user:** "Proceed with 3-class system + XGBoost?"
2. **Day 1:** Modify labels, regenerate datasets, train 3-class RF
3. **Day 2:** Implement XGBoost, tune hyperparameters
4. **Day 3:** Evaluate and document

**Expected completion:** End of week
**Expected result:** 0.74-0.78 F1 (production-ready!)

---

## What We Learned

1. **More data is king:** 338 samples is not enough for 4-class system
2. **Can't predict what you haven't seen:** 0 All-Stars → 0% recall
3. **Simpler is sometimes better:** 3-class easier than 4-class
4. **Business alignment matters:** Classes should match decision-making
5. **Know when to pivot:** After 2 failed phases, change the problem

The path forward is clear: **3-class system with XGBoost**.
