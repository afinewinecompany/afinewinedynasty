# 3. ML Infrastructure

## Training Pipeline

**Model Architecture:**
- **Primary Model**: XGBoost Classifier for binary classification
- **Target Variable**: MLB success (>500 PA or >100 IP within 4 years)
- **Features**: 50+ engineered features including:
  - Age-adjusted performance metrics
  - Level progression rates
  - Scouting grades (20-80 scale normalized)
  - Historical comparisons

**Training Infrastructure:**
```python
# Model training configuration
training_config = {
    'model_type': 'xgboost.XGBClassifier',
    'hyperparameters': {
        'n_estimators': 1000,
        'max_depth': 6,
        'learning_rate': 0.01,
        'subsample': 0.8,
        'colsample_bytree': 0.8
    },
    'validation_strategy': 'time_series_split',
    'retraining_schedule': 'weekly_during_season',
    'target_accuracy': 0.65
}
```

**Model Versioning & Deployment:**
- MLflow for experiment tracking and model registry
- A/B testing framework for model comparison
- Automated rollback on performance degradation
- Model artifacts stored in S3/GCS with versioning

## Inference Service

**Real-Time Prediction API:**
```python
@app.post("/api/ml/predict")
@limiter.limit("10/minute")
async def predict_prospect_success(
    prospect_id: int,
    user: User = Depends(get_current_user)
):
    # Load cached model
    model = await get_cached_model()

    # Get prospect features
    features = await get_prospect_features(prospect_id)

    # Generate prediction with SHAP explanation
    prediction = model.predict_proba([features])[0][1]
    shap_values = await generate_shap_explanation(model, features)

    # Determine confidence level
    confidence = determine_confidence_level(prediction, shap_values)

    return PredictionResponse(
        prospect_id=prospect_id,
        success_probability=prediction,
        confidence_level=confidence,
        explanation=generate_narrative(shap_values)
    )
```

**Performance Optimizations:**
- Model caching in Redis with 1-hour TTL
- Batch prediction capability for rankings updates
- Connection pooling for database queries
- Async processing for non-blocking inference

---
