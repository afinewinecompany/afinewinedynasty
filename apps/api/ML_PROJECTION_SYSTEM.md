# MLB Projection System - Technical Specification

## 🎯 Core Systems

### 1. Player Comparison System (Top 5 Comps)

```python
class PlayerComparison:
    """Find 5 most similar MLB players for each prospect."""

    def find_top_comps(self, prospect_features, mlb_database, n_comps=5):
        """
        Returns exactly 5 most similar MLB players.

        Output format:
        [
            {
                "player_name": "Ronald Acuña Jr.",
                "similarity_score": 0.92,
                "age_at_comp": 21,
                "key_similarities": ["speed", "power", "k_rate"],
                "mlb_stats": {"wrc_plus": 132, "war": 4.5}
            },
            ... (4 more players)
        ]
        """

        # Normalize features for comparison
        scaler = StandardScaler()
        prospect_scaled = scaler.fit_transform(prospect_features)
        mlb_scaled = scaler.transform(mlb_database)

        # Calculate similarity scores
        similarities = cosine_similarity(prospect_scaled, mlb_scaled)[0]

        # Get top 5 indices
        top_5_idx = similarities.argsort()[-5:][::-1]

        # Build comparison profiles
        comparisons = []
        for idx in top_5_idx:
            comp = {
                "player_name": mlb_database.iloc[idx]['name'],
                "similarity_score": round(similarities[idx], 3),
                "age_at_comp": mlb_database.iloc[idx]['age'],
                "key_similarities": self._identify_similar_traits(
                    prospect_features,
                    mlb_database.iloc[idx]
                ),
                "mlb_stats": {
                    "wrc_plus": mlb_database.iloc[idx]['wrc_plus'],
                    "war": mlb_database.iloc[idx]['war'],
                    "ops": mlb_database.iloc[idx]['ops']
                }
            }
            comparisons.append(comp)

        return comparisons[:5]  # Ensure exactly 5
```

---

## 📈 Year-by-Year Projection System

### Core Architecture

