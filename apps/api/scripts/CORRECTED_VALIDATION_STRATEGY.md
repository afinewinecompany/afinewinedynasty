# Corrected ML Validation Strategy

**Date:** October 19, 2025
**Issue:** Original plan assumed we had historical Fangraphs FV labels
**Reality:** We only have 2025 FV grades, but we DO have 2021-2025 performance data

---

## Data Availability Summary

### What We HAVE ✅

| Data Source | Seasons Available | Count |
|-------------|-------------------|-------|
| **MiLB Game Logs** | 2021-2025 (5 years) | 1.3M+ records |
| **Fangraphs FV Grades** | 2025 only | 1,267 prospects |
| **MLB Expectation Labels** | 2025 only | 1,267 prospects |
| **Pitch Tracking (limited)** | Mostly 2025 | 1.2M+ pitches |

### Multi-Season Prospect Coverage

| Coverage | Count |
|----------|-------|
| Prospects with ANY game log data | 1,220 |
| Prospects with 2+ seasons | 989 |
| Prospects with 3+ seasons | 714 |
| Prospects with 4+ seasons | 400 |
| Prospects with all 5 seasons | 145 |

---

## Why We Can't Do Traditional Temporal Split

### The Problem

```python
# DOESN'T WORK - No labels for 2021-2023!
train_data = game_logs[2021-2023]  # ✅ Have performance data
train_labels = fv_grades[2021-2023]  # ❌ DON'T have FV labels!

# We ONLY have labels for 2025
train_labels = fv_grades[2025]  # ✅ Have 1,267 labeled prospects
```

### Why This Matters

- Fangraphs publishes **current** prospect grades each year
- We imported the **2025 edition** of "The Board"
- Historical FV grades would require scraping past years' data
- Without labels, we can't train supervised ML models on 2021-2023 data

---

## Recommended Solution: Multi-Season Features, Single-Year Target

### Approach

**Use historical performance data (2021-2024) as FEATURES**
**Use 2025 FV grades as TARGET**

### Example Feature Set

```python
# For each prospect with a 2025 FV label
features = {
    # === 2025 Performance (Current Year) ===
    'ops_2025': 0.850,
    'level_2025': 'AA',
    'age_2025': 21.5,
    'games_2025': 120,

    # === Historical Trends (2021-2024) ===
    'ops_2024': 0.820,
    'ops_2023': 0.780,
    'ops_2022': 0.720,
    'ops_trend': 0.043,  # (2024 - 2021) / 3 = improvement rate

    # Level progression
    'level_2024': 'A+',
    'level_2023': 'A',
    'levels_climbed': 2,  # A → A+ → AA

    # Experience
    'seasons_played': 4,
    'total_games': 380,

    # Age-relative performance
    'ops_vs_age_cohort_2025': 0.15,  # +150 points above age average
    'was_young_for_level_2024': True,

    # Consistency
    'ops_std_dev': 0.08,  # Low variance = consistent
    'best_month_ops': 1.050,
    'worst_month_ops': 0.650,

    # === Fangraphs Scouting Grades (2025) ===
    'hit_future': 50,
    'power_future': 55,
    'speed_future': 60,
    'field_future': 50,

    # === Physical Attributes ===
    'frame_grade': 1,
    'athleticism_grade': 2,
    'arm_grade': 60,
}

# Target (2025 FV grade)
target = 'Regular'  # or mlb_expectation_numeric = 2
```

### Benefits

✅ **Leverage ALL available data** (5 years of performance)
✅ **Progression matters** - Models can learn from improvement trends
✅ **Age curves** - Younger players at higher levels = higher ceiling
✅ **Risk assessment** - Consistency vs. volatility
✅ **Works with available labels** (2025 FV grades)

---

## Validation Strategy (Revised)

### Option A: Stratified K-Fold Cross-Validation (RECOMMENDED)

