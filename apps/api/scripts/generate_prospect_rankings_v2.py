"""
Generate Prospect Rankings V2 - Age-Aware & Prospect-Focused

KEY IMPROVEMENTS:
1. Hard age cutoff at 26.5 years (27+ are not prospects)
2. Exponential age curves (young players valued much higher)
3. Separate MLB prediction from prospect valuation
4. Level-appropriate age adjustments
5. Progression speed bonuses
6. Ceiling/floor risk adjustments

This system answers: "Who is the most valuable PROSPECT?" not "Who will be best in MLB?"
"""

import asyncio
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import engine
from scripts.prospect_age_curves import ProspectAgeCurve, LevelAgeAdjustment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProspectRankingSystemV2:
    """
    Two-stage prospect ranking system:

    Stage 1: Predict MLB performance (from MiLB data)
    Stage 2: Calculate prospect value (age curves + context)
    """

    def __init__(self):
        self.age_curve = ProspectAgeCurve(
            optimal_age=21.5,
            age_sensitivity=2.5,
            hard_cutoff_age=26.5,
            young_bonus_threshold=22.0,
            young_bonus_multiplier=1.2
        )

    async def load_prospect_data(self) -> pd.DataFrame:
        """Load all MiLB prospect data with birth dates."""
        logger.info("Loading prospect data from database...")

        async with engine.begin() as conn:
            # Get aggregated MiLB stats with birth dates
            result = await conn.execute(text("""
                WITH player_stats AS (
                    SELECT
                        m.mlb_player_id,
                        p.name as full_name,
                        p.birth_date,
                        p.position as primary_position,
                        p.current_team,
                        MAX(m.level) as highest_level,
                        SUM(m.plate_appearances) as total_pa,
                        SUM(m.at_bats) as total_ab,
                        SUM(m.hits) as total_h,
                        SUM(m.doubles) as total_doubles,
                        SUM(m.triples) as total_triples,
                        SUM(m.home_runs) as total_hr,
                        SUM(m.walks) as total_bb,
                        SUM(m.strikeouts) as total_so,
                        SUM(m.stolen_bases) as total_sb,
                        SUM(m.hit_by_pitch) as total_hbp,
                        SUM(m.sacrifice_flies) as total_sf,
                        COUNT(DISTINCT m.season) as seasons_played,
                        MIN(m.game_date) as first_game,
                        MAX(m.game_date) as last_game
                    FROM milb_game_logs m
                    INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                    WHERE m.data_source = 'mlb_stats_api_gamelog'
                    AND m.plate_appearances > 0
                    AND p.birth_date IS NOT NULL
                    GROUP BY m.mlb_player_id, p.name, p.birth_date, p.position, p.current_team
                )
                SELECT
                    ps.*,
                    COALESCE(mlb.mlb_ab, 0) as mlb_ab,
                    COALESCE(mlb.mlb_pa, 0) as mlb_pa
                FROM player_stats ps
                LEFT JOIN (
                    SELECT mlb_player_id, SUM(at_bats) as mlb_ab, SUM(plate_appearances) as mlb_pa
                    FROM mlb_game_logs
                    GROUP BY mlb_player_id
                ) mlb ON ps.mlb_player_id = mlb.mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            logger.error("No prospect data found!")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team',
            'highest_level', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
            'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'total_hbp', 'total_sf', 'seasons_played', 'first_game', 'last_game',
            'mlb_ab', 'mlb_pa'
        ])

        # Convert numeric columns
        numeric_cols = ['total_pa', 'total_ab', 'total_h', 'total_doubles', 'total_triples',
                       'total_hr', 'total_bb', 'total_so', 'total_sb', 'total_hbp', 'total_sf',
                       'seasons_played', 'mlb_ab', 'mlb_pa']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        logger.info(f"Loaded {len(df)} players with MiLB data")
        return df

    def calculate_current_age(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate current age from birth date."""
        df = df.copy()
        current_date = datetime.now()
        df['birth_date'] = pd.to_datetime(df['birth_date'])
        df['current_age'] = (current_date - df['birth_date']).dt.days / 365.25
        return df

    def filter_prospects(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply prospect qualification filters:
        1. Age <= 26.5 years
        2. MLB AB < 130
        3. MiLB PA >= 100
        """
        df = df.copy()

        initial_count = len(df)

        # Filter 1: Age cutoff
        df = df[df['current_age'] <= self.age_curve.hard_cutoff_age]
        logger.info(f"After age filter (≤26.5): {len(df)} players (removed {initial_count - len(df)})")

        # Filter 2: MLB experience
        df = df[df['mlb_ab'] < 130]
        logger.info(f"After MLB AB filter (<130): {len(df)} players")

        # Filter 3: Minimum MiLB experience
        df = df[df['total_pa'] >= 100]
        logger.info(f"After MiLB PA filter (≥100): {len(df)} players")

        return df

    def calculate_milb_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MiLB performance metrics."""
        df = df.copy()

        # Basic stats
        df['singles'] = df['total_h'] - df['total_doubles'] - df['total_triples'] - df['total_hr']
        df['tb'] = (df['singles'] +
                   df['total_doubles'] * 2 +
                   df['total_triples'] * 3 +
                   df['total_hr'] * 4)

        # Rate stats
        df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
        df['obp'] = (df['total_h'] + df['total_bb'] + df['total_hbp']) / (
            df['total_pa'].replace(0, np.nan)
        )
        df['slg'] = df['tb'] / df['total_ab'].replace(0, np.nan)
        df['ops'] = df['obp'] + df['slg']
        df['iso'] = df['slg'] - df['avg']

        # Discipline stats
        df['bb_rate'] = df['total_bb'] / df['total_pa']
        df['so_rate'] = df['total_so'] / df['total_pa']
        df['bb_so_ratio'] = df['total_bb'] / df['total_so'].replace(0, np.nan)

        # Power stats
        df['hr_rate'] = df['total_hr'] / df['total_pa']
        df['sb_rate'] = df['total_sb'] / df['total_pa']

        # Fill NaN
        df = df.fillna(0)

        return df

    def predict_mlb_performance(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict MLB performance using simple translation factors.

        For now, use level-based translation (will integrate trained models later).
        """
        df = df.copy()

        # Level translation factors (MiLB to MLB)
        level_factors = {
            'AAA': 0.90,
            'AA': 0.80,
            'A+': 0.70,
            'A': 0.60,
            'Rookie+': 0.50,
            'Rookie': 0.40
        }

        df['translation_factor'] = df['highest_level'].map(level_factors).fillna(0.60)

        # Predicted MLB stats (conservative estimates)
        df['pred_mlb_ops'] = df['ops'] * df['translation_factor']
        df['pred_mlb_obp'] = df['obp'] * df['translation_factor']
        df['pred_mlb_slg'] = df['slg'] * df['translation_factor']

        # Predict wOBA (simplified)
        df['pred_mlb_woba'] = (df['pred_mlb_obp'] - 0.1) * 0.85

        # Predict wRC+ (wOBA-based, league average = 100)
        # wRC+ formula: ((wOBA - lg_wOBA) / wOBA_scale) * 100 + 100
        league_woba = 0.320
        woba_scale = 1.25
        df['pred_mlb_wrc_plus'] = ((df['pred_mlb_woba'] - league_woba) / woba_scale) * 100 + 100

        # Ensure reasonable bounds
        df['pred_mlb_wrc_plus'] = df['pred_mlb_wrc_plus'].clip(40, 160)
        df['pred_mlb_ops'] = df['pred_mlb_ops'].clip(0.400, 1.100)

        logger.info("Calculated MLB predictions using translation factors")
        return df

    def calculate_prospect_value(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate prospect-specific value scores.

        This is where we apply age curves and context.
        """
        df = df.copy()

        # 1. Base age factor (exponential)
        df['age_factor'] = self.age_curve.calculate_age_factors_vectorized(df['current_age'])
        df['age_tier'] = df['current_age'].apply(self.age_curve.get_age_tier)

        # 2. Age-relative-to-level adjustment
        df['level_age_factor'] = df.apply(
            lambda row: LevelAgeAdjustment.calculate_age_vs_level_factor(
                row['current_age'], row['highest_level']
            ),
            axis=1
        )

        # 3. Combined age adjustment
        df['combined_age_factor'] = df['age_factor'] * df['level_age_factor']

        # 4. Performance quality score
        # Normalize OPS to 0-1 scale (0.600 = poor, 1.000 = elite)
        df['performance_score'] = ((df['ops'] - 0.600) / 0.400).clip(0, 2.0)

        # 5. Level quality multiplier
        level_quality = {
            'AAA': 1.3,
            'AA': 1.2,
            'A+': 1.0,
            'A': 0.85,
            'Rookie+': 0.7,
            'Rookie': 0.6
        }
        df['level_quality'] = df['highest_level'].map(level_quality).fillna(1.0)

        # 6. Sample size reliability
        # Players with more PAs = more reliable (cap at 1.0)
        df['sample_reliability'] = (df['total_pa'] / 500).clip(0.5, 1.0)

        # 7. MLB prediction quality
        # Higher predicted MLB performance = higher ceiling
        df['mlb_ceiling_score'] = (df['pred_mlb_wrc_plus'] / 100.0).clip(0.5, 1.5)

        # 8. FINAL PROSPECT VALUE SCORE
        df['prospect_value_score'] = (
            df['pred_mlb_wrc_plus'] *          # Base MLB prediction
            df['combined_age_factor'] *         # Age curve (HUGE impact)
            df['level_quality'] *               # Level reached
            df['sample_reliability'] *          # Data reliability
            (1 + df['performance_score'] * 0.2) # Performance bonus
        )

        logger.info("Calculated prospect value scores with age curves")
        return df

    async def generate_rankings(self) -> pd.DataFrame:
        """Generate complete prospect rankings."""
        logger.info("="*80)
        logger.info("PROSPECT RANKING SYSTEM V2 - AGE-AWARE")
        logger.info("="*80)

        # Load data
        df = await self.load_prospect_data()

        # Calculate age
        df = self.calculate_current_age(df)

        # Filter prospects
        df = self.filter_prospects(df)

        # Calculate MiLB stats
        df = self.calculate_milb_stats(df)

        # Predict MLB performance
        df = self.predict_mlb_performance(df)

        # Calculate prospect value
        df = self.calculate_prospect_value(df)

        # Sort by prospect value
        df = df.sort_values('prospect_value_score', ascending=False)
        df['rank'] = range(1, len(df) + 1)

        logger.info(f"\n✅ Generated rankings for {len(df)} prospects")
        return df

    def print_top_prospects(self, df: pd.DataFrame, n: int = 50):
        """Print top N prospects."""
        print("\n" + "="*160)
        print(f"TOP {n} PROSPECTS - V2 AGE-AWARE RANKINGS")
        print("="*160)
        print(f"{'Rank':<6} {'Name':<25} {'Age':<7} {'Tier':<20} {'Pos':<6} {'Lvl':<6} {'PAs':<7} "
              f"{'OPS':<7} {'AgeFactor':<11} {'PredwRC+':<10} {'Value':<10}")
        print("-"*160)

        for _, row in df.head(n).iterrows():
            print(f"{int(row['rank']):<6} "
                  f"{row['full_name'][:24]:<25} "
                  f"{row['current_age']:<7.2f} "
                  f"{row['age_tier']:<20} "
                  f"{str(row['primary_position'])[:5]:<6} "
                  f"{str(row['highest_level']):<6} "
                  f"{int(row['total_pa']):<7} "
                  f"{row['ops']:<7.3f} "
                  f"{row['combined_age_factor']:<11.3f} "
                  f"{row['pred_mlb_wrc_plus']:<10.1f} "
                  f"{row['prospect_value_score']:<10.1f}")

    def export_rankings(self, df: pd.DataFrame, filename: str = 'prospect_rankings_v2.csv'):
        """Export rankings to CSV."""
        export_cols = [
            'rank', 'mlb_player_id', 'full_name', 'current_age', 'age_tier',
            'primary_position', 'current_team', 'highest_level', 'total_pa',
            'ops', 'obp', 'slg', 'iso', 'bb_rate', 'so_rate',
            'pred_mlb_wrc_plus', 'pred_mlb_woba', 'pred_mlb_ops',
            'age_factor', 'level_age_factor', 'combined_age_factor',
            'prospect_value_score'
        ]

        df[export_cols].to_csv(filename, index=False)
        logger.info(f"✅ Exported rankings to {filename}")


async def main():
    """Main execution."""
    system = ProspectRankingSystemV2()

    # Generate rankings
    rankings = await system.generate_rankings()

    # Print top 50
    system.print_top_prospects(rankings, n=50)

    # Export
    system.export_rankings(rankings)

    # Show age distribution
    print("\n" + "="*80)
    print("AGE DISTRIBUTION IN NEW RANKINGS (Top 50)")
    print("="*80)
    top_50 = rankings.head(50)
    print(f"Under 21: {len(top_50[top_50['current_age'] < 21])}")
    print(f"21-23: {len(top_50[(top_50['current_age'] >= 21) & (top_50['current_age'] < 23)])}")
    print(f"23-25: {len(top_50[(top_50['current_age'] >= 23) & (top_50['current_age'] < 25)])}")
    print(f"25-27: {len(top_50[top_50['current_age'] >= 25])}")

    print("\n" + "="*80)
    print("DONE!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
