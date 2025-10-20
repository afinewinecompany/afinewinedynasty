# MLB Expectation Predictions - Quick Start

**Status:** ✅ PRODUCTION READY

---

## 🚀 Quick Reference

### API Endpoint

```
GET /ml/prospects/{prospect_id}/mlb-expectation?year=2024
```

**Response:**
```json
{
  "success": true,
  "data": {
    "prediction": {
      "label": "MLB Regular+",
      "probabilities": {
        "Bench/Reserve": 0.15,
        "Part-Time": 0.22,
        "MLB Regular+": 0.63
      }
    }
  }
}
```

---

### Frontend Component

```tsx
import { MLBExpectationPrediction } from '@/components/prospects/MLBExpectationPrediction';

<MLBExpectationPrediction prospectId={12345} year={2024} />
```

---

### CLI Prediction

```bash
cd apps/api
python scripts/predict_mlb_expectation.py --prospect-id 12345 --year 2024 --output json
```

---

## 📊 Model Performance

| Model | F1 Score | Accuracy |
|-------|----------|----------|
| Hitters | 0.713 | 72.4% |
| Pitchers | 0.796 | 82.5% |

---

## 🎯 3 Classes

| Class | FV | Meaning |
|-------|-----|---------|
| **Bench/Reserve** | 35-40 | Limited MLB role |
| **Part-Time** | 45 | Platoon/depth |
| **MLB Regular+** | 50+ | Starter or better |

---

## 📁 Key Files

**Models:**
- `apps/api/scripts/models/hitter_model_3class.pkl`
- `apps/api/scripts/models/pitcher_model_3class.pkl`

**Backend:**
- `apps/api/app/routers/ml_predictions.py` (line 1097+)
- `apps/api/scripts/predict_mlb_expectation.py`

**Frontend:**
- `apps/web/src/components/prospects/MLBExpectationPrediction.tsx`

---

## 🔄 Retrain Models

```bash
cd apps/api
python scripts/save_production_models.py
```

Models automatically saved to `scripts/models/` - no code changes needed!

---

## 📖 Full Documentation

- [COMPLETE_INTEGRATION_SUMMARY.md](COMPLETE_INTEGRATION_SUMMARY.md) - Complete details
- [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) - Technical guide
- [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md) - Integration status

---

**Ready to use! 🎉**
