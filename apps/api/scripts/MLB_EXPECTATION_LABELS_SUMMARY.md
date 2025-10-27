# MLB Expectation Labels - Summary Report

**Date:** October 19, 2025
**Status:** ✅ COMPLETE
**Database Table:** `mlb_expectation_labels`
**CSV Export:** `mlb_expectation_labels_2025.csv`

---

## Label Distribution

### Overall (All Prospects)

| Class | Count | Percentage |
|-------|-------|------------|
| **All-Star** | 7 | 0.6% |
| **Regular** | 88 | 6.9% |
| **Part-Time** | 177 | 14.0% |
| **Bench** | 995 | 78.5% |
| **TOTAL** | 1,267 | 100% |

### By Player Type

| Class | Hitters | Pitchers | Total |
|-------|---------|----------|-------|
| **All-Star** | 6 | 1 | 7 |
| **Regular** | 49 | 39 | 88 |
| **Part-Time** | 95 | 82 | 177 |
| **Bench** | 684 | 311 | 995 |
| **TOTAL** | 834 | 433 | 1,267 |

---

## Class Definitions

| Class | FV Range | MLB Outcome | WAR Range |
|-------|----------|-------------|-----------|
| **All-Star** | 60-70 | Elite player, perennial All-Star | 5+ WAR |
| **Regular** | 50-55 | Above-average starter | 2-4 WAR |
| **Part-Time** | 45 | Role player, platoon/specialist | 0.5-2 WAR |
| **Bench** | 35-40 | Backup/replacement level | 0-0.5 WAR |

---

## Example Players by Class

### Hitters

**All-Star (FV 60+):**
- Konnor Griffin (FV 65) - Hit:45 Power:70 Speed:70
- Jesús Made (FV 65) - Hit:60 Power:60 Speed:45
- Max Clark (FV 60) - Hit:60 Power:45 Speed:70

**Regular (FV 50-55):**
- Carson Williams (FV 55) - Hit:35 Power:55 Speed:55
- Bryce Eldridge (FV 55) - Hit:40 Power:70 Speed:30
- Colt Emerson (FV 55) - Hit:55 Power:50 Speed:50

**Part-Time (FV 45):**
- Justin Crawford (FV 45) - Hit:50 Power:30 Speed:70
- Andrew Fischer (FV 45) - Hit:40 Power:55 Speed:45
- Luis Lara (FV 45) - Hit:50 Power:35 Speed:60

**Bench (FV 35-40):**
- Ryan Ignoffo (FV 40) - Hit:45 Power:30 Speed:40
- Esmil Valencia (FV 40) - Hit:55 Power:45 Speed:45
- Tirso Ornelas (FV 40) - Hit:45 Power:45 Speed:45

### Pitchers

**All-Star (FV 60+):**
- Bubba Chandler (FV 60) - FB:70 CMD:45 Velo:99 Best Secondary:70

**Regular (FV 50-55):**
- Nolan McLean (FV 55) - FB:55 CMD:60 Velo:96 Best Secondary:70
- Liam Doyle (FV 55) - FB:70 CMD:45 Velo:98 Best Secondary:60
- Noah Schultz (FV 55) - FB:55 CMD:50 Velo:97 Best Secondary:70

**Part-Time (FV 45):**
- Andrew Morris (FV 45) - FB:60 CMD:50 Velo:96 Best Secondary:55
- Gary Gill Hill (FV 45) - FB:50 CMD:60 Velo:95 Best Secondary:60
- Owen Hall (FV 45) - FB:60 CMD:45 Velo:94 Best Secondary:60

**Bench (FV 35-40):**
- Micah Bucknam (FV 40) - FB:50 CMD:40 Velo:94 Best Secondary:70
- Janero Miller (FV 40) - FB:60 CMD:40 Velo:94 Best Secondary:60
- Craig Yoho (FV 40) - FB:50 CMD:40 Velo:94 Best Secondary:70

---

## Class Imbalance Challenge

### The Problem

The dataset is **heavily imbalanced**:
- **All-Star class:** Only 0.6% of data (7 players)
- **Bench class:** 78.5% of data (995 players)

This makes machine learning challenging because:
1. Models will tend to predict "Bench" for everyone
2. "All-Star" predictions will have low recall
3. Standard accuracy metrics will be misleading

### Solutions

1. **Use Weighted Metrics**
   - F1-score (weighted by class)
   - Class-specific precision/recall
   - Don't rely on overall accuracy

