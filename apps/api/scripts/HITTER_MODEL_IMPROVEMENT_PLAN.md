# Hitter Model Improvement Plan

**Current Performance:** 0.684 F1 (Success, but below Excellent threshold)
**Target Performance:** 0.75+ F1 (10% improvement)
**Timeline:** 2-4 weeks

---

## Current Weaknesses Analysis

### 1. Overall Performance Gap

| Metric | Hitters | Pitchers | Gap |
|--------|---------|----------|-----|
| **Test F1** | 0.684 | 0.809 | **-12%** |
| **Accuracy** | 68.4% | 81.4% | -13% |
| **Part-Time F1** | 0.225 | 0.398 | **-43%** |
| **Regular F1** | 0.286 | 0.378 | -24% |

**Problem:** Hitter model significantly underperforms pitcher model across all metrics.

### 2. Class-Specific Issues

**Part-Time Class (15.3% of test data):**
- Precision: 0.221 (only 22% accuracy when predicting Part-Time)
- Recall: 0.228 (misses 71% of actual Part-Time hitters)
- **58 false negatives** predicted as Bench (63% of Part-Time prospects)

**Regular Class (8.2% of test data):**
- Precision: 0.268 (73% false positive rate)
- Recall: 0.306 (misses 69% of actual Regulars)
- **16 false negatives** predicted as Bench (33% of Regulars)

**All-Star Class (1.0% of test data):**
- **0% recall** (0 All-Stars in training data)
- Cannot learn what doesn't exist

### 3. Feature Utilization

**Scouting grades dominate (66%):**
- Power features: 34% combined importance
- Hit/Speed/Fielding: 32%
- Development upside: 20%

**Performance stats underutilized (14%):**
- batting_avg: 3.9%
- avg_obp, avg_slg, total_hr, etc.: ~10% combined
- **2.4x less important than for pitchers (33%)**

**Missing features:**
- No "plus_tool_count" equivalent (pitchers have plus_pitch_count at 8.9%)
- No position-specific adjustments
- No park factors
- No level-adjusted stats

### 4. Conservative Bias

**Downgrade pattern:**
- Model predicts Bench 62% of time (actual: 75%)
- Rarely predicts upside classes
- Example errors:
  - Max Clark (FV 60 All-Star) → Predicted Bench
  - Colt Emerson (FV 55 Regular) → Predicted Bench

**Why:** Model learned to be conservative from imbalanced training data (64% Bench).

---

## Improvement Strategies

### Strategy 1: Position-Specific Models ⭐ **HIGHEST IMPACT**

**Problem:** Single model treats all hitters the same, but positions have different value profiles.

**Solution:** Train separate models for position groups.

**Position Groups:**
```
1. Catchers (C) - Defensive value premium
2. Middle Infielders (SS, 2B) - Athletic premium
3. Corner Infielders (1B, 3B) - Power emphasis
4. Outfielders (CF, LF, RF) - Speed/defense balance
```

**Expected Impact:** **+0.05-0.10 F1**

**Why it works:**
- Catchers need lower offensive bar (defensive value)
- Shortstops valued for glove-first profiles
- First basemen MUST hit (no defensive value)
- Center fielders need speed/range

**Implementation:**

```python
# Train 4 separate models
positions_map = {
    'C': 'catcher',
    'SS': 'middle_infield',
    '2B': 'middle_infield',
    '1B': 'corner_infield',
    '3B': 'corner_infield',
    'CF': 'outfield',
    'LF': 'outfield',
    'RF': 'outfield',
    'DH': 'corner_infield'  # Treat like 1B
}

for position_group in ['catcher', 'middle_infield', 'corner_infield', 'outfield']:
    # Filter training data
    train_subset = train_df[train_df['position'].map(positions_map) == position_group]

    # Train model
    model = RandomForestClassifier(...)
    model.fit(X_train_subset, y_train_subset)

    # Save
    joblib.dump(model, f'models/hitter_{position_group}_v1.pkl')
```

**Feature importance by position:**
- Catchers: Framing grade, arm strength, game-calling
- MI: Speed, fielding, range
- CI: Power, hit tool
- OF: Speed, arm, range

### Strategy 2: Enhanced Feature Engineering ⭐ **HIGH IMPACT**

**Problem:** Current features don't capture offensive ceiling or floor well.

**Solution:** Create hitter-specific derived features.

**Expected Impact:** **+0.03-0.05 F1**