```python
class AgeAdjustedProjector:
    """Generate year-by-year projections for visualization."""

    def __init__(self):
        # Age curve factors based on historical MLB data
        self.age_curve = {
            # Position Players
            'hitter': {
                20: 0.70, 21: 0.75, 22: 0.82, 23: 0.89,
                24: 0.94, 25: 0.97, 26: 0.99, 27: 1.00,  # Peak
                28: 0.99, 29: 0.97, 30: 0.94, 31: 0.90,
                32: 0.86, 33: 0.82, 34: 0.78, 35: 0.74
            },
            # Pitchers peak slightly earlier
            'pitcher': {
                20: 0.68, 21: 0.74, 22: 0.81, 23: 0.88,
                24: 0.93, 25: 0.97, 26: 1.00, 27: 1.00,  # Peak
                28: 0.99, 29: 0.97, 30: 0.94, 31: 0.89,
                32: 0.84, 33: 0.79, 34: 0.74, 35: 0.69
            }
        }

    def project_career_arc(self, player_id, current_age, current_stats, years_ahead=10):
        """
        Generate projections for each year of player's career.

        Returns visualization-ready data structure.
        """

        projections = []
        player_type = self._determine_player_type(player_id)

        # Get base projection at current age
        base_projection = self._get_base_projection(current_stats)

        # Calculate peak potential
        peak_stats = self._calculate_peak_potential(
            base_projection,
            current_age,
            player_type
        )

        # Generate year-by-year projections
        for year_offset in range(years_ahead):
            age = current_age + year_offset
            season = 2025 + year_offset

            if age > 35:  # Stop at age 35
                break

            # Apply age curve
            age_factor = self.age_curve[player_type].get(age, 0.70)

            # Calculate projected stats for this age
            year_projection = {
                'season': season,
                'age': age,
                'level': self._project_level(age, current_stats),

                # Offensive projections
                'projected_wrc_plus': round(peak_stats['wrc_plus'] * age_factor),
                'projected_woba': round(peak_stats['woba'] * age_factor, 3),
                'projected_ops': round(peak_stats['ops'] * age_factor, 3),

                # Traditional stats
                'projected_avg': round(peak_stats['avg'] * age_factor, 3),
                'projected_obp': round(peak_stats['obp'] * age_factor, 3),
                'projected_slg': round(peak_stats['slg'] * age_factor, 3),

                # Counting stats (assumes 600 PA)
                'projected_hr': round(peak_stats['hr_rate'] * 600 * age_factor),
                'projected_sb': round(peak_stats['sb_rate'] * 600 * age_factor),
                'projected_rbi': round(peak_stats['rbi_rate'] * 600 * age_factor),

                # WAR projection
                'projected_war': round(peak_stats['war'] * age_factor, 1),

                # Confidence interval
                'confidence': self._calculate_confidence(age, current_age),
                'confidence_band': {
                    'upper': round(peak_stats['wrc_plus'] * age_factor * 1.15),
                    'lower': round(peak_stats['wrc_plus'] * age_factor * 0.85)
                }
            }

            # Add development flags
            if age < 24:
                year_projection['development_phase'] = 'Early'
            elif age <= 27:
                year_projection['development_phase'] = 'Prime'
            elif age <= 31:
                year_projection['development_phase'] = 'Peak'
            else:
                year_projection['development_phase'] = 'Decline'

            projections.append(year_projection)

        return projections

    def _calculate_peak_potential(self, current_stats, current_age, player_type):
        """Calculate expected peak statistics."""

        # Get age adjustment factor
        current_factor = self.age_curve[player_type].get(current_age, 0.80)
        peak_age = 27 if player_type == 'hitter' else 26
        peak_factor = self.age_curve[player_type][peak_age]

        # Scale current performance to peak
        scaling_factor = peak_factor / current_factor

        # Apply development uncertainty for younger players
        if current_age < 23:
            # Higher ceiling for young players showing promise
            scaling_factor *= 1.1

        return {
            'wrc_plus': current_stats['wrc_plus'] * scaling_factor,
            'woba': current_stats['woba'] * scaling_factor,
            'ops': current_stats['ops'] * scaling_factor,
            'avg': current_stats['avg'] * (scaling_factor ** 0.7),  # Batting avg less volatile
            'obp': current_stats['obp'] * (scaling_factor ** 0.8),
            'slg': current_stats['slg'] * scaling_factor,
            'hr_rate': current_stats['hr'] / current_stats['pa'],
            'sb_rate': current_stats['sb'] / current_stats['pa'],
            'rbi_rate': current_stats['rbi'] / current_stats['pa'],
            'war': current_stats.get('war', 2.0) * scaling_factor
        }

    def _project_level(self, age, current_stats):
        """Project what level player will be at given age."""

        if age < 22:
            return 'MiLB'
        elif age < 24 and current_stats['level'] != 'MLB':
            return 'AAA/MLB'
        else:
            return 'MLB'

    def _calculate_confidence(self, projected_age, current_age):
        """Calculate confidence in projection based on age distance."""

        years_out = projected_age - current_age

        if years_out <= 1:
            return 0.90
        elif years_out <= 3:
            return 0.75
        elif years_out <= 5:
            return 0.60
        else:
            return 0.40
```

---

## 📊 Visualization-Ready Output Structure

### Player Projection JSON

