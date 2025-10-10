# MLB Performance Prediction ML Strategy

## Executive Summary
With complete 2024-2025 MiLB data (1.1M+ games, 13,700+ players), we can build sophisticated models to predict MLB performance using wRC+ and wOBA as primary targets, with age-adjusted projections and player similarity matching.

---

## 📊 Available Data Assets

### 1. **MiLB Game Logs (Primary Feature Source)**
- **Coverage**: 2021-2025 (5 seasons)
- **Volume**: 1,095,803 games
- **Players**: 13,746 unique players
- **Stats**: 99 fields per game (36 hitting, 63 pitching)
- **Levels**: AAA, AA, A+, A, Rookie+, Winter

### 2. **MLB Game Logs (Target Labels)**
- **Coverage**: 2020-2025
- **Players**: 1,518 with MLB experience
- **Games**: 200,504 MLB games
- **Overlap**: ~11% of MiLB players have MLB data

### 3. **Missing But Obtainable**
- Fangraphs advanced metrics (wRC+, wOBA, FIP, xFIP)
- Statcast data (exit velocity, launch angle, sprint speed)
- Player demographics (birth dates for accurate age)
- Park factors and league adjustments

---

## 🎯 ML Target Variables

### Primary Targets (MLB Performance)

#### **1. wRC+ (Weighted Runs Created Plus)**
- **Definition**: Offensive value relative to league average (100 = average)
- **Advantages**:
  - Park and league adjusted
  - Single number captures overall offensive value
  - Easily interpretable (120 = 20% above average)
- **Prediction Range**: 0-200 (typical MLB range: 50-150)

#### **2. wOBA (Weighted On-Base Average)**
- **Definition**: Linear weights-based offensive metric
- **Scale**: Similar to OBP (.320 = average)
- **Advantages**:
  - More accurate than OPS
  - Directly translates to run scoring
- **Prediction Range**: .200-.450

#### **3. Peak wRC+ (Age-Adjusted)**
- **Concept**: Project peak performance, not just next season
- **Age Curve Peaks**:
  - Position Players: 26-28 years old
  - Power Hitters: 27-29 years old
  - Speed Players: 24-26 years old
- **Implementation**: Predict wRC+ at age 27, adjust for current age

### Secondary Targets
- **WAR/600 PA**: Wins Above Replacement per full season
- **MLB Success Probability**: Binary (reaches MLB or not)
- **MLB Debut Timeline**: Years until MLB debut
- **Career Length**: Projected MLB seasons

---

## 🧬 Feature Engineering Strategy

### Level 1: Raw Statistics Aggregation
```python
# Per-level aggregations (AAA, AA, A+, etc.)
features = {
    'games_played': sum,
    'plate_appearances': sum,
    'batting_avg': mean,
    'obp': mean,
    'slg': mean,
    'ops': mean,
    'walk_rate': bb / pa,
    'strikeout_rate': so / pa,
    'iso_power': slg - avg,
    'babip': mean
}
```

### Level 2: Age-Relative Performance
```python
# Compare to league average at same age
age_adjusted_features = {
    'ops_plus': player_ops / league_age_ops * 100,
    'avg_plus': player_avg / league_age_avg * 100,
    'k_rate_plus': league_k_rate / player_k_rate * 100,
    'relative_age': player_age - league_avg_age
}
```

### Level 3: Development Trajectories
```python
# Year-over-year improvements
trajectory_features = {
    'ops_growth_rate': (ops_y2 - ops_y1) / ops_y1,
    'level_jump_performance': aaa_ops / aa_ops,
    'consistency': std(monthly_ops),
    'peak_performance': max(monthly_ops)
}
```

### Level 4: Competition Quality Adjustments
```python
# Weight stats by level difficulty
level_weights = {
    'AAA': 1.0,
    'AA': 0.85,
    'A+': 0.70,
    'A': 0.60,
    'Rookie': 0.40
}

weighted_ops = sum(level_ops * level_weight) / sum(level_weight)
```

---

## 🤖 Model Architecture

### Ensemble Approach

#### **1. Gradient Boosting (Primary)**
```python
from xgboost import XGBRegressor

xgb_model = XGBRegressor(
    n_estimators=1000,
    max_depth=6,
    learning_rate=0.01,
    subsample=0.8,
    colsample_bytree=0.8,
    objective='reg:squarederror'
)
```

#### **2. Deep Neural Network (Pattern Detection)**
```python
from tensorflow.keras import Sequential, layers

dnn_model = Sequential([
    layers.Dense(256, activation='relu', input_dim=n_features),
    layers.BatchNormalization(),
    layers.Dropout(0.3),
    layers.Dense(128, activation='relu'),
    layers.BatchNormalization(),
    layers.Dropout(0.2),
    layers.Dense(64, activation='relu'),
    layers.Dense(1)  # wRC+ prediction
])
```

#### **3. Random Forest (Stability)**
```python
from sklearn.ensemble import RandomForestRegressor

rf_model = RandomForestRegressor(
    n_estimators=500,
    max_depth=20,
    min_samples_split=20,
    min_samples_leaf=10
)
```

### Final Ensemble
```python
predictions = (
    0.50 * xgb_predictions +
    0.30 * dnn_predictions +
    0.20 * rf_predictions
)
```

---

## 👥 Player Comparison System

### Similarity Metrics

