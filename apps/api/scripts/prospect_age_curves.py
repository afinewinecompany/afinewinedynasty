"""
Prospect Age Curve Analysis and Implementation.

This module defines proper age valuation curves for prospect evaluation.
Young players have exponentially higher prospect value due to:
1. Higher ceiling potential
2. More time to develop
3. Greater team control
4. Lower risk of decline
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Tuple


class ProspectAgeCurve:
    """
    Implements industry-standard age curves for prospect valuation.

    Key principles:
    - Peak prospect value: Ages 20-22 (highest ceiling + development time)
    - Rapid value decay after 24
    - Players 27+ have minimal prospect value (known commodities)
    - Exponential decay, not linear
    """

    def __init__(
        self,
        optimal_age: float = 21.5,
        age_sensitivity: float = 2.5,
        hard_cutoff_age: float = 26.5,
        young_bonus_threshold: float = 22.0,
        young_bonus_multiplier: float = 1.2
    ):
        """
        Initialize age curve parameters.

        Args:
            optimal_age: Age with maximum prospect value (default 21.5)
            age_sensitivity: Controls decay steepness (lower = steeper)
            hard_cutoff_age: Maximum age to qualify as prospect
            young_bonus_threshold: Age below which to apply elite young player bonus
            young_bonus_multiplier: Extra multiplier for elite young talent
        """
        self.optimal_age = optimal_age
        self.age_sensitivity = age_sensitivity
        self.hard_cutoff_age = hard_cutoff_age
        self.young_bonus_threshold = young_bonus_threshold
        self.young_bonus_multiplier = young_bonus_multiplier

    def calculate_age_factor(self, age: float) -> float:
        """
        Calculate age-based prospect value multiplier.

        Uses exponential decay formula:
            age_factor = exp((optimal_age - current_age) / age_sensitivity)

        Args:
            age: Player's current age

        Returns:
            Multiplier (1.0 = baseline at optimal age, >1 = younger, <1 = older)
        """
        if age > self.hard_cutoff_age:
            return 0.0  # Not a prospect

        # Exponential age curve
        age_factor = np.exp((self.optimal_age - age) / self.age_sensitivity)

        # Elite young player bonus
        if age < self.young_bonus_threshold:
            age_factor *= self.young_bonus_multiplier

        return age_factor

    def calculate_age_factors_vectorized(self, ages: pd.Series) -> pd.Series:
        """Vectorized version for DataFrame operations."""
        # Hard cutoff
        factors = np.where(
            ages > self.hard_cutoff_age,
            0.0,
            np.exp((self.optimal_age - ages) / self.age_sensitivity)
        )

        # Young player bonus
        factors = np.where(
            ages < self.young_bonus_threshold,
            factors * self.young_bonus_multiplier,
            factors
        )

        return pd.Series(factors, index=ages.index)

    def plot_age_curve(self, age_range: Tuple[int, int] = (18, 30)):
        """Visualize the age curve."""
        ages = np.linspace(age_range[0], age_range[1], 100)
        factors = [self.calculate_age_factor(age) for age in ages]

        plt.figure(figsize=(12, 6))
        plt.plot(ages, factors, linewidth=2, label='Age Factor')
        plt.axvline(self.optimal_age, color='g', linestyle='--', label=f'Optimal Age ({self.optimal_age})')
        plt.axvline(self.young_bonus_threshold, color='b', linestyle='--', label=f'Elite Young ({self.young_bonus_threshold})')
        plt.axvline(self.hard_cutoff_age, color='r', linestyle='--', label=f'Cutoff ({self.hard_cutoff_age})')
        plt.axhline(1.0, color='gray', linestyle=':', alpha=0.5)

        plt.xlabel('Age', fontsize=12)
        plt.ylabel('Prospect Value Multiplier', fontsize=12)
        plt.title('Prospect Age Curve - Exponential Decay Model', fontsize=14, fontweight='bold')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig('prospect_age_curve.png', dpi=150)
        print("Saved age curve visualization to prospect_age_curve.png")

        # Print key values
        print("\n=== AGE CURVE VALUES ===")
        for age in [19, 20, 21, 22, 23, 24, 25, 26, 27, 28]:
            factor = self.calculate_age_factor(age)
            print(f"Age {age}: {factor:.3f}x")

    def get_age_tier(self, age: float) -> str:
        """Classify age into prospect tiers."""
        if age > self.hard_cutoff_age:
            return "Non-Prospect"
        elif age < 21:
            return "Elite Youth"
        elif age < 23:
            return "Premium Prospect"
        elif age < 25:
            return "Standard Prospect"
        elif age < 26.5:
            return "Older Prospect"
        else:
            return "Fringe Prospect"


class LevelAgeAdjustment:
    """
    Adjusts prospect value based on age-relative-to-level.

    A 21yo in AA is much more impressive than a 27yo in AAA.
    """

    # Average ages by level (MLB industry standards)
    LEVEL_AVG_AGES = {
        'AAA': 26.0,
        'AA': 24.0,
        'A+': 22.5,
        'A': 21.0,
        'Rookie+': 20.0,
        'Rookie': 19.0
    }

    # Level quality multipliers (higher level = better)
    LEVEL_MULTIPLIERS = {
        'AAA': 1.3,
        'AA': 1.2,
        'A+': 1.0,
        'A': 0.85,
        'Rookie+': 0.7,
        'Rookie': 0.6
    }

    @classmethod
    def calculate_age_vs_level_factor(cls, age: float, level: str) -> float:
        """
        Calculate bonus/penalty for age relative to level average.

        Args:
            age: Player's age
            level: Highest level reached

        Returns:
            Multiplier (>1 if young for level, <1 if old for level)
        """
        if level not in cls.LEVEL_AVG_AGES:
            return 1.0

        level_avg_age = cls.LEVEL_AVG_AGES[level]
        age_diff = level_avg_age - age  # Positive = younger than average

        # Exponential bonus for being young at high levels
        # +1 year younger = +15% value, +2 years = +32%, etc.
        factor = 1.0 + (age_diff * 0.15)

        # Apply level quality multiplier
        level_mult = cls.LEVEL_MULTIPLIERS.get(level, 1.0)

        return max(0.5, factor * level_mult)  # Floor at 0.5x

    @classmethod
    def get_level_context(cls, age: float, level: str) -> str:
        """Get descriptive context for age/level combo."""
        if level not in cls.LEVEL_AVG_AGES:
            return "Unknown level"

        level_avg = cls.LEVEL_AVG_AGES[level]
        diff = age - level_avg

        if diff < -2:
            return f"Elite age for {level} (2+ years young)"
        elif diff < -1:
            return f"Young for {level}"
        elif diff < 1:
            return f"Average age for {level}"
        elif diff < 2:
            return f"Old for {level}"
        else:
            return f"Very old for {level} (2+ years over avg)"


def demonstrate_age_curves():
    """Demo the age curve system."""
    print("="*80)
    print("PROSPECT AGE CURVE SYSTEM")
    print("="*80)

    curve = ProspectAgeCurve()

    # Show age factors
    print("\n1. BASE AGE FACTORS (Exponential Decay)")
    print("-" * 80)
    for age in range(19, 30):
        factor = curve.calculate_age_factor(age)
        tier = curve.get_age_tier(age)
        print(f"Age {age}: {factor:.3f}x  ({tier})")

    # Show level adjustments
    print("\n2. AGE-RELATIVE-TO-LEVEL ADJUSTMENTS")
    print("-" * 80)
    test_cases = [
        (21, 'AA', "21yo in Double-A"),
        (27, 'AAA', "27yo in Triple-A"),
        (20, 'A+', "20yo in High-A"),
        (25, 'AAA', "25yo in Triple-A"),
        (22, 'AAA', "22yo in Triple-A (elite)")
    ]

    for age, level, desc in test_cases:
        base_factor = curve.calculate_age_factor(age)
        level_factor = LevelAgeAdjustment.calculate_age_vs_level_factor(age, level)
        combined = base_factor * level_factor
        context = LevelAgeAdjustment.get_level_context(age, level)

        print(f"{desc}:")
        print(f"  Base age factor: {base_factor:.3f}x")
        print(f"  Level adjustment: {level_factor:.3f}x")
        print(f"  Combined: {combined:.3f}x")
        print(f"  Context: {context}\n")

    # Example comparisons
    print("\n3. REAL-WORLD COMPARISONS")
    print("-" * 80)

    # Jakson Reetz vs young talent
    reetz_age, reetz_level = 29.7, 'AAA'
    reetz_factor = curve.calculate_age_factor(reetz_age)

    young_age, young_level = 21, 'AA'
    young_factor = curve.calculate_age_factor(young_age)
    young_level_adj = LevelAgeAdjustment.calculate_age_vs_level_factor(young_age, young_level)
    young_combined = young_factor * young_level_adj

    print(f"Jakson Reetz (29.7yo, AAA):")
    print(f"  Age factor: {reetz_factor:.3f}x (basically disqualified)\n")

    print(f"Typical 21yo in AA:")
    print(f"  Age factor: {young_factor:.3f}x")
    print(f"  Level adjustment: {young_level_adj:.3f}x")
    print(f"  Combined: {young_combined:.3f}x")
    print(f"  = {young_combined / max(reetz_factor, 0.01):.1f}x more valuable than Reetz!")

    # Plot the curve
    print("\n4. GENERATING VISUALIZATION...")
    curve.plot_age_curve()

    print("\n" + "="*80)
    print("Age curve system ready for integration!")
    print("="*80)


if __name__ == "__main__":
    demonstrate_age_curves()