```json
{
  "player_id": 687867,
  "player_name": "Jackson Holliday",
  "current_age": 21,
  "projection_date": "2025-01-15",

  "yearly_projections": [
    {
      "season": 2025,
      "age": 21,
      "level": "AAA/MLB",
      "projected_wrc_plus": 98,
      "projected_woba": 0.315,
      "projected_ops": 0.745,
      "projected_avg": 0.265,
      "projected_obp": 0.335,
      "projected_slg": 0.410,
      "projected_hr": 15,
      "projected_sb": 18,
      "projected_rbi": 65,
      "projected_war": 1.8,
      "development_phase": "Early",
      "confidence": 0.90,
      "confidence_band": {
        "upper": 113,
        "lower": 83
      }
    },
    {
      "season": 2026,
      "age": 22,
      "level": "MLB",
      "projected_wrc_plus": 108,
      "projected_woba": 0.335,
      "projected_ops": 0.785,
      "projected_avg": 0.272,
      "projected_obp": 0.345,
      "projected_slg": 0.440,
      "projected_hr": 20,
      "projected_sb": 20,
      "projected_rbi": 75,
      "projected_war": 2.8,
      "development_phase": "Early",
      "confidence": 0.75,
      "confidence_band": {
        "upper": 124,
        "lower": 92
      }
    },
    {
      "season": 2027,
      "age": 23,
      "level": "MLB",
      "projected_wrc_plus": 115,
      "projected_woba": 0.348,
      "projected_ops": 0.820,
      "projected_avg": 0.278,
      "projected_obp": 0.355,
      "projected_slg": 0.465,
      "projected_hr": 24,
      "projected_sb": 22,
      "projected_rbi": 85,
      "projected_war": 3.5,
      "development_phase": "Prime",
      "confidence": 0.75,
      "confidence_band": {
        "upper": 132,
        "lower": 98
      }
    },
    {
      "season": 2028,
      "age": 24,
      "level": "MLB",
      "projected_wrc_plus": 122,
      "projected_woba": 0.360,
      "projected_ops": 0.855,
      "projected_avg": 0.282,
      "projected_obp": 0.365,
      "projected_slg": 0.490,
      "projected_hr": 28,
      "projected_sb": 20,
      "projected_rbi": 92,
      "projected_war": 4.2,
      "development_phase": "Prime",
      "confidence": 0.60,
      "confidence_band": {
        "upper": 140,
        "lower": 104
      }
    },
    {
      "season": 2029,
      "age": 25,
      "level": "MLB",
      "projected_wrc_plus": 126,
      "projected_woba": 0.368,
      "projected_ops": 0.875,
      "projected_avg": 0.285,
      "projected_obp": 0.370,
      "projected_slg": 0.505,
      "projected_hr": 30,
      "projected_sb": 18,
      "projected_rbi": 95,
      "projected_war": 4.6,
      "development_phase": "Prime",
      "confidence": 0.60,
      "confidence_band": {
        "upper": 145,
        "lower": 107
      }
    },
    {
      "season": 2030,
      "age": 26,
      "level": "MLB",
      "projected_wrc_plus": 129,
      "projected_woba": 0.372,
      "projected_ops": 0.885,
      "projected_avg": 0.287,
      "projected_obp": 0.373,
      "projected_slg": 0.512,
      "projected_hr": 32,
      "projected_sb": 16,
      "projected_rbi": 98,
      "projected_war": 4.9,
      "development_phase": "Prime",
      "confidence": 0.40,
      "confidence_band": {
        "upper": 148,
        "lower": 110
      }
    },
    {
      "season": 2031,
      "age": 27,
      "level": "MLB",
      "projected_wrc_plus": 130,
      "projected_woba": 0.375,
      "projected_ops": 0.890,
      "projected_avg": 0.288,
      "projected_obp": 0.375,
      "projected_slg": 0.515,
      "projected_hr": 33,
      "projected_sb": 15,
      "projected_rbi": 100,
      "projected_war": 5.0,
      "development_phase": "Peak",
      "confidence": 0.40,
      "confidence_band": {
        "upper": 150,
        "lower": 110
      }
    }
  ],

  "peak_projection": {
    "peak_age": 27,
    "peak_season": 2031,
    "peak_wrc_plus": 130,
    "peak_war": 5.0
  },

  "top_5_comps": [
    {
      "player_name": "Corey Seager",
      "similarity_score": 0.89,
      "age_at_comp": 21,
      "key_similarities": ["hit_tool", "power_potential", "position"],
      "mlb_stats": {"wrc_plus": 138, "war": 5.2, "ops": 0.895}
    },
    {
      "player_name": "Carlos Correa",
      "similarity_score": 0.86,
      "age_at_comp": 21,
      "key_similarities": ["contact", "defense", "trajectory"],
      "mlb_stats": {"wrc_plus": 134, "war": 4.8, "ops": 0.885}
    },
    {
      "player_name": "Xander Bogaerts",
      "similarity_score": 0.84,
      "age_at_comp": 21,
      "key_similarities": ["approach", "hit_tool", "development"],
      "mlb_stats": {"wrc_plus": 125, "war": 4.1, "ops": 0.860}
    },
    {
      "player_name": "Trea Turner",
      "similarity_score": 0.81,
      "age_at_comp": 21,
      "key_similarities": ["speed", "contact", "athleticism"],
      "mlb_stats": {"wrc_plus": 128, "war": 4.5, "ops": 0.870}
    },
    {
      "player_name": "Francisco Lindor",
      "similarity_score": 0.79,
      "age_at_comp": 21,
      "key_similarities": ["tools", "position", "minors_performance"],
      "mlb_stats": {"wrc_plus": 121, "war": 4.3, "ops": 0.845}
    }
  ]
}
```

---

## 📈 Visualization Components