#### **1. Statistical Similarity**
```python
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

# Normalize stats
scaler = StandardScaler()
normalized_stats = scaler.fit_transform(player_stats)

# Find similar players
similarity_scores = cosine_similarity(prospect_vector, mlb_players_matrix)
top_10_comps = similarity_scores.argsort()[-10:]
```

#### **2. Trajectory Matching**
```python
from fastdtw import fastdtw

# Dynamic Time Warping for development paths
def find_similar_trajectories(prospect_path, mlb_paths):
    distances = []
    for mlb_path in mlb_paths:
        distance, _ = fastdtw(prospect_path, mlb_path)
        distances.append(distance)
    return np.argsort(distances)[:10]
```

#### **3. Age-Adjusted Comps**
```python
# Only compare players at same age
same_age_pool = mlb_players[mlb_players['age'] == prospect['age']]
comps = find_most_similar(prospect, same_age_pool)
```

---

## 📈 Age Curve Modeling

### Peak Performance Projection
```python
def project_peak_wrc_plus(current_wrc_plus, current_age):
    """Project peak wRC+ based on typical aging curves."""

    # Typical age curve multipliers
    age_factors = {
        20: 0.70, 21: 0.75, 22: 0.82, 23: 0.89,
        24: 0.94, 25: 0.97, 26: 0.99, 27: 1.00,  # Peak
        28: 0.99, 29: 0.97, 30: 0.94, 31: 0.90
    }

    current_factor = age_factors.get(current_age, 0.85)
    peak_factor = age_factors[27]

    # Adjust for development trajectory
    peak_projection = current_wrc_plus * (peak_factor / current_factor)

    # Add uncertainty based on age distance from peak
    years_to_peak = abs(27 - current_age)
    confidence = 1.0 - (years_to_peak * 0.1)

    return {
        'peak_wrc_plus': peak_projection,
        'confidence': confidence,
        'peak_age': 27
    }
```

---

## 🔄 Implementation Pipeline

### Phase 1: Data Preparation (Week 1)
1. **Collect Missing MLB Data**
   ```bash
   python scripts/collect_mlb_gamelogs.py --seasons 2021 2022 2023
   ```

2. **Calculate Advanced Metrics**
   ```python
   # Calculate wOBA from game logs
   woba = (0.69*walks + 0.72*hbp + 0.89*singles +
           1.27*doubles + 1.62*triples + 2.10*homers) / pa
   ```

3. **Get Player Ages**
   ```bash
   python scripts/collect_player_birth_dates.py
   ```

### Phase 2: Feature Engineering (Week 2)
1. Create aggregated features per player-season
2. Calculate age-adjusted statistics
3. Build trajectory features
4. Generate train/test splits (2021-2023 train, 2024 test)

### Phase 3: Model Training (Week 3)
1. Train individual models (XGBoost, DNN, RF)
2. Optimize hyperparameters via cross-validation
3. Create ensemble predictions
4. Validate on 2024 holdout data

### Phase 4: Comparison System (Week 4)
1. Build MLB player feature database
2. Implement similarity algorithms
3. Create comparison visualizations
4. Generate scouting reports

---

## 🎯 Success Metrics

### Model Performance
- **MAE for wRC+**: < 15 points
- **MAE for wOBA**: < .030
- **MLB Success Classification**: > 85% accuracy
- **Peak Performance R²**: > 0.60

### Business Value
- **Scouting Efficiency**: Identify undervalued prospects
- **Development Tracking**: Monitor prospect progress
- **Trade Analysis**: Evaluate prospect packages
- **Draft Strategy**: Project amateur player outcomes

---

## 🚀 Next Steps

### Immediate Actions
1. Run MLB data collection for missing seasons
2. Implement wOBA/wRC+ calculation from game logs
3. Build age curve database from historical data
4. Create feature engineering pipeline

### Code Structure
```
scripts/
├── ml_pipeline/
│   ├── feature_engineering.py
│   ├── age_curve_modeling.py
│   ├── train_wrc_plus_model.py
│   ├── train_woba_model.py
│   └── player_comparison.py
├── data_collection/
│   ├── collect_remaining_mlb.py
│   ├── calculate_advanced_metrics.py
│   └── get_player_ages.py
└── evaluation/
    ├── backtest_2024.py
    ├── generate_reports.py
    └── visualization.py
```

### Sample Prediction Output
```json
{
  "player_id": 687867,
  "name": "Jackson Holliday",
  "current_age": 21,
  "current_level": "AAA",
  "predictions": {
    "mlb_debut_probability": 0.95,
    "projected_debut": "2024-07",
    "rookie_wrc_plus": 95,
    "peak_wrc_plus": 125,
    "peak_age": 27,
    "confidence": 0.78
  },
  "similar_players": [
    {"name": "Corbin Carroll", "similarity": 0.89},
    {"name": "Gunnar Henderson", "similarity": 0.86},
    {"name": "Bobby Witt Jr.", "similarity": 0.84}
  ],
  "strengths": ["Contact", "Speed", "Plate Discipline"],
  "weaknesses": ["Power Development"],
  "development_trajectory": "On Track - Elite"
}
```

---

## 📊 Risk Factors

### Data Limitations
- Only 11% of MiLB players have MLB outcomes
- Limited to 5 years of historical data
- Missing Statcast/TrackMan data for MiLB

### Mitigation Strategies
- Use transfer learning from MLB players
- Augment with external scouting grades
- Implement confidence intervals on predictions
- Regular model retraining as more data arrives

---

*This strategy leverages your complete 2024-2025 data collection to build state-of-the-art prospect projection models that rival industry tools like ZiPS and Steamer.*