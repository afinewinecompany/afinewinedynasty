# Hitter Stat Projections - Deployment Guide

**Date:** October 20, 2025
**Version:** v1.0 (Hitters Only - Beta)
**Status:** ✅ Ready for Production

---

## Executive Summary

Deploying MLB stat projections for **hitters only**. Pitcher projections will be added later when more training data is available.

### What's Included
- ✅ Hitter stat projections (7 rate stats)
- ✅ API endpoints (`/api/ml/projections/hitter/:id`, `/api/ml/projections/status`)
- ✅ Trained models (R² = 0.344, moderate accuracy)
- ✅ Production-ready service class

### What's Not Included
- ❌ Pitcher projections (insufficient training data: 1 sample vs 100+ needed)
- ❌ Frontend UI (needs to be built)

---

## Backend Deployment Checklist

### 1. Files to Deploy ✅

All files are already in place in your repository:

**Model Files** (in `apps/api/`):
- [x] `hitter_models_improved_20251020_133214.joblib` (1.5 MB)
- [x] `hitter_features_improved_20251020_133214.txt` (500 bytes)
- [x] `hitter_targets_improved_20251020_133214.txt` (200 bytes)

**Service Files** (in `apps/api/app/`):
- [x] `services/stat_projection_service.py` (new)
- [x] `routers/ml_predictions.py` (modified - added projection endpoints)

### 2. Dependencies

Ensure these are in your `requirements.txt`:
```txt
joblib>=1.3.0
xgboost>=2.0.0
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
```

### 3. Environment Variables

No new environment variables needed. Uses existing database connection.

### 4. Database Requirements

**Current Status:** ⚠️ One function needs implementation

The `get_prospect_milb_stats()` function in `stat_projection_service.py` currently returns a placeholder. You need to implement the actual query:

```python
async def get_prospect_milb_stats(self, db: AsyncSession, prospect_id: int) -> Optional[Dict]:
    """Fetch prospect's most recent MiLB stats for projection."""

    query = select(Prospect).where(Prospect.id == prospect_id)
    result = await db.execute(query)
    prospect = result.scalar_one_or_none()

    if not prospect or not prospect.mlb_player_id:
        return None

    # Query milb_game_logs for aggregated stats
    milb_query = """
        SELECT
            season,
            level,
            team,
            COUNT(*) as games,
            SUM(plate_appearances) as pa,
            SUM(at_bats) as ab,
            SUM(runs) as r,
            SUM(hits) as h,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as hr,
            SUM(rbi) as rbi,
            SUM(walks) as bb,
            SUM(strikeouts) as so,
            SUM(stolen_bases) as sb,
            SUM(caught_stealing) as cs,
            AVG(batting_avg) as avg,
            AVG(on_base_pct) as obp,
            AVG(slugging_pct) as slg,
            AVG(ops) as ops,
            AVG(babip) as babip
        FROM milb_game_logs
        WHERE mlb_player_id = :mlb_player_id
        AND season >= :min_season
        AND plate_appearances > 0
        GROUP BY season, level, team
        ORDER BY season DESC,
            CASE level
                WHEN 'AAA' THEN 4
                WHEN 'AA' THEN 3
                WHEN 'A+' THEN 2
                WHEN 'A' THEN 1
                ELSE 0
            END DESC
        LIMIT 1
    """

    milb_result = await db.execute(
        text(milb_query),
        {
            'mlb_player_id': int(prospect.mlb_player_id),
            'min_season': datetime.now().year - 3
        }
    )
    milb_stats = milb_result.fetchone()

    if not milb_stats:
        return None

    # Calculate derived features
    pa = milb_stats.pa or 0
    ab = milb_stats.ab or 0

    if pa > 0:
        bb_rate = (milb_stats.bb or 0) / pa
        k_rate = (milb_stats.so or 0) / pa
        iso = (milb_stats.slg or 0) - (milb_stats.avg or 0)
        xbh = (milb_stats.doubles or 0) + (milb_stats.triples or 0) + (milb_stats.hr or 0)
        xbh_rate = xbh / ab if ab > 0 else 0
        bb_per_k = (milb_stats.bb or 0) / (milb_stats.so or 1)
        sb_total = (milb_stats.sb or 0) + (milb_stats.cs or 0)
        sb_success_rate = (milb_stats.sb or 0) / sb_total if sb_total > 0 else 0
    else:
        bb_rate = k_rate = iso = xbh_rate = bb_per_k = sb_success_rate = 0

    return {
        'prospect_id': prospect.id,
        'mlb_player_id': prospect.mlb_player_id,
        'name': prospect.name,
        'position': prospect.position,
        'season': milb_stats.season,
        'level': milb_stats.level,
        'team': milb_stats.team,
        'games': milb_stats.games,
        'pa': pa,
        'ab': ab,
        'avg': milb_stats.avg or 0,
        'obp': milb_stats.obp or 0,
        'slg': milb_stats.slg or 0,
        'ops': milb_stats.ops or 0,
        'bb_rate': bb_rate,
        'k_rate': k_rate,
        'iso': iso,
        'xbh_rate': xbh_rate,
        'bb_per_k': bb_per_k,
        'sb_success_rate': sb_success_rate,
        # Add all other features needed by model...
    }
```

