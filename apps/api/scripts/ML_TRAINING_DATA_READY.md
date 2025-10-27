# ML Training Data Ready - Complete Report

**Date:** October 19, 2025
**Status:** ✅ READY FOR MODEL TRAINING

---

## Executive Summary

Successfully created **train/validation/test datasets** with proper temporal validation for MLB Expectation Classification machine learning models. All data combines Fangraphs scouting grades with MiLB performance statistics across 4 years (2022-2025).

---

## Dataset Overview

### Files Created

| Split | Hitters File | Pitchers File |
|-------|--------------|---------------|
| **Train (2022-2023)** | `ml_data_hitters_train_20251019_214927.csv`<br>338 prospects, 46 features | `ml_data_pitchers_train_20251019_214927.csv`<br>334 prospects, 43 features |
| **Validation (2024)** | `ml_data_hitters_val_20251019_214927.csv`<br>363 prospects, 46 features | `ml_data_pitchers_val_20251019_214927.csv`<br>347 prospects, 43 features |
| **Test (2025)** | `ml_data_hitters_test_20251019_214928.csv`<br>601 prospects, 46 features | `ml_data_pitchers_test_20251019_214928.csv`<br>667 prospects, 43 features |

### Sample Counts by Split

| Split | Years | Hitters | Pitchers | **Total** |
|-------|-------|---------|----------|-----------|
| **Training** | 2022-2023 | 338 | 334 | **672** |
| **Validation** | 2024 | 363 | 347 | **710** |
| **Test** | 2025 | 601 | 667 | **1,268** |
| **TOTAL** | 2022-2025 | **1,302** | **1,348** | **2,650** |

### Class Distribution

**Hitters:**

| Split | All-Star | Regular | Part-Time | Bench |
|-------|----------|---------|-----------|-------|
| Train (2022-2023) | 0 | 30 (8.9%) | 90 (26.6%) | 218 (64.5%) |
| Validation (2024) | 4 (1.1%) | 37 (10.2%) | 72 (19.8%) | 250 (68.9%) |
| Test (2025) | 6 (1.0%) | 49 (8.2%) | 92 (15.3%) | 454 (75.5%) |

**Pitchers:**

| Split | All-Star | Regular | Part-Time | Bench |
|-------|----------|---------|-----------|-------|
| Train (2022-2023) | 2 (0.6%) | 12 (3.6%) | 51 (15.3%) | 269 (80.5%) |
| Validation (2024) | 1 (0.3%) | 23 (6.6%) | 51 (14.7%) | 272 (78.4%) |
| Test (2025) | 1 (0.1%) | 39 (5.8%) | 85 (12.7%) | 542 (81.3%) |

**Key Observation:** Severe class imbalance, especially for All-Star class (<1% of samples). **MUST use class weighting and/or SMOTE.**

---

## Feature Set

### Hitter Features (46 total)

**Metadata (5):**
- prospect_id, data_year, name, position, fangraphs_id

**Target Variables (3):**
- target (0-3 numeric)
- target_label (All-Star/Regular/Part-Time/Bench)
- fangraphs_fv (original Future Value 35-70)

**Fangraphs Tool Grades - Future (9):**
- hit_future, game_power_future, raw_power_future
- speed_future, fielding_future, versatility_future
- pitch_sel_future, bat_ctrl_future, hard_hit_pct

**Development Upside (4):**
- hit_upside, power_upside, speed_upside, fielding_upside
- (Future grade - Current grade = room for improvement)

**Physical Attributes (4):**
- frame_grade, athleticism_grade, arm_grade, levers_encoded

**Prior Season Performance - MiLB (13):**
- total_pa, total_ab, total_hr, total_sb
- avg_obp, avg_slg, batting_avg
- isolated_power, bb_k_ratio, k_rate, bb_rate
- power_speed_number
- highest_level (1-5 encoding)

**Level Context (4):**
- played_aaa, played_aa, played_a_plus (binary flags)
- avg_age

**Year-over-Year Changes (4):**
- fv_change_1yr, hit_change, power_change, speed_change

