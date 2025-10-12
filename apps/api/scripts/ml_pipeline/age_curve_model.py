#!/usr/bin/env python3
"""
Age Curve Modeling for Year-by-Year Projections

Generates career arc projections with visualization-ready output.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AgeAdjustedProjector:
    """Generate year-by-year projections based on age curves."""

    def __init__(self):
        # Historical age curve factors from MLB data
        self.age_curves = {
            'hitter': {
                18: 0.55, 19: 0.65, 20: 0.70, 21: 0.75, 22: 0.82,
                23: 0.89, 24: 0.94, 25: 0.97, 26: 0.99, 27: 1.00,  # Peak
                28: 0.99, 29: 0.97, 30: 0.94, 31: 0.90, 32: 0.86,
                33: 0.82, 34: 0.78, 35: 0.74, 36: 0.70, 37: 0.65
            },
            'pitcher': {
                18: 0.50, 19: 0.60, 20: 0.68, 21: 0.74, 22: 0.81,
                23: 0.88, 24: 0.93, 25: 0.97, 26: 1.00, 27: 1.00,  # Peak
                28: 0.99, 29: 0.97, 30: 0.94, 31: 0.89, 32: 0.84,
                33: 0.79, 34: 0.74, 35: 0.69, 36: 0.64, 37: 0.58
            },
            'speed': {  # Speed peaks earlier and declines faster
                18: 0.85, 19: 0.90, 20: 0.94, 21: 0.97, 22: 0.99,
                23: 1.00, 24: 1.00, 25: 0.99, 26: 0.97, 27: 0.94,  # Early peak
                28: 0.91, 29: 0.87, 30: 0.83, 31: 0.78, 32: 0.73,
                33: 0.67, 34: 0.61, 35: 0.55, 36: 0.49, 37: 0.43
            }
        }

        # Position-specific adjustments
        self.position_aging = {
            'C': -0.02,   # Catchers age worse
            '1B': 0.01,   # 1B age better
            '2B': -0.01,  # Middle infielders decline faster
            'SS': -0.015,
            '3B': 0.0,
            'LF': 0.0,
            'CF': -0.01,  # CF decline as speed declines
            'RF': 0.005,
            'DH': 0.02,   # DH age best
            'SP': 0.0,
            'RP': 0.01    # Relievers can last longer
        }

    def project_career_arc(
        self,
        current_stats: Dict,
        current_age: int,
        position: str,
        years_ahead: int = 10
    ) -> List[Dict]:
        """
        Generate year-by-year projections for visualization.

        Args:
            current_stats: Current performance metrics
            current_age: Player's current age
            position: Player position
            years_ahead: Number of years to project

        Returns:
            List of yearly projections with confidence bands
        """

        projections = []
        player_type = 'pitcher' if position in ['SP', 'RP'] else 'hitter'

        # Calculate peak potential from current performance
        peak_stats = self._calculate_peak_potential(
            current_stats,
            current_age,
            player_type,
            position
        )

        # Generate projections for each year
        for year_offset in range(years_ahead):
            age = current_age + year_offset
            season = datetime.now().year + year_offset

            if age > 37:  # Stop at age 37
                break

            projection = self._project_single_year(
                peak_stats,
                age,
                season,
                player_type,
                position,
                current_age
            )

            projections.append(projection)

        return projections

    def _calculate_peak_potential(
        self,
        current_stats: Dict,
        current_age: int,
        player_type: str,
        position: str
    ) -> Dict:
        """Calculate expected peak statistics."""

        # Get age adjustment factors
        curve = self.age_curves[player_type]
        current_factor = curve.get(current_age, 0.80)

        # Peak age varies by position
        peak_age = 26 if player_type == 'pitcher' else 27

        # Adjust for position
        position_adj = self.position_aging.get(position, 0.0)
        peak_age += int(position_adj * 3)  # Adjust peak age slightly

        peak_factor = curve[peak_age]

        # Calculate scaling factor
        scaling = peak_factor / current_factor

        # Apply development boost for very young players
        if current_age <= 21:
            scaling *= 1.15  # Young players have more upside
        elif current_age <= 23:
            scaling *= 1.08

        # Calculate peak projections
        peak_stats = {}

        # Offensive stats
        if 'wrc_plus' in current_stats:
            # wRC+ scales with overall performance
            peak_stats['wrc_plus'] = current_stats['wrc_plus'] * scaling

        if 'woba' in current_stats:
            # wOBA scales but less dramatically
            peak_stats['woba'] = current_stats['woba'] * (1 + (scaling - 1) * 0.5)

        # Traditional stats
        peak_stats['avg'] = current_stats.get('batting_avg', .250) * (1 + (scaling - 1) * 0.3)
        peak_stats['obp'] = current_stats.get('obp', .320) * (1 + (scaling - 1) * 0.4)
        peak_stats['slg'] = current_stats.get('slg', .400) * (1 + (scaling - 1) * 0.6)
        peak_stats['ops'] = peak_stats['obp'] + peak_stats['slg']

        # Power develops later, peaks around 27-29
        power_scaling = scaling * 1.1 if current_age < 24 else scaling
        peak_stats['hr_rate'] = current_stats.get('hr_rate', 0.04) * power_scaling

        # Speed declines earlier
        speed_curve = self.age_curves['speed']
        speed_current = speed_curve.get(current_age, 0.90)
        speed_peak = speed_curve[23]  # Speed peaks at 23-24
        speed_scaling = speed_peak / speed_current
        peak_stats['sb_rate'] = current_stats.get('sb_rate', 0.03) * speed_scaling

        # Plate discipline improves with age
        peak_stats['bb_rate'] = current_stats.get('walk_rate', 0.08) * (1 + (scaling - 1) * 0.8)
        peak_stats['k_rate'] = current_stats.get('strikeout_rate', 0.22) * (1 + (scaling - 1) * -0.3)

        # WAR projection
        current_war = current_stats.get('war', 2.0)
        peak_stats['war'] = current_war * scaling

        return peak_stats

    def _project_single_year(
        self,
        peak_stats: Dict,
        age: int,
        season: int,
        player_type: str,
        position: str,
        current_age: int
    ) -> Dict:
        """Project statistics for a single year."""

        # Get age factor
        curve = self.age_curves[player_type]
        age_factor = curve.get(age, 0.70)

        # Position adjustment
        position_adj = self.position_aging.get(position, 0.0)
        age_factor *= (1 + position_adj * (age - 27))  # Adjust based on distance from peak

        # Calculate projected stats
        projection = {
            'season': season,
            'age': age,
            'level': self._project_level(age, position)
        }

        # Core projections
        if 'wrc_plus' in peak_stats:
            projection['projected_wrc_plus'] = round(peak_stats['wrc_plus'] * age_factor)

        if 'woba' in peak_stats:
            projection['projected_woba'] = round(peak_stats['woba'] * age_factor, 3)

        # Traditional stats
        projection['projected_avg'] = round(peak_stats['avg'] * age_factor, 3)
        projection['projected_obp'] = round(peak_stats['obp'] * age_factor, 3)
        projection['projected_slg'] = round(peak_stats['slg'] * age_factor, 3)
        projection['projected_ops'] = round(projection['projected_obp'] + projection['projected_slg'], 3)

        # Counting stats (assume 600 PA for full season)
        pa_adjustment = 600
        projection['projected_hr'] = round(peak_stats['hr_rate'] * pa_adjustment * age_factor)
        projection['projected_sb'] = round(peak_stats['sb_rate'] * pa_adjustment * age_factor)

        # Calculate RBI/Runs (rough estimates)
        projection['projected_rbi'] = round(projection['projected_hr'] * 3.0 + 30)
        projection['projected_runs'] = round(projection['projected_obp'] * 150)

        # WAR projection
        projection['projected_war'] = round(peak_stats['war'] * age_factor, 1)

        # Plate discipline
        projection['projected_bb_rate'] = round(peak_stats['bb_rate'] * age_factor, 3)
        projection['projected_k_rate'] = round(peak_stats['k_rate'] / age_factor, 3)  # K-rate gets worse with age

        # Development phase
        projection['development_phase'] = self._get_development_phase(age)

        # Confidence calculation
        projection['confidence'] = self._calculate_confidence(age, current_age)

        # Confidence bands (±15% for uncertainty)
        uncertainty = 0.15 * (1 + abs(age - current_age) * 0.05)  # More uncertainty further out

        projection['confidence_band'] = {
            'upper': round(projection.get('projected_wrc_plus', 100) * (1 + uncertainty)),
            'lower': round(projection.get('projected_wrc_plus', 100) * (1 - uncertainty))
        }

        # Add percentile projections
        projection['percentiles'] = self._calculate_percentiles(projection, uncertainty)

        return projection

    def _project_level(self, age: int, position: str) -> str:
        """Project what level the player will be at given age."""

        if age < 20:
            return 'A/A+'
        elif age < 22:
            return 'AA/AAA'
        elif age < 24:
            return 'AAA/MLB'
        else:
            return 'MLB'

    def _get_development_phase(self, age: int) -> str:
        """Categorize development phase by age."""

        if age < 23:
            return 'Development'
        elif age <= 26:
            return 'Entering Prime'
        elif age <= 29:
            return 'Peak'
        elif age <= 32:
            return 'Prime'
        else:
            return 'Decline'

    def _calculate_confidence(self, projected_age: int, current_age: int) -> float:
        """Calculate confidence in projection based on age distance."""

        years_out = abs(projected_age - current_age)

        if years_out == 0:
            return 0.95
        elif years_out <= 1:
            return 0.90
        elif years_out <= 2:
            return 0.80
        elif years_out <= 3:
            return 0.70
        elif years_out <= 5:
            return 0.55
        else:
            return 0.40

    def _calculate_percentiles(self, projection: Dict, uncertainty: float) -> Dict:
        """Calculate percentile outcomes for visualization."""

        base_wrc = projection.get('projected_wrc_plus', 100)

        return {
            '90th': round(base_wrc * (1 + uncertainty * 1.5)),  # Optimistic
            '75th': round(base_wrc * (1 + uncertainty * 0.75)),
            '50th': base_wrc,  # Median projection
            '25th': round(base_wrc * (1 - uncertainty * 0.75)),
            '10th': round(base_wrc * (1 - uncertainty * 1.5))  # Pessimistic
        }

    def create_visualization_data(self, projections: List[Dict]) -> Dict:
        """Format projections for easy visualization."""

        return {
            'chart_data': {
                'ages': [p['age'] for p in projections],
                'seasons': [p['season'] for p in projections],
                'wrc_plus': [p.get('projected_wrc_plus', 0) for p in projections],
                'upper_bound': [p['confidence_band']['upper'] for p in projections],
                'lower_bound': [p['confidence_band']['lower'] for p in projections],
                'war': [p.get('projected_war', 0) for p in projections],
                'development_phases': [p['development_phase'] for p in projections]
            },
            'peak_projection': {
                'age': max(projections, key=lambda x: x.get('projected_wrc_plus', 0))['age'],
                'season': max(projections, key=lambda x: x.get('projected_wrc_plus', 0))['season'],
                'wrc_plus': max(p.get('projected_wrc_plus', 0) for p in projections),
                'war': max(p.get('projected_war', 0) for p in projections)
            },
            'table_data': pd.DataFrame(projections)
        }


def demo_projection():
    """Demo the age curve projector."""

    projector = AgeAdjustedProjector()

    # Sample current stats for a 21-year-old shortstop
    current_stats = {
        'batting_avg': .275,
        'obp': .345,
        'slg': .450,
        'wrc_plus': 110,
        'woba': .340,
        'hr_rate': 0.035,  # HR per AB
        'sb_rate': 0.04,   # SB per PA
        'walk_rate': 0.09,
        'strikeout_rate': 0.20,
        'war': 2.5
    }

    # Generate projections
    projections = projector.project_career_arc(
        current_stats=current_stats,
        current_age=21,
        position='SS',
        years_ahead=15
    )

    # Display projections
    print("\n" + "=" * 80)
    print("CAREER ARC PROJECTIONS - 21-Year-Old Shortstop")
    print("=" * 80)

    for proj in projections[:10]:  # Show first 10 years
        print(f"\nAge {proj['age']} ({proj['season']}) - {proj['development_phase']}:")
        print(f"  wRC+: {proj.get('projected_wrc_plus', 'N/A')} [{proj['confidence_band']['lower']}-{proj['confidence_band']['upper']}]")
        print(f"  AVG/OBP/SLG: {proj['projected_avg']:.3f}/{proj['projected_obp']:.3f}/{proj['projected_slg']:.3f}")
        print(f"  HR: {proj['projected_hr']} | SB: {proj['projected_sb']} | WAR: {proj['projected_war']}")
        print(f"  Confidence: {proj['confidence']:.0%}")

    # Get visualization data
    viz_data = projector.create_visualization_data(projections)
    print(f"\n✓ Peak Projection: {viz_data['peak_projection']['wrc_plus']} wRC+ at age {viz_data['peak_projection']['age']}")


if __name__ == "__main__":
    demo_projection()