# Contact Quality Score Design

## Purpose
Create a comprehensive score (0-100) that evaluates a hitter's contact quality by combining:
- Batted ball types (FB, LD, GB, PU)
- Contact hardness (Hard, Medium, Soft)
- Spray direction (Pull, Center, Oppo)

The ultimate power indicator is **Pull Hard Fly Balls**.

## Scoring Algorithm

### Component Weights (Total = 100 points)

#### 1. Elite Power Outcomes (40 points max)
- **Pull Hard Fly Balls**: 25 points (Ultimate power - HR potential)
- **All Hard Fly Balls**: 15 points (Power to all fields)

#### 2. Quality Contact (30 points max)
- **Hard Line Drives**: 20 points (Best overall outcome)
- **All Line Drives**: 10 points (Consistent quality contact)

#### 3. Negative Adjustments (-30 points possible)
- **Hard Ground Balls**: -10 points (Wasted power)
- **Pop Ups**: -10 points (Bad outcome)
- **Soft Contact**: -10 points (Weak contact)

#### 4. Baseline Contact Ability (30 points max)
- **Overall Hard Hit Rate**: 15 points
- **Fly Ball Rate**: 10 points (Power potential)
- **Line Drive Rate**: 5 points (Contact consistency)

## Calculation Formula

```python
contact_quality_score = (
    # Elite Power (40 pts)
    (pull_hard_fb_pct * 2.5) +        # 10% = 25 pts
    (hard_fb_pct * 1.5) +              # 10% = 15 pts

    # Quality Contact (30 pts)
    (hard_ld_pct * 2.0) +              # 10% = 20 pts
    (ld_pct * 0.33) +                   # 30% = 10 pts

    # Negative Adjustments (-30 pts)
    -(hard_gb_pct * 1.0) +             # 10% = -10 pts
    -(popup_pct * 1.0) +                # 10% = -10 pts
    -(soft_contact_pct * 1.0) +         # 10% = -10 pts

    # Baseline Ability (30 pts)
    (hard_hit_pct * 1.5) +             # 10% = 15 pts
    (fb_pct * 0.33) +                   # 30% = 10 pts
    (ld_pct * 0.17)                     # 30% = 5 pts (already counted above)
)
```

## Score Interpretation

| Score Range | Interpretation | Player Profile |
|-------------|---------------|----------------|
| 80-100 | Elite Power | High HR potential, pull-side power |
| 65-79  | Above Average Power | Good power potential, quality contact |
| 50-64  | Average Contact | Solid contact, moderate power |
| 35-49  | Below Average Contact | Contact-oriented, limited power |
| 0-34   | Poor Contact Quality | Weak contact, defensive profile |

## Example Calculations

### Power Hitter Example
- Pull Hard FB%: 8% → 20 pts
- Hard FB%: 12% → 18 pts
- Hard LD%: 10% → 20 pts
- LD%: 25% → 8 pts
- Hard Hit%: 15% → 22 pts
- FB%: 35% → 12 pts
- Hard GB%: 5% → -5 pts
- PU%: 8% → -8 pts
- Soft%: 3% → -3 pts
**Total: 84 points** (Elite Power)

### Contact Hitter Example
- Pull Hard FB%: 2% → 5 pts
- Hard FB%: 4% → 6 pts
- Hard LD%: 12% → 24 pts (capped at 20)
- LD%: 32% → 11 pts (capped at 10)
- Hard Hit%: 8% → 12 pts
- FB%: 20% → 7 pts
- Hard GB%: 3% → -3 pts
- PU%: 5% → -5 pts
- Soft%: 4% → -4 pts
**Total: 63 points** (Average/Slightly Above)

### Ground Ball Hitter Example
- Pull Hard FB%: 1% → 2 pts
- Hard FB%: 3% → 4 pts
- Hard LD%: 6% → 12 pts
- LD%: 22% → 7 pts
- Hard Hit%: 5% → 8 pts
- FB%: 15% → 5 pts
- Hard GB%: 8% → -8 pts
- PU%: 6% → -6 pts
- Soft%: 5% → -5 pts
**Total: 19 points** (Poor Contact Quality)

## Data Requirements

### Minimum Sample Size
- At least 50 balls in play with trajectory AND hardness data
- Ideally 100+ for stable metrics

### Data Fields Used
- `trajectory` (ground_ball, line_drive, fly_ball, popup)
- `hardness` (hard, medium, soft)
- `hit_location` (1-9, 78, 89) for pull/center/oppo classification

## Integration with Rankings

The Contact Quality Score should be:
1. Calculated as a standalone metric
2. Converted to percentile vs level cohort
3. Weighted at 15-20% in overall prospect evaluation
4. Combined with discipline scores and approach metrics

## Key Differentiators

This score differentiates between:
- **Power hitters**: High pull hard FB%, high hard contact
- **Contact hitters**: High LD%, moderate hard hit
- **All-around hitters**: Balanced across categories
- **Weak contact**: High soft contact, high pop ups
- **Groundball specialists**: High GB%, limited air balls