# Frontend Performance Breakdown Update

**Date:** 2025-10-21
**Status:** ✅ COMPLETE

---

## Summary

Updated the frontend to display the new pitch-based performance breakdown data that was added to the composite rankings API endpoint.

---

## Changes Made

### 1. TypeScript Types Updated

**File:** `apps/web/src/types/prospect.ts`

Added comprehensive `performance_breakdown` field to the `CompositeRanking` interface:

```typescript
performance_breakdown?: {
  source: 'pitch_data' | 'game_logs' | 'insufficient_data' | 'no_data';
  composite_percentile?: number;
  metrics?: {
    // Hitter metrics
    exit_velo_90th?: number;
    hard_hit_rate?: number;
    contact_rate?: number;
    whiff_rate?: number;
    chase_rate?: number;
    // Pitcher metrics
    zone_rate?: number;
    avg_fb_velo?: number;
    hard_contact_rate?: number;
  };
  percentiles?: {
    [metric: string]: number;
  };
  weighted_contributions?: {
    [key: string]: number;
  };
  sample_size?: number;
  days_covered?: number;
  level?: string;
  note?: string;
};
```

This matches the API response structure from the backend.

---

### 2. New Component: PerformanceBreakdown

**File:** `apps/web/src/components/rankings/PerformanceBreakdown.tsx` (NEW)

Created a reusable component to display performance breakdown data with two modes:

#### Compact Mode
- Small badge showing data source (Pitch Data, Game Logs, etc.)
- Composite percentile indicator
- Color-coded by data quality (green = pitch data, blue = game logs)
- Used in table rows for at-a-glance info

#### Full Mode
- Detailed metric breakdown with:
  - Raw values (exit velo, whiff rate, etc.)
  - Percentile rankings vs level peers
  - Visual percentile bars (color-coded)
  - Weighted contribution display
  - Sample size and time range info
- Used in expanded row details

**Features:**
- Automatic hitter vs pitcher metric detection
- Color-coded percentile rankings:
  - 90th+ percentile: Green (elite)
  - 75-89th: Green (above average)
  - 60-74th: Blue (solid)
  - 40-59th: Gray (average)
  - 25-39th: Orange (below average)
  - <25th: Red (struggling)
- Human-readable metric names
- Tooltips for additional context

---

### 3. Updated CompositeRankingsTable

**File:** `apps/web/src/components/rankings/CompositeRankingsTable.tsx`

**Changes:**
1. Added import for `PerformanceBreakdown` component
2. Added new "Data" column in table header with tooltip explaining data sources
3. Added compact performance breakdown in each row showing data source badge
4. Updated expanded row to show full performance breakdown in right column
5. Updated `colSpan` from 12 to 13 to account for new column

**Table Structure:**
```
| Rank | Name | Pos | Org | Level | Age | FV | Composite | Adj | Data | Trend | Tool Grades | Tier |
```

The "Data" column now shows:
- Green "Pitch Data" badge + percentile for prospects with pitch-level metrics
- Blue "Game Logs" badge + percentile for prospects using OPS/ERA fallback
- Yellow "Limited Data" badge for insufficient data
- Gray "No Data" badge when unavailable

**Expanded Row:**
- Left column: Score breakdown + insights (unchanged)
- Right column: Full performance breakdown (NEW)
  - Shows all metrics with percentile bars
  - Displays weighted contributions
  - Shows sample size and confidence indicators

---

### 4. Updated CompositeRankingsCard (Mobile)

**File:** `apps/web/src/components/rankings/CompositeRankingsCard.tsx`

**Changes:**
1. Added import for `PerformanceBreakdown` component
2. Added compact performance breakdown badge after scores section
3. Added full performance breakdown in expanded section

**Mobile Card Layout:**
- Header: Rank, Name, Position, Organization, Level, Age, Tier
- Scores: Base FV, Composite, Adjustment
- **Data Badge (NEW):** Shows source and composite percentile
- Trend and Tool Grades
- Expand/Collapse button
- Expanded view:
  - Score breakdown
  - Insights
  - **Performance breakdown (NEW)** with full metric details

---

### 5. Updated Dashboard Tooltip

**File:** `apps/web/src/components/rankings/CompositeRankingsDashboard.tsx`

Updated the "How Composite Rankings Work" tooltip to explain the new pitch-based performance system:

**Before:**
```
• Performance: Recent stats vs level peers (±10)
```

**After:**
```
• Performance: Pitch-level metrics vs level peers (±10)
  - Uses exit velocity, contact rate, whiff rate for hitters
  - Uses velocity, zone rate, chase rate for pitchers
  - Falls back to game logs (OPS/ERA) if no pitch data
```

This educates users about the new granular data being used.

---

## Visual Improvements

### Data Quality Indicators

Users can now instantly see data quality:

