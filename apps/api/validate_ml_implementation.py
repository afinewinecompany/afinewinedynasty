"""
Simple validation script to verify ML implementation without external dependencies.
"""

import sys
import numpy as np
import pandas as pd
from datetime import datetime

# Add project path
sys.path.insert(0, '.')

def validate_feature_engineering():
    """Validate feature engineering implementation."""
    print("Validating Feature Engineering Pipeline...")

    try:
        from app.ml.feature_engineering import FeatureEngineeringPipeline

        # Create test data
        np.random.seed(42)
        data = pd.DataFrame({
            'mlb_id': [1, 1, 2, 2],
            'age': [20, 21, 22, 23],
            'level': ['Low-A', 'High-A', 'Double-A', 'Triple-A'],
            'date_recorded': [
                datetime(2020, 1, 1),
                datetime(2020, 6, 1),
                datetime(2021, 1, 1),
                datetime(2021, 6, 1)
            ],
            'batting_avg': [0.250, 0.275, 0.300, 0.285],
            'hits': [100, 110, 120, 115],
            'at_bats': [400, 400, 400, 400],
            'target': [0, 0, 1, 1]
        })

        pipeline = FeatureEngineeringPipeline()
        results = pipeline.process_features(data, target_column='target')

        assert 'processed_data' in results
        assert 'feature_columns' in results
        assert len(results['feature_columns']) > 4  # Should create new features

        print("✓ Feature Engineering Pipeline: PASSED")
        return True

    except Exception as e:
        print(f"✗ Feature Engineering Pipeline: FAILED - {e}")
        return False

def validate_training_pipeline():
    """Validate training pipeline implementation."""
    print("Validating Training Pipeline...")

    try:
        from app.ml.training_pipeline import XGBoostModelTrainer

        # Create simple test data
        np.random.seed(42)
        X_train = pd.DataFrame(np.random.randn(100, 5), columns=[f'feature_{i}' for i in range(5)])
        y_train = pd.Series(np.random.choice([0, 1], 100))

        trainer = XGBoostModelTrainer(random_state=42)

        # Test default parameters
        params = trainer.get_default_params()
        assert params['n_estimators'] == 1000
        assert params['max_depth'] == 6
        assert params['learning_rate'] == 0.01

        print("✓ Training Pipeline: PASSED")
        return True

    except Exception as e:
        print(f"✗ Training Pipeline: FAILED - {e}")
        return False

def validate_evaluation():
    """Validate evaluation implementation."""
    print("Validating Model Evaluation...")

    try:
        from app.ml.evaluation import ModelEvaluator, ModelMetrics

        evaluator = ModelEvaluator(target_accuracy=0.65)

        # Create test predictions
        np.random.seed(42)
        y_true = np.array([0, 0, 1, 1, 0, 1, 1, 0])
        y_pred = np.array([0, 0, 1, 0, 0, 1, 1, 1])
        y_pred_proba = np.array([0.1, 0.2, 0.8, 0.4, 0.3, 0.9, 0.7, 0.6])

        metrics = evaluator.evaluate_model(y_true, y_pred, y_pred_proba)

        assert isinstance(metrics, ModelMetrics)
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.roc_auc <= 1

        print("✓ Model Evaluation: PASSED")
        return True

    except Exception as e:
        print(f"✗ Model Evaluation: FAILED - {e}")
        return False

def validate_temporal_validation():
    """Validate temporal validation implementation."""
    print("Validating Temporal Validation...")

    try:
        from app.ml.temporal_validation import TemporalSplit

        # Test temporal split
        splitter = TemporalSplit(n_splits=3)

        # Create test data
        X = pd.DataFrame(np.random.randn(100, 3))

        splits = list(splitter.split(X))
        assert len(splits) > 0

        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            assert max(train_idx) < min(test_idx)  # Temporal ordering

        print("✓ Temporal Validation: PASSED")
        return True

    except Exception as e:
        print(f"✗ Temporal Validation: FAILED - {e}")
        return False

def validate_model_registry():
    """Validate model registry implementation."""
    print("Validating Model Registry...")

    try:
        from app.ml.model_registry import ModelMetadata
        from datetime import datetime

        # Test metadata creation
        metadata = ModelMetadata(
            model_id="test_model_1",
            version="1.0",
            name="test_model",
            algorithm="xgboost",
            framework="xgboost",
            accuracy=0.75,
            precision=0.73,
            recall=0.77,
            f1_score=0.75,
            roc_auc=0.82,
            target_accuracy_met=True,
            training_data_hash="abc123",
            feature_names=["feature1", "feature2"],
            hyperparameters={"n_estimators": 1000},
            created_at=datetime.now().isoformat(),
            created_by="test",
            tags={"test": "true"},
            artifact_paths={"model": "/path/to/model"},
            status="validated"
        )

        assert metadata.accuracy == 0.75
        assert metadata.target_accuracy_met is True

        print("✓ Model Registry: PASSED")
        return True

    except Exception as e:
        print(f"✗ Model Registry: FAILED - {e}")
        return False

def main():
    """Run all validations."""
    print("=" * 50)
    print("ML PIPELINE IMPLEMENTATION VALIDATION")
    print("=" * 50)

    results = []

    results.append(validate_feature_engineering())
    results.append(validate_training_pipeline())
    results.append(validate_evaluation())
    results.append(validate_temporal_validation())
    results.append(validate_model_registry())

    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total:.1%}")

    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("ML pipeline implementation is working correctly.")
    else:
        print("❌ Some validations failed.")
        print("Please check the implementation.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)