```python
from sklearn.model_selection import StratifiedKFold
import numpy as np

# Prepare 2025 dataset with multi-season features
df = prepare_multi_season_features(prospects_2025)
X = df.drop(['target'], axis=1)
y = df['target']  # mlb_expectation_numeric (0-3)

# 5-fold stratified cross-validation
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

fold_scores = []
for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
    print(f"\n=== Fold {fold_idx + 1}/5 ===")

    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    # Train model
    model = XGBClassifier(
        objective='multi:softmax',
        num_class=4,
        scale_pos_weight=compute_class_weights(y_train)
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_val)
    f1 = f1_score(y_val, y_pred, average='weighted')
    fold_scores.append(f1)

    print(f"Weighted F1: {f1:.3f}")
    print(classification_report(y_val, y_pred,
          target_names=['Bench', 'Part-Time', 'Regular', 'All-Star']))

# Overall performance
print(f"\nMean Weighted F1: {np.mean(fold_scores):.3f} (+/- {np.std(fold_scores):.3f})")
```

**Pros:**
- ✅ Each fold uses different train/val splits
- ✅ Stratification maintains class distribution
- ✅ Get robust performance estimate (5 different splits)
- ✅ Works with available 2025 labels

**Cons:**
- ⚠️ No true temporal holdout (all data from same year)
- ⚠️ Can't test on "unseen future" data

### Option B: Holdout Validation (Simpler)

```python
from sklearn.model_selection import train_test_split

# Single train/val split (stratified)
X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.20,
    stratify=y,  # Maintain class distribution
    random_state=42
)

# Train model
model = XGBClassifier(...)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_val)
print(classification_report(y_val, y_pred))
```

**Pros:**
- ✅ Simple and fast
- ✅ Clear train/val separation
- ✅ Stratification maintains classes

**Cons:**
- ⚠️ Only one train/val split (less robust)
- ⚠️ Smaller validation set (20% of data)

---

## Feature Engineering: Leveraging Multi-Season Data

### 1. Trend Features (Most Powerful!)

```python
# Calculate improvement rate over time
def calculate_trend(player_stats):
    """
    Linear regression slope of stat over seasons
    Positive = improving, Negative = declining
    """
    seasons = [2021, 2022, 2023, 2024, 2025]
    ops_values = [player_stats.get(s, {}).get('ops') for s in seasons]

    # Remove None values
    valid_data = [(s, v) for s, v in zip(seasons, ops_values) if v is not None]

    if len(valid_data) < 2:
        return None

    # Simple linear regression
    from scipy import stats
    x = [s for s, _ in valid_data]
    y = [v for _, v in valid_data]
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    return {
        'ops_trend_slope': slope,
        'ops_trend_r2': r_value**2,
        'ops_trajectory': 'improving' if slope > 0 else 'declining'
    }
```

### 2. Level Progression Features

```python
def calculate_level_progression(player_history):
    """
    Track player's movement through MiLB levels
    """
    level_hierarchy = {
        'Rookie': 1,
        'A': 2,
        'A+': 3,
        'AA': 4,
        'AAA': 5
    }

    levels_by_year = [
        level_hierarchy.get(player_history[year]['level'], 0)
        for year in [2021, 2022, 2023, 2024, 2025]
        if year in player_history
    ]

    if len(levels_by_year) < 2:
        return None

    return {
        'highest_level_reached': max(levels_by_year),
        'current_level': levels_by_year[-1],
        'levels_climbed': max(levels_by_year) - min(levels_by_year),
        'stuck_at_level': levels_by_year[-1] == levels_by_year[-2],  # No promotion
        'promoted_this_year': levels_by_year[-1] > levels_by_year[-2],
        'demoted_this_year': levels_by_year[-1] < levels_by_year[-2],
    }
```

### 3. Age-Relative Performance Over Time

```python
def calculate_age_relative_history(player_id):
    """
    How did player perform relative to age cohort each year?
    """
    age_relative_ops = []

    for year in [2021, 2022, 2023, 2024, 2025]:
        # Get player's OPS at their level
        player_ops = get_player_stat(player_id, year, 'ops')
        player_level = get_player_stat(player_id, year, 'level')
        player_age = get_player_age(player_id, year)

        # Get league average OPS for that age/level
        league_avg = get_league_average_ops(player_age, player_level, year)

        # Calculate difference
        if player_ops and league_avg:
            age_relative_ops.append(player_ops - league_avg)

    if len(age_relative_ops) < 2:
        return None

    return {
        'avg_ops_vs_age_cohort': np.mean(age_relative_ops),
        'ops_vs_age_improving': age_relative_ops[-1] > age_relative_ops[0],
        'best_year_vs_age': max(age_relative_ops),
        'consistency_vs_age': np.std(age_relative_ops),  # Lower = more consistent
    }
```