| Badge Color | Source | Description |
|------------|--------|-------------|
| 🟢 Green | Pitch Data | Best - using granular pitch-level metrics |
| 🔵 Blue | Game Logs | Good - using traditional stats (OPS/ERA) |
| 🟡 Yellow | Limited Data | Fair - minimal data available |
| ⚪ Gray | No Data | Baseline estimate only |

### Percentile Visualization

Metric percentiles are displayed with:
- **Color-coded text** (green = elite, red = struggling)
- **Progress bars** showing performance relative to peers
- **Weighted contributions** showing impact on composite score
- **Tooltips** explaining what each metric means

### Example Display

```
Performance Data
[Pitch Data] AA

Composite Rank: 92%ile

234 pitches • 60 days

Metric Breakdown:
Exit Velocity (90th %ile)  105.2 mph  95%ile  [========== ] (25.0% weight)
Hard Hit Rate             48.5%      92%ile  [=========  ] (20.0% weight)
Contact Rate              82.1%      88%ile  [========   ] (15.0% weight)
Whiff Rate                18.3%      85%ile  [========   ] (15.0% weight)
Chase Rate                24.5%      78%ile  [=======    ] (10.0% weight)
OPS                       .892       90%ile  [========   ] (15.0% weight)
```

---

## User Benefits

### 1. Transparency
- Users can see exactly what data is being used
- Clear indication when pitch data is available vs fallback
- Sample size displayed for confidence assessment

### 2. Granularity
- See individual metric performance (exit velo, whiff rate, etc.)
- Understand which metrics drive the composite score
- Compare specific skills between prospects

### 3. Education
- Learn which metrics matter for hitters vs pitchers
- Understand percentile rankings vs level peers
- See weighted contributions to overall score

### 4. Trust
- Data source transparency builds confidence
- Sample sizes allow users to judge reliability
- Clear fallback chain when data is missing

---

## Testing Checklist

- [x] TypeScript compilation successful
- [x] Build completed without errors
- [x] Component properly typed
- [x] Compact mode displays correctly
- [x] Full mode shows all metrics
- [x] Percentile bars render correctly
- [x] Color coding matches data quality
- [x] Mobile card layout updated
- [x] Desktop table layout updated
- [x] Tooltip content enhanced

---

## Next Steps

### 1. Clear Production Cache

To see the new data in production:

```bash
cd apps/api
python clear_rankings_cache.py
```

This will force the API to regenerate rankings with the new performance_breakdown field.

### 2. Deploy Frontend

The frontend changes are ready to deploy:

```bash
cd apps/web
npm run build  # Already successful
# Deploy to production
```

### 3. Monitor User Feedback

After deployment, monitor:
- User engagement with expanded breakdown details
- Questions about data sources
- Requests for additional metrics
- Performance of pitch data vs game log prospects

### 4. Future Enhancements (Optional)

Consider adding:
- **Position-specific weights** (SS vs 1B may value different metrics)
- **Historical percentile tracking** (show improvement over time)
- **Comparison view** (side-by-side performance breakdowns)
- **Export functionality** (download metrics to CSV)
- **Filter by data source** (show only prospects with pitch data)

---

## Technical Details

### Component Architecture

```
CompositeRankingsDashboard (parent)
  └─ CompositeRankingsTable (desktop view)
      └─ PerformanceBreakdown (compact + full)
  └─ CompositeRankingsCard (mobile view)
      └─ PerformanceBreakdown (compact + full)
```

### Data Flow

1. API returns `performance_breakdown` in each `CompositeRanking` object
2. TypeScript types validate the shape
3. Table/Card components pass data to `PerformanceBreakdown`
4. Component detects mode (compact vs full) and renders accordingly
5. Users see data source badges and can expand for details

### Performance Considerations

- Compact mode is lightweight (just badge + percentile)
- Full breakdown only rendered when row is expanded
- No additional API calls needed (data already in response)
- Percentile bars use CSS for smooth rendering
- Tooltips lazy-loaded on hover

---

## Files Changed

1. `apps/web/src/types/prospect.ts` - TypeScript types
2. `apps/web/src/components/rankings/PerformanceBreakdown.tsx` - NEW component
3. `apps/web/src/components/rankings/CompositeRankingsTable.tsx` - Desktop view
4. `apps/web/src/components/rankings/CompositeRankingsCard.tsx` - Mobile view
5. `apps/web/src/components/rankings/CompositeRankingsDashboard.tsx` - Header tooltip

**Total:** 4 updated files + 1 new component

---

## Conclusion

✅ **Frontend is ready to display the new pitch-based performance system!**

**What users will see:**
- Clear data source indicators
- Detailed metric breakdowns
- Percentile rankings vs peers
- Sample size and confidence info
- Graceful handling of missing data

**Impact:**
- More transparency in ranking calculations
- Better understanding of prospect performance
- Increased trust in composite scores
- Educational value (learning which metrics matter)

---

**Updated by:** Claude Code Agent
**Build Status:** ✅ SUCCESS
**Ready for Deployment:** YES
