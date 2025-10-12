"""
Generate updated prospect rankings using trained ensemble models.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime
import pickle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RankingsGenerator:
    """Generate prospect rankings from trained models."""

    def __init__(self):
        self.models = None
        self.feature_names = []
        self.load_models()

    def load_models(self):
        """Load trained models from disk."""
        try:
            with open('simplified_ensemble_models.pkl', 'rb') as f:
                model_data = pickle.load(f)
                self.models = model_data['models']
                self.feature_names = model_data['feature_names']
            logger.info(f"Loaded models with {len(self.feature_names)} features")
        except FileNotFoundError:
            logger.warning("No trained models found. Will use database predictions.")
            self.models = None

    async def load_prospect_info(self) -> pd.DataFrame:
        """Load prospect biographical information."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    id as prospect_id,
                    mlb_id,
                    name,
                    age,
                    position,
                    organization,
                    level,
                    eta_year
                FROM prospects
                WHERE id IS NOT NULL
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'mlb_id', 'name', 'age', 'position',
            'organization', 'level', 'eta_year'
        ])

        logger.info(f"Loaded info for {len(df)} prospects")
        return df

    async def load_milb_stats(self) -> pd.DataFrame:
        """Load aggregated MiLB statistics."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    prospect_id,
                    SUM(plate_appearances) as total_pa,
                    SUM(at_bats) as total_ab,
                    SUM(hits) as total_h,
                    SUM(home_runs) as total_hr,
                    AVG(batting_avg) as avg_ba,
                    AVG(on_base_pct) as avg_obp,
                    AVG(slugging_pct) as avg_slg,
                    AVG(ops) as avg_ops,
                    COUNT(DISTINCT season) as seasons_played,
                    COUNT(DISTINCT level) as levels_played
                FROM milb_game_logs
                WHERE plate_appearances > 0
                GROUP BY prospect_id
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'total_pa', 'total_ab', 'total_h', 'total_hr',
            'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops',
            'seasons_played', 'levels_played'
        ])

        for col in df.columns:
            if col != 'prospect_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded MiLB stats for {len(df)} prospects")
        return df

    async def load_existing_predictions(self) -> pd.DataFrame:
        """Load existing ML predictions from database."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    prospect_id,
                    predicted_fv,
                    predicted_tier,
                    confidence_score
                FROM ml_predictions
                WHERE predicted_fv IS NOT NULL
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'predicted_fv', 'predicted_tier', 'confidence_score'
        ])

        logger.info(f"Loaded existing predictions for {len(df)} prospects")
        return df

    async def load_statcast_metrics(self) -> pd.DataFrame:
        """Load Statcast metrics."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    AVG(avg_ev) as avg_ev,
                    MAX(max_ev) as max_ev,
                    AVG(fb_ev) as fb_ev,
                    AVG(barrel_pct) as barrel_pct,
                    AVG(hard_hit_pct) as hard_hit_pct,
                    AVG(ev_90th) as ev_90th
                FROM milb_statcast_metrics
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'avg_ev', 'max_ev', 'fb_ev',
            'barrel_pct', 'hard_hit_pct', 'ev_90th'
        ])

        for col in df.columns:
            if col != 'prospect_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded Statcast for {len(df)} prospects")
        return df

    async def load_mlb_experience(self) -> pd.DataFrame:
        """Check MLB experience to filter prospects."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    SUM(at_bats) as mlb_ab,
                    SUM(plate_appearances) as mlb_pa
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=['prospect_id', 'mlb_ab', 'mlb_pa'])

        df = pd.DataFrame(rows, columns=['prospect_id', 'mlb_ab', 'mlb_pa'])
        df['mlb_ab'] = pd.to_numeric(df['mlb_ab'], errors='coerce').fillna(0)
        df['mlb_pa'] = pd.to_numeric(df['mlb_pa'], errors='coerce').fillna(0)

        logger.info(f"Loaded MLB experience for {len(df)} players")
        return df

    def calculate_composite_score(self, row: pd.Series) -> float:
        """Calculate composite ranking score."""
        # Use predicted FV as primary score
        base_score = row.get('predicted_fv', 40)

        # Boost for strong MiLB performance
        if row.get('avg_ops', 0) > 0.800:
            base_score += 5
        elif row.get('avg_ops', 0) > 0.750:
            base_score += 2

        # Boost for Statcast metrics
        if row.get('avg_ev', 0) > 88:
            base_score += 3
        if row.get('barrel_pct', 0) > 8:
            base_score += 2

        # Boost for young age at high level
        if row.get('level', '') == 'AAA' and row.get('age', 30) < 23:
            base_score += 5
        elif row.get('level', '') == 'AA' and row.get('age', 30) < 22:
            base_score += 3

        # Penalty for older prospects at lower levels
        if row.get('level', '') in ['A', 'A+'] and row.get('age', 20) > 24:
            base_score -= 5

        return base_score

    async def generate_rankings(self) -> pd.DataFrame:
        """Generate comprehensive prospect rankings."""

        # Load all data
        prospect_info = await self.load_prospect_info()
        milb_stats = await self.load_milb_stats()
        existing_preds = await self.load_existing_predictions()
        statcast = await self.load_statcast_metrics()
        mlb_exp = await self.load_mlb_experience()

        # Merge all data
        rankings = prospect_info.copy()
        rankings = rankings.merge(milb_stats, on='prospect_id', how='left')
        rankings = rankings.merge(existing_preds, on='prospect_id', how='left')
        rankings = rankings.merge(statcast, on='prospect_id', how='left')

        # Filter out players with significant MLB experience (>130 ABs)
        rankings = rankings.merge(mlb_exp, on='prospect_id', how='left')
        rankings['mlb_ab'] = rankings['mlb_ab'].fillna(0)
        rankings = rankings[rankings['mlb_ab'] < 130]

        # Fill missing values
        rankings = rankings.fillna(0)

        # Calculate composite score
        rankings['composite_score'] = rankings.apply(self.calculate_composite_score, axis=1)

        # Sort by composite score
        rankings = rankings.sort_values('composite_score', ascending=False)

        # Add rank
        rankings['rank'] = range(1, len(rankings) + 1)

        # Add tier labels
        def assign_tier(score):
            if score >= 60:
                return 'Elite'
            elif score >= 55:
                return 'Plus'
            elif score >= 50:
                return 'Solid'
            elif score >= 45:
                return 'Average'
            else:
                return 'Depth'

        rankings['tier'] = rankings['composite_score'].apply(assign_tier)

        logger.info(f"Generated rankings for {len(rankings)} prospects")
        return rankings

    async def save_to_database(self, rankings: pd.DataFrame):
        """Save rankings to database."""
        async with engine.begin() as conn:
            # Clear existing rankings
            await conn.execute(text("DELETE FROM prospect_rankings"))

            # Insert new rankings
            for _, row in rankings.iterrows():
                await conn.execute(text("""
                    INSERT INTO prospect_rankings
                    (prospect_id, rank, full_name, current_age, primary_position, current_team,
                     highest_level, total_milb_pa, milb_ops, pred_wrc_plus, pred_woba, pred_ops,
                     composite_score, has_statcast, avg_ev, barrel_pct)
                    VALUES
                    (:prospect_id, :rank, :name, :age, :position, :team,
                     :level, :total_pa, :avg_ops, :predicted_fv, :predicted_fv, :avg_ops,
                     :composite_score, :has_statcast, :avg_ev, :barrel_pct)
                    ON CONFLICT (prospect_id) DO UPDATE SET
                        rank = :rank,
                        composite_score = :composite_score,
                        updated_at = NOW()
                """), {
                    'prospect_id': int(row['prospect_id']),
                    'rank': int(row['rank']),
                    'name': str(row['name']) if pd.notna(row['name']) else 'Unknown',
                    'age': float(row['age']) if pd.notna(row['age']) else 0,
                    'position': str(row['position']) if pd.notna(row['position']) else 'N/A',
                    'team': str(row['organization']) if pd.notna(row['organization']) else 'Unknown',
                    'level': str(row['level']) if pd.notna(row['level']) else 'N/A',
                    'total_pa': int(row['total_pa']) if pd.notna(row['total_pa']) else 0,
                    'avg_ops': float(row['avg_ops']) if pd.notna(row['avg_ops']) else 0,
                    'predicted_fv': float(row['predicted_fv']) if pd.notna(row['predicted_fv']) else 0,
                    'composite_score': float(row['composite_score']),
                    'has_statcast': bool(row['avg_ev'] > 0),
                    'avg_ev': float(row['avg_ev']) if pd.notna(row['avg_ev']) else None,
                    'barrel_pct': float(row['barrel_pct']) if pd.notna(row['barrel_pct']) else None
                })

        logger.info(f"Saved {len(rankings)} rankings to database")

    def export_to_csv(self, rankings: pd.DataFrame):
        """Export rankings to CSV."""
        export_cols = [
            'rank', 'prospect_id', 'name', 'age', 'position', 'organization', 'level',
            'total_pa', 'avg_ops', 'predicted_fv', 'composite_score', 'tier',
            'avg_ev', 'max_ev', 'fb_ev', 'barrel_pct', 'hard_hit_pct', 'ev_90th',
            'seasons_played', 'levels_played'
        ]

        export_df = rankings[[col for col in export_cols if col in rankings.columns]]
        export_df.to_csv('updated_prospect_rankings.csv', index=False)
        logger.info("Exported rankings to updated_prospect_rankings.csv")

    def print_top_prospects(self, rankings: pd.DataFrame, top_n: int = 50):
        """Print top N prospects."""
        print("\n" + "="*150)
        print(f"TOP {top_n} PROSPECTS - UPDATED RANKINGS")
        print("="*150)
        print(f"{'Rank':<6} {'Name':<30} {'Age':<6} {'Pos':<8} {'Team':<25} {'Level':<10} {'PAs':<8} {'OPS':<8} {'FV':<6} {'Score':<8} {'Tier':<10}")
        print("-"*150)

        for _, row in rankings.head(top_n).iterrows():
            name = str(row['name'])[:29] if pd.notna(row['name']) else 'Unknown'
            age = int(row['age']) if pd.notna(row['age']) and row['age'] > 0 else 0
            pos = str(row['position'])[:7] if pd.notna(row['position']) else 'N/A'
            team = str(row['organization'])[:24] if pd.notna(row['organization']) else 'Unknown'
            level = str(row['level'])[:9] if pd.notna(row['level']) else 'N/A'
            pa = int(row['total_pa']) if pd.notna(row['total_pa']) else 0
            ops = row['avg_ops'] if pd.notna(row['avg_ops']) else 0
            fv = int(row['predicted_fv']) if pd.notna(row['predicted_fv']) else 0
            score = row['composite_score']
            tier = row['tier']

            print(f"{int(row['rank']):<6} {name:<30} {age:<6} {pos:<8} {team:<25} {level:<10} {pa:<8} {ops:<8.3f} {fv:<6} {score:<8.1f} {tier:<10}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Updated Prospect Rankings Generation")
    logger.info("="*80)

    generator = RankingsGenerator()

    # Generate rankings
    rankings = await generator.generate_rankings()

    # Save to database
    await generator.save_to_database(rankings)

    # Export to CSV
    generator.export_to_csv(rankings)

    # Print top 50
    generator.print_top_prospects(rankings, top_n=50)

    # Summary stats
    print("\n" + "="*150)
    print("SUMMARY STATISTICS")
    print("="*150)
    print(f"Total prospects ranked: {len(rankings)}")
    print(f"With MiLB data: {(rankings['total_pa'] > 0).sum()}")
    print(f"With Statcast data: {(rankings['avg_ev'] > 0).sum()}")
    print(f"\nBy Tier:")
    tier_counts = rankings['tier'].value_counts()
    for tier, count in tier_counts.items():
        print(f"  {tier}: {count}")

    logger.info("\n" + "="*80)
    logger.info("Rankings Generation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
