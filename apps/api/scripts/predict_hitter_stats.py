"""
Hitter Stat Projection - Prediction Utility
===========================================

This module provides functions to generate MLB stat projections for prospects
using the trained model.

Usage:
    from predict_hitter_stats import predict_hitter_stats, load_models

    models, features, targets = load_models()
    predictions = predict_hitter_stats(models, features, prospect_data)
"""

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def load_models(model_dir: Optional[str] = None) -> Tuple[Dict, List[str], List[str]]:
    """
    Load the trained models and metadata.

    Returns:
        models: Dictionary of trained models (one per target)
        feature_names: List of feature names expected by models
        target_names: List of target stat names
    """

    if model_dir is None:
        model_dir = Path(__file__).parent.parent
    else:
        model_dir = Path(model_dir)

    # Find most recent improved model
    model_files = list(model_dir.glob('hitter_models_improved_*.joblib'))

    if not model_files:
        raise FileNotFoundError("No improved hitter models found!")

    # Get most recent
    latest_model_file = max(model_files, key=lambda p: p.stat().st_mtime)
    timestamp = latest_model_file.stem.split('_')[-2] + '_' + latest_model_file.stem.split('_')[-1]

    # Load models
    models = joblib.load(latest_model_file)

    # Load feature names
    feature_file = model_dir / f'hitter_features_improved_{timestamp}.txt'
    with open(feature_file, 'r') as f:
        feature_names = [line.strip() for line in f.readlines()]

    # Load target names
    target_file = model_dir / f'hitter_targets_improved_{timestamp}.txt'
    with open(target_file, 'r') as f:
        target_names = [line.strip() for line in f.readlines()]

    return models, feature_names, target_names


def prepare_prospect_features(prospect_data: Dict, feature_names: List[str]) -> pd.DataFrame:
    """
    Prepare prospect data for prediction.

    Args:
        prospect_data: Dictionary with prospect's MiLB stats
        feature_names: List of features expected by model

    Returns:
        DataFrame with features in correct order
    """

    # Create feature vector
    features = {}

    for feature in feature_names:
        # Get value from prospect data, default to 0 if missing
        features[feature] = prospect_data.get(feature, 0)

    # Convert to DataFrame (single row)
    df = pd.DataFrame([features])

    # Ensure numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df


def predict_hitter_stats(
    models: Dict,
    feature_names: List[str],
    target_names: List[str],
    prospect_data: Dict
) -> Dict[str, float]:
    """
    Generate MLB stat projections for a prospect.

    Args:
        models: Dictionary of trained models
        feature_names: List of feature names
        target_names: List of target stat names
        prospect_data: Dictionary with prospect's MiLB stats

    Returns:
        Dictionary with projected MLB stats
    """

    # Prepare features
    X = prepare_prospect_features(prospect_data, feature_names)

    # Generate predictions for each target
    predictions = {}

    for target in target_names:
        model = models[target]
        pred = model.predict(X)[0]

        # Clip to reasonable ranges
        if 'avg' in target or 'obp' in target or 'slg' in target:
            pred = np.clip(pred, 0.150, 0.450)  # AVG/OBP/SLG range
        elif 'ops' in target:
            pred = np.clip(pred, 0.400, 1.200)  # OPS range
        elif 'rate' in target:
            pred = np.clip(pred, 0.0, 0.50)  # Rate stats (0-50%)
        elif 'iso' in target:
            pred = np.clip(pred, 0.0, 0.350)  # ISO range

        predictions[target.replace('target_', '')] = round(pred, 3)

    return predictions


def predict_batch(
    models: Dict,
    feature_names: List[str],
    target_names: List[str],
    prospects: List[Dict]
) -> List[Dict]:
    """
    Generate predictions for multiple prospects.

    Args:
        models: Dictionary of trained models
        feature_names: List of feature names
        target_names: List of target stat names
        prospects: List of prospect data dictionaries

    Returns:
        List of prediction dictionaries
    """

    results = []

    for prospect in prospects:
        predictions = predict_hitter_stats(models, feature_names, target_names, prospect)

        result = {
            'prospect_id': prospect.get('prospect_id'),
            'name': prospect.get('name'),
            'position': prospect.get('position'),
            'predictions': predictions
        }

        results.append(result)

    return results


def format_prediction_display(predictions: Dict[str, float]) -> str:
    """
    Format predictions for display.

    Args:
        predictions: Dictionary of predicted stats

    Returns:
        Formatted string
    """

    output = []
    output.append("Projected MLB Stats:")
    output.append("-" * 40)

    # Slash line
    avg = predictions.get('avg', 0)
    obp = predictions.get('obp', 0)
    slg = predictions.get('slg', 0)
    output.append(f"Slash Line:  {avg:.3f}/{obp:.3f}/{slg:.3f}")

    # Other stats
    if 'ops' in predictions:
        output.append(f"OPS:         {predictions['ops']:.3f}")

    if 'iso' in predictions:
        output.append(f"ISO:         {predictions['iso']:.3f}")

    if 'bb_rate' in predictions:
        output.append(f"BB%:         {predictions['bb_rate']*100:.1f}%")

    if 'k_rate' in predictions:
        output.append(f"K%:          {predictions['k_rate']*100:.1f}%")

    return '\n'.join(output)


# Example usage
if __name__ == "__main__":
    # Load models
    print("Loading models...")
    models, features, targets = load_models()

    print(f"[OK] Loaded {len(models)} models")
    print(f"[OK] Features: {len(features)}")
    print(f"[OK] Targets: {targets}")

    # Example prospect data (you would get this from database)
    example_prospect = {
        'prospect_id': 9544,
        'name': 'Bobby Witt Jr.',
        'position': 'SS',
        'season': 2021,
        'games': 62,
        'pa': 286,
        'ab': 255,
        'r': 50,
        'h': 74,
        'doubles': 26,
        'triples': 0,
        'hr': 17,
        'rbi': 46,
        'bb': 26,
        'so': 63,
        'sb': 0,
        'avg': 0.290,
        'obp': 0.327,
        'slg': 0.481,
        'ops': 0.798,
        'iso': 0.191,
        'bb_rate': 0.091,
        'k_rate': 0.220,
        'xbh': 43,
        'xbh_rate': 0.169,
        'bb_per_k': 0.41,
        'sb_success_rate': 0.0
    }

    # Generate prediction
    print(f"\nGenerating projection for {example_prospect['name']}...")
    predictions = predict_hitter_stats(models, features, targets, example_prospect)

    print("\n" + format_prediction_display(predictions))

    print("\nRaw predictions:")
    for stat, value in predictions.items():
        print(f"  {stat}: {value}")
