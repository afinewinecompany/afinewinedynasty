# Temporal Validation Ready - Complete Status Report

**Date:** October 19, 2025
**Status:** ✅ ALL SYSTEMS GO FOR ML MODEL TRAINING

---

## Executive Summary

Successfully transformed the Fangraphs grades database from single-year (2025 only) to **multi-year temporal dataset (2022-2025)**, enabling proper temporal validation for machine learning models.

### What Changed

**Before:**
- Only 2025 Fangraphs grades available
- 1,267 labeled prospects (single year)
- Required K-Fold cross-validation (no temporal split possible)
- Risk of data leakage across time periods

**After:**
- 4 years of Fangraphs grades (2022-2025)
- 2,650 labeled prospects across all years
- **207 prospects tracked for all 4 years**
- **745 prospects tracked for 2+ years**
- True temporal validation possible: Train 2022-2023 → Validate 2024 → Test 2025

---

## Database Status

### Fangraphs Grades Tables

**Multi-Year Schema Enabled:**
```sql
-- All tables now support multi-year tracking
-- Composite UNIQUE constraint: (fangraphs_player_id, data_year)
```

| Table | 2022 | 2023 | 2024 | 2025 | Total |
|-------|------|------|------|------|-------|
| **Hitter Grades** | 602 | 557 | 545 | 605 | 2,309 |
| **Pitcher Grades** | 637 | 573 | 542 | 671 | 2,423 |
| **Physical Attributes** | 1,237 | 1,129 | 1,086 | 1,275 | 4,727 |

### MLB Expectation Labels

**4-Class System:** All-Star (FV 60+) | Regular (FV 50-55) | Part-Time (FV 45) | Bench (FV 35-40)

| Year | All-Star | Regular | Part-Time | Bench | **Total** |
|------|----------|---------|-----------|-------|-----------|
| 2022 | 1 (0.4%) | 16 (6.6%) | 46 (19.0%) | 179 (74.0%) | **242** |
| 2023 | 1 (0.2%) | 26 (6.1%) | 95 (22.1%) | 307 (71.6%) | **429** |
| 2024 | 5 (0.7%) | 60 (8.5%) | 123 (17.3%) | 522 (73.5%) | **710** |
| 2025 | 7 (0.6%) | 88 (6.9%) | 177 (14.0%) | 995 (78.5%) | **1,267** |
| **Total** | **14** | **190** | **441** | **2,003** | **2,650** |

### Multi-Year Tracking Coverage

- **1,269 unique prospects** with at least one year of labels
- **207 prospects** tracked for all 4 years (2022-2025)
- **427 prospects** tracked for 3+ years
- **745 prospects** tracked for 2+ years

This is **ideal for longitudinal analysis** - we can track how prospect grades evolve over time and validate if early-career grades predict future MLB success.

---

## Temporal Validation Strategy

### Recommended Split

```python
# Training Set (2022-2023)
train_data = labels[labels['data_year'].isin([2022, 2023])]
# 242 + 429 = 671 labeled prospects

# Validation Set (2024)
val_data = labels[labels['data_year'] == 2024]
# 710 labeled prospects

# Test Set (2025) - TRUE HOLDOUT
test_data = labels[labels['data_year'] == 2025]
# 1,267 labeled prospects
```

### Why This Works

1. **No Data Leakage:** Future data never influences past predictions
2. **Real-World Simulation:** Model trained on 2022-2023 predicts 2024 (validation) and 2025 (test)
3. **Larger Test Set:** 2025 has most prospects (1,267), giving robust evaluation
4. **Temporal Trends:** Can analyze if model degrades over time (2024 vs 2025 performance)

### Query Example

