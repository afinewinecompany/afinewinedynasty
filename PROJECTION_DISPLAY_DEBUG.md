# Projection Display Debugging Guide

## Expected Display Format

Each projection card should show:

### Header
- **Player Name**: e.g., "Juan Soto"
- **Position**: e.g., "OF"
- **Confidence Badge**: "high confidence" / "medium confidence" / "low confidence"

### Slash Line (Large Display)
```
.265/.340/.445
```
This should be AVG/OBP/SLG projected at MLB level

### Stats Grid (4 boxes)

**Box 1: OPS**
- Label: "OPS"
- Value (large): **0.785** (this is the projected OPS)
- R² (small): "R² 0.33" (this is model confidence)

**Box 2: BB%**
- Label: "BB%"
- Value (large): **9.5%** (this is the projected walk rate)
- R² (small): "R² 0.17" (this is model confidence)

**Box 3: K%**
- Label: "K%"
- Value (large): **22.3%** (this is the projected strikeout rate)
- R² (small): "R² 0.44" (this is model confidence)

**Box 4: ISO**
- Label: "ISO"
- Value (large): **0.180** (this is the projected isolated power)
- R² (small): "R² 0.22" (this is model confidence)

### Overall Confidence Bar
- Progress bar showing overall model confidence (0-100%)

---

## What You Might Be Seeing (WRONG)

If the display is broken, you might see:

### Slash Line showing R² values:
```
.444/.409/.391
```
Instead of projected stats like `.265/.340/.445`

### Stats showing R² values as main numbers:
- OPS: **0.332** (should be ~0.700-0.900)
- BB%: **17.3%** (actually R² = 0.173, should show ~5-15% walk rate)
- K%: **44.4%** (actually R² = 0.444, should show ~15-30% K rate)
- ISO: **21.5%** (actually R² = 0.215, should show ~0.100-0.250)

---

## API Response Structure

The API returns this structure:

```json
{
  "prospect_id": 8204,
  "prospect_name": "Player Name",
  "position": "OF",
  "slash_line": ".265/.340/.445",
  "projections": {
    "avg": 0.265,
    "obp": 0.340,
    "slg": 0.445,
    "ops": 0.785,
    "bb_rate": 0.095,
    "k_rate": 0.223,
    "iso": 0.180
  },
  "confidence_scores": {
    "avg": 0.444,
    "obp": 0.409,
    "slg": 0.391,
    "ops": 0.332,
    "bb_rate": 0.173,
    "k_rate": 0.444,
    "iso": 0.215
  },
  "overall_confidence": 0.344,
  "confidence_level": "medium",
  "model_version": "improved_v1_20251020_133214",
  "disclaimer": "..."
}
```

---

## Frontend Code (Current Implementation)

### Slash Line Display
```tsx
<div className="text-3xl font-mono font-bold text-white">
  {data.slash_line}  // Should display: ".265/.340/.445"
</div>
```

### Stat Display
```tsx
<StatItem
  label="OPS"
  value={data.projections.ops.toFixed(3)}  // Should display: "0.785"
  confidence={data.confidence_scores.ops}   // Used for R² display: "0.332"
/>
```

### StatItem Component
```tsx
function StatItem({ label, value, confidence }: StatItemProps) {
  return (
    <div className="bg-wine-plum/30 rounded-lg p-3">
      <div className="text-wine-periwinkle/70 text-xs mb-1">{label}</div>
      <div className="text-white text-lg font-semibold">{value}</div>  // ← Main value
      <div className={`text-xs mt-1 ${getConfidenceColor(confidence)}`}>
        R² {confidence.toFixed(2)}  // ← R² score (small text)
      </div>
    </div>
  );
}
```

---

## Debugging Steps

### 1. Check Browser Console

Open DevTools → Console and look for the API response:

```javascript
// In the Network tab, find the request:
GET /api/v1/ml/projections/hitter/8204

// Click on it and check the "Response" tab
// You should see the full JSON structure above
```

### 2. Verify Data Structure

Add console.log to see what data is being received:

```tsx
// In HitterProjectionCard.tsx, after the useQuery
console.log('Projection data:', data);
console.log('Projections:', data?.projections);
console.log('Confidence scores:', data?.confidence_scores);
```

### 3. Check for Data Swap

If `data.projections` contains R² values like `{ops: 0.332, bb_rate: 0.173}`:
- The backend is returning wrong data
- Check `StatProjectionService.generate_projection()`

If `data.confidence_scores` contains projected stats like `{ops: 0.785, bb_rate: 0.095}`:
- The frontend is using the wrong fields
- Swap `projections` and `confidence_scores` in the component

---

## Common Issues

### Issue 1: No MiLB Data
**Symptom:** Card shows "Projection not available"
**Cause:** Prospect has no pre-debut MiLB stats
**Solution:** This is expected - most current prospects don't have the required data

### Issue 2: Wrong Values Displayed
**Symptom:** Stats show values between 0.1-0.5 (R² range) instead of 0.6-0.9 (OPS range)
**Cause:** Frontend displaying confidence_scores instead of projections
**Solution:** Verify the component is using `data.projections.XXX` not `data.confidence_scores.XXX`

### Issue 3: Slash Line Shows R² Values
**Symptom:** Slash line shows ".444/.409/.391"
**Cause:** Backend generating slash line from confidence_scores instead of projections
**Solution:** Check `StatProjectionService.generate_projection()` line 326-329

---

## Testing with Known Data

To test with a prospect that HAS MiLB data:

1. Find prospects from 2021-2023 who debuted in MLB
2. They must have minor league stats in the database
3. Test with their ID: `/api/v1/ml/projections/hitter/{id}`

Most prospects in the current database WON'T have projections because:
- They're already in MLB (no pre-debut data)
- They're too young (no MiLB stats yet)
- They're international FAs (no MiLB history)

---

*Please provide specific examples of what you're seeing vs. what you expect to help pinpoint the exact issue.*