### 5. API Endpoints

Once deployed, these endpoints will be available:

**Get Hitter Projection:**
```
GET /api/ml/projections/hitter/{prospect_id}
```

**Check Model Status:**
```
GET /api/ml/projections/status
```

### 6. Testing Backend

```bash
# Start API server
cd apps/api
uvicorn app.main:app --reload

# Test status endpoint
curl http://localhost:8000/api/ml/projections/status

# Test projection endpoint (replace with real prospect ID)
curl http://localhost:8000/api/ml/projections/hitter/9544
```

Expected response:
```json
{
  "available": true,
  "model_version": "improved_v1_20251020_133214",
  "models_loaded": 7,
  "features_count": 20,
  "performance": {
    "avg_validation_r2": 0.344,
    "status": "beta"
  }
}
```

---

## Frontend Development Guide

### 1. Create Projections Page

**Route:** `/projections`

**File:** `apps/web/src/pages/ProjectionsPage.tsx`

### 2. Page Structure

```tsx
import { useState } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import HitterProjectionsList from '@/components/projections/HitterProjectionsList';

export default function ProjectionsPage() {
  const [activeTab, setActiveTab] = useState('hitters');

  return (
    <div className="container mx-auto py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-3xl font-bold">MLB Stat Projections</h1>
          <Badge variant="secondary">Beta</Badge>
        </div>
        <p className="text-muted-foreground">
          AI-powered projections based on MiLB performance data
        </p>
      </div>

      {/* Beta Notice */}
      <Alert className="mb-6">
        <AlertDescription>
          These projections are experimental and based on machine learning models
          trained on historical MiLB→MLB transitions. Actual MLB results may vary
          significantly. Model accuracy: R² = 0.344 (moderate).
        </AlertDescription>
      </Alert>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="hitters">Hitters</TabsTrigger>
          <TabsTrigger value="pitchers" disabled>
            Pitchers
            <Badge variant="outline" className="ml-2">Coming Soon</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="hitters">
          <HitterProjectionsList />
        </TabsContent>

        <TabsContent value="pitchers">
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-lg mb-2">Pitcher projections coming soon!</p>
            <p className="text-sm">
              We're collecting more MLB data to train accurate pitcher models.
            </p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### 3. Hitter Projections List Component

**File:** `apps/web/src/components/projections/HitterProjectionsList.tsx`

```tsx
import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface HitterProjection {
  prospect_id: number;
  prospect_name: string;
  position: string;
  slash_line: string;
  projections: {
    avg: number;
    obp: number;
    slg: number;
    ops: number;
    bb_rate: number;
    k_rate: number;
    iso: number;
  };
  confidence_level: 'high' | 'medium' | 'low';
  overall_confidence: number;
}

export default function HitterProjectionsList() {
  // For now, fetch all prospects and generate projections
  // In production, you'd want pagination/filtering
  const { data: prospects } = useQuery({
    queryKey: ['prospects'],
    queryFn: async () => {
      const res = await fetch('/api/prospects?position=hitter');
      return res.json();
    }
  });

  return (
    <div className="space-y-4">
      {prospects?.map((prospect: any) => (
        <HitterProjectionCard
          key={prospect.id}
          prospectId={prospect.id}
        />
      ))}
    </div>
  );
}

