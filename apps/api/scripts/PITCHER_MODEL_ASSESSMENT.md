# Pitcher Stat Projection Model - Assessment

**Date:** October 20, 2025
**Status:** ⚠️ Limited Data Available

---

## Data Availability Summary

### MLB Pitcher Data Collected
- Total appearances: **462**
- Unique pitchers: **62**
- Pitchers with 20+ games: **1** ❌
- Pitchers with 10+ games: **15** ⚠️
- Pitchers with 5+ games: **42** ✅

### MiLB Pitcher Data
- Total appearances: **17,375**
- Unique pitchers: **379**

### Training Data Overlap (MiLB + MLB)

| MLB Games Threshold | Training Samples | Assessment |
|---------------------|------------------|------------|
| 20+ games | 1 | ❌ Unusable (need 100+) |
| 15+ games | 4 | ❌ Unusable (need 30+) |
| 10+ games | **15** | ⚠️ Minimal (risky) |
| 5+ games | **42** | ✅ Possible (with caveats) |

---

## Recommendation: Train with 5+ Games Threshold

### Pros
- 42 training samples (vs 1 with 20+ threshold)
- Enough to train a basic model
- Better than no pitcher projections

### Cons
- Small sample size (42 is still limited)
- 5 games is very little MLB data (unreliable outcomes)
- High variance in target stats
- Model will have poor accuracy

### Expected Performance
With 42 samples:
- **Expected R²: 0.10 - 0.25** (weak to moderate)
- Much worse than hitters (0.344 with 399 samples)
- High uncertainty in predictions

---

## Pitchers with 10+ MLB Games (Top 15)

| Name | Position | MLB Games | MiLB Games |
|------|----------|-----------|------------|
| Connor Phillips | RP | 26 | 119 |
| Brady Basso | SP | 18 | 57 |
| Travis Adams | SP | 18 | 97 |
| Wikelman González | RP | 16 | 104 |
| Ryan Johnson | RP | 14 | 12 |
| Pierson Ohl | SP | 14 | 89 |
| Adam Mazur | SP | 14 | 65 |
| Brandyn Garcia | RP | 14 | 71 |
| Luinder Avila | SP | 13 | 91 |
| Juan Burgos | RP | 13 | 117 |
| Hurston Waldrep | SP | 12 | 45 |
| Mick Abel | SP | 11 | 102 |
| Cade Cavalli | SP | 11 | 63 |
| AJ Blubaugh | RP | 11 | 79 |
| Luis Morales | SP | 10 | 52 |

---

## Three Options

### Option 1: Train Basic Pitcher Model (5+ Games) ⚠️

**Approach:** Lower threshold to 5+ MLB games, train with 42 samples

**Pros:**
- Ship pitcher projections alongside hitters
- Complete feature parity
- Better than nothing

**Cons:**
- Poor accuracy (R² likely 0.10-0.25)
- 5 games is unreliable ground truth
- Risk of misleading projections

**Recommendation:** Label as "Experimental" with strong disclaimers

---

### Option 2: Ship Hitters Only (10+ Games for Later) ✅ RECOMMENDED

**Approach:** Deploy hitter projections now, wait for more pitcher data

**Pros:**
- High-quality hitter model (R² = 0.344)
- No risk of bad pitcher projections
- Can collect more data in background

**Cons:**
- Incomplete feature (hitters only)
- Users will ask for pitchers

**Timeline:**
- Deploy hitters: Now
- Collect more pitcher data: 3-6 months
- Train pitcher model: When 50+ samples available

---

### Option 3: Collect More Historical MLB Pitcher Data 🔄

**Approach:** Expand collection to 2018-2020 (not just 2021-2025)

**Potential gain:**
- 2018-2020 debuts could add 30-50 pitchers
- Total: 50-100 samples (sufficient for training)

**Effort:** 2-3 hours to modify collection script

**Risk:** Historical data quality may vary

---

## My Recommendation

**Deploy Option 2: Hitters Only**

### Rationale

1. **Quality over completeness**
   - Hitter model has R² = 0.344 (moderate accuracy)
   - Pitcher model would have R² ~ 0.15 (poor accuracy)
   - Better to ship one good feature than two mediocre features

2. **Manage expectations**
   - "Beta" label for hitters with moderate confidence
   - "Coming soon" for pitchers
   - Avoid credibility damage from bad pitcher projections

3. **Time to market**
   - Hitters are ready now
   - Pitchers need more data collection (weeks/months)
   - Can add pitchers in v2

### User Communication

**Projections Page:**
```
MLB Stat Projections (Beta)

[Hitters Tab] ← Active
[Pitchers Tab] ← Disabled with tooltip

Tooltip: "Pitcher projections coming soon!
We're collecting more MLB data to train accurate
pitcher models. Expected availability: Q1 2026"
```

---

## If You Choose Option 1 (Train Anyway)

I can train a pitcher model with 42 samples (5+ games threshold), but expect:

**Performance:**
- Validation R²: 0.10 - 0.25 (poor to weak)
- High variance
- Unreliable predictions

**Required disclaimers:**
- "Highly Experimental"
- "Based on very limited data (42 samples)"
- "Accuracy expected to be poor"
- "Use at your own risk"

**Implementation time:** 1-2 hours

---

## If You Choose Option 3 (Collect More Data)

I can modify the collection script to gather 2018-2020 data:

**Expected outcome:**
- Add 30-50 more pitchers
- Total: 50-100 samples
- R² improvement: 0.15 → 0.25-0.30

**Implementation time:** 2-3 hours

---

## Decision Matrix

| Criterion | Option 1 (5+ Games) | Option 2 (Hitters Only) | Option 3 (More Data) |
|-----------|---------------------|-------------------------|----------------------|
| Time to deploy | 1-2 hours | Immediate | 3-4 hours |
| Accuracy | Poor (R²~0.15) | Good (R²=0.344) | Moderate (R²~0.25) |
| Risk | High | Low | Medium |
| User experience | Complete but inaccurate | Incomplete but accurate | Complete and decent |
| Recommendation | ❌ Not advised | ✅ **Best choice** | ⚠️ If time permits |

---

## Summary

**Current Status:**
- Hitter model: ✅ Ready (R²=0.344, 399 samples)
- Pitcher model: ❌ Not ready (only 1 sample with 20+ games, 15 with 10+, 42 with 5+)

**Recommendation:**
Deploy hitters only (Option 2) with "Pitchers coming soon" message

**Alternative:**
If you want pitcher projections now, I can train with 42 samples (5+ games) but accuracy will be poor (R²~0.15)

**What would you like to do?**
1. Deploy hitters only (recommended)
2. Train pitcher model with 42 samples (experimental, poor accuracy)
3. Collect 2018-2020 data first (3-4 hours more work)

---

*Assessment completed: October 20, 2025 13:50*
