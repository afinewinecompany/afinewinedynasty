"""Train age-aware MLB performance predictor using actual MiLB->MLB transitions."""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import pickle

print('AGE-AWARE MLB PERFORMANCE PREDICTOR')
print('=' * 80)

# Load transition data
print('\n1. Loading MiLB->MLB transitions...')
df = pd.read_csv('milb_to_mlb_transitions.csv')
print(f'   Loaded {len(df)} transitions from {df["mlb_player_id"].nunique()} players')

# Feature engineering
print('\n2. Engineering features...')

# Level encoding (AA/AAA are most predictive)
level_encoding = {'AAA': 1.0, 'AA': 0.85, 'A+': 0.65, 'A': 0.50, 'Rookie': 0.30}
df['level_quality'] = df['milb_level'].map(level_encoding).fillna(0.50)

# MiLB advanced stats (already calculated)
df['milb_woba'] = (df['milb_obp'] - 0.1) * 0.85
df['milb_wrc_plus'] = ((df['milb_woba'] - 0.320) / 1.25) * 100 + 100

# Age features
df['is_young'] = (df['milb_age'] <= 22).astype(int)
df['is_elite_age'] = (df['milb_age'] <= 21).astype(int)
df['age_squared'] = df['milb_age'] ** 2

# Performance * Level interactions
df['ops_x_level'] = df['milb_ops'] * df['level_quality']
df['iso_x_level'] = df['milb_iso'] * df['level_quality']
df['bb_rate_x_level'] = df['milb_bb_rate'] * df['level_quality']

# MLB target stats
df['mlb_woba'] = (df['mlb_obp'] - 0.1) * 0.85
df['mlb_wrc_plus'] = ((df['mlb_woba'] - 0.320) / 1.25) * 100 + 100
df['mlb_wrc_plus'] = df['mlb_wrc_plus'].clip(40, 160)

# Filter to quality transitions (sufficient PA in both levels)
df_train = df[
    (df['milb_pa'] >= 200) &
    (df['mlb_pa'] >= 150) &
    (df['milb_age'] <= 26) &
    (df['age_gap'] <= 3)  # Only use transitions within 3 years
].copy()

print(f'   Filtered to {len(df_train)} quality transitions')

# Define features
feature_cols = [
    # MiLB performance
    'milb_ops', 'milb_iso', 'milb_bb_rate', 'milb_k_rate', 'milb_avg',

    # Age context
    'milb_age', 'age_squared', 'is_young', 'is_elite_age', 'age_gap',

    # Level quality
    'level_quality',

    # Interactions
    'ops_x_level', 'iso_x_level', 'bb_rate_x_level',

    # Volume
    'milb_pa'
]

target_cols = [
    'mlb_ops', 'mlb_obp', 'mlb_slg', 'mlb_iso',
    'mlb_wrc_plus', 'mlb_bb_rate', 'mlb_k_rate'
]

# Remove any rows with missing features
df_train = df_train.dropna(subset=feature_cols + target_cols)
print(f'   Final training set: {len(df_train)} transitions')

# Train models for each target
print('\n3. Training models...')
print('=' * 80)

models = {}
X = df_train[feature_cols]

for target in target_cols:
    y = df_train[target]

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train Random Forest
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)

    # Train Gradient Boosting
    gb = GradientBoostingRegressor(
        n_estimators=150,
        max_depth=6,
        learning_rate=0.05,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42
    )
    gb.fit(X_train, y_train)

    # Ensemble (average predictions)
    y_pred_rf = rf.predict(X_test)
    y_pred_gb = gb.predict(X_test)
    y_pred = (y_pred_rf + y_pred_gb) / 2

    # Evaluate
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f'\n{target}:')
    print(f'  R² = {r2:.3f}')
    print(f'  MAE = {mae:.3f}')
    print(f'  Top 3 features:')

    # Feature importance (from RF)
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)

    for idx, row in feature_importance.head(3).iterrows():
        print(f'    {row["feature"]}: {row["importance"]:.3f}')

    # Save both models for ensemble
    models[target] = {'rf': rf, 'gb': gb}

# Save models
print('\n' + '=' * 80)
print('4. Saving models...')

model_data = {
    'models': models,
    'feature_cols': feature_cols,
    'target_cols': target_cols,
    'level_encoding': level_encoding
}

with open('age_aware_mlb_predictor.pkl', 'wb') as f:
    pickle.dump(model_data, f)

print(f'   Saved to age_aware_mlb_predictor.pkl')

# Sample predictions
print('\n' + '=' * 80)
print('5. Sample Predictions (AA age 20-21)')
print('=' * 80)

sample = df_train[
    (df_train['milb_level'].isin(['AA', 'AAA'])) &
    (df_train['milb_age'].between(20, 21)) &
    (df_train['age_gap'] == 1)
].head(10)

if len(sample) > 0:
    X_sample = sample[feature_cols]

    # Predict wRC+
    rf = models['mlb_wrc_plus']['rf']
    gb = models['mlb_wrc_plus']['gb']
    pred_wrc = (rf.predict(X_sample) + gb.predict(X_sample)) / 2

    results = sample[['full_name', 'milb_age', 'milb_level', 'milb_ops', 'mlb_wrc_plus']].copy()
    results['predicted_wrc_plus'] = pred_wrc
    results['error'] = results['predicted_wrc_plus'] - results['mlb_wrc_plus']

    print(results.to_string(index=False))

print('\n[COMPLETE] Age-aware MLB predictor trained!')
print('=' * 80)
