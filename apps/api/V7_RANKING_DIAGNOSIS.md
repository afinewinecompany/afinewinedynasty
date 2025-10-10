# V7 Ranking System Diagnosis

## Problem Summary

User identified that certain players are ranked incorrectly in V7:

**Ranked TOO HIGH:**
- Douglas Glod #100 (FV:35, .667 OPS in 2025 Low-A)
- Oswaldo Osorio #106
- Carlos Colmenarez #111
- Nikau Pouaka-Grego #133

**Ranked TOO LOW:**
- Chase DeLauter #159 (FV:50, Top 100 prospect)
- Eric Bitonti #288 (FV:40, .753 OPS, 19 HR, 17 SB in 2025)
- Sal Stewart #248 (FV:45, MLB-rated prospect)

## Root Cause Analysis

### Issue #1: Missing 2025 Data (DeLauter, Stewart)

**Chase DeLauter (800050):**
- FV: 50 (elite prospect)
- 2025 Data: NONE (no MiLB or MLB games)
- V4 Score: 15.5 (extremely low due to missing recent data)
- V7 Score: 34.4 → Rank #159
- **Cause**: V4 formula heavily weights 2025 performance. No 2025 data = terrible V4 score

**Sal Stewart (701398):**
- FV: 45
- 2025 Data: 55 MLB at-bats (under 130 threshold, should be included)
- No 2025 MiLB data (promoted to majors)
- V4 Score: 19.9 (very low)
- V7 Score: 30.2 → Rank #248
- **Cause**: V4 looks at MiLB performance, but he's been in MLB all 2025

### Issue #2: Tool Grade Mismatch (Bitonti vs Glod)

