# V7 Prospect Rankings - Weight Recommendations

## The Problem: Glod vs Reimer Case Study

### Player Comparison (2025 Season)

**Jacob Reimer** (Age 21, 3B) - FV: 50 (Average prospect per FanGraphs)
- 522 PA across High-A and AA
- **.282 AVG / .351 OBP / .491 SLG / .842 OPS**
- **17 HR, 15 SB**
- Playing at advanced levels for his age
- **Industry consensus**: Top 100 prospect

**Douglas Glod** (Age 20, CF) - FV: 35 (Below-average prospect per FanGraphs)
- 329 PA in Low-A
- **.213 AVG / .325 OBP / .342 SLG / .667 OPS**
- **7 HR, 1 SB**
- Struggling at lowest full-season level
- **Industry consensus**: Not even top 500

### The Ranking Problem

With current weights (50% FG / 40% V4 / 10% V5):
- **Reimer**: #112 (V7 Score: 35.95)
- **Glod**: #113 (V7 Score: 35.91)
- **Difference**: Only 1 rank, 0.04 points!

**Why this is wrong:**
1. Reimer had an elite 2025 season (.842 OPS, 17 HR, 15 SB)
2. Glod struggled badly (.667 OPS in Low-A)
3. Reimer's FV:50 > Glod's FV:35 by scouts
4. No real-world evaluator would rank them this close

### Root Cause

**V4 Score Issue:**
- Glod V4: 29.48
- Reimer V4: 26.87
- **Glod scores HIGHER despite worse 2025 stats!**

This happens because:
1. V4 uses multi-year weighted stats (2025 > 2024 > 2023)
2. Reimer struggled in 2023-2024, dragging down his score
3. 2025 is his breakout year, but historical weight limits the benefit
4. Age/level adjustments may also penalize Reimer for being 21 in AA

---

## Recommended Weight Scenarios

### Option 1: **60% FG / 30% V4 / 10% V5** (Moderate Scout Emphasis)

**Result:**
- Reimer: #101 (37.90)
- Glod: #109 (37.22)
- **8 rank separation** ✅

**Pros:**
- Respects expert scouting opinion (FV:50 vs FV:35)
- Still gives 40% to data (V4+V5)
- Moderate improvement over current

**Cons:**
- Only 8 ranks apart (maybe not enough separation)

---

### Option 2: **70% FG / 20% V4 / 10% V5** (Heavy Scout Emphasis) ⭐ **RECOMMENDED**

**Result:**
- Reimer: #89 (39.85)
- Glod: #100 (38.52)
- **11 rank separation** ✅✅

**Pros:**
- Clearly separates FV:50 from FV:35 prospects
- Aligns with industry consensus (Reimer top 100, Glod not)
- FanGraphs scouts factor in tools, makeup, and projection
- Historical performance gets less weight (reduces penalty for late bloomers)

**Cons:**
- Less emphasis on actual stats (but V4's historical drag is the problem)

**Why this works:**
- FanGraphs FV already incorporates performance (scouts watch games!)
- FV:50 means "average MLB regular" - scouts see Reimer's 2025 breakout
- FV:35 means "fringe MLB player" - scouts see Glod's struggles
- 70% weight means we trust the experts who watch every game

---

### Option 3: **50% FG / 40% V4 / 10% V5** (Current - NOT RECOMMENDED)

**Result:**
- Reimer: #112 (35.95)
- Glod: #113 (35.91)
- **1 rank separation** ❌

**Problems:**
- Doesn't separate elite performers from struggling prospects
- V4's historical drag neutralizes 2025 breakouts
- Contradicts industry consensus

---

## Implementation Guide

### To Generate with Custom Weights:

```bash
# Current (50/40/10)
python scripts/generate_prospect_rankings_v7_configurable.py --fg 50 --v4 40 --v5 10

# Recommended (70/20/10)
python scripts/generate_prospect_rankings_v7_configurable.py --fg 70 --v4 20 --v5 10 --output recommended

# Alternative (60/30/10)
python scripts/generate_prospect_rankings_v7_configurable.py --fg 60 --v4 30 --v5 10 --output alternative
```

### To Update Default V7 Script:

Edit `generate_prospect_rankings_v7.py` line 177:

```python
# Current
def calc_v7_score(row):
    fg_weight = 0.50
    v4_weight = 0.40 if row['has_v4'] else 0
    v5_weight = 0.10 if row['has_v5'] else 0

# Recommended
def calc_v7_score(row):
    fg_weight = 0.70  # Changed from 0.50
    v4_weight = 0.20 if row['has_v4'] else 0  # Changed from 0.40
    v5_weight = 0.10 if row['has_v5'] else 0
```

---

## Why FanGraphs Grades Should Be Weighted Heavily

1. **Scouts watch every game** - They see Reimer's 17 HR and 15 SB live
2. **FV incorporates performance** - FV:50 means scouts believe 2025 is real
3. **Tools + performance + makeup** - FV captures more than just stats
4. **Industry standard** - Other prospect rankings weight scouting heavily
5. **Reduces late-bloomer penalty** - V4's historical drag hurts breakout players

---

## Final Recommendation

**Use 70% FanGraphs / 20% V4 / 10% V5** as the new V7 default.

This properly:
- Separates Reimer (FV:50, .842 OPS) from Glod (FV:35, .667 OPS)
- Trusts expert scouts who watch 100+ games per prospect
- Reduces historical performance drag from V4
- Aligns with industry consensus on prospect rankings