### Pitcher Features (43 total)

**Metadata (5):**
- prospect_id, data_year, name, position, fangraphs_id

**Target Variables (3):**
- target (0-3 numeric)
- target_label
- fangraphs_fv

**Fangraphs Pitch Grades - Future (5):**
- fb_future, sl_future, cb_future, ch_future, cmd_future

**Development Upside (2):**
- fb_upside, cmd_upside

**Velocity (4):**
- velocity_sits_low, velocity_sits_high, velocity_tops, velocity_avg

**Pitch Arsenal (1):**
- plus_pitch_count (number of pitches graded 55+)

**Physical Attributes (4):**
- frame_grade, athleticism_grade, arm_grade, delivery_grade

**Injury History (1):**
- has_tj_surgery (Tommy John surgery flag)

**Prior Season Performance - MiLB (9):**
- total_ip, era, whip
- k_per_9, bb_per_9, k_bb_ratio
- total_k, total_bb, total_hr_allowed

**Level Context (5):**
- played_aaa, played_aa, played_a_plus (binary flags)
- highest_level (1-5 encoding)
- avg_age

**Year-over-Year Changes (4):**
- fv_change_1yr, fb_change, cmd_change, velo_change

---

## Data Quality Notes

### Missing Data Expected in:

1. **Prior Season Stats:** Prospects who didn't play in MiLB the prior year (e.g., 2022 labels missing 2021 stats)
   - International signees who just arrived
   - High school/college draftees (first year in minors)
   - Injured prospects who missed the season

2. **Year-over-Year Changes:** Prospects new to Fangraphs board (no prior year grades)
   - First-time ranked prospects
   - Will show 0 change (comparing to themselves)

3. **Physical Attributes:** Not all prospects have physical grades
   - Older prospects may lack frame/athleticism ratings
   - Some prospects missing from physical CSV files

### Handling Missing Data

**Recommended Strategy:**

```python
import pandas as pd
from sklearn.impute import SimpleImputer

# Load data
train_df = pd.read_csv('ml_data_hitters_train_20251019_214927.csv')

# Separate features from metadata and target
metadata_cols = ['prospect_id', 'data_year', 'name', 'position', 'fangraphs_id']
target_cols = ['target', 'target_label', 'fangraphs_fv']
feature_cols = [c for c in train_df.columns if c not in metadata_cols + target_cols]

X_train = train_df[feature_cols]
y_train = train_df['target']

# Impute missing values
# Option 1: Median imputation (robust to outliers)
imputer = SimpleImputer(strategy='median')
X_train_imputed = imputer.fit_transform(X_train)

# Option 2: Drop rows with ANY missing performance stats
# (Only use if you want to restrict to prospects with recent game logs)
train_df_complete = train_df.dropna(subset=['total_pa', 'avg_obp', 'avg_slg'])

# Option 3: Create "missing indicator" features
# (Let model learn that missing data is informative)
for col in ['total_pa', 'fv_change_1yr']:
    train_df[f'{col}_is_missing'] = train_df[col].isna().astype(int)
train_df.fillna(0, inplace=True)
```

---

## Next Steps: Model Training Pipeline

### Step 1: Data Preprocessing (Week 1, Days 1-2)

**Script:** `preprocess_ml_data.py`

```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from imblearn.over_sampling import SMOTENC

# Load training data
train_hitters = pd.read_csv('ml_data_hitters_train_20251019_214927.csv')

# 1. Handle missing values
imputer = SimpleImputer(strategy='median')
numeric_features = [col for col in train_hitters.columns if train_hitters[col].dtype in ['int64', 'float64']]
train_hitters[numeric_features] = imputer.fit_transform(train_hitters[numeric_features])

# 2. Encode categorical variables
position_dummies = pd.get_dummies(train_hitters['position'], prefix='pos')
train_hitters = pd.concat([train_hitters, position_dummies], axis=1)

# 3. Normalize features (XGBoost doesn't require this, but helps with interpretation)
scaler = StandardScaler()
scaled_features = scaler.fit_transform(train_hitters[numeric_features])

# 4. Address class imbalance with SMOTE
X_train = train_hitters.drop(['target', 'target_label', 'fangraphs_fv', 'name', 'fangraphs_id'], axis=1)
y_train = train_hitters['target']

smote = SMOTENC(categorical_features=[...], random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

print(f"Original class distribution: {np.bincount(y_train)}")
print(f"Resampled class distribution: {np.bincount(y_train_resampled)}")
```