**New Features to Add:**

**A. Plus Tool Count** (equivalent to pitchers' plus_pitch_count)
```python
def calculate_plus_tool_count(grades):
    """Count how many tools are 55+ (above average)."""
    return sum([
        1 if grades.get('hit_future', 0) >= 55 else 0,
        1 if grades.get('game_power_future', 0) >= 55 else 0,
        1 if grades.get('raw_power_future', 0) >= 55 else 0,
        1 if grades.get('speed_future', 0) >= 55 else 0,
        1 if grades.get('fielding_future', 0) >= 55 else 0
    ])

# Expected importance: 7-10% (like pitchers)
```

**B. Hit-Power Balance**
```python
def hit_power_ratio(grades):
    """
    Ratio of hit tool to power tool.

    High ratio (>1.2): Contact-first hitter
    Balanced (0.8-1.2): Five-tool potential
    Low ratio (<0.8): Power-first hitter
    """
    hit = grades.get('hit_future', 50)
    power = grades.get('game_power_future', 50)
    return hit / power if power > 0 else 1.0
```

**C. Offensive Ceiling**
```python
def offensive_ceiling(grades):
    """Maximum of hit or power tool."""
    return max(
        grades.get('hit_future', 0),
        grades.get('game_power_future', 0)
    )

# Rationale: Elite in ONE area can make you MLB regular
# Don't need to be good at everything
```

**D. Defensive Floor**
```python
def defensive_floor(grades):
    """Minimum of fielding and speed (can you stay on field?)."""
    return min(
        grades.get('fielding_future', 50),
        grades.get('speed_future', 50)
    )

# If defense is terrible (<40), need elite bat
```

**E. Power-Speed Number** (already have, but enhance)
```python
def power_speed_number_v2(stats, grades):
    """
    Enhanced PSN using both stats and grades.

    Traditional: 2*HR*SB / (HR+SB)
    Enhanced: Blend with scouting grades
    """
    # Stats-based (actual performance)
    hr = stats.get('total_hr', 0)
    sb = stats.get('total_sb', 0)
    psn_stats = (2 * hr * sb) / (hr + sb) if (hr + sb) > 0 else 0

    # Grade-based (projected)
    power_grade = grades.get('game_power_future', 50)
    speed_grade = grades.get('speed_future', 50)
    psn_grades = (power_grade + speed_grade) / 2

    # Blend: 60% grades, 40% stats
    return 0.6 * psn_grades + 0.4 * psn_stats
```

**F. Age-Relative Performance**
```python
def age_relative_ops(stats, prospect_age):
    """
    Compare OPS to league average for same age.

    Young for level (19yo in A+) → more upside
    Old for level (24yo in AA) → red flag
    """
    ops = stats.get('ops', 0.700)
    level = stats.get('level', 'A')

    # Age-level baselines (empirical)
    baselines = {
        ('A', 19): 0.650,
        ('A', 20): 0.700,
        ('A', 21): 0.750,
        ('A+', 20): 0.700,
        ('A+', 21): 0.750,
        ('AA', 22): 0.750,
        ('AA', 23): 0.800,
        ('AAA', 23): 0.800,
        ('AAA', 24): 0.850
    }

    baseline = baselines.get((level, prospect_age), 0.750)
    return ops - baseline  # Positive = outperforming, negative = underperforming
```

**G. Contact vs Power Profile**
```python
def contact_vs_power_score(stats):
    """
    High K rate + high power = swing-and-miss slugger
    Low K rate + low power = contact hitter
    """
    k_rate = stats.get('k_rate', 0.25)
    iso = stats.get('isolated_power', 0.100)

    if k_rate > 0.30 and iso > 0.200:
        return 'power_slugger'
    elif k_rate < 0.15 and iso < 0.150:
        return 'contact_hitter'
    elif k_rate < 0.20 and iso > 0.200:
        return 'balanced_star'  # Rare and valuable!
    else:
        return 'average_hitter'

# One-hot encode for model
```

**H. Level Progression Speed**
```python
def levels_per_year(prospect):
    """
    Fast risers (2+ levels per year) → high confidence
    Slow grinders (1 level per 2 years) → development concerns
    """
    debut_year = prospect.get('debut_year')
    current_year = 2025
    highest_level = prospect.get('highest_level', 1)  # 1=Rookie, 5=AAA

    years_in_minors = current_year - debut_year
    if years_in_minors > 0:
        return highest_level / years_in_minors
    return 0
```

**I. Platoon Split Indicator**
```python
def has_platoon_concern(stats):
    """
    If available, check vs LHP vs RHP splits.

    Large split (>100 OPS points) → platoon role (Part-Time)
    """
    ops_vs_rhp = stats.get('ops_vs_rhp', 0.750)
    ops_vs_lhp = stats.get('ops_vs_lhp', 0.750)

    split = abs(ops_vs_rhp - ops_vs_lhp)
    return 1 if split > 0.100 else 0
```

**Summary of New Features:**
```python
NEW_FEATURES = [
    'plus_tool_count',           # 0-5 (how many 55+ tools)
    'hit_power_ratio',           # 0.5-2.0 (contact vs power)
    'offensive_ceiling',         # Max of hit/power
    'defensive_floor',           # Min of fielding/speed
    'power_speed_number_v2',     # Enhanced PSN
    'age_relative_ops',          # +/- vs age-level baseline
    'contact_profile',           # One-hot: power/contact/balanced/average
    'levels_per_year',           # Promotion speed
    'has_platoon_concern'        # Binary: severe split?
]

# Expected total features: 35 → 44 (+9 features)
```

### Strategy 3: Better Class Imbalance Handling ⭐ **MEDIUM IMPACT**

**Problem:** Current SMOTE only helped Regular class (30→43), but Part-Time needs help too.

**Solution:** More aggressive SMOTE + focal loss.

**Expected Impact:** **+0.02-0.04 F1**

**A. ADASYN (Adaptive SMOTE)**
```python
from imblearn.over_sampling import ADASYN

# ADASYN focuses on hard-to-learn samples
adasyn = ADASYN(
    sampling_strategy={
        1: 120,  # Part-Time: 90 → 120 (33% increase)
        2: 60    # Regular: 30 → 60 (100% increase)
    },
    random_state=42
)

X_resampled, y_resampled = adasyn.fit_resample(X_train, y_train)

# Result:
# Bench: 218 (55%)
# Part-Time: 120 (30%)
# Regular: 60 (15%)
# All-Star: 0 (0%)
```

**B. Focal Loss (for XGBoost)**
```python
def focal_loss(y_true, y_pred, gamma=2.0, alpha=0.25):
    """
    Focal loss emphasizes hard-to-classify samples.

    gamma: Focusing parameter (higher = more focus on hard samples)
    alpha: Class weighting
    """
    # For XGBoost custom objective
    # Downweights easy examples, focuses on hard ones
    pass

# Use in XGBoost:
xgb_model = xgb.XGBClassifier(
    objective=focal_loss,  # Custom
    # ... other params
)
```

**C. Cost-Sensitive Learning**
```python
# Asymmetric costs: Missing a Regular is worse than false positive
cost_matrix = {
    # Actual → Predicted
    (0, 0): 0,    # Bench → Bench (correct)
    (0, 1): 1,    # Bench → Part-Time (minor cost)
    (0, 2): 2,    # Bench → Regular (moderate cost)
    (1, 0): 5,    # Part-Time → Bench (HIGH COST - missing upside!)
    (1, 1): 0,    # Part-Time → Part-Time (correct)
    (1, 2): 1,    # Part-Time → Regular (minor cost)
    (2, 0): 10,   # Regular → Bench (VERY HIGH COST!)
    (2, 1): 3,    # Regular → Part-Time (moderate cost)
    (2, 2): 0     # Regular → Regular (correct)
}

# Incorporate into model training
sample_weights = np.array([cost_matrix[(y, y)] for y in y_train])
```

### Strategy 4: XGBoost with Hyperparameter Tuning ⭐ **MEDIUM IMPACT**

**Problem:** Random Forest may not be optimal for hitters (works better for pitchers).

**Solution:** Try gradient boosting with extensive tuning.

**Expected Impact:** **+0.03-0.05 F1**

**A. XGBoost Baseline**
```python
import xgboost as xgb

xgb_model = xgb.XGBClassifier(
    objective='multi:softprob',
    num_class=4,
    max_depth=5,              # Shallower than RF
    learning_rate=0.05,       # Slow learning
    n_estimators=500,         # Many iterations
    subsample=0.8,            # Row sampling
    colsample_bytree=0.8,     # Column sampling
    gamma=0.1,                # Regularization
    min_child_weight=3,       # Min samples per leaf
    scale_pos_weight=None,    # Will set per class
    random_state=42
)
```

**B. Hyperparameter Optimization (Optuna)**
```python
import optuna

def objective(trial):
    params = {
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'gamma': trial.suggest_float('gamma', 0, 0.5),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10)
    }

    model = xgb.XGBClassifier(**params, objective='multi:softprob', num_class=4)
    model.fit(X_train, y_train)

    y_val_pred = model.predict(X_val)
    f1 = f1_score(y_val, y_val_pred, average='weighted')

    return f1

# Run optimization
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)

print(f"Best params: {study.best_params}")
print(f"Best F1: {study.best_value}")
```

### Strategy 5: Ensemble Methods ⭐ **LOW-MEDIUM IMPACT**

**Problem:** Single model may not capture all patterns.

**Solution:** Combine multiple models.

**Expected Impact:** +0.01-0.03 F1

**A. Voting Classifier**
```python
from sklearn.ensemble import VotingClassifier

ensemble = VotingClassifier(
    estimators=[
        ('rf', RandomForestClassifier(...)),
        ('xgb', xgb.XGBClassifier(...)),
        ('lgbm', lgb.LGBMClassifier(...))
    ],
    voting='soft',  # Use probabilities
    weights=[1, 2, 1]  # Weight XGBoost 2x
)

ensemble.fit(X_train, y_train)
```

**B. Stacking**
```python
from sklearn.ensemble import StackingClassifier

stacking = StackingClassifier(
    estimators=[
        ('rf', RandomForestClassifier(...)),
        ('xgb', xgb.XGBClassifier(...))
    ],
    final_estimator=LogisticRegression(),  # Meta-learner
    cv=5
)
```

### Strategy 6: Collapse All-Star into Regular ⭐ **ALTERNATIVE APPROACH**

**Problem:** Cannot predict 0-sample All-Star class.

**Solution:** Combine All-Star + Regular → "MLB Regular" class.

**Expected Impact:** +0.02-0.03 F1 (by removing impossible task)

**New 3-Class System:**
```
- Bench (FV 35-40): Not MLB worthy
- Part-Time (FV 45): Role player, bench bat
- MLB Regular (FV 50+): Starter or better (combines Regular + All-Star)
```

**Benefits:**
- 55 MLB Regulars in test set (vs 6 All-Stars) = 9x more samples
- More balanced: Bench 75%, Part-Time 15%, Regular 10%
- Still valuable prediction (starter vs bench)
- Removes impossible All-Star prediction

**Implementation:**
```python
def remap_to_3class(y):
    """
    0 → 0 (Bench)
    1 → 1 (Part-Time)
    2 → 2 (MLB Regular)
    3 → 2 (MLB Regular)  ← All-Star absorbed
    """
    return np.where(y >= 2, 2, y)

y_train_3class = remap_to_3class(y_train)
y_val_3class = remap_to_3class(y_val)
y_test_3class = remap_to_3class(y_test)

# Train 3-class model
model = RandomForestClassifier(...)
model.fit(X_train, y_train_3class)

# Expected: F1 = 0.71-0.73 (vs 0.684 for 4-class)
```

---

## Recommended Implementation Order

### Phase 1 (Week 1): Quick Wins
**Estimated Improvement: +0.05-0.08 F1**

1. **Enhanced Feature Engineering** (2-3 days)
   - Add plus_tool_count
   - Add offensive_ceiling, defensive_floor
   - Add age_relative_ops
   - Retrain baseline RF model
   - Expected: 0.684 → 0.71 F1

2. **Better SMOTE Strategy** (1 day)
   - Use ADASYN instead of SMOTE
   - More aggressive Part-Time oversampling
   - Expected: +0.02 F1

3. **Quick Evaluation** (1 day)
   - Test on validation + test sets
   - Compare to baseline
   - Document improvements

**Week 1 Target: 0.72 F1** (+5% improvement)

### Phase 2 (Week 2): Position-Specific Models
**Estimated Improvement: +0.05-0.10 F1**

1. **Split Data by Position** (1 day)
   - Create 4 position groups
   - Analyze sample sizes per group
   - Check class distributions

2. **Train 4 Models** (2 days)
   - Catcher model
   - Middle infield model
   - Corner infield model
   - Outfield model

3. **Evaluate Position Models** (1 day)
   - Per-position F1 scores
   - Combined weighted F1
   - Error analysis by position

4. **Create Position Router** (1 day)
   ```python
   def predict_by_position(prospect):
       position_group = map_position(prospect['position'])
       model = load_model(f'models/hitter_{position_group}.pkl')
       return model.predict(prospect_features)
   ```

**Week 2 Target: 0.75-0.77 F1** (+10-12% improvement)

### Phase 3 (Week 3): XGBoost Optimization
**Estimated Improvement: +0.02-0.04 F1**

1. **XGBoost Baseline** (1 day)
   - Train with default params
   - Compare to RF

2. **Hyperparameter Tuning** (2-3 days)
   - Optuna optimization (100 trials)
   - Grid search refinement
   - Cross-validation

3. **Best Model Selection** (1 day)
   - RF vs XGBoost comparison
   - Ensemble if both strong

**Week 3 Target: 0.77-0.80 F1** (+13-17% improvement)

### Phase 4 (Week 4): Polish & Deploy
**Estimated Improvement: +0.01-0.02 F1**

1. **Ensemble if Needed** (2 days)
   - Voting or stacking
   - Only if multiple models strong

2. **Final Evaluation** (1 day)
   - Test set performance
   - Error analysis
   - Feature importance review

3. **Production Prep** (2 days)
   - Save all models
   - Create unified prediction API
   - Documentation

**Week 4 Target: 0.78-0.82 F1** (Final goal: match or beat pitcher model)

---

## Alternative: 3-Class System (If 4-Class Struggles)

If after Phases 1-3 we still can't break 0.75 F1:

**Collapse to 3-Class:**
- Bench (FV 35-40)
- Part-Time (FV 45)
- MLB Regular (FV 50+)

**Expected F1:** 0.72-0.75 (removes impossible All-Star task)

**Trade-off:** Less granularity, but more reliable predictions.

---

## Expected Final Performance

### Optimistic Scenario (All improvements work)

| Improvement | F1 Gain | Cumulative F1 |
|-------------|---------|---------------|
| Baseline | - | 0.684 |
| + Enhanced features | +0.03 | 0.714 |
| + Better SMOTE | +0.02 | 0.734 |
| + Position-specific | +0.05 | 0.784 |
| + XGBoost tuning | +0.03 | **0.814** |

**Best Case: 0.81 F1** (exceeds pitcher model!)

### Realistic Scenario

| Improvement | F1 Gain | Cumulative F1 |
|-------------|---------|---------------|
| Baseline | - | 0.684 |
| + Enhanced features | +0.02 | 0.704 |
| + Better SMOTE | +0.015 | 0.719 |
| + Position-specific | +0.04 | 0.759 |
| + XGBoost tuning | +0.02 | **0.779** |

**Realistic: 0.78 F1** (+14% improvement, matches pitcher baseline)

### Conservative Scenario

| Improvement | F1 Gain | Cumulative F1 |
|-------------|---------|---------------|
| Baseline | - | 0.684 |
| + Enhanced features | +0.015 | 0.699 |
| + Position-specific | +0.03 | 0.729 |
| + XGBoost tuning | +0.015 | **0.744** |

**Conservative: 0.74 F1** (+9% improvement, "Excellent" threshold achieved)

---

## Success Criteria

**Minimum Acceptable (0.72 F1):**
- ✅ Exceed 0.70 "Excellent" threshold
- ✅ Reduce Part-Time false negatives by 20%
- ✅ Improve Part-Time recall from 23% to 30%

**Target (0.75 F1):**
- 🎯 Match pitcher baseline (0.767)
- 🎯 Part-Time recall 35%+
- 🎯 Regular recall 40%+

**Stretch Goal (0.80+ F1):**
- 🌟 Beat pitcher hierarchical model (0.809)
- 🌟 Part-Time F1 > 0.40
- 🌟 Regular F1 > 0.45

---

## Next Steps

**Start with Phase 1 (Enhanced Features):**
1. Create new feature engineering script
2. Add plus_tool_count, offensive_ceiling, etc.
3. Retrain RF model
4. Evaluate improvement

**Commands:**
```bash
# Create enhanced features
python scripts/create_enhanced_hitter_features.py

# Retrain with new features
python scripts/train_baseline_model_v2.py --player-type hitters --enhanced-features

# Compare to baseline
python scripts/compare_models.py --baseline v1 --new v2
```

**Would you like me to implement Phase 1 (Enhanced Feature Engineering) now?**