2. **Apply Class Balancing**
   - **SMOTE** (Synthetic Minority Over-sampling)
   - **Class weights** in model training
   - **Stratified sampling** for train/val/test splits

3. **Hierarchical Classification**
   - Stage 1: Good vs Limited (binary)
   - Stage 2a: All-Star vs Regular
   - Stage 2b: Part-Time vs Bench

4. **Ensemble Methods**
   - Combine multiple models
   - Threshold tuning per class
   - Calibration adjustments

---

## Database Schema

### Table: `mlb_expectation_labels`

```sql
CREATE TABLE mlb_expectation_labels (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),

    -- Label info
    mlb_expectation VARCHAR(20) NOT NULL,  -- 'All-Star', 'Regular', 'Part-Time', 'Bench'
    mlb_expectation_numeric INTEGER NOT NULL,  -- 0=Bench, 1=Part-Time, 2=Regular, 3=All-Star

    -- Source
    fv INTEGER NOT NULL,  -- Future Value grade from Fangraphs
    data_year INTEGER NOT NULL DEFAULT 2025,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_expectation CHECK (
        mlb_expectation IN ('All-Star', 'Regular', 'Part-Time', 'Bench')
    ),
    CONSTRAINT valid_numeric CHECK (
        mlb_expectation_numeric BETWEEN 0 AND 3
    ),
    CONSTRAINT valid_fv CHECK (
        fv BETWEEN 35 AND 70
    ),

    -- One label per prospect per year
    UNIQUE(prospect_id, data_year)
);

-- Indexes for fast lookup
CREATE INDEX idx_expectation_labels_prospect ON mlb_expectation_labels(prospect_id);
CREATE INDEX idx_expectation_labels_class ON mlb_expectation_labels(mlb_expectation);
```

### Sample Query

```sql
-- Get all prospects with their MLB expectation
SELECT
    p.name,
    p.position,
    p.organization,
    l.mlb_expectation,
    l.fv,
    fg.hit_future,
    fg.game_power_future,
    fg.speed_future
FROM prospects p
JOIN mlb_expectation_labels l ON p.id = l.prospect_id
LEFT JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
WHERE l.data_year = 2025
AND l.mlb_expectation IN ('All-Star', 'Regular')
ORDER BY l.fv DESC;
```

---

## Files Generated

| File | Location | Description |
|------|----------|-------------|
| `create_mlb_expectation_labels.py` | `apps/api/scripts/` | Label generation script |
| `mlb_expectation_labels_2025.csv` | `apps/api/` | Exported labels for ML training |
| `MLB_EXPECTATION_CLASSIFICATION_GUIDE.md` | `apps/api/scripts/` | Full ML implementation guide |
| `MLB_EXPECTATION_LABELS_SUMMARY.md` | `apps/api/scripts/` | This document |

---

## Next Steps for ML Training

### 1. Feature Engineering (Week 1)

Combine labels with features:
```sql
SELECT
    l.mlb_expectation_numeric as target,

    -- Fangraphs grades
    fg.hit_future,
    fg.game_power_future,
    fg.speed_future,
    fg.fielding_future,

    -- Physical attributes
    phys.frame_grade,
    phys.athleticism_grade,

    -- Performance stats (2024 season)
    gl.ops,
    gl.batting_avg,
    gl.home_runs,
    gl.stolen_bases,

    -- Age-relative features
    EXTRACT(YEAR FROM AGE(DATE('2024-07-01'), p.birth_date)) as age,
    gl.level

FROM mlb_expectation_labels l
JOIN prospects p ON l.prospect_id = p.id
JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
LEFT JOIN fangraphs_physical_attributes phys ON p.fg_player_id = phys.fangraphs_player_id
LEFT JOIN milb_game_logs gl ON p.mlb_player_id = gl.mlb_player_id::varchar
WHERE l.data_year = 2025
AND gl.season = 2024
AND p.position NOT IN ('SP', 'RP');
```

### 2. Handle Class Imbalance (Week 2)

```python
from imblearn.over_sampling import SMOTE
from sklearn.utils.class_weight import compute_class_weight

# Apply SMOTE to oversample minority classes
smote = SMOTE(sampling_strategy='auto', random_state=42)
X_train_balanced, y_train_balanced = smote.fit_resample(X_train, y_train)

# Or use class weights
class_weights = compute_class_weight(
    'balanced',
    classes=np.unique(y_train),
    y=y_train
)
```

### 3. Train Models (Weeks 3-4)

