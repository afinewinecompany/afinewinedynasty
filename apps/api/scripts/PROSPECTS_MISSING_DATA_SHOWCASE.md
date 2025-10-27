# Prospects Missing Data - Showcase

**Generated:** October 17, 2025

## Executive Summary

Out of 1,295 prospects with MLB Player IDs:
- **522 prospects (40.3%)** have some data
- **773 prospects (59.7%)** have NO data at all

---

## Category 1: High-Value Position Players Missing Pitch Data

These position players have substantial plate appearances but are **missing pitch-by-pitch data**:

### Noah Miller (LAD - SS)
- **912 PAs across 2 seasons**
- Has plate appearance records but no detailed pitch tracking
- This is a data collection gap we can fill

### Eddinson Paulino (TOR - 3B)
- **864 PAs across 2 seasons**
- Active player missing granular pitch data

### Leandro Pineda (PHI - RF)
- **827 PAs across 2 seasons**
- Significant playing time without pitch tracking

### Joe Mack (MIA - C)
- **504 PAs in 2023 season**
- Note: Has pitch data for 2024-2025 but missing 2023 pitch-level details

### Notable Others:
- **Javier Vaz** (KCR - 2B): 521 PAs
- **Erick Brito** (PHI - SS): 516 PAs
- **Samuel Zavala** (CHW - CF): 530 PAs
- **Antonio Gomez** (NYY - C): 496 PAs
- **Mikey Romero** (BOS - 3B): 495 PAs

**Impact:** These 20 position players represent **~10,000 plate appearances** without detailed pitch tracking.

---

## Category 2: Pitchers with Zero Pitching Data

We have **440+ pitchers** in the database, but **439 have NO pitching data**. Only Blake Walston has 26 pitches recorded.

### Sample Starting Pitchers Missing Data:

| Name | Team | MLB ID |
|------|------|---------|
| Adam Mazur | MIA | 800049 |
| Adam Serwinowski | LAD | 703445 |
| Aidan Major | CLE | 802146 |
| Aldrin Batista | CHW | 702881 |
| Alejandro Rosario | TEX | 691730 |
| Adrian Herrera | CIN | 805155 |
| Adrian Bohorquez | MIN | 807974 |
| AJ Russell | TEX | 805706 |

**Why This Matters:**
- Pitchers need a different API endpoint (`group: 'pitching'` instead of `group: 'hitting'`)
- Script already created, just needs NULL ID filtering fix
- Huge data collection opportunity

---

## Category 3: Prospects Lost to Time (2023 Only)

These players had significant 2023 activity but disappeared from 2024-2025 data:

### Justin Foscue (TEX - 1B)
- **564 PAs in 2023**
- Zero activity in 2024 or 2025
- Likely promoted to MLB or injured

### Tyler Black (MIL - 1B)
- **558 PAs in 2023**
- No recent MiLB activity

### Tyler Callihan (CIN - 2B)
- **550 PAs in 2023**
- Missing from recent seasons

### Yiddi Cappe (MIA - LF)
- **517 PAs in 2023**
- No 2024/2025 data

### Jorge Barrosa (ARI - CF)
- **503 PAs in 2023**
- Activity ceased after 2023

**Insights:**
- These 10 prospects had ~3,000+ PAs in 2023
- Likely promoted to majors, injured, or released
- Valuable historical data but no recent tracking

---

## Category 4: Complete Data Deserts

These prospects have **NO data at all** across any season:

### Sample Position Players (No Data):
- Aaron Walton (CLE - CF)
- Adrian Rodriguez (TEX - DH)
- Adolfo Sanchez (CIN - RF)
- Adonys Guzman (PIT - C)

### Sample Pitchers (No Data):
- Adam Macko (TOR - RP)
- Aiden May (MIA - RP)
- AJ Blubaugh (HOU - RP)
- Aidan Curry (TEX - RP)

**Possible Reasons:**
1. **Never played MiLB** - International signings, drafted but unsigned
2. **Injured entire period** - On IL for 2023-2025
3. **Recently added** - Just signed, haven't played yet
4. **Data not available** - Games not tracked by MLB Stats API
5. **MLB only** - Skipped minors or already promoted

---

## Data Collection Priorities

### Immediate Opportunities

#### Priority 1: Position Players with PAs Missing Pitch Data
- **20 players** identified
- **~10,000 PAs** without pitch tracking
- Data exists, just needs collection
- **Estimated collection time:** 30-60 minutes

#### Priority 2: Pitcher Data Collection
- **439 pitchers** with zero data
- Requires pitching-specific API calls
- Script exists but needs NULL ID fix
- **Estimated collection time:** 2-3 hours for full run

#### Priority 3: Historical 2023 Data Expansion
- Only **25 prospects** have 2023 pitch data
- Could expand to **70+ prospects** with 2023 PAs
- **Estimated collection time:** 1-2 hours

### Data That May Not Exist

#### Players Without MiLB Activity
- **773 prospects (59.7%)** have no data
- Many are likely:
  - International prospects not yet playing
  - Injured prospects on extended rehab
  - Recently drafted players (no games yet)
  - MLB-only players who skipped minors

**Recommendation:** Focus on Priority 1 & 2 where data definitely exists

---

## Case Studies

### Case Study 1: Noah Miller (LAD - SS)

**The Mystery:** 912 PAs across 2 seasons but no pitch data

**Investigation Needed:**
1. Which seasons? (2024-2025, 2023-2024, or 2023-2025?)
2. Are the PAs from specific levels that aren't tracked?
3. Is this a data collection gap or API limitation?

**Action:** Run targeted collection for Noah Miller to test data availability

### Case Study 2: Adam Mazur (MIA - SP)

**The Mystery:** Known to have pitched 8 games in 2024 (confirmed by API test) but zero data collected

**Known Facts:**
- API returns game list successfully
- Games exist in MLB Stats system
- Collection script found the games but didn't collect pitches

**Likely Cause:** Game feed may not have detailed pitch tracking for some MiLB levels

**Action:** Manual investigation of one game to check data availability

---

## Technical Notes

### Why Position Players Are Missing Pitch Data

The most likely reason: **2023 data wasn't collected initially**. The collection focused on 2024-2025, leaving gaps for players who only played in 2023 or have incomplete multi-year coverage.

### Why Pitchers Have No Data

Two reasons:
1. **Different API endpoint required** - Fixed in new script
2. **NULL mlb_player_id values** - Causes script crash, needs filtering

### Collection Reliability

- **2024 Batter Data:** 100% complete (126/126 with PAs have pitches)
- **2025 Batter Data:** Strong coverage (151 prospects)
- **2023 Batter Data:** Limited (25 prospects)
- **Pitcher Data:** Nearly zero (1/440 pitchers)

---

## Next Steps

1. **Fix pitcher collection script** - Filter out NULL IDs
2. **Run full pitcher collection** - Get data for 440 pitchers
3. **Backfill 2023 pitch data** - Expand from 25 to 70+ prospects
4. **Investigate Noah Miller case** - Understand the 912 PA gap
5. **Document API limitations** - Identify what data truly doesn't exist
