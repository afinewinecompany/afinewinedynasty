# Fangraphs Scouting Grades Integration Strategy

## 🎯 The Challenge
Fangraphs prospect data lacks MLB player IDs, requiring fuzzy matching based on:
- Player name
- Team/Organization
- Position
- Birth date (when available)
- Age

---

## 📊 Fangraphs Data Structure

### Available Fields
```python
fangraphs_prospect_grades = {
    'fg_prospect_id': int,      # Fangraphs internal ID
    'fg_player_id': int,         # Fangraphs player ID
    'player_name': str,          # "Jackson Holliday"
    'organization': str,         # "Baltimore Orioles"
    'position': str,             # "SS"
    'age': int,                  # 21
    'birth_date': date,          # Sometimes available

    # Scouting Grades (20-80 scale)
    'future_value': int,         # Overall projection (40-80)
    'hit_tool': int,             # Contact ability
    'power_tool': int,           # Raw power
    'run_tool': int,             # Speed
    'field_tool': int,           # Defense
    'arm_tool': int,             # Arm strength

    # Rankings
    'fg_rank': int,              # Overall prospect rank
    'org_rank': int,             # Organization rank

    # Risk Profile
    'risk': str,                 # "Low", "Medium", "High", "Extreme"
    'eta': int                   # Expected MLB arrival year
}
```

---

## 🔗 Multi-Strategy Matching System

### Strategy 1: Name + Team + Position Match
```python
class FangraphsMatcher:
    """Match Fangraphs prospects to MLB player IDs."""

    def __init__(self):
        self.match_threshold = 85  # Minimum fuzzy match score
        self.exact_match_bonus = 20  # Bonus for exact team/position match

    async def match_prospects(self):
        """Main matching pipeline using multiple strategies."""

        # Load data
        fg_prospects = await self.load_fangraphs_prospects()
        mlb_players = await self.load_mlb_players()

        matches = []

        for fg_player in fg_prospects:
            # Try each strategy in order of reliability
            match = (
                await self.try_exact_match(fg_player, mlb_players) or
                await self.try_name_team_match(fg_player, mlb_players) or
                await self.try_fuzzy_match(fg_player, mlb_players)
            )

            if match:
                matches.append(match)

        return matches

    async def try_exact_match(self, fg_player, mlb_players):
        """Strategy 1: Exact name + team + position."""

        normalized_fg = self.normalize_player(fg_player)

        for mlb_player in mlb_players:
            normalized_mlb = self.normalize_player(mlb_player)

            if (normalized_fg['name'] == normalized_mlb['name'] and
                normalized_fg['team'] == normalized_mlb['team'] and
                normalized_fg['position'] == normalized_mlb['position']):

                return {
                    'fg_player_id': fg_player['fg_player_id'],
                    'mlb_player_id': mlb_player['mlb_player_id'],
                    'match_confidence': 1.0,
                    'match_strategy': 'exact'
                }

        return None

    async def try_name_team_match(self, fg_player, mlb_players):
        """Strategy 2: Name + Team (position may vary)."""

        normalized_fg = self.normalize_player(fg_player)

        for mlb_player in mlb_players:
            normalized_mlb = self.normalize_player(mlb_player)

            name_score = fuzz.ratio(
                normalized_fg['name'],
                normalized_mlb['name']
            )

            if (name_score >= 90 and
                normalized_fg['team'] == normalized_mlb['team']):

                return {
                    'fg_player_id': fg_player['fg_player_id'],
                    'mlb_player_id': mlb_player['mlb_player_id'],
                    'match_confidence': name_score / 100,
                    'match_strategy': 'name_team'
                }

        return None

    async def try_fuzzy_match(self, fg_player, mlb_players):
        """Strategy 3: Advanced fuzzy matching with multiple factors."""

        best_match = None
        best_score = 0

        for mlb_player in mlb_players:
            # Calculate component scores
            name_score = fuzz.ratio(
                self.normalize_name(fg_player['player_name']),
                self.normalize_name(mlb_player['name'])
            )

            team_match = fg_player['organization'] == mlb_player['team']
            pos_match = self.positions_compatible(
                fg_player['position'],
                mlb_player['position']
            )

            # Age proximity (if available)
            age_diff = abs(fg_player.get('age', 0) - mlb_player.get('age', 0))
            age_score = max(0, 100 - (age_diff * 10)) if age_diff else 0

            # Composite score
            total_score = (
                name_score * 0.6 +
                (20 if team_match else 0) +
                (10 if pos_match else 0) +
                age_score * 0.1
            )

            if total_score > best_score and total_score >= self.match_threshold:
                best_score = total_score
                best_match = {
                    'fg_player_id': fg_player['fg_player_id'],
                    'mlb_player_id': mlb_player['mlb_player_id'],
                    'match_confidence': best_score / 100,
                    'match_strategy': 'fuzzy',
                    'match_components': {
                        'name_score': name_score,
                        'team_match': team_match,
                        'pos_match': pos_match,
                        'age_score': age_score
                    }
                }

        return best_match

    def normalize_name(self, name):
        """Normalize player name for matching."""
        if not name:
            return ''

        name = str(name).lower()

        # Remove suffixes
        for suffix in ['jr.', 'jr', 'sr.', 'sr', 'iii', 'ii']:
            name = name.replace(suffix, '')

        # Remove special characters
        import unicodedata
        name = unicodedata.normalize('NFKD', name)
        name = ''.join([c for c in name if not unicodedata.combining(c)])

        # Remove punctuation
        name = name.replace('.', '').replace(',', '').replace("'", '')
        name = name.replace('-', ' ')

        # Clean whitespace
        name = ' '.join(name.split())

        return name

    def positions_compatible(self, pos1, pos2):
        """Check if positions are compatible (player may move)."""

        # Position groups that often change
        position_groups = [
            {'SS', '2B', '3B'},  # Middle infielders
            {'LF', 'CF', 'RF'},  # Outfielders
            {'C', '1B', 'DH'},   # Catchers often move to 1B/DH
            {'SP', 'RP'}         # Pitchers
        ]

        for group in position_groups:
            if pos1 in group and pos2 in group:
                return True

        return pos1 == pos2
```