```python
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier

# XGBoost with class weights
xgb_model = XGBClassifier(
    objective='multi:softmax',
    num_class=4,
    scale_pos_weight=class_weights,
    max_depth=5,
    learning_rate=0.05,
    n_estimators=200
)

xgb_model.fit(X_train, y_train)

# Evaluate
from sklearn.metrics import classification_report, f1_score

y_pred = xgb_model.predict(X_val)
print(classification_report(
    y_val, y_pred,
    target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']
))

# Weighted F1 (most important metric)
f1_weighted = f1_score(y_val, y_pred, average='weighted')
print(f"Weighted F1-Score: {f1_weighted:.3f}")
```

### 4. Feature Importance Analysis

```python
import pandas as pd
import matplotlib.pyplot as plt

# Get feature importance
feature_importance = pd.DataFrame({
    'feature': feature_names,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 10 Most Important Features:")
print(feature_importance.head(10))

# Plot
plt.figure(figsize=(10, 6))
feature_importance.head(15).plot(x='feature', y='importance', kind='barh')
plt.title('Feature Importance - MLB Expectation Classification')
plt.xlabel('Importance')
plt.tight_layout()
plt.savefig('feature_importance.png')
```

### 5. Model Evaluation

**Expected Performance:**
- Weighted F1-Score: 0.55-0.70
- All-Star F1: 0.30-0.50 (hardest class)
- Regular F1: 0.40-0.60
- Part-Time F1: 0.50-0.65
- Bench F1: 0.70-0.85 (easiest class)

**Comparison to Scouting:**
- Agreement within 1 class: 80-90%
- Exact match: 50-65%

---

## Key Insights

### Class Distribution Insights

1. **Only 1 All-Star pitcher** (Bubba Chandler, FV 60)
   - Makes pitcher All-Star prediction extremely challenging
   - May need to combine with Regular class initially

2. **All-Star hitters have diverse profiles:**
   - Power + Speed (Konnor Griffin: Pwr:70 Spd:70)
   - Hit tool + Power (Jesús Made: Hit:60 Pwr:60)
   - Hit tool + Speed (Max Clark: Hit:60 Spd:70)
   - Shows different paths to stardom

3. **Part-Time class is well-represented** (14% of data)
   - Provides good training signal
   - Most realistic outcome for many prospects

4. **Bench class dominates** (78.5%)
   - Reflects reality: most prospects don't become stars
   - Need to avoid "predict Bench for everyone" trap

### FV to MLB Expectation Mapping

The mapping used:
- **FV 60-70 → All-Star:** Only 7 players (0.6%)
- **FV 50-55 → Regular:** 88 players (6.9%)
- **FV 45 → Part-Time:** 177 players (14.0%)
- **FV 35-40 → Bench:** 995 players (78.5%)

This aligns with Fangraphs' stated outcomes for each FV grade.

---

## Success Criteria

### Model Performance Goals

1. **Weighted F1-Score > 0.60**
   - Accounts for class imbalance
   - Better than random baseline

2. **All-Star Recall > 0.50**
   - Don't miss the stars!
   - Most critical class for dynasty value

3. **Regular F1 > 0.50**
   - Everyday players are valuable
   - Second most important class

4. **Agreement with FV within 1 class > 85%**
   - Model shouldn't dramatically disagree with scouts
   - If predicting "Regular" when actual is "All-Star" → acceptable
   - If predicting "Bench" when actual is "All-Star" → bad

### Business Impact Goals

1. **Identify undervalued prospects**
   - Model predicts "All-Star", scouts say "Regular"
   - Target for dynasty leagues

2. **Identify overvalued prospects**
   - Model predicts "Part-Time", scouts say "Regular"
   - Avoid or trade away

3. **Risk assessment**
   - Probability distributions matter
   - 60% Bench, 30% Part-Time, 10% Regular → risky
   - 40% Regular, 40% Part-Time, 20% All-Star → high upside

---

## Summary

✅ **Labels Generated:** 1,267 prospects with MLB expectation classifications
✅ **Database Table Created:** `mlb_expectation_labels` with proper indexes
✅ **CSV Export:** Ready for ML training pipelines
✅ **Documentation:** Complete implementation guide available

**The foundation is set for multi-class MLB expectation prediction!**

Next: Combine with MiLB performance data and train classification models.

---

**Generated By:** BMad Party Mode Team
**Date:** October 19, 2025
**Status:** ✅ READY FOR ML TRAINING
