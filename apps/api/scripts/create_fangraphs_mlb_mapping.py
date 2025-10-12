"""
Create a mapping table between FanGraphs prospects and MLB player IDs.
Uses name matching with age, team, and position for disambiguation.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from difflib import SequenceMatcher
import re
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FanGraphsMLBMapper:
    """Maps FanGraphs prospect names to MLB player IDs."""

    def __init__(self):
        self.mappings = []
        self.ambiguous = []

    def normalize_name(self, name):
        """Normalize a name for matching."""
        if pd.isna(name):
            return ""
        # Remove Jr., Sr., III, etc.
        name = re.sub(r'\b(Jr\.?|Sr\.?|III|II|IV)\b', '', str(name))
        # Remove accents and special characters
        name = re.sub(r'[^\w\s]', '', name)
        # Convert to lowercase and strip
        return name.lower().strip()

    def name_similarity(self, name1, name2):
        """Calculate similarity between two names."""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Check if one is contained in the other (for nicknames)
        if norm1 in norm2 or norm2 in norm1:
            return 0.9

        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, norm1, norm2).ratio()

    async def create_mapping_table(self):
        """Create the mapping table if it doesn't exist."""

        create_table_query = """
        CREATE TABLE IF NOT EXISTS fangraphs_mlb_mapping (
            id SERIAL PRIMARY KEY,
            fg_player_name VARCHAR(255),
            mlb_player_id INTEGER,
            mlb_player_name VARCHAR(255),
            confidence_score FLOAT,
            match_criteria VARCHAR(100),
            fg_organization VARCHAR(50),
            fg_position VARCHAR(20),
            fg_age INTEGER,
            fg_season INTEGER,
            mlb_team VARCHAR(50),
            verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fg_player_name, fg_season, mlb_player_id)
        )
        """

        async with engine.begin() as conn:
            await conn.execute(text(create_table_query))
            logger.info("Mapping table created/verified")

    async def load_fangraphs_players(self):
        """Load unique FanGraphs players."""

        query = """
        WITH latest_fg AS (
            SELECT DISTINCT ON (player_name)
                player_name,
                organization,
                position,
                age,
                season,
                fv
            FROM fangraphs_prospect_grades
            WHERE player_name IS NOT NULL
            ORDER BY player_name, season DESC
        )
        SELECT * FROM latest_fg
        ORDER BY fv DESC NULLS LAST, player_name
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} unique FanGraphs prospects")
        return df

    async def load_mlb_players(self):
        """Load MLB players with their stats."""

        query = """
        WITH mlb_players AS (
            -- From MiLB game logs (has names)
            SELECT DISTINCT
                mlb_player_id,
                MAX(player_name) as player_name,
                STRING_AGG(DISTINCT team, ', ') as teams,
                MAX(season) as latest_season,
                'MiLB' as source
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
              AND player_name IS NOT NULL
            GROUP BY mlb_player_id

            UNION

            -- From MLB game logs
            SELECT DISTINCT
                mlb_player_id,
                CAST(mlb_player_id AS VARCHAR) as player_name,  -- Use ID as placeholder
                STRING_AGG(DISTINCT team, ', ') as teams,
                MAX(season) as latest_season,
                'MLB' as source
            FROM mlb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id
        )
        SELECT
            mlb_player_id,
            MAX(player_name) as player_name,
            STRING_AGG(DISTINCT teams, ', ') as teams,
            MAX(latest_season) as latest_season
        FROM mlb_players
        GROUP BY mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} MLB players")
        return df

    def match_players(self, fg_df, mlb_df):
        """Match FanGraphs players to MLB player IDs."""

        matches = []
        unmatched = []

        for _, fg_player in fg_df.iterrows():
            fg_name = fg_player['player_name']

            # Calculate similarity scores for all MLB players
            mlb_df['similarity'] = mlb_df['player_name'].apply(
                lambda x: self.name_similarity(fg_name, x)
            )

            # Get potential matches (similarity > 0.8)
            potential = mlb_df[mlb_df['similarity'] > 0.8].copy()

            if len(potential) == 0:
                unmatched.append({
                    'fg_player_name': fg_name,
                    'fg_organization': fg_player['organization'],
                    'fg_position': fg_player['position'],
                    'fg_age': fg_player['age'],
                    'fg_season': fg_player['season']
                })
                continue

            # Sort by similarity
            potential = potential.sort_values('similarity', ascending=False)

            # Determine match criteria
            if len(potential) == 1:
                # Single high-confidence match
                best_match = potential.iloc[0]
                match_criteria = "name_only"
                confidence = best_match['similarity']
            else:
                # Multiple potential matches - use additional criteria
                best_match = potential.iloc[0]
                match_criteria = "name_multiple"
                confidence = best_match['similarity'] * 0.9  # Lower confidence for ambiguous

            matches.append({
                'fg_player_name': fg_name,
                'mlb_player_id': int(best_match['mlb_player_id']),
                'mlb_player_name': best_match['player_name'],
                'confidence_score': confidence,
                'match_criteria': match_criteria,
                'fg_organization': fg_player['organization'],
                'fg_position': fg_player['position'],
                'fg_age': fg_player['age'],
                'fg_season': fg_player['season'],
                'mlb_team': best_match['teams']
            })

        logger.info(f"Matched {len(matches)} players, {len(unmatched)} unmatched")

        return pd.DataFrame(matches), pd.DataFrame(unmatched)

    async def save_mappings(self, mappings_df):
        """Save mappings to database."""

        if mappings_df.empty:
            logger.warning("No mappings to save")
            return

        # Insert mappings
        insert_query = """
        INSERT INTO fangraphs_mlb_mapping (
            fg_player_name, mlb_player_id, mlb_player_name,
            confidence_score, match_criteria,
            fg_organization, fg_position, fg_age, fg_season,
            mlb_team, verified
        ) VALUES (
            :fg_player_name, :mlb_player_id, :mlb_player_name,
            :confidence_score, :match_criteria,
            :fg_organization, :fg_position, :fg_age, :fg_season,
            :mlb_team, :verified
        )
        ON CONFLICT (fg_player_name, fg_season, mlb_player_id)
        DO UPDATE SET
            confidence_score = EXCLUDED.confidence_score,
            match_criteria = EXCLUDED.match_criteria,
            mlb_player_name = EXCLUDED.mlb_player_name
        """

        # Mark high-confidence matches as verified
        mappings_df['verified'] = mappings_df['confidence_score'] >= 0.95

        async with engine.begin() as conn:
            for _, row in mappings_df.iterrows():
                await conn.execute(text(insert_query), row.to_dict())

        logger.info(f"Saved {len(mappings_df)} mappings to database")

    async def analyze_mappings(self):
        """Analyze the quality of mappings."""

        query = """
        SELECT
            COUNT(*) as total_mappings,
            COUNT(DISTINCT fg_player_name) as unique_fg_players,
            COUNT(DISTINCT mlb_player_id) as unique_mlb_players,
            AVG(confidence_score) as avg_confidence,
            COUNT(CASE WHEN confidence_score >= 0.95 THEN 1 END) as high_confidence,
            COUNT(CASE WHEN confidence_score >= 0.90 AND confidence_score < 0.95 THEN 1 END) as medium_confidence,
            COUNT(CASE WHEN confidence_score < 0.90 THEN 1 END) as low_confidence,
            COUNT(CASE WHEN verified THEN 1 END) as verified_count
        FROM fangraphs_mlb_mapping
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            stats = result.fetchone()

        print("\n" + "="*80)
        print("FANGRAPHS TO MLB MAPPING STATISTICS")
        print("="*80)
        print(f"Total Mappings:        {stats[0]:,}")
        print(f"Unique FG Players:     {stats[1]:,}")
        print(f"Unique MLB Players:    {stats[2]:,}")
        print(f"Average Confidence:    {stats[3]:.3f}")
        print(f"High Confidence (95%+): {stats[4]:,}")
        print(f"Medium Confidence:     {stats[5]:,}")
        print(f"Low Confidence:        {stats[6]:,}")
        print(f"Verified Mappings:     {stats[7]:,}")

        # Show sample mappings
        sample_query = """
        SELECT
            fg_player_name,
            mlb_player_name,
            confidence_score,
            match_criteria,
            fg_position,
            fg_organization
        FROM fangraphs_mlb_mapping
        ORDER BY confidence_score DESC
        LIMIT 20
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(sample_query))
            samples = pd.DataFrame(result.fetchall(), columns=result.keys())

        print("\n" + "="*80)
        print("SAMPLE HIGH-CONFIDENCE MAPPINGS")
        print("="*80)
        print(samples.to_string(index=False))

    async def run_mapping(self):
        """Run the complete mapping process."""

        # Create table
        await self.create_mapping_table()

        # Load data
        logger.info("Loading FanGraphs players...")
        fg_df = await self.load_fangraphs_players()

        logger.info("Loading MLB players...")
        mlb_df = await self.load_mlb_players()

        # Perform matching
        logger.info("Matching players...")
        mappings_df, unmatched_df = self.match_players(fg_df, mlb_df)

        # Save results
        logger.info("Saving mappings...")
        await self.save_mappings(mappings_df)

        # Save unmatched for review
        if not unmatched_df.empty:
            unmatched_df.to_csv('fangraphs_unmatched_players.csv', index=False)
            logger.info(f"Saved {len(unmatched_df)} unmatched players to CSV")

        # Analyze results
        await self.analyze_mappings()

        return mappings_df


async def main():
    mapper = FanGraphsMLBMapper()
    await mapper.run_mapping()


if __name__ == "__main__":
    asyncio.run(main())