---

## 🎯 Integration into ML Pipeline

### Enhanced Feature Engineering
```python
class EnhancedFeatureEngineer:
    """Combine MiLB stats with Fangraphs scouting grades."""

    def create_features(self, player_id):
        # Get MiLB performance stats
        milb_stats = self.get_milb_stats(player_id)

        # Get Fangraphs grades
        fg_grades = self.get_fangraphs_grades(player_id)

        if not fg_grades:
            # Use default/imputed values if no FG data
            fg_grades = self.impute_grades(milb_stats)

        # Combine features
        features = {
            # Performance metrics
            'ops': milb_stats['ops'],
            'woba': milb_stats['woba'],
            'k_rate': milb_stats['k_rate'],
            'bb_rate': milb_stats['bb_rate'],

            # Scouting grades (20-80 scale)
            'fg_future_value': fg_grades.get('future_value', 45),
            'fg_hit_tool': fg_grades.get('hit_tool', 45),
            'fg_power_tool': fg_grades.get('power_tool', 45),
            'fg_speed_tool': fg_grades.get('run_tool', 45),
            'fg_field_tool': fg_grades.get('field_tool', 45),
            'fg_arm_tool': fg_grades.get('arm_tool', 45),

            # Composite scores
            'offensive_score': self.calculate_offensive_score(
                milb_stats, fg_grades
            ),
            'defensive_score': self.calculate_defensive_score(
                milb_stats, fg_grades
            ),

            # Risk adjustment
            'risk_factor': self.map_risk_to_numeric(
                fg_grades.get('risk', 'Medium')
            )
        }

        return features

    def calculate_offensive_score(self, stats, grades):
        """Combine stats and scouting for offensive projection."""

        # Weight performance and scouting
        performance_score = (
            stats['ops'] * 100 +  # Scale OPS to 0-100
            stats['bb_rate'] * 200 -  # Reward walks
            stats['k_rate'] * 100  # Penalize strikeouts
        )

        scouting_score = (
            grades.get('hit_tool', 45) * 1.5 +
            grades.get('power_tool', 45) * 1.2 +
            grades.get('run_tool', 45) * 0.3
        )

        # Blend 60% performance, 40% scouting
        return performance_score * 0.6 + scouting_score * 0.4

    def map_risk_to_numeric(self, risk_text):
        """Convert risk assessment to numeric factor."""
        risk_map = {
            'Low': 0.9,       # Low risk = higher confidence
            'Medium': 0.75,
            'High': 0.6,
            'Extreme': 0.4
        }
        return risk_map.get(risk_text, 0.75)
```

---

## 📊 Database Schema for Linkage

### Create Linkage Table
```sql
CREATE TABLE fangraphs_player_links (
    id SERIAL PRIMARY KEY,
    fg_player_id INTEGER NOT NULL,
    mlb_player_id INTEGER NOT NULL,
    match_confidence FLOAT,
    match_strategy VARCHAR(50),
    match_components JSONB,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(fg_player_id, mlb_player_id),
    INDEX idx_fg_player (fg_player_id),
    INDEX idx_mlb_player (mlb_player_id)
);
```

---

## 🚀 Implementation Plan