```sql
-- Get training data with all features
SELECT
    l.mlb_expectation,
    l.mlb_expectation_numeric,
    l.fv,

    -- Fangraphs grades (for hitters)
    fg.hit_future,
    fg.game_power_future,
    fg.speed_future,
    fg.fielding_future,

    -- Physical attributes
    phys.frame_grade,
    phys.athleticism_grade,

    -- MiLB performance stats (season prior to label year)
    gl.ops,
    gl.home_runs,
    gl.stolen_bases

FROM mlb_expectation_labels l
JOIN prospects p ON l.prospect_id = p.id
JOIN fangraphs_hitter_grades fg
    ON p.fg_player_id = fg.fangraphs_player_id
    AND fg.data_year = l.data_year
LEFT JOIN fangraphs_physical_attributes phys
    ON p.fg_player_id = phys.fangraphs_player_id
    AND phys.data_year = l.data_year
LEFT JOIN milb_game_logs gl
    ON p.mlb_player_id = gl.mlb_player_id::varchar
    AND gl.season = (l.data_year - 1)  -- Prior season performance
WHERE l.data_year IN (2022, 2023)  -- Training set
AND gl.at_bats >= 50
ORDER BY l.data_year, l.fv DESC;
```

---

## Class Imbalance Analysis

### Problem Severity by Year

| Year | All-Star | Regular | Part-Time | Bench | Imbalance Ratio |
|------|----------|---------|-----------|-------|-----------------|
| 2022 | 0.4% | 6.6% | 19.0% | 74.0% | **179:1** (Bench:All-Star) |
| 2023 | 0.2% | 6.1% | 22.1% | 71.6% | **307:1** |
| 2024 | 0.7% | 8.5% | 17.3% | 73.5% | **104:1** |
| 2025 | 0.6% | 6.9% | 14.0% | 78.5% | **142:1** |

**Status:** Severe class imbalance, especially for All-Star class.

### Recommended Solutions

1. **SMOTE Oversampling:**
   ```python
   from imblearn.over_sampling import SMOTENC

   smote = SMOTENC(
       categorical_features=[...],
       sampling_strategy={
           0: 1500,  # Bench: keep original
           1: 300,   # Part-Time: moderate oversample
           2: 150,   # Regular: aggressive oversample
           3: 50     # All-Star: max oversample
       }
   )
   X_train, y_train = smote.fit_resample(X_train, y_train)
   ```

2. **Class Weights in XGBoost:**
   ```python
   import xgboost as xgb
   from sklearn.utils.class_weight import compute_class_weight

   # Calculate inverse frequency weights
   class_weights = compute_class_weight(
       'balanced',
       classes=np.unique(y_train),
       y=y_train
   )

   # Create sample weights
   sample_weights = np.array([class_weights[y] for y in y_train])

   model = xgb.XGBClassifier(
       objective='multi:softmax',
       num_class=4,
       scale_pos_weight=class_weights  # or use sample_weights in fit()
   )
   ```

3. **Stratified Validation:**
   ```python
   from sklearn.model_selection import StratifiedKFold

   # For within-year cross-validation (if needed)
   skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

   for fold, (train_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
       # Each fold preserves class distribution
       ...
   ```

4. **Evaluation Metrics:**
   ```python
   from sklearn.metrics import classification_report, f1_score

   # Weighted F1 (primary metric)
   f1_weighted = f1_score(y_true, y_pred, average='weighted')

   # Per-class metrics
   print(classification_report(y_true, y_pred,
       target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']))
   ```

---

## Feature Engineering Enhancements

### Temporal Features (Now Possible!)

With multi-year data, we can create powerful temporal features:

```python
# 1. Year-over-year FV change
SELECT
    p.name,
    fg2023.fv - fg2022.fv as fv_change_2022_to_2023,
    fg2024.fv - fg2023.fv as fv_change_2023_to_2024
FROM prospects p
JOIN fangraphs_hitter_grades fg2022 ON p.fg_player_id = fg2022.fangraphs_player_id AND fg2022.data_year = 2022
JOIN fangraphs_hitter_grades fg2023 ON p.fg_player_id = fg2023.fangraphs_player_id AND fg2023.data_year = 2023
JOIN fangraphs_hitter_grades fg2024 ON p.fg_player_id = fg2024.fangraphs_player_id AND fg2024.data_year = 2024
WHERE p.fg_player_id IN (
    SELECT fangraphs_player_id FROM fangraphs_hitter_grades
    GROUP BY fangraphs_player_id HAVING COUNT(DISTINCT data_year) >= 3
);

# 2. Grade trajectory (improving vs declining)
# If FV increased year-over-year → positive momentum
# If FV decreased → red flag

# 3. Consistency of grades
# Low variance across years → stable evaluation
# High variance → uncertain / volatile prospect

# 4. Performance vs scouting alignment
# Did MiLB stats improve when FV increased?
# If stats improved but FV didn't → undervalued prospect
```

