# MLB Expectation Classification - Implementation Guide

**Date:** October 19, 2025
**Purpose:** Multi-class classification model to predict MLB role expectations
**Team:** BMad Party Mode

---

## Overview

Instead of binary "Top 100 or not" classification, we're building a **4-class model** that predicts a prospect's expected MLB impact level:

| Class | FV Range | Description | WAR Range | Examples |
|-------|----------|-------------|-----------|----------|
| **All-Star** | 60+ | Elite player, perennial All-Star | 5+ WAR | Mike Trout, Shohei Ohtani, Aaron Judge |
| **Regular** | 50-55 | Above-average starter | 2-4 WAR | Solid everyday player, occasional All-Star |
| **Part-Time** | 45 | Role player, platoon/specialist | 0.5-2 WAR | 4th OF, utility infielder, long reliever |
| **Bench** | 35-40 | Backup/replacement level | 0-0.5 WAR | May reach MLB but limited impact |

---

## Why This Classification?

### Better Than Binary "Top 100"
- **More granular:** Captures the full spectrum of prospect outcomes
- **More actionable:** Helps with roster construction and trade decisions
- **Aligns with FV scale:** Fangraphs already segments prospects this way

### Business Value
- **Dynasty leagues:** Know which prospects to trade vs. hold
- **Roster planning:** Understand depth vs. star potential
- **Risk assessment:** Part-Time prospects are safer bets than All-Star swings

---

## Mapping FV to MLB Expectation Classes

### Fangraphs Future Value (FV) Scale

| FV | Label | MLB Outcome | Our Class |
|----|-------|-------------|-----------|
| 70 | Franchise | Top 5 player in baseball | **All-Star** |
| 60 | All-Star | Perennial All-Star, top 20 player | **All-Star** |
| 55 | Plus Regular | Above-average regular, 3-4 WAR | **Regular** |
| 50 | Regular | Average starter, 2-3 WAR | **Regular** |
| 45 | 4th OF/Utility/Swingman | Role player, 1-2 WAR | **Part-Time** |
| 40 | Up-and-Down | Backup/depth, replacement level | **Bench** |
| 35 | Org Guy | Unlikely to stick in MLB | **Bench** |

---

## Class Distribution in Current Data

### Hitters (605 total)
| Class | FV Range | Count | % of Total |
|-------|----------|-------|------------|
| **All-Star** | 60+ | 6 | 1.0% |
| **Regular** | 50-55 | 49 | 8.1% |
| **Part-Time** | 45 | 92 | 15.2% |
| **Bench** | 35-40 | 457 | 75.5% |

### Pitchers (671 total)
| Class | FV Range | Count | % of Total |
|-------|----------|-------|------------|
| **All-Star** | 60+ | 7 | 1.0% |
| **Regular** | 50-55 | 39 | 5.8% |
| **Part-Time** | 45 | 85 | 12.7% |
| **Bench** | 35-40 | 546 | 81.4% |

**Class Imbalance:** The "All-Star" class is heavily underrepresented (~1%), while "Bench" dominates (75-81%). This will require special handling.

---

## Model Architecture

### Option 1: Single Multi-Class Classifier

**Pros:**
- Simple architecture
- Single model to maintain
- Direct probability outputs for each class

**Cons:**
- Struggles with extreme class imbalance
- May predict "Bench" for nearly everyone

**Best Models:**
- **XGBoost** with `scale_pos_weight` for class balancing
- **Random Forest** with class weights
- **Neural Network** with focal loss

### Option 2: Hierarchical Classification (RECOMMENDED)

**Stage 1:** Binary "Will they be good?" (All-Star/Regular vs Part-Time/Bench)
**Stage 2a:** Among "good" players → All-Star vs Regular
**Stage 2b:** Among "limited" players → Part-Time vs Bench

**Pros:**
- Better handles class imbalance
- Each classifier focuses on a specific boundary
- Can use different features at each stage