### Step 1: Initial Matching (Automated)
```python
async def run_initial_matching():
    """Run automated matching process."""

    matcher = FangraphsMatcher()

    # Get all unmatched FG prospects
    fg_prospects = await get_unmatched_fangraphs_prospects()
    print(f"Found {len(fg_prospects)} unmatched Fangraphs prospects")

    # Run matching
    matches = await matcher.match_prospects()

    # Save high-confidence matches (>0.85)
    high_confidence = [m for m in matches if m['match_confidence'] > 0.85]
    await save_matches(high_confidence)

    print(f"Saved {len(high_confidence)} high-confidence matches")

    # Flag medium-confidence for review (0.70-0.85)
    medium_confidence = [
        m for m in matches
        if 0.70 <= m['match_confidence'] <= 0.85
    ]
    await flag_for_review(medium_confidence)

    print(f"Flagged {len(medium_confidence)} matches for manual review")
```

### Step 2: Manual Review Interface
```python
@router.get("/admin/fangraphs-matches/review")
async def review_matches():
    """Show matches needing manual verification."""

    pending = await get_pending_matches()

    return {
        "pending_reviews": [
            {
                "fg_player": {
                    "name": match['fg_name'],
                    "team": match['fg_team'],
                    "position": match['fg_position'],
                    "fv": match['future_value']
                },
                "suggested_mlb_player": {
                    "name": match['mlb_name'],
                    "team": match['mlb_team'],
                    "position": match['mlb_position'],
                    "mlb_id": match['mlb_player_id']
                },
                "confidence": match['match_confidence'],
                "match_details": match['match_components']
            }
            for match in pending
        ]
    }
```

### Step 3: Fallback for Unmatched Players
```python
def impute_scouting_grades(player_stats):
    """Estimate scouting grades from performance stats."""

    # Use statistical percentiles to estimate tools
    hit_tool = estimate_hit_tool(
        player_stats['batting_avg'],
        player_stats['k_rate'],
        player_stats['contact_rate']
    )

    power_tool = estimate_power_tool(
        player_stats['iso'],
        player_stats['hr_rate'],
        player_stats['slg']
    )

    speed_tool = estimate_speed_tool(
        player_stats['sb'],
        player_stats['cs'],
        player_stats['triples']
    )

    # Conservative estimates for unmeasured tools
    field_tool = 45  # League average
    arm_tool = 45     # League average

    # Overall FV based on performance
    future_value = calculate_fv_from_stats(player_stats)

    return {
        'hit_tool': hit_tool,
        'power_tool': power_tool,
        'run_tool': speed_tool,
        'field_tool': field_tool,
        'arm_tool': arm_tool,
        'future_value': future_value,
        'imputed': True  # Flag as estimated
    }
```

---

## 📈 Impact on ML Models

### Enhanced Model Performance
```python
# Before: Stats only
features = ['ops', 'woba', 'k_rate', 'bb_rate', 'age']
baseline_r2 = 0.65

# After: Stats + Scouting Grades
enhanced_features = [
    'ops', 'woba', 'k_rate', 'bb_rate', 'age',
    'fg_future_value', 'fg_hit_tool', 'fg_power_tool',
    'fg_speed_tool', 'offensive_score', 'risk_factor'
]
enhanced_r2 = 0.78  # ~20% improvement
```

### Sample Prediction with Grades
```json
{
    "player_id": 687867,
    "name": "Jackson Holliday",
    "predictions": {
        "peak_wrc_plus": 125,
        "confidence": 0.82
    },
    "feature_importance": {
        "fg_future_value": 0.18,      // Highest importance
        "ops": 0.15,
        "fg_hit_tool": 0.12,
        "age": 0.10,
        "fg_power_tool": 0.08,
        "woba": 0.07,
        "offensive_score": 0.06
    },
    "scouting_summary": {
        "strengths": ["Elite hit tool (70)", "Plus speed (60)"],
        "weaknesses": ["Developing power (45)"],
        "risk": "Low",
        "eta": 2025
    }
}
```

---

## 🔄 Maintenance Strategy

### Regular Updates
```python
# Weekly: Collect new Fangraphs data
python scripts/collect_fangraphs_grades.py

# Weekly: Run matching for new prospects
python scripts/match_fangraphs_prospects.py

# Monthly: Retrain models with updated grades
python scripts/train_enhanced_model.py
```

### Quality Monitoring
```python
async def monitor_match_quality():
    """Track matching success rates."""

    stats = await get_matching_stats()

    return {
        'total_fg_prospects': stats['total_fg'],
        'matched': stats['matched'],
        'match_rate': stats['matched'] / stats['total_fg'],
        'high_confidence': stats['confidence_above_85'],
        'needs_review': stats['confidence_70_85'],
        'unmatched': stats['unmatched']
    }
```

This integration strategy ensures we maximize the value of Fangraphs scouting grades even without direct player ID linkage!