### Multi-Season Performance Features

```python
# Aggregate performance over multiple seasons
SELECT
    p.mlb_player_id,

    -- Career totals
    SUM(gl.home_runs) as career_hr,
    SUM(gl.stolen_bases) as career_sb,

    -- Career rate stats (weighted by PA)
    SUM(gl.ops * gl.plate_appearances) / SUM(gl.plate_appearances) as career_ops,

    -- Trend features
    MAX(gl.ops) - MIN(gl.ops) as ops_range,

    -- Level progression speed
    MAX(CASE WHEN gl.level = 'AAA' THEN gl.season END) -
    MIN(gl.season) as years_to_aaa

FROM milb_game_logs gl
JOIN prospects p ON gl.mlb_player_id::varchar = p.mlb_player_id
WHERE gl.season BETWEEN 2021 AND 2023
GROUP BY p.mlb_player_id;
```

---

## Expected Model Performance

### Baseline (Majority Class Classifier)

If we always predict "Bench" (most common class):
- Accuracy: ~74%
- F1-Score: ~42% (weighted)
- All-Star Recall: 0%
- Regular Recall: 0%

**This is unacceptable** - we need to beat this baseline significantly.

### Target Performance (XGBoost with Class Weights + SMOTE)

Based on similar imbalanced classification tasks:

| Metric | Training (2022-2023) | Validation (2024) | Test (2025) |
|--------|----------------------|-------------------|-------------|
| **Weighted F1** | 0.72-0.78 | 0.68-0.74 | 0.65-0.72 |
| **All-Star Recall** | 0.50-0.70 | 0.40-0.60 | 0.35-0.55 |
| **Regular Recall** | 0.55-0.70 | 0.50-0.65 | 0.45-0.60 |
| **Part-Time Recall** | 0.60-0.75 | 0.55-0.70 | 0.50-0.65 |
| **Bench Recall** | 0.85-0.92 | 0.82-0.90 | 0.80-0.88 |

### Success Criteria

**Minimum Acceptable Performance (2025 Test Set):**
- ✅ Weighted F1 > 0.65
- ✅ All-Star Recall > 0.30 (catch at least 2 of 7)
- ✅ Regular Recall > 0.40 (catch at least 35 of 88)
- ✅ Part-Time Recall > 0.45
- ✅ Bench Recall > 0.75

**Excellent Performance:**
- 🎯 Weighted F1 > 0.72
- 🎯 All-Star Recall > 0.50 (catch 4 of 7)
- 🎯 Regular Recall > 0.60 (catch 53 of 88)
- 🎯 All classes have precision > 0.50

---

## Next Steps for ML Implementation

### Phase 1: Data Preparation (Week 1)

**Tasks:**
1. ✅ Multi-year labels created (DONE)
2. Create feature engineering pipeline
   - Combine Fangraphs grades with MiLB performance data
   - Calculate temporal features (FV changes, grade trajectories)
   - Handle missing values (birth dates, physical attributes)
   - Normalize features by position and level
3. Export training/validation/test CSVs
4. Exploratory data analysis
   - Feature correlations
   - Class separability visualization (t-SNE/UMAP)
   - Feature importance analysis (Random Forest baseline)

**Scripts to Create:**
```
apps/api/scripts/
├── create_temporal_training_data.py   # Export train/val/test splits
├── analyze_temporal_features.py       # EDA on multi-year data
└── baseline_model_evaluation.py       # Quick RF baseline
```