**Eric Bitonti (800724):**
- FV: 40
- 2025 Stats: .753 OPS, 19 HR, 17 SB (excellent Low-A performance)
- FG Score: 24.4 (LOW - here's why:)
  - Hit grade: 35 (below 40 baseline → negative contribution)
  - Performance grade: NaN (missing 12% of formula)
  - Frame: 1, Athleticism: -1 (negative scores)
  - Age: 19.9 (optimal, but only offsets other deficits)
- V4 Score: 39.6 (excellent, reflects his breakout 2025)
- V5 Score: 39.7 (excellent)
- V7 Score: 28.9 → Rank #288
- **Problem**: 70% FG weight crushes him despite great V4/V5

**Douglas Glod (800180):**
- FV: 35 (LOWER than Bitonti)
- 2025 Stats: .667 OPS, 7 HR, 1 SB (mediocre Low-A performance)
- FG Score: 42.5 (HIGH - here's why:)
  - Hit grade: 55 (strong)
  - Power grades: 50 game / 55 raw (strong)
  - Performance grade: 1.0 (adds 12%)
  - Age: 18.7 (very young → 15% weight boost)
- V4 Score: 29.5 (mediocre)
- V5 Score: 28.5 (mediocre)
- V7 Score: 38.5 → Rank #100
- **Problem**: Despite lower FV and worse 2025 stats, his individual tool grades + young age boost FG score

## Core Issues with FG Score Formula

The `calculate_fangraphs_score()` function uses:

```
FG Score =
  FV * 20% +
  Power * 15% +
  Hit * 12% +
  Performance * 12% +  ← Missing for Bitonti
  Speed * 10% +
  Age * 15% +          ← Glod at 18.7 gets huge boost
  Top100 * 8% +
  Field * 5% +
  Frame/Athleticism * 3%
```

**Problems:**
1. **FV only 20%** - Industry consensus grade is underweighted
2. **Individual tool grades override FV** - Glod (FV:35) can outscore Bitonti (FV:40)
3. **Age heavily weighted** - 18.7yo Glod gets massive boost vs 19.9yo Bitonti
4. **Missing grades = 0** - Bitonti missing "performance" loses 12% of score
5. **Tool grades are static** - Don't reflect 2025 breakout performance

## Current V7 Formula (70/20/10 weights)

```
V7 = FG_score * 70% + V4_score * 20% + V5_score * 10%
```

### Comparison Table

| Player | FV | FG | V4 | V5 | V7 | Rank | 2025 Stats |
|--------|----|----|----|----|----|----|------------|
| Glod | 35 | 42.5 | 29.5 | 28.5 | 38.5 | #100 | .667 OPS, 7 HR |
| DeLauter | 50 | 43.8 | 15.5 | 6.4 | 34.4 | #159 | NO DATA |
| Stewart | 45 | 34.8 | 19.9 | 18.5 | 30.2 | #248 | NO DATA (in MLB) |
| Bitonti | 40 | 24.4 | 39.6 | 39.7 | 28.9 | #288 | .753 OPS, 19 HR, 17 SB |

## Proposed Solutions

### Option 1: Simplify FG Score (Use FV Directly)

Replace complex tool grade formula with simple FV-based score:

```python
fg_score = fg_df['fv'].fillna(40)  # 40-80 scale
```

**Pros:**
- FV reflects industry consensus
- Scouts already factor in tools, age, performance
- Simple and transparent

**Cons:**
- Loses granularity of individual tool analysis
- Can't identify undervalued prospects with specific tool strengths

### Option 2: Increase FV Weight in Formula

Change FG score formula to weight FV at 50% instead of 20%:

```python
composite_score = (
    fv_score * 0.50 +           # FV (was 20%)
    power_score * 0.12 +        # Reduced
    hit_score * 0.10 +          # Reduced
    speed_score * 0.08 +        # Reduced
    perf_score * 0.10 +         # Reduced
    age_score * 0.05 +          # Reduced (was 15%)
    top100_score * 0.05 +       # Reduced
    ...
)
```

**Pros:**
- Keeps tool grade analysis
- Makes FV more influential
- Reduces age bias

**Cons:**
- Still complex formula
- May not fully fix Bitonti/Glod reversal

### Option 3: Reduce FG Weight in V7 Formula

Change V7 weights to give more weight to performance:

```
V7 = FG * 50% + V4 * 35% + V5 * 15%
```

With this formula, Bitonti would rank higher:
- Bitonti: 24.4*0.5 + 39.6*0.35 + 39.7*0.15 = **12.2 + 13.9 + 6.0 = 32.1**
- Glod: 42.5*0.5 + 29.5*0.35 + 28.5*0.15 = **21.3 + 10.3 + 4.3 = 35.9**

Still doesn't fix it (Glod still ahead).

### Option 4: Hybrid Approach (RECOMMENDED)

**Step 1:** Simplify FG score to use FV as primary component:

```python
# FV is 60% of FG score
fv_component = ((fg_df['fv'].fillna(40) - 40) / 40) * 100 * 0.60

# Tool grades add adjustment (40% of FG score)
tool_component = (
    hit_score * 0.15 +
    power_score * 0.15 +
    speed_score * 0.05 +
    age_score * 0.05  # Much reduced
) * 0.40

fg_score = fv_component + tool_component
```

**Step 2:** Keep V7 at 60/30/10 weights:

```
V7 = FG * 60% + V4 * 30% + V5 * 10%
```

This balances:
- Expert scouting opinion (FV) as primary driver
- Recent performance (V4) has meaningful weight
- Tool grades provide nuance but don't override consensus

### Option 5: Handle Missing Data Better

For prospects without 2025 data:
1. Use most recent season available (2024 for DeLauter/Stewart)
2. Apply light recency penalty but don't zero them out
3. Or: Manually mark as "insufficient data" and rank separately

## Immediate Actions

1. **Test Option 4** (Hybrid FG formula + 60/30/10 weights)
2. **Investigate DeLauter/Stewart** - Why no 2025 data? Injured? Season not started?
3. **Consider data quality** - Is 2025 MiLB data collection complete?
4. **Manual override** - For clearly wrong rankings (Bitonti #288), consider temporary fixes

## Long-term Improvements

1. **Update FanGraphs grades regularly** - Bitonti's grades are from 2023-2025 but don't reflect his 2025 breakout
2. **Collect mid-season grades** - FanGraphs updates throughout season
3. **Handle missing data gracefully** - Don't tank V4 score when 2025 data unavailable
4. **Consider recency in FG grades** - 2025 grade should weigh more than 2023 (already doing this, but verify)
5. **Add data quality flags** - Mark prospects with insufficient 2025 data