### Step 2: Baseline Model (Week 1, Days 3-4)

**Script:** `train_baseline_model.py`

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score

# Train Random Forest baseline
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=20,
    class_weight='balanced',  # Handle class imbalance
    random_state=42
)

rf.fit(X_train_resampled, y_train_resampled)

# Evaluate on validation set
val_hitters = pd.read_csv('ml_data_hitters_val_20251019_214927.csv')
# ... preprocess val data same way as train ...

y_val_pred = rf.predict(X_val)
y_val_true = val_hitters['target']

# Metrics
print(classification_report(y_val_true, y_val_pred,
    target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']))

f1_weighted = f1_score(y_val_true, y_val_pred, average='weighted')
print(f"Weighted F1-Score: {f1_weighted:.3f}")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': X_train.columns,
    'importance': rf.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 10 Most Important Features:")
print(feature_importance.head(10))
```

### Step 3: XGBoost Model (Week 1, Days 5-7)

**Script:** `train_xgboost_model.py`

```python
import xgboost as xgb
from sklearn.utils.class_weight import compute_class_weight
from sklearn.model_selection import GridSearchCV

# Calculate class weights
class_weights = compute_class_weight(
    'balanced',
    classes=np.unique(y_train),
    y=y_train
)

# Create sample weights
sample_weights = np.array([class_weights[y] for y in y_train])

# XGBoost with hyperparameter tuning
param_grid = {
    'max_depth': [3, 5, 7],
    'learning_rate': [0.01, 0.05, 0.1],
    'n_estimators': [100, 200, 500],
    'min_child_weight': [1, 3, 5],
    'gamma': [0, 0.1, 0.2],
    'subsample': [0.8, 0.9],
    'colsample_bytree': [0.8, 0.9]
}

xgb_model = xgb.XGBClassifier(
    objective='multi:softmax',
    num_class=4,
    random_state=42
)

grid_search = GridSearchCV(
    xgb_model,
    param_grid,
    cv=5,
    scoring='f1_weighted',
    n_jobs=-1,
    verbose=2
)

grid_search.fit(X_train, y_train, sample_weight=sample_weights)

print(f"Best params: {grid_search.best_params_}")
print(f"Best CV F1: {grid_search.best_score_:.3f}")

# Final model evaluation on test set (ONLY ONCE!)
best_model = grid_search.best_estimator_
test_hitters = pd.read_csv('ml_data_hitters_test_20251019_214928.csv')
# ... preprocess test data ...

y_test_pred = best_model.predict(X_test)
y_test_true = test_hitters['target']

print("\n=== FINAL TEST SET RESULTS ===")
print(classification_report(y_test_true, y_test_pred,
    target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']))

f1_test = f1_score(y_test_true, y_test_pred, average='weighted')
print(f"Test Weighted F1-Score: {f1_test:.3f}")
```

### Step 4: Model Interpretation (Week 2, Days 1-3)

**Script:** `analyze_model_predictions.py`

```python
import shap

# SHAP values for interpretability
explainer = shap.TreeExplainer(best_model)
shap_values = explainer.shap_values(X_test)

# Summary plot (feature importance)
shap.summary_plot(shap_values, X_test, plot_type="bar")

# Individual prediction explanation
sample_idx = 0  # First test prospect
shap.force_plot(
    explainer.expected_value,
    shap_values[sample_idx],
    X_test.iloc[sample_idx],
    feature_names=X_test.columns
)

# Analyze misclassifications
errors = test_hitters[y_test_true != y_test_pred].copy()
errors['predicted'] = y_test_pred[y_test_true != y_test_pred]
errors['actual'] = y_test_true[y_test_true != y_test_pred]

print("\n=== MISCLASSIFIED PROSPECTS ===")
print(errors[['name', 'fangraphs_fv', 'predicted', 'actual']].head(20))

# Common error patterns
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(y_test_true, y_test_pred)
print("\nConfusion Matrix:")
print(cm)
# Rows = True class, Columns = Predicted class
```

---

## Expected Performance Benchmarks

### Baseline (Random Forest)

| Metric | Training (2022-2023) | Validation (2024) | Test (2025) |
|--------|----------------------|-------------------|-------------|
| **Weighted F1** | 0.68-0.74 | 0.62-0.68 | 0.60-0.66 |
| **All-Star Recall** | 0.40-0.60 | 0.25-0.50 | 0.17-0.33 |
| **Regular Recall** | 0.45-0.60 | 0.35-0.50 | 0.30-0.45 |
| **Part-Time Recall** | 0.50-0.65 | 0.45-0.60 | 0.40-0.55 |
| **Bench Recall** | 0.80-0.90 | 0.75-0.85 | 0.70-0.82 |

### Optimized XGBoost (with SMOTE + Class Weights)

| Metric | Training (2022-2023) | Validation (2024) | Test (2025) |
|--------|----------------------|-------------------|-------------|
| **Weighted F1** | 0.72-0.78 | 0.68-0.74 | 0.65-0.72 |
| **All-Star Recall** | 0.50-0.70 | 0.40-0.60 | 0.33-0.50 |
| **Regular Recall** | 0.55-0.70 | 0.50-0.65 | 0.45-0.60 |
| **Part-Time Recall** | 0.60-0.75 | 0.55-0.70 | 0.50-0.65 |
| **Bench Recall** | 0.85-0.92 | 0.82-0.90 | 0.80-0.88 |

**Success Criteria:**
- ✅ **Minimum:** Test Weighted F1 > 0.65
- ✅ **Good:** Test Weighted F1 > 0.70
- 🎯 **Excellent:** Test Weighted F1 > 0.75

---

## Production Deployment Plan

### Phase 1: API Integration (Week 3)

Create FastAPI endpoint in `apps/api/src/routes/ml_predictions.py`:

```python
from fastapi import APIRouter, HTTPException
import joblib
import pandas as pd

router = APIRouter(prefix="/ml", tags=["Machine Learning"])

# Load trained model (do this at startup, not per request)
hitter_model = joblib.load('models/xgboost_hitter_classifier_v1.pkl')
pitcher_model = joblib.load('models/xgboost_pitcher_classifier_v1.pkl')

@router.get("/prospects/{prospect_id}/predict-expectation")
async def predict_mlb_expectation(prospect_id: int):
    """
    Predict MLB expectation for a prospect using ML model.

    Returns:
    {
        "prospect_id": 123,
        "prospect_name": "John Smith",
        "position": "SS",
        "fangraphs_fv": 50,
        "predictions": {
            "All-Star": 0.05,
            "Regular": 0.25,
            "Part-Time": 0.40,
            "Bench": 0.30
        },
        "predicted_class": "Part-Time",
        "confidence": 0.40
    }
    """

    # 1. Fetch prospect data from database
    prospect = await get_prospect_with_features(prospect_id)

    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    # 2. Determine if hitter or pitcher
    is_pitcher = prospect['position'] in ['SP', 'RP']
    model = pitcher_model if is_pitcher else hitter_model

    # 3. Prepare features (same preprocessing as training)
    features = prepare_features(prospect)

    # 4. Get predictions
    proba = model.predict_proba(features)[0]

    return {
        "prospect_id": prospect_id,
        "prospect_name": prospect['name'],
        "position": prospect['position'],
        "fangraphs_fv": prospect['fv'],
        "predictions": {
            "Bench": float(proba[0]),
            "Part-Time": float(proba[1]),
            "Regular": float(proba[2]),
            "All-Star": float(proba[3])
        },
        "predicted_class": ["Bench", "Part-Time", "Regular", "All-Star"][proba.argmax()],
        "confidence": float(proba.max())
    }


@router.get("/prospects/top-breakouts")
async def get_top_breakouts(limit: int = 20):
    """
    Find prospects most likely to outperform their Fangraphs grade.

    Identifies prospects where ML model predicts higher expectation than FV suggests.
    """

    prospects = await get_all_prospects_with_predictions()

    # Calculate disagreement score
    for p in prospects:
        fv_implied_class = map_fv_to_class(p['fangraphs_fv'])
        ml_predicted_class = p['predicted_class']

        # Score = how many classes higher ML predicts
        p['breakout_score'] = ml_predicted_class - fv_implied_class

    # Return top breakout candidates
    breakouts = sorted(prospects, key=lambda x: x['breakout_score'], reverse=True)[:limit]

    return breakouts
```

### Phase 2: Frontend Integration (Week 4)

Add ML predictions to prospect profile pages:

```tsx
// apps/web/src/components/ProspectProfile.tsx

function ProspectMLPrediction({ prospectId }: { prospectId: number }) {
  const { data, loading } = useQuery(GET_ML_PREDICTION, {
    variables: { prospectId }
  });

  if (loading) return <Spinner />;

  const { predictions, predicted_class, confidence } = data.mlPrediction;

  return (
    <Card title="ML-Based Projection">
      <div className="flex justify-between">
        <div>
          <h3 className="font-bold text-lg">{predicted_class}</h3>
          <p className="text-sm text-gray-500">
            {(confidence * 100).toFixed(1)}% confidence
          </p>
        </div>

        <ProbabilityChart data={predictions} />
      </div>

      {/* Show if ML disagrees with Fangraphs */}
      {predicted_class !== data.prospect.fangraphsImpliedClass && (
        <Alert variant="info">
          <InfoIcon />
          <span>
            ML model projects higher upside than Fangraphs grade suggests.
            Consider as potential breakout candidate.
          </span>
        </Alert>
      )}
    </Card>
  );
}
```

---

## Files Summary

**Data Files Created (6):**
1. `ml_data_hitters_train_20251019_214927.csv` (79 KB, 338 rows, 46 features)
2. `ml_data_pitchers_train_20251019_214927.csv` (66 KB, 334 rows, 43 features)
3. `ml_data_hitters_val_20251019_214927.csv` (93 KB, 363 rows, 46 features)
4. `ml_data_pitchers_val_20251019_214927.csv` (74 KB, 347 rows, 43 features)
5. `ml_data_hitters_test_20251019_214928.csv` (142 KB, 601 rows, 46 features)
6. `ml_data_pitchers_test_20251019_214928.csv` (140 KB, 667 rows, 43 features)

**Scripts Created:**
- `create_ml_training_data.py` - Feature extraction from database to CSV
- `verify_temporal_data.py` - Data verification and validation
- `migrate_fangraphs_grades.py` - Initial 2025 grades import
- `import_historical_fangraphs_grades.py` - Historical 2022-2024 import
- `create_multi_year_mlb_expectation_labels.py` - Label generation

**Documentation:**
- `TEMPORAL_VALIDATION_READY_REPORT.md` - Multi-year setup report
- `ML_MIGRATION_COMPLETE_SUMMARY.md` - Database schema and ML readiness
- `MLB_EXPECTATION_CLASSIFICATION_GUIDE.md` - Complete ML implementation guide (40+ pages)
- `ML_TRAINING_DATA_READY.md` - This document

---

## Status: ✅ READY FOR MODEL TRAINING

All data preparation is complete. The ML training datasets are ready for:

1. ✅ Preprocessing and feature engineering
2. ✅ Baseline model training (Random Forest)
3. ✅ XGBoost hyperparameter tuning
4. ✅ Model evaluation and interpretation
5. ✅ Production deployment via API

**Next Action:** Begin model training pipeline with preprocessing script.

---

**Generated:** October 19, 2025
**Total Prospects:** 2,650 across 4 years
**Total Features:** 46 (hitters), 43 (pitchers)
**Temporal Splits:** Train (2022-2023) → Val (2024) → Test (2025)
