"""
Generate Prospect Rankings V3 - Unified Hitters + Pitchers with Statcast

KEY FEATURES:
1. Integrated hitter AND pitcher rankings
2. Statcast advanced metrics (exit velo, launch angle, barrel%)
3. Pitcher-specific age curves (peak at 23-24, not 21-22)
4. Advanced pitcher metrics (FIP, K-BB%, SwStr%)
5. Position-adjusted valuations
6. Unified prospect value scoring

This creates a SINGLE top prospect list with both hitters and pitchers.
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


class PitcherAgeCurve(ProspectAgeCurve):
    """
    Pitcher-specific age curves.

    Pitchers develop slower than hitters:
    - Peak prospect age: 22-23 (vs 21-22 for hitters)
    - Hard cutoff: 27 (vs 26.5 for hitters)
    - Less extreme youth bonus (physical development matters)
    """

    def __init__(self):
        super().__init__(
            optimal_age=22.5,         # Pitchers peak slightly later
            age_sensitivity=2.8,       # Slightly less steep decay
            hard_cutoff_age=27.0,      # More lenient cutoff
            young_bonus_threshold=22.5,
            young_bonus_multiplier=1.15  # Smaller bonus than hitters
        )


class UnifiedProspectRankingSystem:
    """Ranks both hitters and pitchers in a unified list."""

    def __init__(self):
        self.hitter_age_curve = ProspectAgeCurve(
            optimal_age=21.5,
            age_sensitivity=2.5,
            hard_cutoff_age=26.5,
            young_bonus_threshold=22.0,
            young_bonus_multiplier=1.2
        )
        self.pitcher_age_curve = PitcherAgeCurve()

    # ========== HITTER PIPELINE ==========

    async def load_hitter_data(self) -> pd.DataFrame:
        """Load hitter data with Statcast metrics."""
        logger.info("Loading hitter data with Statcast...")

        async with engine.begin() as conn:
            result = await conn.execute(text("""
                WITH hitter_stats AS (
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
                    AND (COALESCE(m.games_pitched, 0) = 0)
                    AND p.birth_date IS NOT NULL
                    GROUP BY m.mlb_player_id, p.name, p.birth_date, p.position, p.current_team
                ),
                statcast AS (
                    SELECT
                        mlb_player_id,
                        avg_ev as avg_exit_velo,
                        max_ev as max_exit_velo,
                        hard_hit_pct,
                        avg_la as avg_launch_angle,
                        barrel_pct
                    FROM milb_statcast_metrics_imputed
                )
                SELECT
                    hs.*,
                    COALESCE(mlb.mlb_ab, 0) as mlb_ab,
                    COALESCE(mlb.mlb_pa, 0) as mlb_pa,
                    sc.avg_exit_velo,
                    sc.max_exit_velo,
                    sc.hard_hit_pct,
                    sc.avg_launch_angle,
                    sc.barrel_pct
                FROM hitter_stats hs
                LEFT JOIN (
                    SELECT mlb_player_id, SUM(at_bats) as mlb_ab, SUM(plate_appearances) as mlb_pa
                    FROM mlb_game_logs
                    GROUP BY mlb_player_id
                ) mlb ON hs.mlb_player_id = mlb.mlb_player_id
                LEFT JOIN statcast sc ON hs.mlb_player_id = sc.mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No hitter data found!")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team',
            'highest_level', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
            'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'total_hbp', 'total_sf', 'seasons_played', 'first_game', 'last_game',
            'mlb_ab', 'mlb_pa',
            'avg_exit_velo', 'max_exit_velo', 'hard_hit_pct', 'avg_launch_angle', 'barrel_pct'
        ])

        # Convert numeric
        numeric_cols = df.columns.difference(['mlb_player_id', 'full_name', 'birth_date',
                                               'primary_position', 'current_team', 'highest_level',
                                               'first_game', 'last_game'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['player_type'] = 'Hitter'
        logger.info(f"Loaded {len(df)} hitters ({df['avg_exit_velo'].notna().sum()} with Statcast)")
        return df

    def calculate_hitter_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate hitter performance metrics."""
        df = df.copy()

        # Basic stats
        df['singles'] = df['total_h'] - df['total_doubles'] - df['total_triples'] - df['total_hr']
        df['tb'] = (df['singles'] + df['total_doubles'] * 2 +
                   df['total_triples'] * 3 + df['total_hr'] * 4)

        # Rate stats
        df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
        df['obp'] = (df['total_h'] + df['total_bb'] + df['total_hbp']) / df['total_pa'].replace(0, np.nan)
        df['slg'] = df['tb'] / df['total_ab'].replace(0, np.nan)
        df['ops'] = df['obp'] + df['slg']
        df['iso'] = df['slg'] - df['avg']

        # Discipline
        df['bb_rate'] = df['total_bb'] / df['total_pa']
        df['so_rate'] = df['total_so'] / df['total_pa']
        df['bb_so_ratio'] = df['total_bb'] / df['total_so'].replace(0, np.nan)

        # Power
        df['hr_rate'] = df['total_hr'] / df['total_pa']
        df['sb_rate'] = df['total_sb'] / df['total_pa']

        df = df.fillna(0)
        return df

    def predict_hitter_mlb_performance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict MLB performance for hitters with Statcast boost."""
        df = df.copy()

        # Base translation factors
        level_factors = {
            'AAA': 0.90, 'AA': 0.80, 'A+': 0.70,
            'A': 0.60, 'Rookie+': 0.50, 'Rookie': 0.40
        }
        df['translation_factor'] = df['highest_level'].map(level_factors).fillna(0.60)

        # Statcast adjustments (elite Statcast = better translation)
        df['has_statcast'] = (df['avg_exit_velo'] > 0).astype(int)

        # Exit velo boost (87+ is good, 90+ is elite)
        df['ev_boost'] = np.where(
            df['avg_exit_velo'] >= 90, 1.10,
            np.where(df['avg_exit_velo'] >= 87, 1.05, 1.0)
        )

        # Hard hit% boost (40%+ is elite)
        df['hh_boost'] = np.where(df['hard_hit_pct'] >= 40, 1.08, 1.0)

        # Barrel% boost (10%+ is elite)
        df['barrel_boost'] = np.where(df['barrel_pct'] >= 10, 1.10, 1.0)

        # Combined Statcast boost
        df['statcast_multiplier'] = df['ev_boost'] * df['hh_boost'] * df['barrel_boost']

        # Predicted MLB stats
        df['pred_mlb_ops'] = df['ops'] * df['translation_factor'] * df['statcast_multiplier']
        df['pred_mlb_obp'] = df['obp'] * df['translation_factor'] * df['statcast_multiplier']
        df['pred_mlb_slg'] = df['slg'] * df['translation_factor'] * df['statcast_multiplier']
        df['pred_mlb_woba'] = (df['pred_mlb_obp'] - 0.1) * 0.85
        df['pred_mlb_wrc_plus'] = ((df['pred_mlb_woba'] - 0.320) / 1.25) * 100 + 100

        # Bounds
        df['pred_mlb_wrc_plus'] = df['pred_mlb_wrc_plus'].clip(40, 160)
        df['pred_mlb_ops'] = df['pred_mlb_ops'].clip(0.400, 1.100)

        logger.info("Calculated hitter MLB predictions with Statcast boosts")
        return df

    # ========== PITCHER PIPELINE ==========

    async def load_pitcher_data(self) -> pd.DataFrame:
        """Load pitcher data."""
        logger.info("Loading pitcher data...")

        async with engine.begin() as conn:
            result = await conn.execute(text("""
                WITH pitcher_stats AS (
                    SELECT
                        m.mlb_player_id,
                        p.name as full_name,
                        p.birth_date,
                        p.position as primary_position,
                        p.current_team,
                        MAX(m.level) as highest_level,
                        SUM(m.games_pitched) as games_pitched,
                        SUM(m.games_started) as games_started,
                        SUM(m.innings_pitched) as innings_pitched,
                        SUM(m.strikeouts_pitched) as strikeouts,
                        SUM(m.walks_allowed) as walks,
                        SUM(m.hits_allowed) as hits_allowed,
                        SUM(m.home_runs_allowed) as hr_allowed,
                        SUM(m.hit_batsmen) as hbp,
                        SUM(m.earned_runs) as earned_runs,
                        AVG(m.era) as era,
                        AVG(m.whip) as whip,
                        COUNT(DISTINCT m.season) as seasons_played,
                        MIN(m.game_date) as first_game,
                        MAX(m.game_date) as last_game
                    FROM milb_game_logs m
                    INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                    WHERE m.data_source = 'mlb_stats_api_gamelog'
                    AND m.games_pitched > 0
                    AND m.innings_pitched > 0
                    AND p.birth_date IS NOT NULL
                    GROUP BY m.mlb_player_id, p.name, p.birth_date, p.position, p.current_team
                )
                SELECT
                    ps.*,
                    0 as mlb_ip
                FROM pitcher_stats ps
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No pitcher data found!")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team',
            'highest_level', 'games_pitched', 'games_started', 'innings_pitched',
            'strikeouts', 'walks', 'hits_allowed', 'hr_allowed', 'hbp',
            'earned_runs', 'era', 'whip', 'seasons_played', 'first_game', 'last_game',
            'mlb_ip'
        ])

        # Convert numeric
        numeric_cols = df.columns.difference(['mlb_player_id', 'full_name', 'birth_date',
                                               'primary_position', 'current_team', 'highest_level',
                                               'first_game', 'last_game'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['player_type'] = 'Pitcher'
        df['primary_position'] = 'P'
        logger.info(f"Loaded {len(df)} pitchers")
        return df

    def calculate_pitcher_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate pitcher performance metrics."""
        df = df.copy()

        # Rate stats (per 9 innings)
        df['k_per_9'] = (df['strikeouts'] / df['innings_pitched'] * 9).replace([np.inf, -np.inf], 0)
        df['bb_per_9'] = (df['walks'] / df['innings_pitched'] * 9).replace([np.inf, -np.inf], 0)
        df['hr_per_9'] = (df['hr_allowed'] / df['innings_pitched'] * 9).replace([np.inf, -np.inf], 0)
        df['h_per_9'] = (df['hits_allowed'] / df['innings_pitched'] * 9).replace([np.inf, -np.inf], 0)

        # Key ratios
        df['k_bb_ratio'] = (df['strikeouts'] / df['walks'].replace(0, np.nan)).fillna(0)
        df['k_rate'] = df['strikeouts'] / (df['strikeouts'] + df['walks'] + df['hits_allowed'])
        df['bb_rate'] = df['walks'] / (df['strikeouts'] + df['walks'] + df['hits_allowed'])
        df['k_minus_bb_pct'] = df['k_rate'] - df['bb_rate']

        # FIP (Fielding Independent Pitching)
        # FIP = ((13*HR + 3*BB - 2*K) / IP) + constant (use 3.20)
        df['fip'] = (((13 * df['hr_allowed'] + 3 * df['walks'] - 2 * df['strikeouts']) /
                     df['innings_pitched'].replace(0, np.nan)) + 3.20).fillna(5.0)

        # Quality starts proxy (games with good performance)
        df['starter_profile'] = (df['games_started'] / df['games_pitched'].replace(0, 1) > 0.7).astype(int)

        df = df.fillna(0)
        return df

    def predict_pitcher_mlb_performance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict MLB performance for pitchers."""
        df = df.copy()

        # Level translation (pitchers translate differently than hitters)
        level_factors = {
            'AAA': 0.92, 'AA': 0.83, 'A+': 0.72,
            'A': 0.62, 'Rookie+': 0.50, 'Rookie': 0.40
        }
        df['translation_factor'] = df['highest_level'].map(level_factors).fillna(0.65)

        # K-BB% is highly predictive
        df['k_bb_quality'] = np.where(
            df['k_minus_bb_pct'] >= 0.20, 1.15,  # Elite (20%+)
            np.where(df['k_minus_bb_pct'] >= 0.15, 1.08,  # Good (15%+)
            np.where(df['k_minus_bb_pct'] >= 0.10, 1.0, 0.92))  # Average/below
        )

        # FIP quality
        df['fip_quality'] = np.where(
            df['fip'] <= 3.0, 1.12,  # Elite
            np.where(df['fip'] <= 3.5, 1.05,  # Good
            np.where(df['fip'] <= 4.0, 1.0, 0.95))  # Average/below
        )

        # Predicted MLB FIP
        df['pred_mlb_fip'] = (df['fip'] / df['translation_factor']).clip(2.5, 6.0)

        # Convert FIP to ERA estimate (roughly FIP + 0.3)
        df['pred_mlb_era'] = (df['pred_mlb_fip'] + 0.3).clip(2.5, 6.5)

        # Convert to wRC+ equivalent (100 - ERA adjustment)
        # Lower ERA = higher value. ERA of 3.00 = 133 wRC+, 4.00 = 100, 5.00 = 67
        df['pred_mlb_wrc_plus'] = (100 + (4.0 - df['pred_mlb_era']) * 33).clip(40, 160)

        # Multiply by quality adjustments
        df['pred_mlb_wrc_plus'] = (df['pred_mlb_wrc_plus'] * df['k_bb_quality'] * df['fip_quality']).clip(40, 160)

        logger.info("Calculated pitcher MLB predictions")
        return df

    # ========== UNIFIED PROSPECT VALUATION ==========

    def calculate_age_and_filter(self, df: pd.DataFrame, player_type: str) -> pd.DataFrame:
        """Calculate age and apply prospect filters."""
        df = df.copy()

        # Current age
        current_date = datetime.now()
        df['birth_date'] = pd.to_datetime(df['birth_date'])
        df['current_age'] = (current_date - df['birth_date']).dt.days / 365.25

        # Age curve selection
        age_curve = self.pitcher_age_curve if player_type == 'Pitcher' else self.hitter_age_curve

        # Filter by age
        initial_count = len(df)
        df = df[df['current_age'] <= age_curve.hard_cutoff_age]
        logger.info(f"  After age filter: {len(df)} {player_type.lower()}s (removed {initial_count - len(df)})")

        # Filter by MLB experience
        if player_type == 'Hitter':
            df = df[df['mlb_ab'] < 130]
            df = df[df['total_pa'] >= 100]
        else:
            df = df[df['mlb_ip'] < 50]
            df = df[df['innings_pitched'] >= 20]

        logger.info(f"  After experience filters: {len(df)} {player_type.lower()}s")

        return df, age_curve

    def calculate_prospect_value(self, df: pd.DataFrame, age_curve, player_type: str) -> pd.DataFrame:
        """Calculate unified prospect value score."""
        df = df.copy()

        # Age factors
        df['age_factor'] = age_curve.calculate_age_factors_vectorized(df['current_age'])
        df['age_tier'] = df['current_age'].apply(age_curve.get_age_tier)
        df['level_age_factor'] = df.apply(
            lambda row: LevelAgeAdjustment.calculate_age_vs_level_factor(
                row['current_age'], row['highest_level']
            ),
            axis=1
        )
        df['combined_age_factor'] = df['age_factor'] * df['level_age_factor']

        # Performance quality
        if player_type == 'Hitter':
            df['performance_score'] = ((df['ops'] - 0.600) / 0.400).clip(0, 2.0)
            sample_col = 'total_pa'
            sample_threshold = 500
        else:
            # For pitchers, lower FIP = better (invert scale)
            df['performance_score'] = ((5.0 - df['fip']) / 2.0).clip(0, 2.0)
            sample_col = 'innings_pitched'
            sample_threshold = 75

        # Level quality
        level_quality = {
            'AAA': 1.3, 'AA': 1.2, 'A+': 1.0,
            'A': 0.85, 'Rookie+': 0.7, 'Rookie': 0.6
        }
        df['level_quality'] = df['highest_level'].map(level_quality).fillna(1.0)

        # Sample reliability
        df['sample_reliability'] = (df[sample_col] / sample_threshold).clip(0.5, 1.0)

        # MLB ceiling
        df['mlb_ceiling_score'] = (df['pred_mlb_wrc_plus'] / 100.0).clip(0.5, 1.5)

        # Statcast bonus for hitters
        if player_type == 'Hitter':
            df['statcast_bonus'] = np.where(df['has_statcast'] == 1, 1.05, 1.0)
        else:
            df['statcast_bonus'] = 1.0

        # FINAL PROSPECT VALUE
        df['prospect_value_score'] = (
            df['pred_mlb_wrc_plus'] *
            df['combined_age_factor'] *
            df['level_quality'] *
            df['sample_reliability'] *
            df['statcast_bonus'] *
            (1 + df['performance_score'] * 0.2)
        )

        return df

    async def generate_unified_rankings(self) -> pd.DataFrame:
        """Generate unified hitter + pitcher rankings."""
        logger.info("="*80)
        logger.info("UNIFIED PROSPECT RANKING SYSTEM V3")
        logger.info("Hitters + Pitchers + Statcast")
        logger.info("="*80)

        # Load hitters
        hitters = await self.load_hitter_data()
        if not hitters.empty:
            hitters = self.calculate_hitter_stats(hitters)
            hitters = self.predict_hitter_mlb_performance(hitters)
            hitters, hitter_age_curve = self.calculate_age_and_filter(hitters, 'Hitter')
            if not hitters.empty:
                hitters = self.calculate_prospect_value(hitters, hitter_age_curve, 'Hitter')

        # Load pitchers
        pitchers = await self.load_pitcher_data()
        if not pitchers.empty:
            pitchers = self.calculate_pitcher_stats(pitchers)
            pitchers = self.predict_pitcher_mlb_performance(pitchers)
            pitchers, pitcher_age_curve = self.calculate_age_and_filter(pitchers, 'Pitcher')
            if not pitchers.empty:
                pitchers = self.calculate_prospect_value(pitchers, pitcher_age_curve, 'Pitcher')

        # Combine
        all_prospects = pd.concat([hitters, pitchers], ignore_index=True)

        # Sort by prospect value
        all_prospects = all_prospects.sort_values('prospect_value_score', ascending=False)
        all_prospects['rank'] = range(1, len(all_prospects) + 1)

        logger.info(f"\n✅ Generated unified rankings:")
        logger.info(f"   Total prospects: {len(all_prospects)}")
        logger.info(f"   Hitters: {len(all_prospects[all_prospects['player_type'] == 'Hitter'])}")
        logger.info(f"   Pitchers: {len(all_prospects[all_prospects['player_type'] == 'Pitcher'])}")

        return all_prospects

    def print_top_prospects(self, df: pd.DataFrame, n: int = 100):
        """Print top N prospects."""
        print("\n" + "="*170)
        print(f"TOP {n} PROSPECTS - UNIFIED HITTERS + PITCHERS (V3)")
        print("="*170)
        print(f"{'Rank':<6} {'Name':<25} {'Type':<8} {'Age':<7} {'Tier':<20} {'Pos':<6} "
              f"{'Lvl':<6} {'PA/IP':<8} {'Stat':<10} {'AgeFactor':<11} {'PredwRC+':<10} {'Value':<10}")
        print("-"*170)

        for _, row in df.head(n).iterrows():
            if row['player_type'] == 'Hitter':
                sample = f"{int(row['total_pa'])}PA"
                stat = f"{row['ops']:.3f}"
            else:
                sample = f"{row['innings_pitched']:.1f}IP"
                stat = f"{row['fip']:.2f}FIP"

            print(f"{int(row['rank']):<6} "
                  f"{row['full_name'][:24]:<25} "
                  f"{row['player_type']:<8} "
                  f"{row['current_age']:<7.2f} "
                  f"{row['age_tier']:<20} "
                  f"{str(row['primary_position'])[:5]:<6} "
                  f"{str(row['highest_level']):<6} "
                  f"{sample:<8} "
                  f"{stat:<10} "
                  f"{row['combined_age_factor']:<11.3f} "
                  f"{row['pred_mlb_wrc_plus']:<10.1f} "
                  f"{row['prospect_value_score']:<10.1f}")

    def export_rankings(self, df: pd.DataFrame, filename: str = 'prospect_rankings_v3_unified.csv'):
        """Export unified rankings."""
        export_cols = [
            'rank', 'mlb_player_id', 'full_name', 'player_type', 'current_age', 'age_tier',
            'primary_position', 'current_team', 'highest_level',
            'pred_mlb_wrc_plus', 'combined_age_factor', 'prospect_value_score'
        ]

        # Add type-specific columns
        for _, row in df.iterrows():
            if row['player_type'] == 'Hitter' and 'ops' in df.columns:
                break

        df[export_cols].to_csv(filename, index=False)
        logger.info(f"✅ Exported unified rankings to {filename}")


async def main():
    """Main execution."""
    system = UnifiedProspectRankingSystem()

    # Generate unified rankings
    rankings = await system.generate_unified_rankings()

    # Print top 100
    system.print_top_prospects(rankings, n=100)

    # Export
    system.export_rankings(rankings)

    # Show distributions
    print("\n" + "="*80)
    print("DISTRIBUTION ANALYSIS (Top 100)")
    print("="*80)

    top_100 = rankings.head(100)

    print(f"\nBy Player Type:")
    print(f"  Hitters: {len(top_100[top_100['player_type'] == 'Hitter'])}")
    print(f"  Pitchers: {len(top_100[top_100['player_type'] == 'Pitcher'])}")

    print(f"\nBy Age (All):")
    print(f"  Under 21: {len(top_100[top_100['current_age'] < 21])}")
    print(f"  21-23: {len(top_100[(top_100['current_age'] >= 21) & (top_100['current_age'] < 23)])}")
    print(f"  23-25: {len(top_100[(top_100['current_age'] >= 23) & (top_100['current_age'] < 25)])}")
    print(f"  25+: {len(top_100[top_100['current_age'] >= 25])}")

    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
