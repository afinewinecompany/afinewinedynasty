# Production Configuration for Railway

## Required Environment Variables

To enable the new pitch-level performance metrics (discipline score and power score) in production, you must set the following environment variables in Railway:

```bash
# Enable enhanced pitch metrics with batted ball data
USE_ENHANCED_METRICS=true

# Enable pitch metrics processing (MUST be false to enable)
SKIP_PITCH_METRICS=false
```

## How to Set in Railway

1. Go to your Railway project
2. Select the API service
3. Go to Variables tab
4. Add or update these variables:
   - `USE_ENHANCED_METRICS` = `true`
   - `SKIP_PITCH_METRICS` = `false`
5. Railway will automatically redeploy with the new configuration

## What This Enables

When these variables are set correctly:
- **Discipline Score**: Composite metric combining contact rate, whiff rate, chase rate, and plate discipline
- **Power Score**: Composite metric combining hard hit rate, fly ball rate, and pull fly ball rate
- **Comprehensive batted ball metrics** for all hitters
- These metrics will appear in:
  - Composite rankings table (as badges next to performance data)
  - Individual prospect profiles (in the Statistics tab)
  - Expanded performance breakdowns

## Verification

After setting these variables and redeploying:
1. Visit the composite rankings page
2. Look in the "Data" column - you should see badges like `D: 72` and `P: 68`
3. Click on a prospect to see detailed pitch metrics in their profile

## Important Notes

- Cache may need to be cleared after changing these settings
- The first load after enabling may be slower as pitch data is aggregated
- Only prospects with sufficient pitch-level data will show these metrics