### Phase 2: Model Training (Weeks 2-3)

**Tasks:**
1. Train baseline models
   - Random Forest (interpretable baseline)
   - Logistic Regression (linear baseline)
2. Train XGBoost classifier
   - Hyperparameter tuning (grid search or Optuna)
   - Class weight optimization
   - SMOTE variants (SMOTE-Tomek, ADASYN)
3. Train LightGBM classifier (comparison)
4. Ensemble models (voting or stacking)

**Key Hyperparameters to Tune:**
```python
param_grid = {
    'max_depth': [3, 5, 7, 10],
    'learning_rate': [0.01, 0.05, 0.1],
    'n_estimators': [100, 200, 500],
    'min_child_weight': [1, 3, 5],
    'subsample': [0.7, 0.8, 0.9],
    'colsample_bytree': [0.7, 0.8, 0.9],
    'gamma': [0, 0.1, 0.2],
    'scale_pos_weight': [1, 5, 10]  # For class imbalance
}
```

### Phase 3: Evaluation & Iteration (Week 4)

**Tasks:**
1. Evaluate on validation set (2024)
   - Per-class metrics
   - Confusion matrix analysis
   - Calibration curves (predicted probability vs actual)
2. Error analysis
   - Which prospects are misclassified?
   - Are errors systematic (e.g., always under-predict pitchers)?
3. Feature importance analysis
   - Which features drive predictions?
   - SHAP values for interpretability
4. Final evaluation on test set (2025)
   - Lock model, report final metrics
   - Compare 2024 vs 2025 performance (temporal degradation?)

### Phase 4: Production Deployment (Weeks 5-6)

**Tasks:**
1. Create prediction API endpoint
   ```python
   @app.post("/api/prospects/{prospect_id}/predict-expectation")
   async def predict_mlb_expectation(prospect_id: int, season: int):
       features = get_features(prospect_id, season)
       prediction = model.predict_proba(features)
       return {
           'prospect_id': prospect_id,
           'predictions': {
               'All-Star': prediction[3],
               'Regular': prediction[2],
               'Part-Time': prediction[1],
               'Bench': prediction[0]
           },
           'predicted_class': class_names[prediction.argmax()],
           'confidence': prediction.max()
       }
   ```

2. Automated retraining pipeline
   - Trigger when new Fangraphs data arrives
   - Retrain on updated temporal splits
   - A/B test new model vs current production model

3. Monitoring dashboard
   - Track prediction distribution over time
   - Alert on distribution shift (e.g., too many All-Star predictions)
   - Compare predictions to actual MLB outcomes (when available)

4. Integration with A Fine Wine Dynasty app
   - Display ML predictions alongside Fangraphs grades
   - Highlight disagreements (model says All-Star, Fangraphs says Part-Time)
   - Custom hybrid rankings (50% scouting, 50% ML)

---

## Files Created

### Migration & Label Generation Scripts

**`migrate_fangraphs_grades.py`**
- Initial 2025 data import
- Table creation with multi-year support

**`import_historical_fangraphs_grades.py`**
- Imported 2022-2024 historical data
- Updated schemas for multi-year tracking
- Result: 2,309 hitter records, 2,423 pitcher records, 4,727 physical records

**`create_multi_year_mlb_expectation_labels.py`**
- Generated 2,650 labels across 2022-2025
- 207 prospects tracked all 4 years
- Temporal validation now enabled

### Feature Engineering Example

**`ml_feature_engineering_example.py`**
- Demonstrates combining Fangraphs grades with MiLB stats
- Age-relative-to-level percentiles
- Derived features (Power-Speed Number, K/BB ratio, etc.)
- Separate functions for hitters and pitchers

### Documentation

**`ML_MIGRATION_COMPLETE_SUMMARY.md`**
- Database schema documentation
- ML readiness assessment
- Feature sources guide

**`MLB_EXPECTATION_CLASSIFICATION_GUIDE.md`** (40+ pages)
- Complete ML implementation guide
- Class imbalance strategies
- Model architectures
- Evaluation metrics