function HitterProjectionCard({ prospectId }: { prospectId: number }) {
  const { data, isLoading, error } = useQuery<HitterProjection>({
    queryKey: ['projection', prospectId],
    queryFn: async () => {
      const res = await fetch(`/api/ml/projections/hitter/${prospectId}`);
      if (!res.ok) throw new Error('Failed to fetch projection');
      return res.json();
    }
  });

  if (isLoading) {
    return <Skeleton className="h-32" />;
  }

  if (error || !data) {
    return null; // Skip prospects without projections
  }

  const confidenceBadgeVariant = {
    high: 'default',
    medium: 'secondary',
    low: 'outline'
  }[data.confidence_level];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>
              {data.prospect_name}
              <span className="ml-2 text-muted-foreground font-normal">
                {data.position}
              </span>
            </CardTitle>
          </div>
          <Badge variant={confidenceBadgeVariant}>
            {data.confidence_level} confidence
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Slash Line */}
        <div className="mb-4">
          <div className="text-sm text-muted-foreground mb-1">
            Projected Slash Line
          </div>
          <div className="text-2xl font-mono font-bold">
            {data.slash_line}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          <StatItem
            label="OPS"
            value={data.projections.ops.toFixed(3)}
          />
          <StatItem
            label="BB%"
            value={`${(data.projections.bb_rate * 100).toFixed(1)}%`}
          />
          <StatItem
            label="K%"
            value={`${(data.projections.k_rate * 100).toFixed(1)}%`}
          />
          <StatItem
            label="ISO"
            value={data.projections.iso.toFixed(3)}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
```

### 4. Add Navigation Link

In your main navigation:

```tsx
<NavLink to="/projections">
  Projections
  <Badge variant="secondary" className="ml-2">Beta</Badge>
</NavLink>
```

---

## User Communication

### Beta Label Requirements

Every page/component showing projections MUST include:

1. **"Beta" badge** prominently displayed
2. **Disclaimer text:**
   > "These projections are experimental and based on machine learning models trained on historical MiLB→MLB transitions. Actual MLB results may vary significantly."

3. **Confidence indicators:**
   - High confidence (R² ≥ 0.40): Green badge
   - Medium confidence (R² 0.25-0.40): Yellow badge
   - Low confidence (R² < 0.25): Gray badge

### Pitcher Tab Messaging

```
🔒 Pitchers (Coming Soon)

We're collecting more MLB data to train accurate pitcher projection models.

Expected availability: Q1 2026