### 1. Career Arc Chart
```python
def create_career_arc_chart(projections):
    """Create interactive plotly chart of career projections."""

    import plotly.graph_objects as go

    fig = go.Figure()

    # Main projection line
    fig.add_trace(go.Scatter(
        x=[p['age'] for p in projections],
        y=[p['projected_wrc_plus'] for p in projections],
        mode='lines+markers',
        name='Projected wRC+',
        line=dict(color='blue', width=3),
        marker=dict(size=8)
    ))

    # Confidence bands
    fig.add_trace(go.Scatter(
        x=[p['age'] for p in projections],
        y=[p['confidence_band']['upper'] for p in projections],
        mode='lines',
        name='Upper bound',
        line=dict(color='lightblue', dash='dash'),
        showlegend=False
    ))

    fig.add_trace(go.Scatter(
        x=[p['age'] for p in projections],
        y=[p['confidence_band']['lower'] for p in projections],
        mode='lines',
        name='Lower bound',
        line=dict(color='lightblue', dash='dash'),
        fill='tonexty',
        showlegend=False
    ))

    # Add phase annotations
    for phase in ['Early', 'Prime', 'Peak', 'Decline']:
        phase_data = [p for p in projections if p['development_phase'] == phase]
        if phase_data:
            fig.add_annotation(
                x=phase_data[0]['age'],
                y=max(p['projected_wrc_plus'] for p in phase_data),
                text=phase,
                showarrow=False,
                yshift=10
            )

    fig.update_layout(
        title='Career Projection Arc',
        xaxis_title='Age',
        yaxis_title='Projected wRC+',
        hovermode='x',
        showlegend=True
    )

    return fig
```

### 2. Comparison Radar Chart
```python
def create_comparison_radar(player, comps):
    """Create radar chart comparing player to top 5 comps."""

    categories = ['Contact', 'Power', 'Speed', 'Discipline', 'Defense']

    fig = go.Figure()

    # Add player
    fig.add_trace(go.Scatterpolar(
        r=player['tool_grades'],
        theta=categories,
        fill='toself',
        name=player['name']
    ))

    # Add top comp only (to avoid clutter)
    fig.add_trace(go.Scatterpolar(
        r=comps[0]['tool_grades'],
        theta=categories,
        fill='toself',
        name=f"Comp: {comps[0]['player_name']}",
        opacity=0.6
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 80]
            )
        ),
        showlegend=True
    )

    return fig
```

### 3. Statistical Table
```python
def create_projection_table(projections):
    """Create formatted table for year-by-year projections."""

    import pandas as pd

    df = pd.DataFrame(projections)

    # Format for display
    display_columns = [
        'season', 'age', 'level',
        'projected_avg', 'projected_obp', 'projected_slg',
        'projected_hr', 'projected_sb', 'projected_wrc_plus',
        'projected_war', 'confidence'
    ]

    df = df[display_columns]

    # Apply formatting
    df['projected_avg'] = df['projected_avg'].apply(lambda x: f'.{str(x)[2:]}')
    df['projected_obp'] = df['projected_obp'].apply(lambda x: f'.{str(x)[2:]}')
    df['projected_slg'] = df['projected_slg'].apply(lambda x: f'.{str(x)[2:]}')
    df['confidence'] = df['confidence'].apply(lambda x: f'{x:.0%}')

    return df
```

---

## 🚀 Implementation Timeline

### Week 1: Data Preparation
- Calculate wOBA/wRC+ from existing stats
- Build age curve database
- Create player comparison pool

### Week 2: Core Models
- Train base projection models
- Implement age curve adjustments
- Build similarity engine (top 5 only)

### Week 3: Projection System
- Create year-by-year projector
- Add confidence intervals
- Generate visualization data

### Week 4: Integration
- Build API endpoints
- Create visualization components
- Generate sample reports

---

## 📊 Sample API Endpoint

```python
@router.get("/prospects/{player_id}/projections")
async def get_player_projections(
    player_id: int,
    years_ahead: int = 10,
    include_comps: bool = True
):
    """
    Get complete projection package for a player.

    Returns:
    - Year-by-year projections (up to 10 years)
    - Top 5 MLB comparisons
    - Peak projection summary
    - Visualization-ready data
    """

    projector = AgeAdjustedProjector()
    comparison = PlayerComparison()

    # Get current stats
    current = await get_player_current_stats(player_id)

    # Generate projections
    projections = projector.project_career_arc(
        player_id,
        current['age'],
        current['stats'],
        years_ahead
    )

    # Find comparisons
    comps = []
    if include_comps:
        comps = comparison.find_top_comps(
            current['features'],
            mlb_database,
            n_comps=5
        )

    return {
        "player_id": player_id,
        "player_name": current['name'],
        "current_age": current['age'],
        "yearly_projections": projections,
        "peak_projection": extract_peak(projections),
        "top_5_comps": comps,
        "visualization_data": {
            "chart_data": format_for_charts(projections),
            "table_data": format_for_table(projections)
        }
    }
```

This system provides exactly 5 player comparisons and complete year-by-year projections perfect for graphing and visualization!