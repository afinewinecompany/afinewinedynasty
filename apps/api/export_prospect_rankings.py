"""Export prospect rankings from existing ML predictions."""

import asyncio
import pandas as pd
from sqlalchemy import text
from app.db.database import engine


async def export_rankings():
    """Export prospect rankings to CSV.

    Filters to only include true prospects:
    - Not at MLB level (level != 'MLB')
    - Has assigned organization OR signed to MiLB
    - Excludes NCAA players (no org) and MLB-level players

    Note: Cannot filter by game logs since pitching stats aren't collected yet.
    """
    async with engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT
                p.id as prospect_id,
                p.name,
                p.age,
                p.position,
                p.organization,
                p.level,
                pred.predicted_fv,
                pred.predicted_tier,
                pred.confidence_score,
                pred.model_version,
                (SELECT COUNT(*) FROM milb_game_logs WHERE prospect_id = p.id) as milb_games
            FROM ml_predictions pred
            JOIN prospects p ON pred.prospect_id = p.id
            WHERE pred.predicted_fv IS NOT NULL
                -- Filter out MLB-level players
                AND (p.level != 'MLB' OR p.level IS NULL)
                -- Keep players with organization OR those with MiLB game logs
                AND (p.organization IS NOT NULL OR EXISTS (SELECT 1 FROM milb_game_logs WHERE prospect_id = p.id))
            ORDER BY pred.predicted_fv DESC
        '''))
        rows = result.fetchall()

    if not rows:
        print("No ML predictions found with FV values")
        return

    # Create DataFrame
    df = pd.DataFrame(rows, columns=[
        'prospect_id', 'name', 'age', 'position', 'organization', 'level',
        'predicted_fv', 'predicted_tier', 'confidence_score', 'model_version', 'milb_games'
    ])

    # Add rank
    df['rank'] = range(1, len(df) + 1)

    # Reorder columns
    df = df[['rank', 'prospect_id', 'name', 'age', 'position', 'organization', 'level',
             'predicted_fv', 'predicted_tier', 'confidence_score', 'milb_games', 'model_version']]

    # Export to CSV
    output_file = 'prospect_rankings.csv'
    df.to_csv(output_file, index=False)

    print(f'\n{"="*150}')
    print(f'PROSPECT RANKINGS EXPORTED')
    print(f'{"="*150}')
    print(f'Total prospects ranked: {len(df):,}')
    print(f'Output file: {output_file}')
    print(f'\nTop 50 Prospects:')
    print(f'{"="*150}')
    print(f'{"Rank":<6} {"Name":<30} {"Age":<6} {"Pos":<8} {"Team":<25} {"Level":<10} {"FV":<6} {"Tier":<15} {"Games":<8}')
    print(f'{"-"*150}')

    for _, row in df.head(50).iterrows():
        name = str(row['name'])[:29] if pd.notna(row['name']) else 'Unknown'
        age = int(row['age']) if pd.notna(row['age']) else 0
        pos = str(row['position'])[:7] if pd.notna(row['position']) else 'N/A'
        team = str(row['organization'])[:24] if pd.notna(row['organization']) else 'Unknown'
        level = str(row['level'])[:9] if pd.notna(row['level']) else 'N/A'
        fv = int(row['predicted_fv']) if pd.notna(row['predicted_fv']) else 0
        tier = str(row['predicted_tier'])[:14] if pd.notna(row['predicted_tier']) else 'N/A'
        games = int(row['milb_games']) if pd.notna(row['milb_games']) else 0

        print(f'{int(row["rank"]):<6} {name:<30} {age:<6} {pos:<8} {team:<25} {level:<10} {fv:<6} {tier:<15} {games:<8}')

    print(f'\n{"="*150}')
    print(f'Full rankings exported to: {output_file}')
    print(f'{"="*150}\n')


if __name__ == "__main__":
    asyncio.run(export_rankings())
