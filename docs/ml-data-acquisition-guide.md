# ML Data Acquisition Guide - Hybrid Approach

## 🎯 Overview

This guide implements the **Hybrid Strategy** for ML data acquisition:
- **Fast Track**: MVP dataset (5 years, 10K prospects) in 2-3 weeks
- **Parallel Track**: Full 15-year dataset collection in background
- **Result**: Working ML model ASAP + continuous improvement

---

## 📋 Prerequisites

✅ MLB Stats API integration - READY
✅ Fangraphs scraping service - READY
✅ Apache Airflow pipeline - READY
✅ Feature engineering pipeline - READY
✅ Target variable creator - **CREATED** ✨
✅ MVP collection script - **CREATED** ✨

---

## 🚀 Quick Start (Week 1)

### Step 1: Test API Access

```bash
# Test MLB API historical access
cd apps/api
python -c "
import asyncio
from app.services.mlb_api_service import MLBAPIClient

async def test():
    async with MLBAPIClient() as client:
        data = await client.get_prospects_data()
        print(f'✅ MLB API working: {len(data.get(\"people\", []))} prospects')

asyncio.run(test())
"
```

```bash
# Test Fangraphs access
python -c "
import asyncio
from app.services.fangraphs_service import FangraphsService

async def test():
    async with FangraphsService() as service:
        prospects = await service.get_top_prospects_list(year=2024, limit=10)
        print(f'✅ Fangraphs working: {len(prospects)} prospects retrieved')

asyncio.run(test())
"
```

### Step 2: Run MVP Data Collection

```bash
# Collect 5 years of historical data (2020-2024)
python scripts/run_mvp_data_collection.py \
    --start-year 2020 \
    --end-year 2024

# Expected: ~10,000 prospects collected
# Duration: 2-6 hours (depending on rate limits)
```

### Step 3: Test Success Definitions

```bash
# Test which success definition works best for your data
python scripts/run_mvp_data_collection.py \
    --start-year 2020 \
    --end-year 2020 \
    --test-definitions

# This will show you which threshold (strict/moderate/loose)
# gives the best balanced dataset
```

---

## 📊 Expected Results

After MVP collection completes, you should have:

```
✅ Prospects Collected: 8,000 - 12,000
✅ Labeled with MLB Outcomes: 8,000 - 12,000
✅ Success Rate: 30% - 50% (ideal for balanced training)
✅ Training Data: Ready for ML model
```

---

## 🔄 Week 2: Train Initial Model

### Step 1: Prepare Training Data

```bash
cd apps/api
python -c "
import asyncio
from app.ml.training_pipeline import ModelTrainingPipeline
from app.core.database import get_db
import pandas as pd

async def prepare_data():
    # Load collected and labeled data
    async with get_db() as db:
        # Query prospects with labels
        query = '''
            SELECT p.*, ps.*, ml.mlb_success
            FROM prospects p
            JOIN prospect_stats ps ON p.id = ps.prospect_id
            JOIN ml_labels ml ON p.mlb_id = ml.mlb_id
            WHERE p.prospect_year >= 2020
        '''

        df = pd.read_sql(query, db.connection())
        print(f'✅ Loaded {len(df)} prospects with features and labels')

        # Prepare training splits
        pipeline = ModelTrainingPipeline()
        data_splits = pipeline.prepare_training_data(
            df,
            target_column='mlb_success',
            temporal_split=True
        )

        print(f'Train: {len(data_splits[\"X_train\"])} samples')
        print(f'Val: {len(data_splits[\"X_val\"])} samples')
        print(f'Test: {len(data_splits[\"X_test\"])} samples')

asyncio.run(prepare_data())
"
```

### Step 2: Train Model

```bash
# Train with default parameters (fast)
python -c "
import asyncio
from app.ml.training_pipeline import ModelTrainingPipeline

async def train():
    pipeline = ModelTrainingPipeline()

    # ... load data_splits from Step 1 ...

    results = pipeline.train_model(
        data_splits,
        hyperparameter_tuning='none'  # Use defaults for speed
    )

    print(f'✅ Model trained!')
    print(f'Test Accuracy: {results[\"test_results\"][\"accuracy\"]:.1%}')
    print(f'Target (65%): {\"✅ MET\" if results[\"target_accuracy_achieved\"] else \"❌ NOT MET\"}')

asyncio.run(train())
"
```

### Step 3: Validate Model

```bash
# Check if we hit 60%+ accuracy target
# If yes → Deploy to inference service
# If no → Need more data or feature engineering
```

---

## 🔄 Parallel Track: Full 15-Year Collection

While your MVP model is training, start the full historical collection:

