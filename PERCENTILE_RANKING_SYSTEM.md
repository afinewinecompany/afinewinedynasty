# Composite Rankings Percentile System Redesign

## Overview
Complete redesign of the percentile ranking system to properly compare each player against ALL other players in the dataset, establishing true comparative percentiles for each statistical category.

## The Problem
The previous system was not calculating true percentiles - it was either:
1. Showing raw values without context
2. Using pre-calculated percentiles that weren't comparing against the full player pool
3. Not properly determining what constitutes "good" vs "bad" for each metric

## The Solution
Created a comprehensive client-side percentile calculation system that:
1. **Compares each player against ALL others** in the dataset
2. **Calculates percentiles dynamically** based on the current filtered set
3. **Properly handles directional metrics** (higher vs lower is better)
4. **Provides visual feedback** with color-coded tiers

## System Architecture

### 1. **Percentile Calculation Utility** (`calculatePercentiles.ts`)
```typescript
// Core calculation function
calculatePercentileRank(value, allValues, higherIsBetter)
// Returns 0-100, where 100 = best

// Handles directionality
HIGHER_IS_BETTER_METRICS = {
  'exit_velo_90th': true,  // Higher exit velo is better
  'chase_rate': false,      // Lower chase rate is better for hitters
  'era': false,            // Lower ERA is better for pitchers
  // ... etc
}
```

### 2. **Context Provider** (`PercentilesContext.tsx`)
- Calculates percentiles for ALL players when data loads
- Shares calculated percentiles across all components
- Updates automatically when player list changes

### 3. **Visual Presentation** (`ExpandedPlayerRowV2.tsx`)
- Shows percentile rank (0-100) for each metric
- Visual progress bars with quartile markers
- Color-coded performance tiers
- Raw values displayed alongside percentiles

## Key Features

### Comparative Percentiles
Each player's metrics are compared against ALL other players:
- **100th percentile** = Better than all other players
- **75th percentile** = Better than 75% of players (Plus performance)
- **50th percentile** = Median (Average performance)
- **25th percentile** = Better than only 25% of players (Below average)
- **0th percentile** = Worst performance

### Directional Awareness
The system knows which direction is "better" for each metric:

**Higher is Better:**
- Exit Velocity, Hard Hit Rate, Contact Rate (hitters)
- Fastball Velocity, Whiff Rate, K Rate (pitchers)

**Lower is Better:**
- Chase Rate, Whiff Rate (for hitters)
- ERA, WHIP, Hard Contact Allowed (pitchers)

### Performance Tiers
Visual color coding based on percentile ranges:
- **Elite (90-100th)**: Emerald green
- **Plus (75-89th)**: Green
- **Above Average (60-74th)**: Blue
- **Average (40-59th)**: Gray
- **Below Average (25-39th)**: Orange
- **Poor (0-24th)**: Red

### Composite Percentile
Weighted average of key metrics:

**Hitters:**
- Exit Velocity (25%)
- Hard Hit Rate (20%)
- Contact Rate (20%)
- Whiff Rate (15%)
- Chase Rate (10%)
- OPS (10%)

**Pitchers:**
- Fastball Velocity (25%)
- Whiff Rate (25%)
- Zone Rate (15%)
- K-BB% (20%)
- Hard Contact Allowed (15%)

## Visual Components

### Percentile Bar
```
[█████████████████░░░░░░] 75th percentile
0    25    50    75    100
```
- Gradient fill based on performance tier
- Quartile markers for reference
- Labels showing scale

### Metric Display
```
Exit Velocity    104.5 mph    [92nd]
                 (raw value)  (percentile)
```

### Top Metrics Highlight
- Shows top 3 performing metrics
- Sorted by percentile rank
- Quick visual of player strengths

## Implementation Files

### Created:
1. **`utils/calculatePercentiles.ts`** - Core percentile calculation logic
2. **`contexts/PercentilesContext.tsx`** - React context for sharing percentiles
3. **`components/rankings/ExpandedPlayerRowV2.tsx`** - New expanded row with proper percentiles

### Modified:
1. **`CompositeRankingsDashboard.tsx`** - Added PercentilesProvider wrapper
2. **`CompositeRankingsTable.tsx`** - Using new ExpandedPlayerRowV2

## How It Works

1. **Data Loading**: When prospects data loads in the dashboard
2. **Percentile Calculation**: PercentilesProvider calculates percentiles for all players
3. **Context Sharing**: Percentiles stored in React context
4. **Component Access**: Any component can access percentiles via `useProspectPercentiles()`
5. **Visual Display**: Components show percentiles with bars, colors, and labels

## Example Display

For a player with 104.5 mph exit velocity:
1. System collects all exit velocities from all players
2. Calculates that 104.5 mph is better than 92% of players
3. Displays: `Exit Velocity: 104.5 mph [92nd %ile]` with green coloring
4. Shows visual bar filled to 92%

## Benefits

1. **True Comparative Rankings**: Every percentile shows where a player stands vs all others
2. **Context for Raw Values**: 12% whiff rate means nothing without knowing if that's good
3. **Visual Clarity**: Instantly see strengths and weaknesses
4. **Position-Aware**: Different metrics weighted for pitchers vs hitters
5. **Dynamic Updates**: Percentiles recalculate when filtering players

## Future Enhancements

1. **Level-Specific Percentiles**: Compare only within same level (AAA, AA, etc.)
2. **Age-Adjusted Percentiles**: Account for age relative to level
3. **Historical Percentiles**: Track percentile changes over time
4. **Peer Group Comparison**: Compare against similar positions only
5. **Custom Weights**: Allow users to adjust metric importance

## Testing Checklist

- [ ] Verify percentiles calculate 0-100 with 100 being best
- [ ] Check directional metrics (lower chase rate = higher percentile for hitters)
- [ ] Confirm visual bars match percentile values
- [ ] Test with filtered subsets of players
- [ ] Verify composite percentile calculation
- [ ] Check performance with large datasets

## Summary

The new percentile ranking system provides true comparative analysis by ranking each player against all others in the dataset. Every metric now has context - users can instantly see if a 12% whiff rate is elite (for a hitter) or poor (for a pitcher). The visual presentation with color-coded tiers and progress bars makes it easy to identify player strengths and weaknesses at a glance.