**`CORRECTED_VALIDATION_STRATEGY.md`**
- Initially documented single-year limitation
- NOW OBSOLETE: Replaced by temporal validation

**`TEMPORAL_VALIDATION_READY_REPORT.md`** (this document)
- Multi-year status report
- Temporal validation strategy
- Next steps for ML implementation

---

## Database Tables Summary

### Fangraphs Grades (Multi-Year Enabled)

**`fangraphs_hitter_grades`** (2,309 records across 2022-2025)
- 17 tool grades (current/future for hit, power, speed, fielding, etc.)
- FV (Future Value) as target variable
- UNIQUE constraint: (fangraphs_player_id, data_year)

**`fangraphs_pitcher_grades`** (2,423 records across 2022-2025)
- 10 pitch grades (FB, SL, CB, CH, CMD current/future)
- Velocity ranges (sits low/high, tops)
- Tommy John surgery dates
- UNIQUE constraint: (fangraphs_player_id, data_year)

**`fangraphs_physical_attributes`** (4,727 records across 2022-2025)
- Frame grade, Athleticism grade
- Levers (arm/leg length)
- Arm strength grade
- Delivery grade (pitchers only)
- UNIQUE constraint: (fangraphs_player_id, data_year)

### ML Labels

**`mlb_expectation_labels`** (2,650 records across 2022-2025)
- mlb_expectation: Text label (All-Star/Regular/Part-Time/Bench)
- mlb_expectation_numeric: Integer (0-3) for ML models
- fv: Original Fangraphs Future Value
- data_year: Year of evaluation (2022-2025)
- UNIQUE constraint: (prospect_id, data_year)

---

## Validation Results

### Data Quality Checks

✅ **All imports successful:**
- 2022: 1,840 total records (602 hitters, 637 pitchers, 1,237 physical)
- 2023: 1,702 total records (557 hitters, 573 pitchers, 1,129 physical)
- 2024: 1,632 total records (545 hitters, 542 pitchers, 1,086 physical)
- 2025: 2,551 total records (605 hitters, 671 pitchers, 1,275 physical)

✅ **Label generation successful:**
- 2,650 labels created across 4 years
- No constraint violations
- All FV values mapped correctly to expectation classes

✅ **Multi-year tracking:**
- 207 prospects with all 4 years (ideal for longitudinal studies)
- 427 prospects with 3+ years (good sample for trend analysis)
- 745 prospects with 2+ years (sufficient for year-over-year comparisons)

✅ **Linkage quality:**
- 99.3% of hitters linked to prospects table
- 99.4% of pitchers linked to prospects table
- Foreign keys work via manual JOIN (fg_player_id)

---

## Summary

### Mission Accomplished

🎉 **All requested tasks completed:**
1. ✅ Deleted old `fangraphs_unified_grades` table
2. ✅ Created separate hitter and pitcher tables
3. ✅ Imported 2025 Fangraphs grades (3 CSV files)
4. ✅ Changed classification from Top 100 to MLB Expectation (4 classes)
5. ✅ Imported historical 2022-2024 grades (9 CSV files)
6. ✅ Generated multi-year labels (2,650 total)
7. ✅ Enabled temporal validation (train 2022-2023, val 2024, test 2025)

### Key Advantages

**Data Infrastructure:**
- Multi-year tracking (2022-2025)
- Temporal validation enabled
- Position-specific models supported
- Rich feature space (scouting + performance + physical + pitch tracking)

**ML Readiness:**
- 2,650 labeled examples across 4 years
- 207 prospects tracked longitudinally (all 4 years)
- Class imbalance strategies documented
- Feature engineering examples provided

**Production Ready:**
- Scalable database schema
- Repeatable migration scripts
- Comprehensive documentation
- Clear next steps defined

---

**The database is now fully prepared for machine learning model training with proper temporal validation!**

---

**Generated by:** BMad Party Mode Team
**Date:** October 19, 2025
**Status:** ✅ TEMPORAL VALIDATION READY - PROCEED TO MODEL TRAINING