```bash
# Run in background (nohup for long-running)
nohup python scripts/run_mvp_data_collection.py \
    --start-year 2008 \
    --end-year 2024 \
    > full_collection.log 2>&1 &

# Monitor progress
tail -f full_collection.log
```

**Expected Timeline:**
- 2-4 weeks for complete collection (rate limits)
- 40,000 - 60,000 prospects
- Better model accuracy (potentially 65%+)

---

## 🎯 Success Criteria Checklist

### Week 1 ✅
- [ ] APIs tested and working
- [ ] MVP data collection completed (~10K prospects)
- [ ] Prospects labeled with MLB outcomes
- [ ] Success rate 30-50% (balanced dataset)

### Week 2 ✅
- [ ] Training data prepared with temporal splits
- [ ] Initial model trained with default params
- [ ] Model accuracy measured (target: 60%+)
- [ ] Full 15-year collection started in background

### Week 3 ✅
- [ ] Model deployed to inference service
- [ ] <500ms prediction latency validated
- [ ] API integration tested end-to-end
- [ ] First SHAP explanations generated

### Week 4-8 🔄
- [ ] Full 15-year dataset collection completed
- [ ] Model retrained with full data
- [ ] 65% accuracy target achieved
- [ ] Production deployment ready

---

## ⚠️ Troubleshooting

### Issue: "MLB API rate limit exceeded"
```bash
# Solution: Reduce batch size or add delays
# Edit apps/api/app/services/mlb_api_service.py
# Increase: self.request_delay from 0.1 to 1.0 seconds
```

### Issue: "Fangraphs scraping fails"
```bash
# Solution: Check circuit breaker status
python -c "
import asyncio
from app.services.fangraphs_service import FangraphsService

async def check():
    async with FangraphsService() as service:
        health = service.get_service_health()
        print(health)

asyncio.run(check())
"

# Reset circuit breaker if needed
# service.reset_circuit_breaker()
```

### Issue: "Success rate too low (<20%)"
```bash
# Solution: Use 'moderate' or 'loose' success definition
# Re-run labeling with different threshold
python scripts/run_mvp_data_collection.py \
    --start-year 2020 \
    --end-year 2024 \
    --test-definitions
```

### Issue: "Not enough data for training"
```bash
# Solution: Expand year range
python scripts/run_mvp_data_collection.py \
    --start-year 2018 \  # Go back 2 more years
    --end-year 2024
```

---

## 📈 Monitoring Progress

### Check Collection Stats
```bash
# View log file
tail -f mvp_data_collection_*.log

# Check database
psql $DATABASE_URL -c "
SELECT
    prospect_year,
    COUNT(*) as prospect_count,
    COUNT(CASE WHEN mlb_success = true THEN 1 END) as successes
FROM prospects
WHERE prospect_year >= 2020
GROUP BY prospect_year
ORDER BY prospect_year;
"
```

### Validate Data Quality
```bash
python -c "
from app.ml.target_variable_creator import TargetVariableCreator

labeler = TargetVariableCreator()
# ... load your labeled results ...
distribution = labeler.analyze_success_distribution(results)
print(f'Balanced: {distribution[\"balanced_dataset\"]}')
print(f'Success rate: {distribution[\"success_rate\"]:.1%}')
"
```

---

## 🎓 Next Steps After MVP

1. **Deploy MVP Model** (Week 3)
   - Load model to inference service
   - Test <500ms latency
   - Generate first predictions

2. **Monitor Performance** (Week 3-4)
   - Track prediction accuracy
   - Collect user feedback
   - Identify edge cases

3. **Improve with Full Dataset** (Week 5-8)
   - Complete 15-year collection
   - Retrain with 50K prospects
   - Achieve 65% accuracy target
   - Deploy improved model

---

## 📚 Reference

- **PRD**: [docs/prd.md](prd.md) - Story 2.1 (Historical Data Collection)
- **Architecture**: [docs/technical-architecture/3-ml-infrastructure.md](technical-architecture/3-ml-infrastructure.md)
- **Training Pipeline**: [apps/api/app/ml/training_pipeline.py](../apps/api/app/ml/training_pipeline.py)
- **Feature Engineering**: [apps/api/app/ml/feature_engineering.py](../apps/api/app/ml/feature_engineering.py)

---

## 🎯 Success Metrics

**MVP (Week 3):**
- ✅ 10,000+ labeled prospects
- ✅ 60%+ model accuracy
- ✅ <500ms inference latency
- ✅ Working SHAP explanations

**Full (Week 8):**
- ✅ 50,000+ labeled prospects
- ✅ 65%+ model accuracy
- ✅ Production-ready ML service
- ✅ All Epic 2 stories complete

---

**Let's get started!** 🚀

Run the MVP collection script now:
```bash
cd apps/api
python scripts/run_mvp_data_collection.py
```