### 4. Consistency/Volatility Features

```python
def calculate_consistency(player_stats):
    """
    How consistent is the player's performance?
    """
    monthly_ops = [
        player_stats[month]['ops']
        for month in ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
        if 'ops' in player_stats.get(month, {})
    ]

    if len(monthly_ops) < 3:
        return None

    return {
        'ops_std_dev': np.std(monthly_ops),
        'ops_range': max(monthly_ops) - min(monthly_ops),
        'ops_best_month': max(monthly_ops),
        'ops_worst_month': min(monthly_ops),
        'hot_streak_potential': max(monthly_ops) - np.mean(monthly_ops),
        'floor_performance': min(monthly_ops),
    }
```

---

## Example: Full Feature Engineering Pipeline

```python
def build_ml_dataset_with_multi_season_features():
    """
    Build complete dataset for ML training
    """
    features_list = []

    # For each prospect with a 2025 FV label
    for prospect in prospects_with_2025_labels:

        # Get multi-season history
        history = get_player_history(prospect.id, seasons=[2021, 2022, 2023, 2024, 2025])

        # Current year (2025) features
        current_features = {
            'ops_2025': history[2025]['ops'],
            'level_2025': level_to_numeric(history[2025]['level']),
            'age_2025': calculate_age(prospect.birth_date, '2025-07-01'),
            'games_2025': history[2025]['games'],
        }

        # Historical trends
        trend_features = calculate_trend(history)

        # Level progression
        progression_features = calculate_level_progression(history)

        # Age-relative performance
        age_relative_features = calculate_age_relative_history(prospect.id)

        # Consistency
        consistency_features = calculate_consistency(history[2025])

        # Fangraphs grades (2025)
        scouting_features = {
            'hit_future': prospect.hit_future,
            'power_future': prospect.power_future,
            'speed_future': prospect.speed_future,
            'field_future': prospect.field_future,
        }

        # Physical attributes
        physical_features = {
            'frame_grade': prospect.frame_grade,
            'athleticism_grade': prospect.athleticism_grade,
            'arm_grade': prospect.arm_grade,
        }

        # Combine all features
        all_features = {
            **current_features,
            **trend_features,
            **progression_features,
            **age_relative_features,
            **consistency_features,
            **scouting_features,
            **physical_features,
        }

        # Add target
        all_features['target'] = prospect.mlb_expectation_numeric

        features_list.append(all_features)

    # Convert to DataFrame
    df = pd.DataFrame(features_list)

    return df
```

---

## Future: When You Get More Historical FV Grades

### If You Scrape Past Years' Fangraphs Data

Once you have FV grades for 2021-2024, you CAN do true temporal validation:

```python
# With historical labels, temporal split becomes possible
train_df = df[df['season'].between(2021, 2023)]
val_df = df[df['season'] == 2024]
test_df = df[df['season'] == 2025]

# Train on past years
model.fit(train_df[features], train_df['target'])

# Validate on 2024
val_pred = model.predict(val_df[features])

# Test on 2025 (true holdout)
test_pred = model.predict(test_df[features])
```

### Where to Get Historical FV Grades

- **Fangraphs archives** (may require subscription)
- **Baseball Prospectus** (alternative prospect grades)
- **MLB Pipeline** (historical rankings)
- **Internet Archive / Wayback Machine** (saved pages)

---

## Summary

### What You Should Do NOW

✅ **Use Stratified K-Fold Cross-Validation** with 2025 data
✅ **Build multi-season features** from 2021-2025 game logs
✅ **Focus on trend/progression features** (most predictive)
✅ **Expect Weighted F1 of 0.55-0.70** (realistic with single year)

### What to Do LATER (Optional)

🔄 **Scrape historical FV grades** (2021-2024)
🔄 **Implement true temporal validation**
🔄 **Test on 2026 prospects** (when 2026 data available)

---

**Key Insight:** You have PLENTY of multi-season performance data (2021-2025). The limitation is only on the TARGET labels (FV grades), which you only have for 2025. By using multi-season features with 2025 targets, you can still build a powerful model that learns from 5 years of player progression!

---

**Status:** ✅ Corrected validation strategy
**Date:** October 19, 2025
**Author:** BMad Party Mode Team