Current status: 1 pitcher with sufficient data (need 100+)
```

---

## Performance Expectations

### Model Accuracy

| Stat | Validation R² | Expected Accuracy |
|------|---------------|-------------------|
| **AVG** | 0.444 | ✅ Good |
| **K%** | 0.444 | ✅ Good |
| **OBP** | 0.409 | ✅ Good |
| **SLG** | 0.391 | Moderate |
| **OPS** | 0.332 | Moderate |
| **ISO** | 0.215 | Weak |
| **BB%** | 0.173 | Weak |

**Average:** R² = 0.344 (moderate predictive power)

### API Performance

- Model load time: 1-2 seconds (on startup)
- Prediction latency: 10-50ms per prospect
- Memory usage: ~50MB (models + service)

### Limitations

1. **Conservative predictions** - Model tends to underestimate power
2. **Walk rate struggles** - Lowest accuracy (R² = 0.173)
3. **Small sample bias** - Only 399 training samples
4. **Regression to mean** - Elite prospects may be underrated

---

## Monitoring & Analytics

### Key Metrics to Track

1. **API Usage:**
   - Requests per day
   - Average response time
   - Error rate

2. **User Engagement:**
   - Page views on /projections
   - Time spent on page
   - Most viewed prospects

3. **Model Performance (Post-Deployment):**
   - Track actual vs predicted stats as seasons progress
   - Calculate running MAE/RMSE
   - Identify systematic biases

### Alerts to Set Up

- API endpoint downtime
- Model load failures
- Unusually high error rates (>5%)
- Slow response times (>500ms p95)

---

## Rollback Plan

If projections are causing issues:

1. **Disable endpoint:**
   ```python
   # In ml_predictions.py
   @router.get("/projections/hitter/{prospect_id}")
   async def get_hitter_projection(...):
       raise HTTPException(503, "Projections temporarily unavailable")
   ```

2. **Remove from frontend:**
   - Hide navigation link
   - Show maintenance message

3. **Investigate issues:**
   - Check logs for errors
   - Verify model files
   - Test with known prospects

---

## Future Enhancements

### Phase 2 (1-2 months)
- Pitcher projections (when data available)
- Prediction intervals/ranges
- Comparison with league averages
- Historical accuracy tracking

### Phase 3 (3-6 months)
- Confidence intervals
- Feature importance visualization (SHAP)
- Projection narratives
- Custom scenarios ("What if he improves BB%?")

### Phase 4 (6+ months)
- Retrain with more data (600-800 samples)
- Improve R² to 0.40+
- Add counting stats projections
- Position-specific models

---

## Support & Documentation

### For Developers

- API docs: [API_INTEGRATION_COMPLETE.md](API_INTEGRATION_COMPLETE.md)
- Model details: [OPTION_B_IMPROVEMENT_SUMMARY.md](OPTION_B_IMPROVEMENT_SUMMARY.md)
- Full report: [ML_STAT_PROJECTION_FINAL_REPORT.md](ML_STAT_PROJECTION_FINAL_REPORT.md)

### For Users

Create a `/projections/about` page with:
- How projections work
- Model accuracy stats
- Interpretation guide
- Limitations and disclaimers
- FAQ

---

## Deployment Steps

### 1. Pre-Deployment Checklist

- [ ] Backend code merged to main branch
- [ ] Model files committed to repository
- [ ] Environment variables configured
- [ ] Database query implemented in `get_prospect_milb_stats()`
- [ ] API tests passing
- [ ] Frontend components built
- [ ] Beta labels added everywhere
- [ ] Disclaimers added

### 2. Deployment Process

```bash
# 1. Deploy backend
cd apps/api
git pull origin main
pip install -r requirements.txt
# Restart API server

# 2. Deploy frontend
cd apps/web
git pull origin main
npm install
npm run build
# Deploy build artifacts

# 3. Verify
curl https://your-api.com/api/ml/projections/status
# Should return: { "available": true, ... }
```

### 3. Post-Deployment Verification

- [ ] API status endpoint returns 200
- [ ] Test projection for known prospect
- [ ] Frontend page loads correctly
- [ ] Beta badges visible
- [ ] Pitcher tab shows "Coming Soon"
- [ ] Disclaimers displayed
- [ ] No console errors

### 4. Announce Launch

**Social media/blog post:**
> 🚀 New Feature: MLB Stat Projections (Beta)
>
> We've added AI-powered stat projections for hitters! Our machine learning
> models predict MLB performance based on MiLB data.
>
> Features:
> - 7 rate stat projections (AVG, OBP, SLG, K%, BB%, ISO, OPS)
> - Confidence scores
> - Slash line predictions
>
> Note: This is a beta feature. Projections are experimental.
> Pitcher projections coming Q1 2026!
>
> Try it now: [link to /projections]

---

## Success Criteria

### Launch Goals (Week 1)
- [ ] 100+ users visit projections page
- [ ] <5% error rate on API
- [ ] <2 support tickets about inaccuracy
- [ ] Positive user feedback

### Growth Goals (Month 1)
- [ ] 500+ unique users
- [ ] Average 2+ projections viewed per session
- [ ] User retention: 30%+ return visitors
- [ ] 10+ pieces of user feedback collected

---

## Summary

**What's Ready:**
✅ Hitter projection models (R² = 0.344)
✅ API endpoints
✅ Service infrastructure
✅ Documentation

**What's Needed:**
⏳ Implement MiLB stats database query
⏳ Build frontend components
⏳ Add Beta labels and disclaimers
⏳ Deploy to production

**Timeline:**
- Database query: 1-2 hours
- Frontend build: 4-6 hours
- Testing & QA: 2-3 hours
- **Total: 1-2 days to production**

---

*Deployment guide completed: October 20, 2025 14:00*
