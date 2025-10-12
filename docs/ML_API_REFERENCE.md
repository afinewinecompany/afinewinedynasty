# ML Predictions API - Model Training Reference

**Version:** 1.0.0
**Last Updated:** 2025-10-12
**Purpose:** Reference documentation for data scientists training ML models for the A Fine Wine Dynasty platform

---

## Table of Contents
1. [Overview](#overview)
2. [Data Schema](#data-schema)
3. [API Contract](#api-contract)
4. [Prediction Types](#prediction-types)
5. [Feature Engineering](#feature-engineering)
6. [Model Requirements](#model-requirements)
7. [Integration Guide](#integration-guide)
8. [Performance Metrics](#performance-metrics)

---

## Overview

The ML Predictions API provides real-time prospect evaluation for fantasy baseball players. Models must predict MLB success probability, support SHAP explanations, and integrate with the existing dynasty ranking system.

### **Architecture**
- **Framework:** FastAPI (async)
- **Database:** PostgreSQL with TimescaleDB (time-series data)
- **Caching:** Redis (planned)
- **Model Serving:** Background tasks via FastAPI
- **API Base:** `/api/v1/ml/`

### **Key Services**
- `DynastyRankingService` - Composite scoring (ML 35%, scouting 25%, age 20%, stats 15%, ETA 5%)
- `BreakoutDetectionService` - Statistical trend analysis (30-90 day windows)

---

## Data Schema

### **Primary Tables**

#### **1. Prospects** (`prospects`)
Core player information.

```sql
CREATE TABLE prospects (
    id SERIAL PRIMARY KEY,
    mlb_id VARCHAR(10) UNIQUE NOT NULL,  -- External MLB ID
    name VARCHAR(100) NOT NULL,
    position VARCHAR(10) NOT NULL,       -- P, C, 1B, 2B, 3B, SS, LF, CF, RF, SP, RP
    organization VARCHAR(50),            -- Team/franchise
    level VARCHAR(20),                   -- MLB, Triple-A, Double-A, High-A, Low-A, Rookie
    age INTEGER,
    eta_year INTEGER,                    -- Expected MLB arrival year
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_prospects_mlb_id ON prospects(mlb_id);
CREATE INDEX idx_prospects_position ON prospects(position);
CREATE INDEX idx_prospects_organization ON prospects(organization);
```

**Positions:**
- **Hitters:** C, 1B, 2B, 3B, SS, LF, CF, RF, DH, IF, OF
- **Pitchers:** P, SP, RP, RHP, LHP

**Levels (Minor → Major):**
1. DSL / FCL / Complex
2. Rookie
3. Low-A
4. High-A
5. Double-A
6. Triple-A
7. MLB

---

#### **2. ProspectStats** (`prospect_stats`)
Time-series performance statistics (TimescaleDB hypertable).

```sql
CREATE TABLE prospect_stats (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    date_recorded DATE NOT NULL,

    -- Hitting Stats
    games_played INTEGER,
    at_bats INTEGER,
    hits INTEGER,
    home_runs INTEGER,
    rbi INTEGER,
    batting_avg FLOAT,           -- 0.0 - 1.0 (decimal format, e.g., 0.285)
    on_base_pct FLOAT,           -- 0.0 - 1.0
    slugging_pct FLOAT,          -- 0.0 - 2.0+ (e.g., 0.550)

    -- Pitching Stats
    innings_pitched FLOAT,
    era FLOAT,                   -- 0.0 - 20.0+ (e.g., 3.45)
    whip FLOAT,                  -- 0.0 - 5.0+ (e.g., 1.20)
    strikeouts_per_nine FLOAT,   -- 0.0 - 20.0+ (e.g., 9.5)

    -- Advanced Metrics
    woba FLOAT,                  -- 0.0 - 1.0 (weighted on-base average)
    wrc_plus FLOAT,              -- 0 - 500+ (weighted runs created, 100 = average)

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- TimescaleDB hypertable (time-series optimization)
SELECT create_hypertable('prospect_stats', 'date_recorded');

CREATE INDEX idx_prospect_stats_prospect ON prospect_stats(prospect_id, date_recorded DESC);
CREATE INDEX idx_prospect_stats_date ON prospect_stats(date_recorded);
```

**Important Notes:**
- Percentages stored as decimals (0.285, not 285 or 28.5)
- Multiple entries per prospect (time-series)
- Historical data available for trend analysis
- Minimum 10 data points required for breakout detection

---

#### **3. ScoutingGrades** (`scouting_grades`)
Professional scout evaluations (20-80 scale).

```sql
CREATE TABLE scouting_grades (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    source VARCHAR(100),          -- "MLB Pipeline", "FanGraphs", "Baseball America"

    -- 20-80 Scouting Scale (50 = MLB average, 60+ = above average, 70+ = elite)
    overall_future_value INTEGER, -- Overall FV grade (20-80)
    hit_tool INTEGER,             -- Contact ability (20-80)
    power_tool INTEGER,           -- Power potential (20-80)
    run_tool INTEGER,             -- Speed/running (20-80)
    field_tool INTEGER,           -- Defensive ability (20-80)
    arm_tool INTEGER,             -- Arm strength (20-80)

    -- Pitchers
    fastball INTEGER,             -- Fastball grade (20-80)
    curve INTEGER,                -- Curveball grade (20-80)
    slider INTEGER,               -- Slider grade (20-80)
    changeup INTEGER,             -- Changeup grade (20-80)
    control INTEGER,              -- Control/command (20-80)

    grade_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scouting_grades_prospect ON scouting_grades(prospect_id);
```

**Scouting Scale:**
- **20-30:** Well below average
- **40-45:** Below average
- **50:** MLB average
- **55-60:** Above average
- **65-70:** Plus/elite
- **75-80:** Best in baseball

---

#### **4. MLPrediction** (`ml_predictions`)
Model predictions storage.

```sql
CREATE TABLE ml_predictions (
    id SERIAL PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    prediction_type VARCHAR(50),    -- "success_rating", "eta_projection", etc.
    prediction_value FLOAT,         -- Main prediction (0.0 - 1.0 for probability)
    confidence_score FLOAT,         -- Model confidence (0.0 - 1.0)
    model_version VARCHAR(50),      -- "v1.0.0", "v1.2.0", etc.
    feature_importances JSONB,      -- SHAP values
    metadata JSONB,                 -- Additional model outputs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ml_predictions_prospect ON ml_predictions(prospect_id, created_at DESC);
CREATE INDEX idx_ml_predictions_type ON ml_predictions(prediction_type);
```

---

## API Contract

### **Model Input Format**

When the API calls your model, it will provide:

```python
{
    "prospect_id": 123,
    "mlb_id": "676828",
    "name": "Jackson Holliday",
    "position": "SS",
    "age": 21,
    "organization": "Baltimore Orioles",
    "level": "Triple-A",
    "eta_year": 2025,

    # Latest stats (most recent entry)
    "latest_stats": {
        "date_recorded": "2025-10-01",
        "batting_avg": 0.312,
        "on_base_pct": 0.398,
        "slugging_pct": 0.567,
        "games_played": 120,
        "woba": 0.385,
        "wrc_plus": 145
    },

    # Historical stats (last 30-90 days)
    "historical_stats": [
        {"date_recorded": "2025-09-15", "batting_avg": 0.305, ...},
        {"date_recorded": "2025-09-01", "batting_avg": 0.298, ...},
        # ... more entries
    ],

    # Scouting grades
    "scouting_grade": {
        "overall_future_value": 65,  # 20-80 scale
        "hit_tool": 60,
        "power_tool": 65,
        "run_tool": 55,
        "field_tool": 60,
        "arm_tool": 55
    }
}
```

---

### **Model Output Format**

Your model must return:

```python
{
    "success_probability": 0.85,      # REQUIRED: 0.0 - 1.0
    "confidence_score": 0.92,         # REQUIRED: 0.0 - 1.0
    "model_version": "v1.0.0",        # REQUIRED: string

    # REQUIRED: Top 5-10 SHAP feature importances
    "feature_importances": [
        {
            "feature_name": "age",
            "importance": 0.25,
            "feature_value": 21,
            "impact": "positive"  # "positive" | "negative" | "neutral"
        },
        {
            "feature_name": "current_level",
            "importance": 0.20,
            "feature_value": "Triple-A",
            "impact": "positive"
        },
        {
            "feature_name": "batting_avg",
            "importance": 0.18,
            "feature_value": 0.312,
            "impact": "positive"
        },
        # ... more features (max 10)
    ],

    # OPTIONAL: Additional metadata
    "metadata": {
        "prediction_time_ms": 45,
        "model_framework": "XGBoost",
        "feature_count": 45,
        "training_date": "2025-01-15"
    }
}
```

---

## Prediction Types

### **1. Success Probability (PRIMARY)**

**Prediction Type:** `"success_rating"`
**Definition:** Probability (0.0 - 1.0) that prospect will achieve "MLB success"

**MLB Success Criteria:**
- Accumulate ≥ 500 MLB PA (plate appearances) for hitters
- OR accumulate ≥ 200 MLB IP (innings pitched) for pitchers
- Within 5 years of MLB debut
- With positive WAR (Wins Above Replacement)

**Training Labels:**
- `1` = Success (met criteria)
- `0` = Failure (did not meet criteria)

**Model Requirements:**
- Binary classification (logistic regression, XGBoost, neural network)
- Output probability (not just class label)
- SHAP explainability support
- Confidence score calculation

**API Storage:**
```python
MLPrediction(
    prospect_id=123,
    prediction_type="success_rating",
    prediction_value=0.85,         # 85% probability
    confidence_score=0.92,
    model_version="v1.0.0"
)
```

---

### **2. Breakout Detection (SECONDARY)**

**Prediction Type:** Calculated by `BreakoutDetectionService` (not ML model)
**Method:** Statistical trend analysis

**Calculation:**
1. Compare recent stats (last N days) vs baseline (previous N days)
2. Calculate improvement rates for key metrics
3. Test statistical significance (p-value < 0.05)
4. Generate breakout score (0-100)

**Metrics Analyzed:**

**Hitters:**
- Batting average improvement rate
- OBP improvement rate
- Slugging improvement rate
- wOBA improvement rate
- Trend consistency

**Pitchers:**
- ERA improvement rate (lower is better)
- WHIP improvement rate (lower is better)
- K/9 improvement rate
- Trend consistency

**API Endpoint:** `/api/v1/ml/breakout-candidates`

---

### **3. Dynasty Ranking (COMPOSITE)**

**Prediction Type:** Composite score from multiple sources
**Formula:**

```
Dynasty Score = (ML_Score × 0.35)
              + (Scouting_Score × 0.25)
              + (Age_Score × 0.20)
              + (Performance_Score × 0.15)
              + (ETA_Score × 0.05)
```

**Component Calculations:**

**ML Score (35% weight):**
```python
ml_raw = success_probability * 100  # Convert to 0-100
ml_score = ml_raw * 0.35
```

**Scouting Score (25% weight):**
```python
scout_raw = ((future_value - 20) / 60) * 100  # Convert 20-80 → 0-100
scouting_score = scout_raw * 0.25
```

**Age Score (20% weight):**
```python
age_factor = max(0, min(100, (25 - age) * 10))  # Peak at 15, decline after 25
age_score = age_factor * 0.20
```

**Performance Score (15% weight):**
- Hitters: Based on BA, OBP, SLG, wRC+
- Pitchers: Based on ERA, WHIP, K/9
- Normalized to 0-100 scale
- `performance_score = perf_raw * 0.15`

**ETA Score (5% weight):**
```python
years_to_majors = max(0, eta_year - current_year)
eta_factor = max(0, 100 - (years_to_majors * 20))  # Lose 20pts per year
eta_score = eta_factor * 0.05
```

**Service:** `DynastyRankingService.calculate_dynasty_score()`

---

## Feature Engineering

### **Recommended Features**

Based on successful prospect prediction models, include these features:

#### **Demographic Features**
- `age` - Current age (continuous, 16-30)
- `age_squared` - Age squared (for non-linear effects)
- `years_to_eta` - Years until projected MLB debut
- `position_encoded` - One-hot encoded position
- `level_encoded` - Ordinal encoded level (1-7)

#### **Performance Features (Latest)**
- `batting_avg` - Most recent batting average
- `on_base_pct` - Most recent OBP
- `slugging_pct` - Most recent SLG
- `woba` - Weighted on-base average
- `wrc_plus` - Weighted runs created plus
- `iso` - Isolated power (SLG - AVG)
- `bb_rate` - Walk rate
- `k_rate` - Strikeout rate
- `era` - Earned run average (pitchers)
- `whip` - Walks + hits per inning (pitchers)
- `k_per_9` - Strikeouts per 9 innings (pitchers)

#### **Trend Features (30-day)**
- `batting_avg_30d_change` - 30-day BA change
- `woba_30d_change` - 30-day wOBA change
- `performance_momentum` - Direction of recent trend
- `games_played_30d` - Sample size indicator

#### **Scouting Features**
- `overall_fv` - Overall future value (20-80)
- `hit_tool` - Contact ability
- `power_tool` - Power potential
- `speed_tool` - Running ability
- `tools_average` - Average of 5 tools

#### **Contextual Features**
- `organization_strength` - Farm system ranking (1-30)
- `level_competition` - Opponent quality score
- `injury_history` - Binary flag (has/no injuries)
- `season_progression` - Days into season / 180

#### **Derived Features**
- `age_level_interaction` - age × level (younger at higher level = better)
- `performance_vs_league` - Stats relative to league average
- `tool_consistency` - Std dev of scouting tools (lower = more balanced)
- `projection_confidence` - Based on sample size and data quality

---

### **Feature Scaling**

**Continuous Features:**
- Use StandardScaler or MinMaxScaler
- Save scaler parameters for inference

**Categorical Features:**
- Position: One-hot encoding (create binary columns for each position)
- Level: Ordinal encoding (1=DSL, 2=Rookie, ..., 7=MLB)
- Organization: Target encoding or entity embeddings

**Time-Series Features:**
- Rolling windows: 7-day, 14-day, 30-day, 90-day averages
- Lag features: t-1, t-7, t-14, t-30 values
- Rate of change: (current - previous) / previous

---

## Model Requirements

### **1. Minimum Requirements**

✅ **Binary Classification Model**
- Predict success probability (0.0 - 1.0)
- Handle missing values gracefully
- Support batch prediction (100+ prospects)

✅ **SHAP Explainability**
- Generate SHAP values for each prediction
- Return top 5-10 feature importances
- Include impact direction (positive/negative)

✅ **Confidence Estimation**
- Provide confidence score (0.0 - 1.0) for each prediction
- Based on data quality, sample size, or ensemble variance

✅ **Version Control**
- Semantic versioning (e.g., "v1.0.0", "v1.2.3")
- Track model lineage and training date

---

### **2. Performance Targets**

| Metric | Target | Minimum |
|--------|--------|---------|
| **Accuracy** | ≥ 82% | ≥ 75% |
| **F1 Score** | ≥ 0.78 | ≥ 0.70 |
| **AUC-ROC** | ≥ 0.85 | ≥ 0.78 |
| **Precision** | ≥ 0.80 | ≥ 0.72 |
| **Recall** | ≥ 0.75 | ≥ 0.68 |
| **Calibration** | Well-calibrated | Brier score < 0.15 |

**Inference Performance:**
- Single prediction: < 50ms
- Batch (100 prospects): < 2 seconds
- Model loading: < 5 seconds

---

### **3. Data Quality Requirements**

**Minimum Data for Training:**
- ≥ 5,000 prospects with labels
- ≥ 20% positive class (MLB success)
- ≥ 3 years of historical data
- Representative distribution across positions, levels, ages

**Minimum Data for Prediction:**
- ≥ 10 statistical data points (prospect_stats entries)
- ≥ 1 scouting grade (if available)
- Prospect age, position, level, organization

**Data Freshness:**
- Stats: Updated weekly during season
- Scouting grades: Updated quarterly
- Predictions: Cached for 1 hour, regenerate on demand

---

## Integration Guide

### **Step 1: Model Development**

```python
# Example training pipeline
import pandas as pd
import xgboost as xgb
import shap

# Load data from PostgreSQL
prospects_df = load_prospects_from_db()
features_df = engineer_features(prospects_df)
X, y = features_df.drop('success_label', axis=1), features_df['success_label']

# Train model
model = xgb.XGBClassifier(
    max_depth=6,
    learning_rate=0.1,
    n_estimators=200,
    random_state=42
)
model.fit(X, y)

# Generate SHAP explainer
explainer = shap.TreeExplainer(model)

# Save model
model.save_model('prospect_success_v1.0.0.json')
```

---

### **Step 2: Create Prediction Service**

Create a prediction service that implements this interface:

```python
# apps/api/app/services/ml_model_service.py

import xgboost as xgb
import shap
import numpy as np
from typing import Dict, List, Any

class MLModelService:
    """ML model prediction service"""

    def __init__(self, model_path: str, model_version: str):
        self.model = xgb.Booster()
        self.model.load_model(model_path)
        self.explainer = shap.TreeExplainer(self.model)
        self.model_version = model_version
        self.feature_names = [...]  # Your feature names

    def predict(self, prospect_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate prediction for a single prospect

        Args:
            prospect_data: Dict containing prospect features

        Returns:
            Dict with success_probability, confidence_score, feature_importances
        """
        # Extract and transform features
        features = self._extract_features(prospect_data)

        # Generate prediction
        prediction_proba = self.model.predict(xgb.DMatrix(features))[0]

        # Calculate confidence (based on prediction certainty)
        confidence = self._calculate_confidence(prediction_proba)

        # Generate SHAP values
        shap_values = self.explainer.shap_values(features)
        feature_importances = self._format_shap_values(
            shap_values[0],
            features,
            top_k=10
        )

        return {
            "success_probability": float(prediction_proba),
            "confidence_score": float(confidence),
            "model_version": self.model_version,
            "feature_importances": feature_importances
        }

    def batch_predict(self, prospects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate predictions for multiple prospects"""
        return [self.predict(p) for p in prospects]

    def _extract_features(self, prospect_data: Dict) -> np.ndarray:
        """Transform raw prospect data into model features"""
        # Implement feature engineering
        features = []

        # Demographic
        features.append(prospect_data['age'])
        features.append(prospect_data['age'] ** 2)

        # Performance
        latest_stats = prospect_data.get('latest_stats', {})
        features.append(latest_stats.get('batting_avg', 0))
        features.append(latest_stats.get('on_base_pct', 0))
        # ... more features

        # Scouting
        scouting = prospect_data.get('scouting_grade', {})
        features.append(scouting.get('overall_future_value', 50) / 80)
        # ... more features

        return np.array([features])

    def _calculate_confidence(self, probability: float) -> float:
        """
        Calculate confidence score based on prediction certainty

        Confidence is higher when probability is closer to 0 or 1
        (model is more certain)
        """
        return 1 - 2 * abs(0.5 - probability)

    def _format_shap_values(
        self,
        shap_values: np.ndarray,
        features: np.ndarray,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Format SHAP values for API response"""

        feature_impacts = []
        for idx, (shap_val, feat_val) in enumerate(zip(shap_values, features[0])):
            feature_impacts.append({
                "feature_name": self.feature_names[idx],
                "importance": abs(float(shap_val)),
                "feature_value": float(feat_val),
                "impact": "positive" if shap_val > 0 else "negative" if shap_val < 0 else "neutral"
            })

        # Sort by importance and return top K
        feature_impacts.sort(key=lambda x: x['importance'], reverse=True)
        return feature_impacts[:top_k]
```

---

### **Step 3: Integrate with API Router**

Update the `regenerate_predictions` function in `ml_predictions.py`:

```python
# apps/api/app/routers/ml_predictions.py

from app.services.ml_model_service import MLModelService

# Initialize model service (singleton)
ml_service = MLModelService(
    model_path="models/prospect_success_v1.0.0.json",
    model_version="v1.0.0"
)

async def regenerate_predictions(prospect_id: int, db: AsyncSession):
    """Background task to regenerate predictions"""
    try:
        # Get prospect with related data
        stmt = select(Prospect).filter(Prospect.id == prospect_id).options(
            selectinload(Prospect.stats),
            selectinload(Prospect.scouting_grades)
        )
        result = await db.execute(stmt)
        prospect = result.scalar_one_or_none()

        if not prospect:
            logger.error(f"Prospect {prospect_id} not found")
            return

        # Prepare data for model
        prospect_data = {
            "prospect_id": prospect.id,
            "mlb_id": prospect.mlb_id,
            "name": prospect.name,
            "position": prospect.position,
            "age": prospect.age,
            "organization": prospect.organization,
            "level": prospect.level,
            "eta_year": prospect.eta_year,
            "latest_stats": _get_latest_stats(prospect),
            "historical_stats": _get_historical_stats(prospect),
            "scouting_grade": _get_scouting_grade(prospect)
        }

        # Generate prediction
        prediction_result = ml_service.predict(prospect_data)

        # Save to database
        ml_prediction = MLPrediction(
            prospect_id=prospect.id,
            prediction_type="success_rating",
            prediction_value=prediction_result['success_probability'],
            confidence_score=prediction_result['confidence_score'],
            model_version=prediction_result['model_version'],
            feature_importances=prediction_result['feature_importances']
        )

        db.add(ml_prediction)
        await db.commit()

        logger.info(f"Generated prediction for {prospect.name}: {prediction_result['success_probability']:.2%}")

    except Exception as e:
        logger.error(f"Failed to regenerate prediction for prospect {prospect_id}: {str(e)}")
        await db.rollback()
```

---

### **Step 4: Deploy Model**

```bash
# 1. Export trained model
python scripts/export_model.py --version v1.0.0

# 2. Copy model to API server
cp models/prospect_success_v1.0.0.json apps/api/models/

# 3. Update model version in service
# Edit apps/api/app/services/ml_model_service.py

# 4. Restart API server
pm2 restart api

# 5. Trigger batch prediction for all prospects
curl -X POST http://localhost:8001/api/v1/ml/batch-predict \
  -H "Authorization: Bearer $TOKEN"
```

---

## Performance Metrics

### **Model Evaluation**

Track these metrics during training and validation:

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, brier_score_loss,
    confusion_matrix, classification_report
)

# Binary classification metrics
accuracy = accuracy_score(y_true, y_pred)
precision = precision_score(y_true, y_pred)
recall = recall_score(y_true, y_pred)
f1 = f1_score(y_true, y_pred)
auc = roc_auc_score(y_true, y_pred_proba)

# Calibration metric (how well probabilities match reality)
brier = brier_score_loss(y_true, y_pred_proba)

print(f"Accuracy: {accuracy:.3f}")
print(f"Precision: {precision:.3f}")
print(f"Recall: {recall:.3f}")
print(f"F1 Score: {f1:.3f}")
print(f"AUC-ROC: {auc:.3f}")
print(f"Brier Score: {brier:.3f}")
```

---

### **Production Monitoring**

Monitor these metrics in production:

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Prediction Accuracy** | % of predictions matching reality | ≥ 80% | < 75% |
| **Average Confidence** | Mean confidence score | 0.75-0.85 | < 0.60 |
| **Prediction Latency** | Time to generate prediction | < 50ms | > 100ms |
| **Cache Hit Rate** | % of cached predictions | ≥ 80% | < 70% |
| **Data Quality Score** | % of predictions with complete data | ≥ 90% | < 80% |
| **Model Drift** | Distribution shift in features | Stable | KS test p < 0.05 |

---

### **A/B Testing**

When deploying new model versions:

```python
# Route 10% of traffic to new model v1.1.0
if random.random() < 0.10:
    model = ml_service_v1_1_0
else:
    model = ml_service_v1_0_0

# Log predictions for comparison
log_prediction_for_ab_test(
    prospect_id=prospect_id,
    model_version=model.model_version,
    prediction=prediction_result
)

# After 1 week, compare metrics
compare_model_performance(
    model_a="v1.0.0",
    model_b="v1.1.0",
    metrics=["accuracy", "f1_score", "user_engagement"]
)
```

---

## FAQ

### **Q: How often should predictions be regenerated?**
A: Automatically refresh predictions when:
- New stats are added (weekly during season)
- Scouting grades are updated (quarterly)
- Player changes level or organization
- Manual refresh requested by user
- Cache expires (1 hour TTL)

### **Q: How do I handle missing data?**
A:
- Use median/mean imputation for continuous features
- Use mode imputation for categorical features
- Create `is_missing` binary indicator features
- Train model to be robust to missing values

### **Q: What's the expected training time?**
A:
- Feature engineering: 5-10 minutes (5,000 prospects)
- Model training: 2-5 minutes (XGBoost on CPU)
- SHAP calculation: 10-15 minutes (full dataset)
- Total pipeline: ~30 minutes

### **Q: How do I update the model in production?**
A:
1. Train new model with updated data
2. Validate on hold-out test set (ensure metrics meet targets)
3. Export model with new version number
4. Deploy via A/B test (10% traffic)
5. Monitor for 1 week
6. Roll out to 100% if successful

### **Q: What if a prospect has no scouting grades?**
A:
- Use position-specific defaults (e.g., 50 for all tools)
- Weight ML and performance scores higher in dynasty ranking
- Flag as "low confidence" prediction
- Reduce confidence score by 10-20%

---

## Contact

**For model training questions:**
- Email: ml-team@afinewinedynasty.com
- Slack: #ml-models

**For API integration questions:**
- Email: dev-team@afinewinedynasty.com
- Slack: #api-development

**Documentation:**
- API Docs: https://api.afinewinedynasty.com/docs
- Model Specs: https://github.com/afinewinedynasty/ml-models

---

**Version History:**
- v1.0.0 (2025-10-12) - Initial release