**Cons:**
- More complex to maintain
- Errors cascade (if Stage 1 wrong, Stage 2 can't fix it)

### Option 3: Ordinal Regression

Treat classes as ordered: Bench < Part-Time < Regular < All-Star

**Pros:**
- Respects natural ordering of player quality
- More efficient than multi-class
- Can use threshold adjustment for calibration

**Cons:**
- Assumes equal spacing between classes (debatable)
- Less flexible than hierarchical

---

## Feature Engineering for Classification

### Key Features (by importance based on scouting)

#### For Hitters:
1. **Hit Tool Future** (most predictive for reaching MLB)
2. **Game Power Future** (separates stars from regulars)
3. **Age-Adjusted OPS** (performance relative to level)
4. **Speed + Fielding** (determines floor - defensive value)
5. **Age Advantage** (young for level → higher ceiling)
6. **Contact Style** (all-fields hitters → higher floor)
7. **Physical Attributes** (frame, athleticism → projectability)

#### For Pitchers:
1. **Fastball Grade + Velocity** (most predictive)
2. **Command/Control** (separates starters from relievers)
3. **Best Secondary Pitch** (need one plus pitch minimum)
4. **Age-Adjusted K/9 and BB/9** (performance metrics)
5. **Stuff Composite** (FB velo + breaking ball grades)
6. **Durability** (innings pitched, injury history/TJ surgery)
7. **Delivery Mechanics** (physical attributes)

### Derived Features

```python
# Composite "Star Potential" Score (Hitters)
star_potential = (
    hit_future * 2.0 +      # Hit tool is most important
    game_power_future * 1.5 +
    speed_future * 0.5 +
    fielding_future * 0.5
) / 5.0

# Composite "Floor" Score (defensive value + plate discipline)
floor_score = (
    fielding_future +
    speed_future +
    pitch_sel_future
) / 3.0

# Age-adjusted ceiling
ceiling_multiplier = 1 + (age_advantage_years * 0.1)

# Final feature
prospect_ceiling = star_potential * ceiling_multiplier

# Composite "Stuff" Score (Pitchers)
stuff_score = (
    fb_future * 2.0 +
    max(sl_future, cb_future, ch_future) * 1.5 +  # Best secondary
    cmd_future * 1.0
) / 4.5

# Starter vs Reliever indicator
is_starter = (cmd_future >= 45) and (pitch_types_thrown >= 3)
```

---

## Handling Class Imbalance

### Techniques

1. **SMOTE (Synthetic Minority Over-sampling)**
   - Generate synthetic "All-Star" and "Regular" examples
   - Use only on training set, not validation

2. **Class Weights**
   ```python
   from sklearn.utils.class_weight import compute_class_weight

   class_weights = compute_class_weight(
       'balanced',
       classes=np.unique(y_train),
       y=y_train
   )

   # XGBoost
   xgb_model = XGBClassifier(
       scale_pos_weight=class_weights,
       ...
   )
   ```

3. **Stratified Sampling**
   - Ensure each class represented in train/val/test
   - Use `StratifiedKFold` for cross-validation

4. **Focal Loss (Neural Networks)**
   - Downweights loss for easy examples (Bench class)
   - Focuses on hard examples (All-Star class)

5. **Ensemble with Threshold Tuning**
   - Adjust decision thresholds per class
   - Optimize for F1-score instead of accuracy

---

## Training Strategy

### Data Splits

**IMPORTANT:** We only have 2025 FV labels! See `CORRECTED_VALIDATION_STRATEGY.md` for details.

```python
# Option A: Stratified K-Fold (RECOMMENDED)
# Use 2025 data with multi-season FEATURES
from sklearn.model_selection import StratifiedKFold

df = prepare_multi_season_features(prospects_2025)  # Features from 2021-2025
X = df.drop(['target'], axis=1)
y = df['target']  # 2025 FV labels

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
for train_idx, val_idx in skf.split(X, y):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
    # Train model...

# Option B: Simple Train/Val Split
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=42
)

# Within each split, stratify by class
X_train, y_train = prepare_features(train_df)
X_val, y_val = prepare_features(val_df)

# Stratified split to maintain class distribution
from sklearn.model_selection import StratifiedKFold

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
for train_idx, val_idx in skf.split(X_train, y_train):
    # Train fold
    ...
```

### Hyperparameter Tuning

```python
# XGBoost for multi-class
import xgboost as xgb
from sklearn.model_selection import GridSearchCV

param_grid = {
    'max_depth': [3, 5, 7],
    'learning_rate': [0.01, 0.05, 0.1],
    'n_estimators': [100, 200, 500],
    'min_child_weight': [1, 3, 5],
    'subsample': [0.7, 0.8, 1.0],
    'colsample_bytree': [0.7, 0.8, 1.0],
    'scale_pos_weight': [1, 2, 5, 10],  # For class imbalance
}

xgb_model = xgb.XGBClassifier(
    objective='multi:softmax',  # Multi-class
    num_class=4,                # 4 classes
    eval_metric='mlogloss',
    random_state=42
)

grid_search = GridSearchCV(
    xgb_model,
    param_grid,
    cv=5,
    scoring='f1_weighted',  # Weighted F1 for imbalanced classes
    n_jobs=-1
)

grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_
```

---

## Evaluation Metrics

### Primary Metrics

1. **Weighted F1-Score** (accounts for class imbalance)
2. **Per-Class Precision/Recall**
3. **Confusion Matrix** (where are we getting it wrong?)
4. **ROC-AUC (One-vs-Rest)** for each class
5. **Calibration Curve** (are probabilities accurate?)

### Secondary Metrics

6. **Top-K Accuracy** (are we close?)
   - If predict "Regular" but actual is "All-Star" → not as bad
   - If predict "Bench" but actual is "All-Star" → very bad
7. **Expected Value** (dollar value in dynasty leagues)
8. **Scouting Consensus Agreement** (vs Fangraphs FV)

### Example Evaluation Code

```python
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

# Predictions
y_pred = best_model.predict(X_val)
y_pred_proba = best_model.predict_proba(X_val)

# Classification report
print(classification_report(
    y_val,
    y_pred,
    target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']
))

# Confusion matrix
cm = confusion_matrix(y_val, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Bench', 'Part-Time', 'Regular', 'All-Star'],
            yticklabels=['Bench', 'Part-Time', 'Regular', 'All-Star'])
plt.ylabel('Actual')
plt.xlabel('Predicted')
plt.title('MLB Expectation Classification - Confusion Matrix')
plt.show()

# Per-class metrics
for i, class_name in enumerate(['Bench', 'Part-Time', 'Regular', 'All-Star']):
    precision = precision_score(y_val, y_pred, labels=[i], average=None)[0]
    recall = recall_score(y_val, y_pred, labels=[i], average=None)[0]
    f1 = f1_score(y_val, y_pred, labels=[i], average=None)[0]

    print(f"{class_name:12s} - Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
```

---

## Interpreting Results

### Feature Importance

```python
# XGBoost feature importance
import pandas as pd

feature_importance = pd.DataFrame({
    'feature': feature_names,
    'importance': best_model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 10 Features for MLB Expectation:")
print(feature_importance.head(10))

# Plot
plt.figure(figsize=(10, 6))
sns.barplot(data=feature_importance.head(15), x='importance', y='feature')
plt.title('Top 15 Features - MLB Expectation Classification')
plt.xlabel('Importance')
plt.show()
```

### SHAP Values (for explainability)

```python
import shap

# SHAP explainer
explainer = shap.TreeExplainer(best_model)
shap_values = explainer.shap_values(X_val)

# Summary plot (shows feature impact for each class)
shap.summary_plot(shap_values, X_val, feature_names=feature_names,
                  class_names=['Bench', 'Part-Time', 'Regular', 'All-Star'])

# Force plot for specific player
player_idx = 0  # Example: first player in validation set
shap.force_plot(explainer.expected_value[3],  # All-Star class
                shap_values[3][player_idx],
                X_val.iloc[player_idx],
                feature_names=feature_names)
```

---

## Production Deployment

### API Endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib

app = FastAPI()

# Load trained model
model = joblib.load('mlb_expectation_classifier.pkl')

class ProspectFeatures(BaseModel):
    hit_future: int
    game_power_future: int
    speed_future: int
    fielding_future: int
    age: float
    level: str
    ops: float
    # ... more features

@app.post("/predict/mlb-expectation")
async def predict_mlb_expectation(features: ProspectFeatures):
    # Convert to feature vector
    X = prepare_features_from_api(features)

    # Predict
    prediction = model.predict(X)[0]
    probabilities = model.predict_proba(X)[0]

    class_names = ['Bench', 'Part-Time', 'Regular', 'All-Star']

    return {
        'prediction': class_names[prediction],
        'probabilities': {
            class_name: float(prob)
            for class_name, prob in zip(class_names, probabilities)
        },
        'confidence': float(max(probabilities))
    }
```

### Database Storage

```sql
-- Add predictions table
CREATE TABLE mlb_expectation_predictions (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    prediction_date DATE NOT NULL,
    predicted_class VARCHAR(20) NOT NULL, -- 'All-Star', 'Regular', etc.

    -- Class probabilities
    prob_all_star NUMERIC(5,4),
    prob_regular NUMERIC(5,4),
    prob_part_time NUMERIC(5,4),
    prob_bench NUMERIC(5,4),

    -- Model metadata
    model_version VARCHAR(20),
    feature_count INTEGER,

    -- Outcome tracking (fill in later when player reaches MLB)
    actual_class VARCHAR(20),
    actual_war_3yr NUMERIC(4,1),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_predictions_prospect ON mlb_expectation_predictions(prospect_id);
CREATE INDEX idx_predictions_date ON mlb_expectation_predictions(prediction_date);
```

---

## Expected Results

### Baseline Performance Estimates

Based on similar prospect classification tasks:

| Metric | Expected Range | Notes |
|--------|----------------|-------|
| **Overall Accuracy** | 60-75% | Highly dependent on class imbalance handling |
| **Weighted F1** | 0.55-0.70 | More important than raw accuracy |
| **All-Star F1** | 0.30-0.50 | Hardest class (smallest sample) |
| **Regular F1** | 0.40-0.60 | Moderate difficulty |
| **Part-Time F1** | 0.50-0.65 | Mid-range class |
| **Bench F1** | 0.70-0.85 | Easiest (largest sample) |

### Comparison to Scouting (FV)

- **Agreement with FV within 1 class:** 80-90% expected
- **Exact match with FV:** 50-65% expected
- **Model advantages:**
  - Better age-relative adjustments
  - Objective performance weighting
  - No recency bias
- **Scouting advantages:**
  - Intangibles (makeup, work ethic)
  - Injury context
  - Tool projection (physical development)

---

## Next Steps

### Phase 1: Prototype (Week 1-2)
- [ ] Create target labels from FV grades
- [ ] Build baseline Random Forest model
- [ ] Evaluate with weighted F1-score
- [ ] Identify most important features

### Phase 2: Optimization (Weeks 3-4)
- [ ] Implement SMOTE for class balancing
- [ ] Try XGBoost with class weights
- [ ] Hyperparameter tuning with GridSearchCV
- [ ] Compare hierarchical vs single-classifier

### Phase 3: Validation (Month 2)
- [ ] Test on 2025 prospects (holdout)
- [ ] Compare to Fangraphs FV consensus
- [ ] Analyze disagreements (model vs scouts)
- [ ] Feature importance + SHAP analysis

### Phase 4: Production (Month 3)
- [ ] Build API endpoint
- [ ] Store predictions in database
- [ ] Create dashboard for prospect rankings
- [ ] Set up automated retraining pipeline

---

## References

**Fangraphs FV Scale:**
- https://blogs.fangraphs.com/scouting-explained-the-20-80-scouting-scale/

**Class Imbalance Techniques:**
- SMOTE: https://arxiv.org/abs/1106.1813
- Focal Loss: https://arxiv.org/abs/1708.02002

**Similar Work:**
- MLB Prospect Success Prediction (Baseball Prospectus)
- NFL Draft Success Models (538)

---

**Document Created By:** BMad Party Mode Team
**Date:** October 19, 2025
**Status:** Ready for Implementation
